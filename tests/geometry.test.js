import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  orderQuad,
  isConvex,
  squareToQuad,
  applyHomography,
  invert3,
  quadSize,
  smoothQuad,
} from '../src/geometry.js';

const near = (a, b, eps = 1e-9) => Math.abs(a - b) < eps;
const pointNear = (p, q) => near(p.x, q.x) && near(p.y, q.y);

test('orderQuad returns TL, TR, BR, BL regardless of input order', () => {
  const tl = { x: 10, y: 10 };
  const tr = { x: 90, y: 12 };
  const br = { x: 95, y: 80 };
  const bl = { x: 8, y: 85 };
  const shuffles = [
    [tl, tr, br, bl],
    [br, tl, bl, tr],
    [bl, br, tr, tl],
    [tr, bl, tl, br],
  ];
  for (const input of shuffles) {
    const out = orderQuad(input);
    assert.deepEqual(out, [tl, tr, br, bl]);
  }
});

test('isConvex distinguishes convex and concave quads', () => {
  assert.equal(isConvex([{ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 1, y: 1 }, { x: 0, y: 1 }]), true);
  // One corner pushed inside the triangle of the other three.
  assert.equal(isConvex([{ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 0.4, y: 0.4 }, { x: 0, y: 1 }]), false);
  // Collinear points are not convex.
  assert.equal(isConvex([{ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 2, y: 0 }, { x: 0, y: 1 }]), false);
});

test('squareToQuad maps unit-square corners onto the quad', () => {
  const quad = [
    { x: 100, y: 80 },
    { x: 620, y: 120 },
    { x: 700, y: 560 },
    { x: 60, y: 480 },
  ];
  const H = squareToQuad(quad);
  assert.ok(H);
  assert.ok(pointNear(applyHomography(H, 0, 0), quad[0]));
  assert.ok(pointNear(applyHomography(H, 1, 0), quad[1]));
  assert.ok(pointNear(applyHomography(H, 1, 1), quad[2]));
  assert.ok(pointNear(applyHomography(H, 0, 1), quad[3]));
  // Midpoint of the top edge stays on the segment between TL and TR.
  const mid = applyHomography(H, 0.5, 0);
  const t = (mid.x - quad[0].x) / (quad[1].x - quad[0].x);
  assert.ok(near(mid.y, quad[0].y + t * (quad[1].y - quad[0].y), 1e-6));
});

test('squareToQuad handles the affine (parallelogram) case', () => {
  const quad = [
    { x: 0, y: 0 },
    { x: 2, y: 0 },
    { x: 3, y: 1 },
    { x: 1, y: 1 },
  ];
  const H = squareToQuad(quad);
  assert.ok(H);
  assert.equal(H[6], 0);
  assert.equal(H[7], 0);
  assert.ok(pointNear(applyHomography(H, 1, 1), quad[2]));
  assert.ok(pointNear(applyHomography(H, 0.5, 0.5), { x: 1.5, y: 0.5 }));
});

test('invert3 gives the inverse homography', () => {
  const quad = [
    { x: 0.2, y: 0.1 },
    { x: 0.8, y: 0.15 },
    { x: 0.9, y: 0.9 },
    { x: 0.1, y: 0.7 },
  ];
  const H = squareToQuad(quad);
  const Hinv = invert3(H);
  assert.ok(Hinv);
  for (const [u, v] of [[0, 0], [1, 0], [1, 1], [0, 1], [0.3, 0.7]]) {
    const p = applyHomography(H, u, v);
    const back = applyHomography(Hinv, p.x, p.y);
    assert.ok(near(back.x, u, 1e-9) && near(back.y, v, 1e-9), `roundtrip ${u},${v}`);
  }
});

test('invert3 returns null for a singular matrix', () => {
  assert.equal(invert3([1, 2, 3, 2, 4, 6, 0, 0, 1]), null);
});

test('quadSize averages opposite edges', () => {
  const size = quadSize([
    { x: 0, y: 0 },
    { x: 10, y: 0 },
    { x: 10, y: 6 },
    { x: 0, y: 4 },
  ]);
  assert.ok(near(size.width, (10 + Math.hypot(10, 2)) / 2));
  assert.equal(size.height, 5);
});

test('smoothQuad blends towards the new quad', () => {
  const prev = [{ x: 0, y: 0 }, { x: 0, y: 0 }, { x: 0, y: 0 }, { x: 0, y: 0 }];
  const next = [{ x: 10, y: 10 }, { x: 10, y: 10 }, { x: 10, y: 10 }, { x: 10, y: 10 }];
  const out = smoothQuad(prev, next, 0.5);
  assert.ok(out.every((p) => p.x === 5 && p.y === 5));
  assert.deepEqual(smoothQuad(null, next, 0.9), next);
});
