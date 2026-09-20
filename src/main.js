import { createHandTracker } from './hands.js';
import { AsciiRenderer } from './renderer.js';
import {
  orderQuad,
  isConvex,
  squareToQuad,
  invert3,
  toColumnMajor,
  quadSize,
  smoothQuad,
} from './geometry.js';
import { CHARSETS, DEFAULT_CHARSET_ID, splitChars } from './charsets.js';

const STORAGE_KEY = 'ascii-prism.settings.v1';
const MAX_ROWS = 400;

const DEFAULTS = {
  charsetId: DEFAULT_CHARSET_ID,
  charset: CHARSETS.find((c) => c.id === DEFAULT_CHARSET_ID).chars,
  columns: 80,
  colorMode: 'sampled',
  monoColor: '#7cff6b',
  background: '#000000',
  invert: false,
  smoothing: 0.6,
  showTips: true,
  mirror: true,
};

const $ = (id) => document.getElementById(id);
const els = {
  stage: $('stage'),
  video: $('video'),
  gl: $('gl'),
  overlay: $('overlay'),
  hint: $('hint'),
  banner: $('banner'),
  statusModel: $('status-model'),
  statusHands: $('status-hands'),
  statusGrid: $('status-grid'),
  statusFps: $('status-fps'),
  lock: $('lock'),
  fullscreen: $('fullscreen'),
  togglePanel: $('toggle-panel'),
  panel: $('panel'),
  charsetPreset: $('charset-preset'),
  charsetInput: $('charset-input'),
  charsetCount: $('charset-count'),
  invert: $('invert'),
  columns: $('columns'),
  columnsValue: $('columns-value'),
  rowsValue: $('rows-value'),
  colorMode: $('color-mode'),
  monoColorRow: $('mono-color-row'),
  monoColor: $('mono-color'),
  background: $('background'),
  smoothing: $('smoothing'),
  smoothingValue: $('smoothing-value'),
  showTips: $('show-tips'),
  mirror: $('mirror'),
  preview: $('preview'),
  reset: $('reset'),
};

const settings = { ...DEFAULTS, ...loadSettings() };
let locked = false;
let preview = false;
let renderer = null;
let tracker = null;
let smoothedQuad = null;
let lastRegion = null;
let lastVideoTime = -1;
let frameCount = 0;
let fpsWindowStart = performance.now();

// ---------------------------------------------------------------------------
// Settings persistence and UI wiring
// ---------------------------------------------------------------------------

function loadSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveSettings() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  } catch {
    /* private mode etc. */
  }
}

function applyCharset(chars) {
  const list = splitChars(chars);
  if (list.length === 0) list.push(' ');
  settings.charset = list.join('');
  els.charsetCount.textContent = String(list.length);
  renderer?.setCharset(list);
}

function syncUiFromSettings() {
  els.charsetPreset.value = settings.charsetId;
  els.charsetInput.value = settings.charset;
  els.invert.checked = settings.invert;
  els.columns.value = String(settings.columns);
  els.columnsValue.textContent = String(settings.columns);
  els.colorMode.value = settings.colorMode;
  els.monoColor.value = settings.monoColor;
  els.background.value = settings.background;
  els.monoColorRow.hidden = settings.colorMode !== 'mono';
  els.smoothing.value = String(settings.smoothing);
  els.smoothingValue.textContent = settings.smoothing.toFixed(2);
  els.showTips.checked = settings.showTips;
  els.mirror.checked = settings.mirror;
  applyCharset(settings.charset);
}

function wireUi() {
  for (const preset of CHARSETS) {
    const opt = document.createElement('option');
    opt.value = preset.id;
    opt.textContent = preset.label;
    els.charsetPreset.appendChild(opt);
  }
  const custom = document.createElement('option');
  custom.value = 'custom';
  custom.textContent = 'Custom';
  els.charsetPreset.appendChild(custom);

  els.charsetPreset.addEventListener('change', () => {
    const preset = CHARSETS.find((c) => c.id === els.charsetPreset.value);
    settings.charsetId = els.charsetPreset.value;
    if (preset) {
      els.charsetInput.value = preset.chars;
      applyCharset(preset.chars);
    }
    saveSettings();
  });

  els.charsetInput.addEventListener('input', () => {
    settings.charsetId = 'custom';
    els.charsetPreset.value = 'custom';
    applyCharset(els.charsetInput.value);
    saveSettings();
  });

  els.invert.addEventListener('change', () => {
    settings.invert = els.invert.checked;
    saveSettings();
  });

  els.columns.addEventListener('input', () => {
    settings.columns = Number(els.columns.value);
    els.columnsValue.textContent = String(settings.columns);
    saveSettings();
  });

  els.colorMode.addEventListener('change', () => {
    settings.colorMode = els.colorMode.value;
    els.monoColorRow.hidden = settings.colorMode !== 'mono';
    saveSettings();
  });
  els.monoColor.addEventListener('input', () => {
    settings.monoColor = els.monoColor.value;
    saveSettings();
  });
  els.background.addEventListener('input', () => {
    settings.background = els.background.value;
    saveSettings();
  });

  els.smoothing.addEventListener('input', () => {
    settings.smoothing = Number(els.smoothing.value);
    els.smoothingValue.textContent = settings.smoothing.toFixed(2);
    saveSettings();
  });
  els.showTips.addEventListener('change', () => {
    settings.showTips = els.showTips.checked;
    saveSettings();
  });
  els.mirror.addEventListener('change', () => {
    settings.mirror = els.mirror.checked;
    smoothedQuad = null;
    saveSettings();
  });
  els.preview.addEventListener('change', () => {
    preview = els.preview.checked;
  });

  els.reset.addEventListener('click', () => {
    Object.assign(settings, DEFAULTS);
    syncUiFromSettings();
    saveSettings();
  });

  els.lock.addEventListener('click', toggleLock);
  els.fullscreen.addEventListener('click', () => {
    if (document.fullscreenElement) document.exitFullscreen();
    else els.stage.requestFullscreen?.();
  });
  els.togglePanel.addEventListener('click', togglePanel);

  window.addEventListener('keydown', (e) => {
    const t = e.target;
    const typing =
      t instanceof HTMLSelectElement ||
      t instanceof HTMLTextAreaElement ||
      (t instanceof HTMLInputElement && (t.type === 'text' || t.type === 'color'));
    if (typing || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === 'l' || e.key === 'L') toggleLock();
    if (e.key === 'h' || e.key === 'H') togglePanel();
    if (e.key === 'f' || e.key === 'F') els.fullscreen.click();
  });
}

function toggleLock() {
  if (!locked && !lastRegion) return; // nothing to lock yet
  locked = !locked;
  els.lock.classList.toggle('active', locked);
  els.lock.textContent = locked ? 'Unlock region' : 'Lock region';
}

function togglePanel() {
  els.panel.classList.toggle('collapsed');
}

function showBanner(message) {
  els.banner.textContent = message;
  els.banner.hidden = false;
}

// ---------------------------------------------------------------------------
// Camera and model start-up
// ---------------------------------------------------------------------------

async function startCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error('This browser cannot access the camera (getUserMedia is missing).');
  }
  const stream = await navigator.mediaDevices.getUserMedia({
    video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' },
    audio: false,
  });
  els.video.srcObject = stream;
  await els.video.play();
  if (els.video.readyState < 2) {
    await new Promise((resolve) => els.video.addEventListener('loadeddata', resolve, { once: true }));
  }
}

async function init() {
  wireUi();
  syncUiFromSettings();

  try {
    renderer = new AsciiRenderer(els.gl);
    renderer.setCharset(splitChars(settings.charset));
  } catch (err) {
    showBanner(err.message);
    return;
  }

  els.statusModel.textContent = 'Requesting camera…';
  const cameraReady = startCamera().catch((err) => {
    showBanner(`Camera unavailable: ${err.message}. Allow camera access and reload.`);
    throw err;
  });
  const trackerReady = createHandTracker({
    onProgress: (msg) => (els.statusModel.textContent = msg),
  }).catch((err) => {
    console.error(err);
    showBanner('Could not load the hand-tracking model. Check your internet connection and reload.');
    return null;
  });

  try {
    await cameraReady;
  } catch {
    return;
  }
  requestAnimationFrame(loop);
  tracker = await trackerReady;
  if (tracker) els.statusModel.textContent = 'Tracking';
}

// ---------------------------------------------------------------------------
// Per-frame work
// ---------------------------------------------------------------------------

function previewQuad(width, height) {
  return [
    { x: width * 0.25, y: height * 0.22 },
    { x: width * 0.72, y: height * 0.18 },
    { x: width * 0.78, y: height * 0.8 },
    { x: width * 0.22, y: height * 0.74 },
  ];
}

/** Turn an ordered pixel-space quad into shader-ready homographies and a grid size. */
function buildRegion(quad, width, height) {
  const size = quadSize(quad);
  if (size.width < width * 0.03 || size.height < height * 0.03) return null;
  const cols = settings.columns;
  const rows = Math.max(
    1,
    Math.min(MAX_ROWS, Math.round(cols * (size.height / size.width) * renderer.cellAspect)),
  );
  const normalized = quad.map((p) => ({ x: p.x / width, y: p.y / height }));
  const H = squareToQuad(normalized);
  if (!H) return null;
  const Hinv = invert3(H);
  if (!Hinv) return null;
  return { H: toColumnMajor(H), Hinv: toColumnMajor(Hinv), cols, rows, quad };
}

function loop(now) {
  requestAnimationFrame(loop);
  const video = els.video;
  if (video.readyState < 2 || video.currentTime === lastVideoTime) return;
  lastVideoTime = video.currentTime;

  const width = video.videoWidth;
  const height = video.videoHeight;
  renderer.setSize(width, height);
  renderer.uploadVideo(video);

  let hands = [];
  if (tracker) {
    try {
      hands = tracker.detect(video, now);
    } catch (err) {
      console.error(err);
    }
  }

  // Fingertips in display (mirrored) pixel space.
  const tips = [];
  for (const hand of hands.slice(0, 2)) {
    for (const p of [hand.thumb, hand.index]) {
      tips.push({ x: (settings.mirror ? 1 - p.x : p.x) * width, y: p.y * height });
    }
  }

  let region = null;
  let hintText = '';
  if (preview) {
    region = buildRegion(previewQuad(width, height), width, height);
  } else if (locked) {
    // Rebuild from the frozen corners so the customizer still applies.
    region = lastRegion ? buildRegion(lastRegion.quad, width, height) : null;
  } else if (tips.length === 4) {
    const ordered = orderQuad(tips);
    if (isConvex(ordered)) {
      smoothedQuad = smoothQuad(smoothedQuad, ordered, settings.smoothing);
      region = buildRegion(smoothedQuad, width, height);
      if (!region) hintText = 'Move your hands apart to open a larger window.';
    } else {
      smoothedQuad = null;
      hintText = 'Your fingertips cross over. Spread thumbs and index fingers into four corners.';
    }
  } else {
    smoothedQuad = null;
    if (!tracker) hintText = 'Loading hand tracking…';
    else if (hands.length === 1) hintText = 'One hand found. Show the other hand too.';
    else hintText = 'Show both hands with thumbs and index fingers out. The four fingertips frame the ASCII window.';
  }
  if (region && !locked) lastRegion = region;
  if (locked && region) lastRegion = region;

  renderer.render({
    mirror: settings.mirror,
    region,
    colorMode: settings.colorMode,
    monoColor: settings.monoColor,
    background: settings.background,
    invert: settings.invert,
  });
  drawOverlay(tips, region, width, height);

  els.hint.textContent = hintText;
  els.hint.hidden = !hintText;
  els.statusHands.textContent = String(hands.length);
  els.statusGrid.textContent = region ? `${region.cols} × ${region.rows}` : '–';
  els.rowsValue.textContent = region ? String(region.rows) : '–';

  frameCount++;
  if (now - fpsWindowStart >= 500) {
    els.statusFps.textContent = String(Math.round((frameCount * 1000) / (now - fpsWindowStart)));
    frameCount = 0;
    fpsWindowStart = now;
  }
}

function drawOverlay(tips, region, width, height) {
  const canvas = els.overlay;
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, width, height);
  if (!settings.showTips) return;

  const scale = Math.max(1, width / 640);
  if (region) {
    ctx.beginPath();
    region.quad.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)));
    ctx.closePath();
    ctx.lineWidth = 1.5 * scale;
    ctx.strokeStyle = locked ? 'rgba(255, 196, 0, 0.9)' : 'rgba(255, 255, 255, 0.55)';
    ctx.setLineDash(preview ? [8 * scale, 6 * scale] : []);
    ctx.stroke();
    ctx.setLineDash([]);
  }
  tips.forEach((p, i) => {
    const isThumb = i % 2 === 0;
    ctx.beginPath();
    ctx.arc(p.x, p.y, 6 * scale, 0, Math.PI * 2);
    ctx.fillStyle = isThumb ? 'rgba(255, 96, 160, 0.9)' : 'rgba(96, 200, 255, 0.9)';
    ctx.fill();
    ctx.lineWidth = 2 * scale;
    ctx.strokeStyle = 'rgba(0,0,0,0.6)';
    ctx.stroke();
  });
}

init();
