"""Ordering fingertip points into a quad, sizing it, smoothing it, and the
perspective maps between a flat rectangle and that quad.

Coordinates are image-style: x to the right, y down. Quads are (4, 2) arrays
ordered [top-left, top-right, bottom-right, bottom-left].
"""

from __future__ import annotations

import cv2
import numpy as np


def order_quad(points) -> np.ndarray:
    """Order four points clockwise on screen, starting at the top-left-most.

    Works regardless of which finger produced which point.
    """
    pts = np.asarray(points, dtype=np.float64).reshape(4, 2)
    centre = pts.mean(axis=0)
    # Ascending atan2 with y pointing down is clockwise as seen on screen.
    angles = np.arctan2(pts[:, 1] - centre[1], pts[:, 0] - centre[0])
    pts = pts[np.argsort(angles)]
    start = int(np.argmin(pts.sum(axis=1)))
    return np.roll(pts, -start, axis=0)


def is_convex(quad) -> bool:
    """True when the ordered corners form a strictly convex quadrilateral."""
    q = np.asarray(quad, dtype=np.float64).reshape(4, 2)
    sign = 0
    for i in range(4):
        a, b, c = q[i], q[(i + 1) % 4], q[(i + 2) % 4]
        cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        if abs(cross) < 1e-9:
            return False
        s = 1 if cross > 0 else -1
        if sign == 0:
            sign = s
        elif s != sign:
            return False
    return True


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


def rect_corners(width: float, height: float) -> np.ndarray:
    return np.array([[0, 0], [width, 0], [width, height], [0, height]], dtype=np.float32)


def rect_to_quad(width: float, height: float, quad) -> np.ndarray:
    """3x3 perspective map from a width x height rectangle onto the quad."""
    return cv2.getPerspectiveTransform(rect_corners(width, height), np.asarray(quad, dtype=np.float32))


def quad_to_rect(quad, width: float, height: float) -> np.ndarray:
    """3x3 perspective map from the quad onto a width x height rectangle."""
    return cv2.getPerspectiveTransform(np.asarray(quad, dtype=np.float32), rect_corners(width, height))


def apply_homography(h: np.ndarray, points) -> np.ndarray:
    pts = np.asarray(points, dtype=np.float64).reshape(-1, 2)
    hom = np.hstack([pts, np.ones((len(pts), 1))]) @ h.T
    return hom[:, :2] / hom[:, 2:3]
