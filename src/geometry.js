/**
 * Geometry helpers: ordering fingertip points into a quad, building the
 * projective map (homography) from the unit square to that quad, and
 * smoothing corners over time.
 *
 * Coordinates are screen-style: x to the right, y down.
 * Matrices are 3x3, row-major, flat arrays of 9 numbers applied to
 * column vectors:  [x, y, w]^T = M * [u, v, 1]^T
 */

/**
 * Order four points clockwise (on screen) starting from the top-left-most
 * point. Returns [topLeft, topRight, bottomRight, bottomLeft].
 * Works regardless of which finger produced which point.
 */
export function orderQuad(points) {
  if (points.length !== 4) throw new Error('orderQuad expects exactly 4 points');
  const cx = (points[0].x + points[1].x + points[2].x + points[3].x) / 4;
  const cy = (points[0].y + points[1].y + points[2].y + points[3].y) / 4;
  // Ascending atan2 with y pointing down is clockwise as seen on screen.
  const sorted = points
    .map((p) => ({ p, angle: Math.atan2(p.y - cy, p.x - cx) }))
    .sort((a, b) => a.angle - b.angle)
    .map((e) => e.p);
  let start = 0;
  let best = Infinity;
  for (let i = 0; i < 4; i++) {
    const s = sorted[i].x + sorted[i].y;
    if (s < best) {
      best = s;
      start = i;
    }
  }
  return [0, 1, 2, 3].map((i) => sorted[(start + i) % 4]);
}

/** True when the four ordered corners form a strictly convex quadrilateral. */
export function isConvex(quad) {
  let sign = 0;
  for (let i = 0; i < 4; i++) {
    const a = quad[i];
    const b = quad[(i + 1) % 4];
    const c = quad[(i + 2) % 4];
    const cross = (b.x - a.x) * (c.y - b.y) - (b.y - a.y) * (c.x - b.x);
    if (Math.abs(cross) < 1e-9) return false;
    const s = Math.sign(cross);
    if (sign === 0) sign = s;
    else if (s !== sign) return false;
  }
  return true;
}

/**
 * Projective map from the unit square to a quad (Heckbert, "Fundamentals of
 * Texture Mapping and Image Warping", 1989).
 *   (0,0) -> quad[0]   (1,0) -> quad[1]   (1,1) -> quad[2]   (0,1) -> quad[3]
 * Returns null when the quad is degenerate.
 */
export function squareToQuad(quad) {
  const [p0, p1, p2, p3] = quad;
  const sx = p0.x - p1.x + p2.x - p3.x;
  const sy = p0.y - p1.y + p2.y - p3.y;
  let a, b, c, d, e, f, g, h;
  if (Math.abs(sx) < 1e-12 && Math.abs(sy) < 1e-12) {
    // Parallelogram: plain affine map.
    a = p1.x - p0.x; b = p2.x - p1.x; c = p0.x;
    d = p1.y - p0.y; e = p2.y - p1.y; f = p0.y;
    g = 0; h = 0;
  } else {
    const dx1 = p1.x - p2.x;
    const dx2 = p3.x - p2.x;
    const dy1 = p1.y - p2.y;
    const dy2 = p3.y - p2.y;
    const den = dx1 * dy2 - dx2 * dy1;
    if (Math.abs(den) < 1e-12) return null;
    g = (sx * dy2 - dx2 * sy) / den;
    h = (dx1 * sy - sx * dy1) / den;
    a = p1.x - p0.x + g * p1.x;
    b = p3.x - p0.x + h * p3.x;
    c = p0.x;
    d = p1.y - p0.y + g * p1.y;
    e = p3.y - p0.y + h * p3.y;
    f = p0.y;
  }
  return [a, b, c, d, e, f, g, h, 1];
}

/** Apply a homography to a point (with perspective divide). */
export function applyHomography(m, u, v) {
  const x = m[0] * u + m[1] * v + m[2];
  const y = m[3] * u + m[4] * v + m[5];
  const w = m[6] * u + m[7] * v + m[8];
  return { x: x / w, y: y / w };
}

/** Inverse of a 3x3 matrix, or null when singular. */
export function invert3(m) {
  const [a, b, c, d, e, f, g, h, i] = m;
  const A = e * i - f * h;
  const B = -(d * i - f * g);
  const C = d * h - e * g;
  const det = a * A + b * B + c * C;
  if (Math.abs(det) < 1e-18) return null;
  const inv = [
    A, -(b * i - c * h), b * f - c * e,
    B, a * i - c * g, -(a * f - c * d),
    C, -(a * h - b * g), a * e - b * d,
  ];
  return inv.map((v) => v / det);
}

/** Row-major 3x3 -> column-major flat array, as WebGL's uniformMatrix3fv expects. */
export function toColumnMajor(m) {
  return new Float32Array([m[0], m[3], m[6], m[1], m[4], m[7], m[2], m[5], m[8]]);
}

/** Average width and height of an ordered quad (edge lengths averaged). */
export function quadSize(quad) {
  const [tl, tr, br, bl] = quad;
  const dist = (p, q) => Math.hypot(p.x - q.x, p.y - q.y);
  return {
    width: (dist(tl, tr) + dist(bl, br)) / 2,
    height: (dist(tl, bl) + dist(tr, br)) / 2,
  };
}

/**
 * Exponential smoothing of corners. factor=0 follows the new quad exactly,
 * factor close to 1 lags heavily. Returns the new smoothed quad.
 */
export function smoothQuad(prev, next, factor) {
  if (!prev) return next.map((p) => ({ x: p.x, y: p.y }));
  return next.map((p, i) => ({
    x: prev[i].x * factor + p.x * (1 - factor),
    y: prev[i].y * factor + p.y * (1 - factor),
  }));
}
