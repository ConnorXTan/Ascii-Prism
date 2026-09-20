/**
 * Browser end-to-end test. Drives the app in headless Google Chrome with a
 * fake camera, checks the model loads, the ASCII region renders and the
 * customizer applies, then feeds Chrome a photo of two hands as the camera
 * and checks that fingertips are tracked and a region appears.
 *
 * Requires Google Chrome installed and `npm install` (playwright-core).
 * Run with:  npm run test:browser
 */
import { chromium } from 'playwright-core';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const CACHE = path.join(ROOT, 'tests', 'browser', '.cache');
const PORT = 5199;
const ORIGIN = `http://127.0.0.1:${PORT}`;
const HANDS_PHOTO = 'https://storage.googleapis.com/mediapipe-tasks/hand_landmarker/woman_hands.jpg';
const W = 1280;
const H = 720;

const CHROME_ARGS = [
  '--use-fake-ui-for-media-stream',
  '--use-fake-device-for-media-stream',
  '--use-angle=swiftshader',
  '--enable-unsafe-swiftshader',
  '--ignore-gpu-blocklist',
];

let failures = 0;
function check(name, ok, detail = '') {
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? `  (${detail})` : ''}`);
  if (!ok) failures++;
}

function startServer() {
  const proc = spawn('python3', ['-m', 'http.server', String(PORT), '--bind', '127.0.0.1'], {
    cwd: ROOT,
    stdio: 'ignore',
  });
  return new Promise((resolve) => setTimeout(() => resolve(proc), 800));
}

async function openApp(browser) {
  const context = await browser.newContext({ viewport: { width: 1400, height: 900 } });
  await context.grantPermissions(['camera'], { origin: ORIGIN });
  const page = await context.newPage();
  const errors = [];
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto(`${ORIGIN}/index.html`);
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.waitForFunction(
    () =>
      document.getElementById('status-model').textContent === 'Tracking' ||
      !document.getElementById('banner').hidden,
    null,
    { timeout: 120000 },
  );
  await page.waitForTimeout(2500);
  return { page, errors };
}

const readStatus = (page) =>
  page.evaluate(() => ({
    model: document.getElementById('status-model').textContent,
    hands: Number(document.getElementById('status-hands').textContent),
    grid: document.getElementById('status-grid').textContent,
    banner: document.getElementById('banner').hidden ? null : document.getElementById('banner').textContent,
  }));

/** Decode the sample photo in Chrome and write it out as a Y4M fake-camera file. */
async function buildHandsVideo(browser) {
  fs.mkdirSync(CACHE, { recursive: true });
  const jpg = path.join(CACHE, 'hands.jpg');
  const y4m = path.join(CACHE, 'hands.y4m');
  if (fs.existsSync(y4m)) return y4m;
  if (!fs.existsSync(jpg)) {
    const res = await fetch(HANDS_PHOTO);
    if (!res.ok) throw new Error(`Could not download sample photo: ${res.status}`);
    fs.writeFileSync(jpg, Buffer.from(await res.arrayBuffer()));
  }
  const page = await browser.newPage();
  await page.goto(`${ORIGIN}/tests/browser/.cache/hands.jpg`);
  const rgba = await page.evaluate(
    ([W, H]) => {
      const img = document.querySelector('img');
      const c = document.createElement('canvas');
      c.width = W;
      c.height = H;
      const ctx = c.getContext('2d');
      ctx.fillStyle = '#334';
      ctx.fillRect(0, 0, W, H);
      const s = H / img.naturalHeight;
      const dw = img.naturalWidth * s;
      ctx.translate(W, 0);
      ctx.scale(-1, 1); // pre-mirror so the app's selfie mirroring shows the original
      ctx.drawImage(img, (W - dw) / 2, 0, dw, H);
      return Array.from(ctx.getImageData(0, 0, W, H).data);
    },
    [W, H],
  );
  await page.close();
  const Y = Buffer.alloc(W * H);
  const U = Buffer.alloc((W / 2) * (H / 2));
  const V = Buffer.alloc((W / 2) * (H / 2));
  const clamp = (v) => Math.max(0, Math.min(255, Math.round(v)));
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const i = (y * W + x) * 4;
      const [r, g, b] = [rgba[i], rgba[i + 1], rgba[i + 2]];
      Y[y * W + x] = clamp(0.257 * r + 0.504 * g + 0.098 * b + 16);
      if (y % 2 === 0 && x % 2 === 0) {
        const j = (y / 2) * (W / 2) + x / 2;
        U[j] = clamp(-0.148 * r - 0.291 * g + 0.439 * b + 128);
        V[j] = clamp(0.439 * r - 0.368 * g - 0.071 * b + 128);
      }
    }
  }
  const parts = [Buffer.from(`YUV4MPEG2 W${W} H${H} F30:1 Ip A1:1 C420jpeg\n`)];
  for (let f = 0; f < 30; f++) parts.push(Buffer.from('FRAME\n'), Y, U, V);
  fs.writeFileSync(y4m, Buffer.concat(parts));
  return y4m;
}

const server = await startServer();
try {
  // Part 1: synthetic camera pattern, no hands, customizer.
  let browser = await chromium.launch({ channel: 'chrome', headless: true, args: CHROME_ARGS });
  {
    const { page, errors } = await openApp(browser);
    const s = await readStatus(page);
    check('model loads and reports Tracking', s.model === 'Tracking', s.model);
    check('no banner error', s.banner === null, s.banner ?? '');
    check('no region without hands', s.grid === '–', s.grid);
    check('hint asks for both hands', /both hands/i.test(await page.textContent('#hint')));

    await page.selectOption('#charset-preset', 'blocks');
    const count = await page.textContent('#charset-count');
    check('charset preset applies', count === '5', count);
    await page.keyboard.press('l');
    check('lock does nothing without a region', (await page.textContent('#lock')) === 'Lock region');
    check('no console errors (pattern camera)', errors.length === 0, errors.join(' | '));
    await page.screenshot({ path: path.join(CACHE, 'no-hands.png') });
  }

  // Part 2: real hand tracking on a photo of two hands.
  const y4m = await buildHandsVideo(browser);
  await browser.close();
  browser = await chromium.launch({
    channel: 'chrome',
    headless: true,
    args: [...CHROME_ARGS, `--use-file-for-fake-video-capture=${y4m}`],
  });
  {
    const { page, errors } = await openApp(browser);
    let s = await readStatus(page);
    check('both hands detected on the sample photo', s.hands === 2, `hands=${s.hands}`);
    check('fingertips produce an ASCII region', /^80 × \d+$/.test(s.grid), s.grid);

    await page.fill('#columns', '40');
    await page.dispatchEvent('#columns', 'input');
    await page.check('#invert');
    await page.waitForTimeout(400);
    s = await readStatus(page);
    check('column count applies', /^40 × \d+$/.test(s.grid), s.grid);
    await page.keyboard.press('l');
    check('lock hotkey works after clicking a checkbox', (await page.textContent('#lock')) === 'Unlock region');
    check('no console errors (hands camera)', errors.length === 0, errors.join(' | '));
    await page.screenshot({ path: path.join(CACHE, 'hands.png') });
  }
  await browser.close();
} finally {
  server.kill();
}

console.log(failures === 0 ? '\nAll browser checks passed.' : `\n${failures} check(s) failed.`);
console.log(`Screenshots: ${CACHE}`);
process.exit(failures === 0 ? 0 : 1);
