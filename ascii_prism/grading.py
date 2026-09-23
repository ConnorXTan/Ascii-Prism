"""Colour grading of the sampled cell colours.

Every character takes the average colour of the video it replaces. Before it
is drawn that colour goes through brightness gain, a hue rotation and a
saturation change, in that order. Hue is rotated in HSV so a pure red can
become a pure green without clipping; saturation scales the distance from
the cell's own luminance so greyscale stays at the right brightness.
"""

from __future__ import annotations

import cv2
import numpy as np

from .settings import Settings

_LUMA_BGR = np.array([0.0722, 0.7152, 0.2126], dtype=np.float32)


def grade(cells: np.ndarray, settings: Settings) -> np.ndarray:
    """Return graded ink colours for `cells`, a (rows, cols, 3) float32 BGR array in 0..1."""
    ink = np.asarray(cells, dtype=np.float32)
    if settings.brightness != 1.0:
        ink = np.clip(ink * np.float32(settings.brightness), 0.0, 1.0)
    shift = settings.hue % 360.0
    if shift:
        hsv = cv2.cvtColor(np.ascontiguousarray(ink), cv2.COLOR_BGR2HSV)
        hsv[..., 0] = (hsv[..., 0] + np.float32(shift)) % 360.0
        ink = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    if settings.saturation != 1.0:
        lum = (ink @ _LUMA_BGR)[..., None]
        ink = np.clip(lum + (ink - lum) * np.float32(settings.saturation), 0.0, 1.0)
    return ink


def blend(region: np.ndarray, rendered: np.ndarray, opacity: float) -> np.ndarray:
    """Mix the rendered characters over the video region (both uint8 BGR)."""
    if opacity >= 1.0:
        return rendered
    return cv2.addWeighted(region, 1.0 - opacity, rendered, opacity, 0.0)
