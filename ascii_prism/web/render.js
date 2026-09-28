/*
 * ASCII window renderer for the browser.
 *
 * Python finds the hands and says where the window is: four corners in
 * normalized coordinates. Everything about the pixels happens here, on the
 * visitor's own machine, from the full-size camera feed that never leaves
 * it. Per frame: sample the average video colour under every character cell,
 * grade it, pick a glyph by brightness, compose the flat character grid,
 * then warp that grid into the window with a bilinear map. As in the Python
 * renderer, a bilinear map (rather than a perspective one) lets a twisted
 * window fold over itself like a ribbon.
 */
(() => {
  'use strict';

  const FONT_FAMILY = 'Menlo, "DejaVu Sans Mono", Consolas, "Liberation Mono", monospace';
  const PROBE_SIZE = 100;
  const MIN_GLYPH_H = 6;
  const MAX_GLYPH_H = 48;
  const MAX_ROWS = 400;
  const SAMPLE_WIDTH = 640; // the view is shrunk to this width before cell colours are sampled
  const SUPERSAMPLE = 2; // samples per cell edge when averaging
  const MAX_PATCHES = 24; // per axis, for the warp
  const PATCH_ERROR_PX = 0.75; // allowed corner mismatch of a patch's affine approximation
  const PATCH_BLEED = 0.5; // source pixels of overdraw so patch seams never show the video through

  function quadSize(q) {
    const d = (p, r) => Math.hypot(p[0] - r[0], p[1] - r[1]);
    const [tl, tr, br, bl] = q;
    return [(d(tl, tr) + d(bl, br)) / 2, (d(tl, bl) + d(tr, br)) / 2];
  }

  /** Map unit-square coordinates (u right, v down) onto the quad. */
  function bilinear(q, u, v) {
    const [tl, tr, br, bl] = q;
    const w00 = (1 - u) * (1 - v);
    const w10 = u * (1 - v);
    const w11 = u * v;
    const w01 = (1 - u) * v;
    return [
      w00 * tl[0] + w10 * tr[0] + w11 * br[0] + w01 * bl[0],
      w00 * tl[1] + w10 * tr[1] + w11 * br[1] + w01 * bl[1],
    ];
  }

  const clamp01 = (v) => (v < 0 ? 0 : v > 1 ? 1 : v);

  /** Rotate a colour's hue by `degrees` in HSV, the way the Python grading does. */
  function rotateHue(r, g, b, degrees) {
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    const delta = max - min;
    if (delta <= 0) return [r, g, b];
    let h;
    if (max === r) h = 60 * ((g - b) / delta);
    else if (max === g) h = 120 + 60 * ((b - r) / delta);
    else h = 240 + 60 * ((r - g) / delta);
    h = (((h + degrees) % 360) + 360) % 360;
    const s = delta / max;
    const v = max;
    const c = v * s;
    const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
    const m = v - c;
    let rgb;
    if (h < 60) rgb = [c, x, 0];
    else if (h < 120) rgb = [x, c, 0];
    else if (h < 180) rgb = [0, c, x];
    else if (h < 240) rgb = [0, x, c];
    else if (h < 300) rgb = [x, 0, c];
    else rgb = [c, 0, x];
    return [rgb[0] + m, rgb[1] + m, rgb[2] + m];
  }

  /** Brightness gain, hue rotation, then saturation about the cell's own luminance. */
  function grade(r, g, b, s) {
    if (s.brightness !== 1) {
      r = clamp01(r * s.brightness);
      g = clamp01(g * s.brightness);
      b = clamp01(b * s.brightness);
    }
    const shift = ((s.hue % 360) + 360) % 360;
    if (shift) [r, g, b] = rotateHue(r, g, b, shift);
    if (s.saturation !== 1) {
      const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
      r = clamp01(lum + (r - lum) * s.saturation);
      g = clamp01(lum + (g - lum) * s.saturation);
      b = clamp01(lum + (b - lum) * s.saturation);
    }
    return [r, g, b];
  }

  class PrismRenderer {
    constructor(view) {
      this.view = view;
      this.ctx = view.getContext('2d');
      this.sample = document.createElement('canvas');
      this.sctx = this.sample.getContext('2d', { willReadFrequently: true });
      this.colour = document.createElement('canvas');
      this.cctx = this.colour.getContext('2d');
      this.flat = document.createElement('canvas');
      this.fctx = this.flat.getContext('2d');
      this.warp = document.createElement('canvas');
      this.wctx = this.warp.getContext('2d');
      this.metrics = new Map();
      this.advances = new Map();
      this.cellAspect = this.measureCellAspect();
    }

    /** Width / height of a character cell for the page's monospace font. */
    measureCellAspect() {
      const ctx = this.fctx;
      ctx.font = `${PROBE_SIZE}px ${FONT_FAMILY}`;
      const m = ctx.measureText('█');
      const h = Math.max(1, m.actualBoundingBoxAscent + m.actualBoundingBoxDescent);
      return Math.max(0.2, Math.min(1, m.width / h));
    }

    /**
     * Font, cell width and baseline for one glyph height. The size is chosen
     * so a block character overflows the cell by about a pixel top and
     * bottom (rows overlap, so block ramps have no seams) and then nudged so
     * the advance is a whole number of pixels, keeping long rows aligned.
     */
    metricsFor(glyphH) {
      let met = this.metrics.get(glyphH);
      if (met) return met;
      const ctx = this.fctx;
      ctx.font = `${PROBE_SIZE}px ${FONT_FAMILY}`;
      let m = ctx.measureText('█');
      const blockH = Math.max(1, m.actualBoundingBoxAscent + m.actualBoundingBoxDescent);
      let size = (PROBE_SIZE * (glyphH + 2)) / blockH;
      ctx.font = `${size.toFixed(3)}px ${FONT_FAMILY}`;
      m = ctx.measureText('█');
      const glyphW = Math.max(3, Math.round(m.width));
      size *= glyphW / Math.max(0.01, m.width);
      const font = `${size.toFixed(3)}px ${FONT_FAMILY}`;
      ctx.font = font;
      m = ctx.measureText('█');
      const asc = m.actualBoundingBoxAscent;
      const desc = m.actualBoundingBoxDescent;
      met = { font, glyphW, glyphH, baseline: (glyphH - (asc + desc)) / 2 + asc };
      if (this.metrics.size > 64) this.metrics.clear();
      this.metrics.set(glyphH, met);
      return met;
    }

    /** True when every character in the ramp advances by exactly one cell in this font. */
    uniformAdvance(met, chars) {
      const key = `${met.font}|${chars.join('')}`;
      let uniform = this.advances.get(key);
      if (uniform !== undefined) return uniform;
      const ctx = this.fctx;
      ctx.font = met.font;
      uniform = chars.every((ch) => Math.abs(ctx.measureText(ch).width - met.glyphW) < 0.5);
      if (this.advances.size > 64) this.advances.clear();
      this.advances.set(key, uniform);
      return uniform;
    }

    /** Character grid for a quad in view pixels, or null if it is degenerate. */
    gridFor(quadPx, columns) {
      const [w, h] = quadSize(quadPx);
      if (w < 1 || h < 1) return null;
      const rows = Math.max(1, Math.min(MAX_ROWS, Math.round(columns * (h / w) * this.cellAspect)));
      const glyphH = Math.round(Math.min(MAX_GLYPH_H, Math.max(MIN_GLYPH_H, h / rows)));
      return { cols: columns, rows, glyphH };
    }

    gridForNorm(quadNorm, columns) {
      const { width: W, height: H } = this.view;
      if (!W || !H) return null;
      return this.gridFor(quadNorm.map(([x, y]) => [x * W, y * H]), columns);
    }

    /** Fill the view with a camera frame (a video element or a canvas), mirrored if asked. */
    drawVideo(source, mirror) {
      const { view, ctx } = this;
      const w = source.videoWidth || source.width;
      const h = source.videoHeight || source.height;
      if (view.width !== w || view.height !== h) {
        view.width = w;
        view.height = h;
      }
      ctx.globalAlpha = 1;
      ctx.setTransform(mirror ? -1 : 1, 0, 0, 1, mirror ? w : 0, 0);
      ctx.drawImage(source, 0, 0, w, h);
      ctx.setTransform(1, 0, 0, 1, 0, 0);
    }

    /**
     * Draw the ASCII window over whatever is in the view. `quadNorm` is the
     * window in normalized view coordinates; `s` is the settings object.
     * Returns the grid that was drawn, or null.
     */
    drawWindow(quadNorm, s) {
      const { view, ctx } = this;
      const W = view.width;
      const H = view.height;
      const quad = quadNorm.map(([x, y]) => [x * W, y * H]);
      const grid = this.gridFor(quad, s.columns);
      if (!grid) return null;
      const { cols, rows, glyphH } = grid;
      const met = this.metricsFor(glyphH);
      const chars = Array.from(s.charset || ' ');
      const n = chars.length;

      // 1. Average colour under every cell, from a shrunk copy of the view.
      const sw = SAMPLE_WIDTH;
      const sh = Math.max(1, Math.round((SAMPLE_WIDTH * H) / W));
      if (this.sample.width !== sw || this.sample.height !== sh) {
        this.sample.width = sw;
        this.sample.height = sh;
      }
      this.sctx.drawImage(view, 0, 0, sw, sh);
      const px = this.sctx.getImageData(0, 0, sw, sh).data;
      const [tl, tr, br, bl] = quadNorm.map(([x, y]) => [x * sw, y * sh]);
      const ink = new Uint8ClampedArray(cols * rows * 4);
      const glyphs = new Array(rows);
      const ss = SUPERSAMPLE;
      const norm = 1 / (ss * ss * 255);
      for (let r = 0; r < rows; r++) {
        const row = new Array(cols);
        for (let c = 0; c < cols; c++) {
          let rs = 0;
          let gs = 0;
          let bs = 0;
          for (let i = 0; i < ss; i++) {
            const v = (r + (i + 0.5) / ss) / rows;
            for (let j = 0; j < ss; j++) {
              const u = (c + (j + 0.5) / ss) / cols;
              const w00 = (1 - u) * (1 - v);
              const w10 = u * (1 - v);
              const w11 = u * v;
              const w01 = (1 - u) * v;
              let x = w00 * tl[0] + w10 * tr[0] + w11 * br[0] + w01 * bl[0];
              let y = w00 * tl[1] + w10 * tr[1] + w11 * br[1] + w01 * bl[1];
              x = x < 0 ? 0 : x > sw - 1 ? sw - 1 : Math.floor(x);
              y = y < 0 ? 0 : y > sh - 1 ? sh - 1 : Math.floor(y);
              const k = (y * sw + x) * 4;
              rs += px[k];
              gs += px[k + 1];
              bs += px[k + 2];
            }
          }
          const cr = rs * norm;
          const cg = gs * norm;
          const cb = bs * norm;
          let lum = 0.2126 * cr + 0.7152 * cg + 0.0722 * cb;
          if (s.invert) lum = 1 - lum;
          let idx = Math.floor(lum * n);
          if (idx >= n) idx = n - 1;
          if (idx < 0) idx = 0;
          row[c] = chars[idx];
          const [ir, ig, ib] = grade(cr, cg, cb, s);
          const k = (r * cols + c) * 4;
          ink[k] = ir * 255 + 0.5;
          ink[k + 1] = ig * 255 + 0.5;
          ink[k + 2] = ib * 255 + 0.5;
          ink[k + 3] = 255;
        }
        glyphs[r] = row;
      }

      // 2. The flat character grid: white glyphs, tinted per cell, over the backdrop.
      const gw = met.glyphW;
      const gh = glyphH;
      const FW = cols * gw;
      const FH = rows * gh;
      const { flat, fctx } = this;
      if (flat.width !== FW || flat.height !== FH) {
        flat.width = FW;
        flat.height = FH;
      } else {
        fctx.clearRect(0, 0, FW, FH);
      }
      fctx.globalCompositeOperation = 'source-over';
      fctx.font = met.font;
      fctx.fontKerning = 'none';
      fctx.textBaseline = 'alphabetic';
      fctx.textAlign = 'left';
      fctx.fillStyle = '#fff';
      if (this.uniformAdvance(met, chars)) {
        for (let r = 0; r < rows; r++) fctx.fillText(glyphs[r].join(''), 0, r * gh + met.baseline);
      } else {
        // A fallback glyph with a different advance would drift a whole row; place each one.
        fctx.textAlign = 'center';
        for (let r = 0; r < rows; r++) {
          const y = r * gh + met.baseline;
          for (let c = 0; c < cols; c++) fctx.fillText(glyphs[r][c], c * gw + gw / 2, y);
        }
      }
      if (this.colour.width !== cols || this.colour.height !== rows) {
        this.colour.width = cols;
        this.colour.height = rows;
      }
      this.cctx.putImageData(new ImageData(ink, cols, rows), 0, 0);
      fctx.globalCompositeOperation = 'source-in';
      fctx.imageSmoothingEnabled = false;
      fctx.drawImage(this.colour, 0, 0, cols, rows, 0, 0, FW, FH);
      fctx.globalCompositeOperation = 'destination-over';
      fctx.fillStyle = s.background;
      fctx.fillRect(0, 0, FW, FH);
      fctx.globalCompositeOperation = 'source-over';
      fctx.imageSmoothingEnabled = true;

      // 3. Warp the flat grid into the window. The bilinear surface is drawn
      // as a grid of patches, each an affine image draw; more patches when the
      // window is far from a parallelogram (keystoned or twisted).
      const { warp, wctx } = this;
      if (warp.width !== W || warp.height !== H) {
        warp.width = W;
        warp.height = H;
      } else {
        wctx.clearRect(0, 0, W, H);
      }
      const ex = quad[1][0] - quad[0][0] - (quad[2][0] - quad[3][0]);
      const ey = quad[1][1] - quad[0][1] - (quad[2][1] - quad[3][1]);
      const patches = Math.max(2, Math.min(MAX_PATCHES, Math.ceil(Math.sqrt(Math.hypot(ex, ey) / PATCH_ERROR_PX))));
      const pw = FW / patches;
      const ph = FH / patches;
      const bleed = PATCH_BLEED;
      for (let i = 0; i < patches; i++) {
        const v0 = i / patches;
        const v1 = (i + 1) / patches;
        for (let j = 0; j < patches; j++) {
          const u0 = j / patches;
          const u1 = (j + 1) / patches;
          const p00 = bilinear(quad, u0, v0);
          const p10 = bilinear(quad, u1, v0);
          const p01 = bilinear(quad, u0, v1);
          wctx.setTransform(
            (p10[0] - p00[0]) / pw,
            (p10[1] - p00[1]) / pw,
            (p01[0] - p00[0]) / ph,
            (p01[1] - p00[1]) / ph,
            p00[0],
            p00[1],
          );
          wctx.drawImage(
            flat,
            j * pw - bleed, i * ph - bleed, pw + 2 * bleed, ph + 2 * bleed,
            -bleed, -bleed, pw + 2 * bleed, ph + 2 * bleed,
          );
        }
      }
      wctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.globalAlpha = s.opacity;
      ctx.drawImage(warp, 0, 0);
      ctx.globalAlpha = 1;
      return { cols, rows };
    }

    /** The outline of the window and the four fingertips, as the desktop app draws them. */
    drawOverlay(tipsNorm, quadNorm, locked) {
      const { view, ctx } = this;
      const W = view.width;
      const H = view.height;
      const scale = Math.max(1, W / 640);
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.globalAlpha = 1;
      ctx.lineWidth = Math.max(1, Math.round(1.5 * scale));
      ctx.lineJoin = 'round';
      if (quadNorm) {
        ctx.strokeStyle = locked ? 'rgb(255, 196, 0)' : '#fff';
        ctx.beginPath();
        quadNorm.forEach(([x, y], k) => (k ? ctx.lineTo(x * W, y * H) : ctx.moveTo(x * W, y * H)));
        ctx.closePath();
        ctx.stroke();
      }
      const radius = 6 * scale;
      for (const [x, y] of tipsNorm) {
        ctx.beginPath();
        ctx.arc(x * W, y * H, radius, 0, Math.PI * 2);
        ctx.fillStyle = '#000';
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.stroke();
      }
    }
  }

  window.PrismRenderer = PrismRenderer;
})();
