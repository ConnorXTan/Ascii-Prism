/**
 * WebGL2 renderer.
 *
 * Pass 1 draws the (optionally mirrored) camera frame full screen.
 * Pass 2 draws the ASCII region: a full-screen fragment shader maps each pixel
 * through the inverse homography into the unit square, discards pixels that
 * fall outside it (so the plain video stays visible there), works out which
 * character cell the pixel is in, samples the video colour for that cell,
 * picks a glyph from the ramp by luminance and looks it up in a glyph atlas.
 * Because the mapping is projective, the character grid tilts and skews with
 * your hands.
 */

const ATLAS_COLS = 16;
const GLYPH_H = 96;
/** Fallback width / height of one character cell before a font is measured. */
export const DEFAULT_CELL_ASPECT = 0.5;

const VIDEO_VS = `#version 300 es
layout(location = 0) in vec2 aPos;
uniform float uMirror;
out vec2 vTex;
void main() {
  vec2 t = aPos * 0.5 + 0.5;
  t.y = 1.0 - t.y;
  if (uMirror > 0.5) t.x = 1.0 - t.x;
  vTex = t;
  gl_Position = vec4(aPos, 0.0, 1.0);
}`;

const VIDEO_FS = `#version 300 es
precision mediump float;
in vec2 vTex;
uniform sampler2D uVideo;
out vec4 outColor;
void main() {
  outColor = vec4(texture(uVideo, vTex).rgb, 1.0);
}`;

const ASCII_VS = `#version 300 es
layout(location = 0) in vec2 aPos;
void main() {
  gl_Position = vec4(aPos, 0.0, 1.0);
}`;

const ASCII_FS = `#version 300 es
precision highp float;
uniform sampler2D uVideo;
uniform sampler2D uAtlas;
uniform mat3 uH;          // unit square -> display space (normalized, y down)
uniform mat3 uHinv;       // display space -> unit square
uniform vec2 uGrid;       // character columns, rows
uniform vec2 uAtlasGrid;  // atlas columns, rows
uniform vec2 uGlyphPx;    // pixel size of one atlas cell
uniform float uGlyphCount;
uniform vec2 uResolution;
uniform float uMirror;
uniform int uColorMode;   // 0 = sampled, 1 = vivid, 2 = mono
uniform vec3 uMonoColor;
uniform vec3 uBackground;
uniform float uInvert;
out vec4 outColor;

vec2 toVideoTex(vec2 d) {
  return vec2(uMirror > 0.5 ? 1.0 - d.x : d.x, d.y);
}

void main() {
  vec2 d = vec2(gl_FragCoord.x / uResolution.x, 1.0 - gl_FragCoord.y / uResolution.y);
  vec3 p = uHinv * vec3(d, 1.0);
  if (abs(p.z) < 1e-7) discard;
  vec2 uv = p.xy / p.z;
  if (uv.x < 0.0 || uv.x >= 1.0 || uv.y < 0.0 || uv.y >= 1.0) discard;

  vec2 cellF = uv * uGrid;
  vec2 cell = floor(cellF);
  vec2 inCell = cellF - cell;

  // Average a 3x3 set of samples across the cell's footprint in the video.
  vec3 sum = vec3(0.0);
  for (int j = 0; j < 3; j++) {
    for (int i = 0; i < 3; i++) {
      vec2 suv = (cell + (vec2(float(i), float(j)) + 0.5) / 3.0) / uGrid;
      vec3 q = uH * vec3(suv, 1.0);
      sum += texture(uVideo, toVideoTex(q.xy / q.z)).rgb;
    }
  }
  vec3 color = sum / 9.0;

  float lum = dot(color, vec3(0.2126, 0.7152, 0.0722));
  lum = mix(lum, 1.0 - lum, uInvert);
  float idx = floor(clamp(lum, 0.0, 0.999999) * uGlyphCount);
  vec2 glyphCell = vec2(mod(idx, uAtlasGrid.x), floor(idx / uAtlasGrid.x));
  // Derivatives of the continuous cell coordinate keep mip selection stable
  // across cell boundaries (plain texture() would see a jump in atlasUV).
  vec2 gx = dFdx(cellF) / uAtlasGrid;
  vec2 gy = dFdy(cellF) / uAtlasGrid;
  // Keep samples half a texel (at the mip level in use) inside the glyph cell
  // so bilinear filtering never blends in the neighbouring glyph.
  vec2 atlasPx = uAtlasGrid * uGlyphPx;
  float lod = max(0.0, log2(max(length(gx * atlasPx), length(gy * atlasPx))));
  vec2 inset = min(vec2(0.5), 0.5 * exp2(lod) / uGlyphPx);
  vec2 atlasUV = (glyphCell + clamp(inCell, inset, 1.0 - inset)) / uAtlasGrid;
  float glyph = textureGrad(uAtlas, atlasUV, gx, gy).r;

  vec3 ink;
  if (uColorMode == 2) {
    ink = uMonoColor;
  } else if (uColorMode == 1) {
    float m = max(color.r, max(color.g, color.b));
    ink = color / max(m, 0.15);
  } else {
    ink = color;
  }
  outColor = vec4(mix(uBackground, ink, glyph), 1.0);
}`;

function compileShader(gl, type, source) {
  const shader = gl.createShader(type);
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const log = gl.getShaderInfoLog(shader);
    gl.deleteShader(shader);
    throw new Error(`Shader compile failed: ${log}`);
  }
  return shader;
}

function createProgram(gl, vsSource, fsSource) {
  const program = gl.createProgram();
  gl.attachShader(program, compileShader(gl, gl.VERTEX_SHADER, vsSource));
  gl.attachShader(program, compileShader(gl, gl.FRAGMENT_SHADER, fsSource));
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    throw new Error(`Program link failed: ${gl.getProgramInfoLog(program)}`);
  }
  return program;
}

function createTexture(gl, minFilter) {
  const tex = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, tex);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, minFilter);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  return tex;
}

const FONT_FAMILY = 'Menlo, Consolas, "DejaVu Sans Mono", "Courier New", monospace';
function fontSpec(px) {
  return `${px}px ${FONT_FAMILY}`;
}

/**
 * Pick a font size so that a full block character exactly fills one atlas
 * cell, and return the baseline offset that centres it. This keeps block
 * ramps seamless and lets dense glyphs like '@' fill their cell the way they
 * do in a terminal.
 */
function fitFont(ctx) {
  const probe = 100;
  ctx.font = fontSpec(probe);
  const m = ctx.measureText('\u2588');
  const blockW = Math.max(1, m.width);
  const blockH = Math.max(1, m.actualBoundingBoxAscent + m.actualBoundingBoxDescent);
  // Fill the cell height (slightly over, the clip trims it) and let the cell
  // width follow the font's own block proportions.
  const fontSize = probe * (GLYPH_H / blockH) * 1.03;
  const glyphW = Math.max(8, Math.round((blockW * fontSize) / probe));
  ctx.font = fontSpec(fontSize);
  const fitted = ctx.measureText('\u2588');
  const ascent = fitted.actualBoundingBoxAscent;
  const descent = fitted.actualBoundingBoxDescent;
  // Baseline offset from the top of the cell that centres the block box.
  const baseline = (GLYPH_H - (ascent + descent)) / 2 + ascent;
  return { fontSize, baseline, glyphW };
}

function uniformLocations(gl, program, names) {
  const out = {};
  for (const name of names) out[name] = gl.getUniformLocation(program, name);
  return out;
}

function hexToRgb(hex) {
  const n = parseInt(hex.replace('#', ''), 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

export class AsciiRenderer {
  constructor(canvas) {
    const gl = canvas.getContext('webgl2', {
      antialias: false,
      alpha: false,
      premultipliedAlpha: false,
      preserveDrawingBuffer: false,
    });
    if (!gl) throw new Error('WebGL2 is not available in this browser.');
    this.gl = gl;
    this.canvas = canvas;

    this.videoProgram = createProgram(gl, VIDEO_VS, VIDEO_FS);
    this.asciiProgram = createProgram(gl, ASCII_VS, ASCII_FS);
    this.videoUniforms = uniformLocations(gl, this.videoProgram, ['uVideo', 'uMirror']);
    this.asciiUniforms = uniformLocations(gl, this.asciiProgram, [
      'uVideo', 'uAtlas', 'uH', 'uHinv', 'uGrid', 'uAtlasGrid', 'uGlyphPx', 'uGlyphCount',
      'uResolution', 'uMirror', 'uColorMode', 'uMonoColor', 'uBackground', 'uInvert',
    ]);

    // One full-screen triangle strip shared by both passes.
    this.vao = gl.createVertexArray();
    gl.bindVertexArray(this.vao);
    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);

    this.videoTex = createTexture(gl, gl.LINEAR);
    this.atlasTex = createTexture(gl, gl.LINEAR_MIPMAP_LINEAR);
    this.glyphCount = 1;
    this.atlasRows = 1;
    this.glyphW = Math.round(GLYPH_H * DEFAULT_CELL_ASPECT);
    this.hasVideo = false;

    this.atlasCanvas = document.createElement('canvas');
    this.setCharset([' ']);
  }

  /** Width / height of one character cell, as measured from the font. */
  get cellAspect() {
    return this.glyphW / GLYPH_H;
  }

  setSize(width, height) {
    if (this.canvas.width !== width || this.canvas.height !== height) {
      this.canvas.width = width;
      this.canvas.height = height;
    }
    this.gl.viewport(0, 0, width, height);
  }

  /** Upload the current video frame as a texture. */
  uploadVideo(video) {
    const gl = this.gl;
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, this.videoTex);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, video);
    this.hasVideo = true;
  }

  /**
   * Rebuild the glyph atlas from an array of characters ordered darkest to
   * brightest. Each glyph is rendered white on black into a fixed cell.
   */
  setCharset(chars) {
    const count = Math.max(1, chars.length);
    const rows = Math.ceil(count / ATLAS_COLS);
    const canvas = this.atlasCanvas;
    const ctx = canvas.getContext('2d');
    const { fontSize, baseline, glyphW } = fitFont(ctx);
    canvas.width = ATLAS_COLS * glyphW;
    canvas.height = rows * GLYPH_H;
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#fff';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'alphabetic';
    ctx.font = fontSpec(fontSize);
    chars.forEach((ch, i) => {
      const col = i % ATLAS_COLS;
      const row = Math.floor(i / ATLAS_COLS);
      const x = col * glyphW;
      const y = row * GLYPH_H;
      ctx.save();
      ctx.beginPath();
      ctx.rect(x, y, glyphW, GLYPH_H);
      ctx.clip();
      ctx.fillText(ch, x + glyphW / 2, y + baseline);
      ctx.restore();
    });
    this.glyphW = glyphW;

    const gl = this.gl;
    gl.activeTexture(gl.TEXTURE1);
    gl.bindTexture(gl.TEXTURE_2D, this.atlasTex);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, canvas);
    gl.generateMipmap(gl.TEXTURE_2D);
    this.glyphCount = count;
    this.atlasRows = rows;
  }

  /**
   * Draw one frame.
   * @param {object} opts
   * @param {boolean} opts.mirror
   * @param {null | { H: Float32Array, Hinv: Float32Array, cols: number, rows: number }} opts.region
   *        Column-major homographies in normalized display space, plus grid size.
   * @param {'sampled'|'vivid'|'mono'} opts.colorMode
   * @param {string} opts.monoColor  hex colour
   * @param {string} opts.background hex colour
   * @param {boolean} opts.invert
   */
  render({ mirror, region, colorMode, monoColor, background, invert }) {
    const gl = this.gl;
    if (!this.hasVideo) return;
    gl.bindVertexArray(this.vao);

    gl.useProgram(this.videoProgram);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, this.videoTex);
    gl.uniform1i(this.videoUniforms.uVideo, 0);
    gl.uniform1f(this.videoUniforms.uMirror, mirror ? 1 : 0);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);

    if (!region) return;
    const u = this.asciiUniforms;
    gl.useProgram(this.asciiProgram);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, this.videoTex);
    gl.activeTexture(gl.TEXTURE1);
    gl.bindTexture(gl.TEXTURE_2D, this.atlasTex);
    gl.uniform1i(u.uVideo, 0);
    gl.uniform1i(u.uAtlas, 1);
    gl.uniformMatrix3fv(u.uH, false, region.H);
    gl.uniformMatrix3fv(u.uHinv, false, region.Hinv);
    gl.uniform2f(u.uGrid, region.cols, region.rows);
    gl.uniform2f(u.uAtlasGrid, ATLAS_COLS, this.atlasRows);
    gl.uniform2f(u.uGlyphPx, this.glyphW, GLYPH_H);
    gl.uniform1f(u.uGlyphCount, this.glyphCount);
    gl.uniform2f(u.uResolution, this.canvas.width, this.canvas.height);
    gl.uniform1f(u.uMirror, mirror ? 1 : 0);
    gl.uniform1i(u.uColorMode, colorMode === 'mono' ? 2 : colorMode === 'vivid' ? 1 : 0);
    gl.uniform3fv(u.uMonoColor, hexToRgb(monoColor));
    gl.uniform3fv(u.uBackground, hexToRgb(background));
    gl.uniform1f(u.uInvert, invert ? 1 : 0);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  }
}
