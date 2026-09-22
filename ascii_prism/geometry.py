"""Quad geometry: sizing, smoothing, twist detection, and the bilinear maps
between the unit square and the fingertip quad.

Coordinates are image-style: x to the right, y down. Quads are (4, 2) arrays
ordered [top-left, top-right, bottom-right, bottom-left], where "top" means
the index-finger edge and "bottom" the thumb edge. The quad may be twisted
(edges crossing, like an hourglass) when one hand is flipped; a bilinear map
handles that where a perspective map cannot.
"""

from __future__ import annotations

import numpy as np


def quad_size(quad) -> tuple[float, float]:
    """Average width and height of an ordered quad (opposite edges averaged)."""
    tl, tr, br, bl = np.asarray(quad, dtype=np.float64).reshape(4, 2)

    def dist(p, q):
        return float(np.hypot(p[0] - q[0], p[1] - q[1]))

    return (dist(tl, tr) + dist(bl, br)) / 2, (dist(tl, bl) + dist(tr, br)) / 2


def smooth_quad(prev, new, factor: float) -> np.ndarray:
    """Exponential smoothing. factor=0 follows exactly, close to 1 lags heavily."""
    new = np.asarray(new, dtype=np.float64)
    if prev is None:
        return new.copy()
    return np.asarray(prev, dtype=np.float64) * factor + new * (1.0 - factor)


def _segments_cross(p1, p2, q1, q2) -> bool:
    def orient(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    return (orient(p1, p2, q1) * orient(p1, p2, q2) < 0) and (orient(q1, q2, p1) * orient(q1, q2, p2) < 0)


def is_twisted(quad) -> bool:
    """True when opposite edges cross (an hourglass), e.g. one hand is flipped."""
    tl, tr, br, bl = np.asarray(quad, dtype=np.float64).reshape(4, 2)
    return _segments_cross(tl, tr, bl, br) or _segments_cross(tl, bl, tr, br)


def bilinear_map(quad, u, v) -> tuple[np.ndarray, np.ndarray]:
    """Map unit-square coordinates (u right, v down) onto the quad."""
    tl, tr, br, bl = np.asarray(quad, dtype=np.float64).reshape(4, 2)
    u = np.asarray(u, dtype=np.float64)
    v = np.asarray(v, dtype=np.float64)
    w00, w10, w11, w01 = (1 - u) * (1 - v), u * (1 - v), u * v, (1 - u) * v
    x = w00 * tl[0] + w10 * tr[0] + w11 * br[0] + w01 * bl[0]
    y = w00 * tl[1] + w10 * tr[1] + w11 * br[1] + w01 * bl[1]
    return x, y


def inverse_bilinear(quad, x, y) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Map image points back into the unit square (vectorized).

    Returns (u, v, valid). `valid` is False where the point lies outside the
    quad. For a twisted quad the surface folds over itself; in the overlap
    the first root is used consistently. Based on the closed form in
    I. Quilez, "Inverse bilinear interpolation".
    """
    tl, tr, br, bl = np.asarray(quad, dtype=np.float64).reshape(4, 2)
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    e = tr - tl
    f = bl - tl
    g = tl - tr + br - bl
    hx, hy = x - tl[0], y - tl[1]

    def cross(ax, ay, bx, by):
        return ax * by - ay * bx

    k2 = cross(g[0], g[1], f[0], f[1])
    k1 = cross(e[0], e[1], f[0], f[1]) + cross(hx, hy, g[0], g[1])
    k0 = cross(hx, hy, e[0], e[1])

    def solve_u(v):
        dx = e[0] + g[0] * v
        dy = e[1] + g[1] * v
        use_x = np.abs(dx) >= np.abs(dy)
        with np.errstate(divide="ignore", invalid="ignore"):
            ux = (hx - f[0] * v) / dx
            uy = (hy - f[1] * v) / dy
        return np.where(use_x, ux, uy)

    def in_range(u, v):
        return np.isfinite(u) & np.isfinite(v) & (u >= 0) & (u <= 1) & (v >= 0) & (v <= 1)

    if abs(k2) < 1e-9:
        with np.errstate(divide="ignore", invalid="ignore"):
            v = np.where(np.abs(k1) > 1e-12, -k0 / k1, np.nan)
        u = solve_u(v)
        return u, v, in_range(u, v)

    disc = k1 * k1 - 4.0 * k0 * k2
    has_root = disc >= 0
    root = np.sqrt(np.maximum(disc, 0.0))
    v1 = (-k1 - root) / (2.0 * k2)
    v2 = (-k1 + root) / (2.0 * k2)
    u1 = solve_u(v1)
    u2 = solve_u(v2)
    ok1 = has_root & in_range(u1, v1)
    ok2 = has_root & in_range(u2, v2)
    u = np.where(ok1, u1, u2)
    v = np.where(ok1, v1, v2)
    return u, v, ok1 | ok2
