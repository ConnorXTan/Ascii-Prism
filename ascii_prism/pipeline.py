"""Per-frame processing: hand tracking, region geometry, ASCII rendering and
the fingertip overlay. No windows or input handling here, so it is easy to
test and to drive from a file instead of a camera.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .ascii import AsciiRenderer, RegionInfo
from .geometry import is_convex, order_quad, smooth_quad
from .hands import HandTracker
from .settings import Settings

HINT_BOTH_HANDS = "Show both hands with thumbs and index fingers out. The four fingertips frame the ASCII window."
HINT_ONE_HAND = "One hand found. Show the other hand too."
HINT_CROSSED = "Your fingertips cross over. Spread thumbs and index fingers into four corners."
HINT_SMALL = "Move your hands apart to open a larger window."


@dataclass
class FrameResult:
    frame: np.ndarray
    hands: int
    tips: np.ndarray  # (N, 2) fingertip pixels in display space
    quad: np.ndarray | None
    region: RegionInfo | None
    hint: str
    locked: bool


class Pipeline:
    def __init__(self, tracker: HandTracker | None, renderer: AsciiRenderer, settings: Settings):
        self.tracker = tracker
        self.renderer = renderer
        self.settings = settings
        self.locked = False
        self._smoothed: np.ndarray | None = None
        self._last_quad: np.ndarray | None = None

    def toggle_lock(self) -> bool:
        if not self.locked and self._last_quad is None:
            return False
        self.locked = not self.locked
        return self.locked

    def reset_tracking(self) -> None:
        self._smoothed = None

    def process(self, frame_bgr: np.ndarray, timestamp_ms: int) -> FrameResult:
        s = self.settings
        frame = cv2.flip(frame_bgr, 1) if s.mirror else frame_bgr.copy()
        h, w = frame.shape[:2]

        hands = []
        if self.tracker is not None:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            hands = self.tracker.detect(rgb, timestamp_ms)
        tips = np.array(
            [[p[0] * w, p[1] * h] for hand in hands[:2] for p in (hand.thumb, hand.index)],
            dtype=np.float64,
        ).reshape(-1, 2)

        quad = None
        hint = ""
        if self.locked and self._last_quad is not None:
            quad = self._last_quad
        elif len(tips) == 4:
            ordered = order_quad(tips)
            if is_convex(ordered):
                self._smoothed = smooth_quad(self._smoothed, ordered, s.smoothing)
                quad = self._smoothed
            else:
                self._smoothed = None
                hint = HINT_CROSSED
        else:
            self._smoothed = None
            if self.tracker is None:
                hint = "Hand tracking unavailable."
            elif len(hands) == 1:
                hint = HINT_ONE_HAND
            else:
                hint = HINT_BOTH_HANDS

        region = None
        if quad is not None:
            region = self.renderer.render(frame, quad, s)
            if region is None:
                hint = HINT_SMALL
                quad = None
        if quad is not None:
            self._last_quad = quad
        elif not self.locked:
            self._last_quad = None

        if s.show_tips:
            self._draw_overlay(frame, tips, quad)
        return FrameResult(frame, len(hands), tips, quad, region, hint, self.locked)

    def _draw_overlay(self, frame: np.ndarray, tips: np.ndarray, quad: np.ndarray | None) -> None:
        h, w = frame.shape[:2]
        scale = max(1.0, w / 640)
        if quad is not None:
            colour = (0, 196, 255) if self.locked else (255, 255, 255)
            pts = np.round(quad).astype(np.int32).reshape(-1, 1, 2)
            cv2.polylines(frame, [pts], True, colour, max(1, int(round(1.5 * scale))), cv2.LINE_AA)
        for x, y in tips:
            centre = (int(round(x)), int(round(y)))
            cv2.circle(frame, centre, int(6 * scale), (0, 0, 0), -1, cv2.LINE_AA)
            cv2.circle(frame, centre, int(6 * scale), (255, 255, 255), max(1, int(round(1.5 * scale))), cv2.LINE_AA)
