/*
 * Lenses for the browser: what the fingertip window looks into.
 *
 * Browser ports of ascii_prism/lenses/looks.py, so the website draws every
 * lens on the visitor's machine while Python only tracks the hands. Each
 * lens has paint(renderer, quad, settings, extra), which samples the window
 * through the renderer (render.js) and returns { flat, grid?, smooth? }: a
 * flat canvas to warp into the window, the character grid if it drew
 * characters, and smooth: false to keep its pixels chunky. A lens that
 * looks into the past also has observe(renderer, now), called every frame.
 * The person lens paints with a mask the server sends (see person.py).
 */
(() => {
  'use strict';

  const { clamp01, grade } = window.PrismRender;

  const LUMA = [0.2126, 0.7152, 0.0722]; // RGB weights
  const INFERNO = hexTable('00000401000501010601010802010a02020c02020e03021004031204031405041706041907051b08051d09061f0a07220b07240c08260d08290e092b10092d110a30120a32140b34150b37160b39180c3c190c3e1b0c411c0c431e0c451f0c48210c4a230c4c240c4f260c51280b53290b552b0b572d0b592f0a5b310a5c320a5e340a5f3609613809623909633b09643d09653e0966400a67420a68440a68450a69470b6a490b6a4a0c6b4c0c6b4d0d6c4f0d6c510e6c520e6d540f6d550f6d57106e59106e5a116e5c126e5d126e5f136e61136e62146e64156e65156e67166e69166e6a176e6c186e6d186e6f196e71196e721a6e741a6e751b6e771c6d781c6d7a1d6d7c1d6d7d1e6d7f1e6c801f6c82206c84206b85216b87216b88226a8a226a8c23698d23698f24699025689225689326679526679727669827669a28659b29649d29649f2a63a02a63a22b62a32c61a52c60a62d60a82e5fa92e5eab2f5ead305dae305cb0315bb1325ab3325ab43359b63458b73557b93556ba3655bc3754bd3853bf3952c03a51c13a50c33b4fc43c4ec63d4dc73e4cc83f4bca404acb4149cc4248ce4347cf4446d04545d24644d34743d44842d54a41d74b3fd84c3ed94d3dda4e3cdb503bdd513ade5238df5337e05536e15635e25734e35933e45a31e55c30e65d2fe75e2ee8602de9612bea632aeb6429eb6628ec6726ed6925ee6a24ef6c23ef6e21f06f20f1711ff1731df2741cf3761bf37819f47918f57b17f57d15f67e14f68013f78212f78410f8850ff8870ef8890cf98b0bf98c0af98e09fa9008fa9207fa9407fb9606fb9706fb9906fb9b06fb9d07fc9f07fca108fca309fca50afca60cfca80dfcaa0ffcac11fcae12fcb014fcb216fcb418fbb61afbb81dfbba1ffbbc21fbbe23fac026fac228fac42afac62df9c72ff9c932f9cb35f8cd37f8cf3af7d13df7d340f6d543f6d746f5d949f5db4cf4dd4ff4df53f4e156f3e35af3e55df2e661f2e865f2ea69f1ec6df1ed71f1ef75f1f179f2f27df2f482f3f586f3f68af4f88ef5f992f6fa96f8fb9af9fc9dfafda1fcffa4');
  const GB_PALETTE = [[15, 56, 15], [48, 98, 48], [139, 172, 15], [155, 188, 15]];
  const BAYER4 = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5].map((v) => v / 16);
  const SKETCH_PAPER = [0.96, 0.92, 0.86];
  const SKETCH_GRAPHITE = [0.18, 0.19, 0.2];
  const NIGHT_PHOSPHOR = [0.42, 1.0, 0.28];
  const RAIN_GREEN = [0.45, 1.0, 0.3];
  const RAIN_WHITE = [0.9, 1.0, 0.85];
  const RAIN_CHARS = Array.from({ length: 0xff9e - 0xff71 }, (_, i) => String.fromCharCode(0xff71 + i)).concat(Array.from('0123456789'));
  const RAIN_FONT = '"Hiragino Sans", "Hiragino Kaku Gothic ProN", "Noto Sans CJK JP", "Noto Sans JP", "Yu Gothic", "MS Gothic", Meiryo, sans-serif';
  const SENSOR_W = 160; // thermal camera and Game Boy screen width
  const MAX_DT = 0.25; // seconds; a stall is not one long frame
  const ECHO_WIDTH = 480; // echo history frames are kept this wide
  const ECHO_MARGIN_S = 0.5; // kept beyond the delay so a longer delay has frames ready
  const ECHO_EVERY_MS = 30; // at most one history frame per this, whatever the camera's rate
  const MASK_FEATHER = 0.15;

  function hexTable(hex) {
    const out = new Uint8Array(hex.length / 2);
    for (let i = 0; i < out.length; i++) out[i] = parseInt(hex.substr(i * 2, 2), 16);
    return out;
  }

  // Gaussian noise, drawn once; each frame reads it from a random offset.
  const NOISE_SIZE = 1 << 18;
  const NOISE = new Float32Array(NOISE_SIZE);
  for (let i = 0; i < NOISE_SIZE; i += 2) {
    const r = Math.sqrt(-2 * Math.log(1 - Math.random()));
    const a = 2 * Math.PI * Math.random();
    NOISE[i] = r * Math.cos(a);
    NOISE[i + 1] = r * Math.sin(a);
  }
  const noiseOffset = () => (Math.random() * NOISE_SIZE) | 0;

  /** Luminance in 0..1 of RGBA bytes, one float per pixel. */
  function luminance(rgba, n) {
    const out = new Float32Array(n);
    for (let i = 0, k = 0; i < n; i++, k += 4) {
      out[i] = (LUMA[0] * rgba[k] + LUMA[1] * rgba[k + 1] + LUMA[2] * rgba[k + 2]) / 255;
    }
    return out;
  }

  /** Average 2x2 blocks of a float image (area downscale by two). */
  function halve(a, w, h) {
    const hw = Math.max(1, w >> 1);
    const hh = Math.max(1, h >> 1);
    const out = new Float32Array(hw * hh);
    for (let y = 0; y < hh; y++) {
      const y0 = Math.min(h - 1, y * 2);
      const y1 = Math.min(h - 1, y * 2 + 1);
      for (let x = 0; x < hw; x++) {
        const x0 = Math.min(w - 1, x * 2);
        const x1 = Math.min(w - 1, x * 2 + 1);
        out[y * hw + x] = (a[y0 * w + x0] + a[y0 * w + x1] + a[y1 * w + x0] + a[y1 * w + x1]) / 4;
      }
    }
    return out;
  }

  /** One box blur pass of radius r along rows (step 1) or columns (step w), edges clamped. */
  function boxPass(src, dst, w, h, r, horizontal) {
    const len = horizontal ? w : h;
    const lines = horizontal ? h : w;
    const step = horizontal ? 1 : w;
    const inv = 1 / (2 * r + 1);
    for (let l = 0; l < lines; l++) {
      const base = horizontal ? l * w : l;
      let sum = 0;
      for (let i = -r; i <= r; i++) sum += src[base + Math.min(len - 1, Math.max(0, i)) * step];
      for (let i = 0; i < len; i++) {
        dst[base + i * step] = sum * inv;
        const add = Math.min(len - 1, i + r + 1);
        const sub = Math.max(0, i - r);
        sum += src[base + add * step] - src[base + sub * step];
      }
    }
  }

  /** Approximate Gaussian blur of a float image: three box blurs each way. */
  function blur(a, w, h, sigma) {
    const r = Math.max(1, Math.round((Math.sqrt(4 * sigma * sigma + 1) - 1) / 2));
    const tmp = new Float32Array(a.length);
    const out = Float32Array.from(a);
    for (let pass = 0; pass < 3; pass++) {
      boxPass(out, tmp, w, h, r, true);
      boxPass(tmp, out, w, h, r, false);
    }
    return out;
  }

  /** Window sampled at its own size, capped, as RGBA bytes. */
  function pixels(r, quad, cap) {
    const [w, h] = r.pixelSize(quad, cap);
    return { rgba: r.sampleFlat(r.viewSample(), quad, w, h), w, h };
  }

  /** Window sampled at a fixed width (twice over, then averaged), as luminance or RGBA. */
  function sensor(r, quad, width) {
    const [pw, ph] = r.pixelSize(quad);
    const sw = Math.min(pw, width);
    const sh = Math.max(1, Math.round((ph * sw) / pw));
    return { rgba: r.sampleFlat(r.viewSample(), quad, sw * 2, sh * 2), w: sw, h: sh };
  }

  // ----------------------------------------------------------- ascii

  /** Cells, colour grading, glyphs: shared by every lens that draws characters. */
  function asciiGlyphs(r, grid, cells, s) {
    const { cols, rows } = grid;
    const chars = Array.from(s.charset || ' ');
    const n = chars.length;
    const ink = new Uint8ClampedArray(cols * rows * 4);
    const glyphs = new Array(rows);
    for (let y = 0; y < rows; y++) {
      const row = new Array(cols);
      for (let x = 0; x < cols; x++) {
        const i = y * cols + x;
        const cr = cells[i * 3];
        const cg = cells[i * 3 + 1];
        const cb = cells[i * 3 + 2];
        let lum = LUMA[0] * cr + LUMA[1] * cg + LUMA[2] * cb;
        if (s.invert) lum = 1 - lum;
        row[x] = chars[Math.min(n - 1, Math.max(0, Math.floor(lum * n)))];
        const [ir, ig, ib] = grade(cr, cg, cb, s);
        ink[i * 4] = ir * 255 + 0.5;
        ink[i * 4 + 1] = ig * 255 + 0.5;
        ink[i * 4 + 2] = ib * 255 + 0.5;
        ink[i * 4 + 3] = 255;
      }
      glyphs[y] = row;
    }
    return r.glyphCanvas(grid, glyphs, ink, s.background, chars);
  }

  const ascii = () => ({
    glyphs: true,
    paint(r, quad, s) {
      const grid = r.gridForNorm(quad, s.columns);
      if (!grid) return null;
      const cells = r.sampleCells(r.viewSample(), quad, grid.cols, grid.rows);
      return { flat: asciiGlyphs(r, grid, cells, s), grid };
    },
  });

  // --------------------------------------------------------- thermal

  /** Heat is luminance pushed by red-over-blue, so skin reads hotter than a white shirt. */
  const thermal = () => ({
    paint(r, quad) {
      const { rgba, w, h } = sensor(r, quad, SENSOR_W);
      const n = rgba.length / 4;
      const heat = new Float32Array(n);
      for (let i = 0, k = 0; i < n; i++, k += 4) {
        const R = rgba[k] / 255;
        const G = rgba[k + 1] / 255;
        const B = rgba[k + 2] / 255;
        heat[i] = (LUMA[0] * R + LUMA[1] * G + LUMA[2] * B) * 0.5 + Math.max(0, R - B);
      }
      const small = blur(halve(heat, w * 2, h * 2), w, h, 0.8);
      const out = new Uint8ClampedArray(w * h * 4);
      for (let i = 0; i < w * h; i++) {
        const t = Math.round(clamp01((small[i] - 0.05) / 0.75) * 255) * 3;
        out[i * 4] = INFERNO[t];
        out[i * 4 + 1] = INFERNO[t + 1];
        out[i * 4 + 2] = INFERNO[t + 2];
        out[i * 4 + 3] = 255;
      }
      return { flat: r.pixelCanvas('thermal', out, w, h) };
    },
  });

  // --------------------------------------------------------- gameboy

  /** Four-tone handheld: 160 px wide, 4x4 ordered dither, chunky pixels. */
  const gameboy = () => ({
    paint(r, quad) {
      const { rgba, w, h } = sensor(r, quad, SENSOR_W);
      const lum = halve(luminance(rgba, rgba.length / 4), w * 2, h * 2);
      const out = new Uint8ClampedArray(w * h * 4);
      for (let y = 0; y < h; y++) {
        for (let x = 0; x < w; x++) {
          const i = y * w + x;
          const l = clamp01((lum[i] - 0.04) / 0.85) ** 0.9;
          const level = Math.min(3, Math.max(0, Math.floor(l * 3 + BAYER4[(y & 3) * 4 + (x & 3)])));
          const c = GB_PALETTE[level];
          out[i * 4] = c[0];
          out[i * 4 + 1] = c[1];
          out[i * 4 + 2] = c[2];
          out[i * 4 + 3] = 255;
        }
      }
      return { flat: r.pixelCanvas('gameboy', out, w, h), smooth: false };
    },
  });

  // ---------------------------------------------------------- sketch

  /** Pencil on paper: colour-dodge of grey over its blurred inverse, deepened, with grain. */
  const sketch = () => ({
    paint(r, quad) {
      const { rgba, w, h } = pixels(r, quad);
      const n = w * h;
      const grey = new Float32Array(n);
      const inv = new Float32Array(n);
      for (let i = 0, k = 0; i < n; i++, k += 4) {
        grey[i] = 0.299 * rgba[k] + 0.587 * rgba[k + 1] + 0.114 * rgba[k + 2];
        inv[i] = 255 - grey[i];
      }
      const blurred = blur(inv, w, h, Math.max(1, 0.018 * w));
      const out = new Uint8ClampedArray(n * 4);
      const off = noiseOffset();
      for (let i = 0; i < n; i++) {
        const dodge = Math.min(1, (grey[i] * 256) / Math.max(1, 255 - blurred[i]) / 255);
        const m = clamp01(dodge ** 2.8 + NOISE[(off + i) & (NOISE_SIZE - 1)] * 0.04);
        for (let c = 0; c < 3; c++) out[i * 4 + c] = (SKETCH_GRAPHITE[c] + (SKETCH_PAPER[c] - SKETCH_GRAPHITE[c]) * m) * 255 + 0.5;
        out[i * 4 + 3] = 255;
      }
      return { flat: r.pixelCanvas('sketch', out, w, h) };
    },
  });

  // ----------------------------------------------------------- night

  /** Night-vision goggles: soft-knee gain, phosphor green, grain, vignette, scanlines, bloom. */
  const night = () => ({
    paint(r, quad) {
      const { rgba, w, h } = pixels(r, quad);
      const n = w * h;
      const lum = luminance(rgba, n);
      const off = noiseOffset();
      for (let y = 0; y < h; y++) {
        const dy = (y - h / 2) / (h / 2);
        const scan = y % 3 === 1 ? 0.82 : 1;
        for (let x = 0; x < w; x++) {
          const i = y * w + x;
          const dx = (x - w / 2) / (w / 2);
          const vignette = clamp01(1 - 0.6 * Math.hypot(dx, dy) ** 2.4);
          const l = 1 - Math.exp(-lum[i] * 2.2) + NOISE[(off + i) & (NOISE_SIZE - 1)] * 0.07;
          lum[i] = clamp01(l * vignette * scan);
        }
      }
      const glow = new Float32Array(n);
      for (let i = 0; i < n; i++) glow[i] = lum[i] ** 4;
      const bloom = blur(glow, w, h, Math.max(1, 0.01 * w));
      const out = new Uint8ClampedArray(n * 4);
      for (let i = 0; i < n; i++) {
        for (let c = 0; c < 3; c++) out[i * 4 + c] = (lum[i] * NIGHT_PHOSPHOR[c] + bloom[i] * 0.6) * 255 + 0.5;
        out[i * 4 + 3] = 255;
      }
      return { flat: r.pixelCanvas('night', out, w, h) };
    },
  });

  // --------------------------------------------------------- kaleido

  /** The window's top-left quarter reflected into all four quarters. */
  const kaleido = () => ({
    paint(r, quad) {
      const { rgba, w, h } = pixels(r, quad);
      const out = new Uint8ClampedArray(rgba.length);
      for (let y = 0; y < h; y++) {
        const sy = Math.min(y, h - 1 - y);
        for (let x = 0; x < w; x++) {
          const sx = Math.min(x, w - 1 - x);
          const o = (y * w + x) * 4;
          const k = (sy * w + sx) * 4;
          out[o] = rgba[k];
          out[o + 1] = rgba[k + 1];
          out[o + 2] = rgba[k + 2];
          out[o + 3] = 255;
        }
      }
      return { flat: r.pixelCanvas('kaleido', out, w, h) };
    },
  });

  // ------------------------------------------------------------ echo

  /**
   * The window looks a moment into the past. Every video frame is kept,
   * small, for as long as the delay needs; right after a switch the history
   * is short, so the echo starts close to live and drifts back.
   */
  const echo = () => {
    const history = []; // { t, canvas }, oldest first
    const spare = [];
    return {
      observe(r, now, s) {
        const { width: W, height: H } = r.view;
        if (!W || !H) return;
        if (history.length && now - history[history.length - 1].t < ECHO_EVERY_MS) return;
        const w = Math.min(ECHO_WIDTH, W);
        const h = Math.max(1, Math.round((H * w) / W));
        let canvas = spare.pop();
        if (!canvas) canvas = document.createElement('canvas');
        if (canvas.width !== w || canvas.height !== h) {
          canvas.width = w;
          canvas.height = h;
        }
        canvas.getContext('2d', { willReadFrequently: true }).drawImage(r.view, 0, 0, w, h);
        history.push({ t: now, canvas });
        const keep = (s.delay + ECHO_MARGIN_S) * 1000;
        while (history.length > 1 && now - history[0].t > keep) spare.push(history.shift().canvas);
      },
      paint(r, quad, s, extra) {
        const target = (extra.now || performance.now()) - s.delay * 1000;
        let best = history[0];
        for (const item of history) if (Math.abs(item.t - target) < Math.abs(best.t - target)) best = item;
        const src = best
          ? { px: best.canvas.getContext('2d', { willReadFrequently: true }).getImageData(0, 0, best.canvas.width, best.canvas.height).data, w: best.canvas.width, h: best.canvas.height }
          : r.viewSample();
        const [w, h] = r.pixelSize(quad);
        return { flat: r.pixelCanvas('echo', r.sampleFlat(src, quad, w, h), w, h) };
      },
    };
  };

  // ------------------------------------------------------------ rain

  /**
   * Matrix rain over the character grid. One drop head per column falls at
   * its own speed and leaves a trail that fades; the trail is scaled by the
   * video's brightness so whatever is bright glows through the code, and
   * `lift` is how much shows on black so a dark room is not empty.
   */
  const rain = () => {
    let cols = 0;
    let rows = 0;
    let head = new Float32Array(0);
    let speed = new Float32Array(0);
    let trail = new Float32Array(0);
    let glyph = new Uint16Array(0);
    let last = 0;
    const FADE = 0.8;
    const uniform = (lo, hi) => lo + Math.random() * (hi - lo);
    const randomGlyph = () => (Math.random() * RAIN_CHARS.length) | 0;

    /** Keep falling when the grid changes shape: overlapping columns and rows are kept. */
    function resize(c, r) {
      if (c === cols && r === rows) return;
      const nHead = new Float32Array(c);
      const nSpeed = new Float32Array(c);
      const nTrail = new Float32Array(c * r);
      const nGlyph = new Uint16Array(c * r);
      for (let x = 0; x < c; x++) {
        nHead[x] = x < cols ? head[x] : uniform(-r * 0.7, r);
        nSpeed[x] = x < cols ? speed[x] : uniform(r * 0.4, r * 1.0);
      }
      for (let y = 0; y < r; y++) {
        for (let x = 0; x < c; x++) {
          const keep = x < cols && y < rows;
          nTrail[y * c + x] = keep ? trail[y * cols + x] : 0;
          nGlyph[y * c + x] = keep ? glyph[y * cols + x] : randomGlyph();
        }
      }
      [cols, rows, head, speed, trail, glyph] = [c, r, nHead, nSpeed, nTrail, nGlyph];
    }

    function step(dt) {
      const decay = Math.exp(-dt / FADE);
      for (let i = 0; i < trail.length; i++) trail[i] *= decay;
      for (let x = 0; x < cols; x++) {
        const prev = head[x];
        head[x] += speed[x] * dt;
        const lo = Math.max(0, Math.ceil(prev));
        const hi = Math.min(rows - 1, Math.floor(head[x]));
        for (let y = lo; y <= hi; y++) trail[y * cols + x] = 1;
        if (head[x] >= rows + 2) {
          head[x] = uniform(-rows * 0.7, -1);
          speed[x] = uniform(rows * 0.4, rows * 1.0);
        }
      }
      const p = Math.min(1, dt * 1.5);
      for (let i = 0; i < glyph.length; i++) if (Math.random() < p) glyph[i] = randomGlyph();
    }

    return {
      glyphs: true,
      paint(r, quad, s, extra) {
        const grid = r.gridForNorm(quad, s.columns);
        if (!grid) return null;
        const now = extra.now || performance.now();
        const dt = last ? Math.min(MAX_DT, Math.max(0, (now - last) / 1000)) : 0;
        last = now;
        resize(grid.cols, grid.rows);
        step(dt);
        const cells = r.sampleCells(r.viewSample(), quad, cols, rows);
        const floor = 0.05;
        const lift = 0.07;
        const headLift = Math.min(1, lift * 2);
        const ink = new Uint8ClampedArray(cols * rows * 4);
        const glyphs = new Array(rows);
        for (let y = 0; y < rows; y++) glyphs[y] = new Array(cols).fill('');
        for (let y = 0; y < rows; y++) {
          for (let x = 0; x < cols; x++) {
            const i = y * cols + x;
            const lum = LUMA[0] * cells[i * 3] + LUMA[1] * cells[i * 3 + 1] + LUMA[2] * cells[i * 3 + 2];
            const reveal = clamp01((lum - floor) / (0.55 - floor)) ** 0.7;
            const isHead = Math.floor(head[x]) === y;
            const light = isHead ? headLift + (1 - headLift) * reveal : clamp01(trail[i] * (lift + (1 - lift) * reveal));
            if (light < 0.02) continue; // black on black: skip the draw
            const colour = isHead ? RAIN_WHITE : RAIN_GREEN;
            ink[i * 4] = colour[0] * light * 255 + 0.5;
            ink[i * 4 + 1] = colour[1] * light * 255 + 0.5;
            ink[i * 4 + 2] = colour[2] * light * 255 + 0.5;
            ink[i * 4 + 3] = 255;
            glyphs[y][x] = RAIN_CHARS[glyph[i]];
          }
        }
        const font = `${Math.max(4, Math.round(grid.glyphH * 0.78))}px ${RAIN_FONT}`;
        return { flat: r.glyphCanvas(grid, glyphs, ink, '#000', RAIN_CHARS, font), grid };
      },
      reset() {
        cols = rows = 0;
        last = 0;
      },
    };
  };

  // ---------------------------------------------------------- person

  /** The server's mask, looked up at a point in normalized frame coordinates. */
  function maskAt(mask, x, y) {
    const [x0, y0, x1, y1] = mask.box;
    const mx = ((x - x0) / (x1 - x0)) * mask.w - 0.5;
    const my = ((y - y0) / (y1 - y0)) * mask.h - 0.5;
    if (mx < -0.5 || my < -0.5 || mx > mask.w - 0.5 || my > mask.h - 0.5) return 0;
    const ix = Math.max(0, Math.min(mask.w - 2, Math.floor(mx)));
    const iy = Math.max(0, Math.min(mask.h - 2, Math.floor(my)));
    const fx = clamp01(mx - ix);
    const fy = clamp01(my - iy);
    const d = mask.data;
    const W = mask.w;
    if (W < 2 || mask.h < 2) return d[0] / 255;
    const top = d[iy * W + ix] * (1 - fx) + d[iy * W + ix + 1] * fx;
    const bottom = d[(iy + 1) * W + ix] * (1 - fx) + d[(iy + 1) * W + ix + 1] * fx;
    return (top * (1 - fy) + bottom * fy) / 255;
  }

  /**
   * Only the person becomes characters; the room stays video (or its
   * negative). The mask comes from Python's selfie segmenter with each
   * tracking answer, so it trails the video by one round trip, like the
   * window itself. Until one arrives the lens shows plain characters.
   */
  const person = () => ({
    glyphs: true,
    paint(r, quad, s, extra) {
      const grid = r.gridForNorm(quad, s.columns);
      if (!grid) return null;
      const src = r.viewSample();
      const cells = r.sampleCells(src, quad, grid.cols, grid.rows);
      const glyphs = asciiGlyphs(r, grid, cells, s);
      const mask = extra.mask;
      if (!mask) return { flat: glyphs, grid };

      const FW = glyphs.width;
      const FH = glyphs.height;
      const [vw, vh] = r.pixelSize(quad);
      const video = r.sampleFlat(src, quad, vw, vh);
      if (s.person_invert) {
        for (let k = 0; k < video.length; k += 4) {
          video[k] = 255 - video[k];
          video[k + 1] = 255 - video[k + 1];
          video[k + 2] = 255 - video[k + 2];
        }
      }
      const mw = Math.min(160, vw);
      const mh = Math.max(1, Math.round((vh * mw) / vw));
      const alpha = new Uint8ClampedArray(mw * mh * 4);
      const [tl, tr, br, bl] = quad;
      for (let y = 0; y < mh; y++) {
        const v = (y + 0.5) / mh;
        const lx = tl[0] + (bl[0] - tl[0]) * v;
        const ly = tl[1] + (bl[1] - tl[1]) * v;
        const rx = tr[0] + (br[0] - tr[0]) * v;
        const ry = tr[1] + (br[1] - tr[1]) * v;
        for (let x = 0; x < mw; x++) {
          const u = (x + 0.5) / mw;
          const m = maskAt(mask, lx + (rx - lx) * u, ly + (ry - ly) * u);
          const k = (y * mw + x) * 4;
          alpha[k] = alpha[k + 1] = alpha[k + 2] = 255;
          alpha[k + 3] = clamp01((m - 0.5 + MASK_FEATHER) / (2 * MASK_FEATHER)) * 255 + 0.5;
        }
      }

      // The glyphs cut out by the mask, over the video.
      const cut = r.canvas('person-cut', FW, FH);
      const cctx = cut.getContext('2d');
      cctx.globalCompositeOperation = 'copy';
      cctx.drawImage(glyphs, 0, 0);
      cctx.globalCompositeOperation = 'destination-in';
      cctx.drawImage(r.pixelCanvas('person-mask', alpha, mw, mh), 0, 0, FW, FH);
      cctx.globalCompositeOperation = 'source-over';
      const out = r.canvas('person-out', FW, FH);
      const octx = out.getContext('2d');
      octx.drawImage(r.pixelCanvas('person-video', video, vw, vh), 0, 0, FW, FH);
      octx.drawImage(cut, 0, 0);
      return { flat: out, grid };
    },
  });

  const FACTORIES = { ascii, thermal, echo, rain, gameboy, sketch, night, kaleido, person };

  /** One lens object per id, created on first use; unknown ids get ASCII. */
  class LensBox {
    constructor() {
      this.id = null;
      this.lens = null;
    }

    get(id) {
      if (id !== this.id) {
        this.id = id;
        this.lens = (FACTORIES[id] || ascii)();
      }
      return this.lens;
    }

    reset() {
      this.id = null;
      this.lens = null;
    }
  }

  window.PrismLenses = { LensBox, ids: Object.keys(FACTORIES) };
})();
