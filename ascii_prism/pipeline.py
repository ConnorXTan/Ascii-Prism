"""Per-frame processing: hand tracking, region geometry, ASCII rendering and
the fingertip overlay. No windows or input handling here, so it is easy to
test and to drive from a file instead of a camera.

Two entry points share the tracking and geometry: `track()` returns where the
window is in normalized coordinates, for a client that draws the ASCII
itself (the website); `process()` also renders the window into the frame
and draws the overlay (desktop mode).
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .ascii import AsciiRenderer, RegionInfo
from .geometry import QuadFilter, is_twisted, quad_size
from .hands import Hand, HandTracker
from .settings import Settings

HINT_BOTH_HANDS = "Hold up both hands, thumbs and index fingers out."
HINT_ONE_HAND = "One hand found. Show the other one too."
HINT_SMALL = "Spread your hands apart to open a bigger window."
HINT_NO_TRACKER = "Hand tracking unavailable."

MIN_WINDOW = 0.03  # of the frame's width and height, below which there is no window


@dataclass
class TrackResult:
    """Tracking and window geometry for one frame.

    Coordinates are normalized (0..1 of the frame, origin top-left, after
    mirroring if that is on) so a client can scale them to whatever it draws.
    """

    hands: int
    tips: list[tuple[float, float]]  # thumb then index tip, per hand
    quad: np.ndarray | None  # (4, 2) ordered as in geometry.py
    twisted: bool
    hint: str
    locked: bool


@dataclass
class FrameResult:
    frame: np.ndarray
    hands: int
    tips: np.ndarray  # (N, 2) fingertip pixels in display space
    quad: np.ndarray | None
    region: RegionInfo | None
    twisted: bool
    hint: str
    locked: bool


def quad_from_hands(hands: list[Hand], width: float, height: float) -> np.ndarray:
    """Corners follow the fingers: index tips make the top edge, thumb tips
    the bottom edge, and the hand further left on screen gives the left
    corners. Flip one hand and the edges cross into an hourglass."""
    left, right = sorted(hands[:2], key=lambda h: h.center[0])
    return np.array(
        [
            [left.index[0] * width, left.index[1] * height],
            [right.index[0] * width, right.index[1] * height],
            [right.thumb[0] * width, right.thumb[1] * height],
            [left.thumb[0] * width, left.thumb[1] * height],
        ],
        dtype=np.float64,
    )


def too_small(quad_norm: np.ndarray, width: int, height: int) -> bool:
    """True when a normalized quad would be less than MIN_WINDOW of the frame."""
    qw, qh = quad_size(quad_norm * np.array([width, height], dtype=np.float64))
    return qw < width * MIN_WINDOW or qh < height * MIN_WINDOW


class Pipeline:
    def __init__(self, tracker: HandTracker | None, renderer: AsciiRenderer | None, settings: Settings):
        self.tracker = tracker
        self.renderer = renderer
        self.settings = settings
        self.locked = False
        self._filter = QuadFilter()  # normalized
        self._last_quad: np.ndarray | None = None  # normalized

    def toggle_lock(self) -> bool:
        if not self.locked and self._last_quad is None:
            return False
        self.locked = not self.locked
        return self.locked

    def reset_tracking(self) -> None:
        self._filter.reset()

    def track(self, frame_bgr: np.ndarray, timestamp_ms: int) -> TrackResult:
        """Find the hands and the window in a camera frame, without rendering."""
        frame = cv2.flip(frame_bgr, 1) if self.settings.mirror else frame_bgr
        return self._track_oriented(frame, timestamp_ms)

    def _track_oriented(self, frame: np.ndarray, timestamp_ms: int) -> TrackResult:
        s = self.settings
        h, w = frame.shape[:2]

        hands: list[Hand] = []
        if self.tracker is not None:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            hands = self.tracker.detect(rgb, timestamp_ms)
        tips = [p for hand in hands[:2] for p in (hand.thumb, hand.index)]

        quad = None
        hint = ""
        if self.locked and self._last_quad is not None:
            quad = self._last_quad
        elif len(hands) >= 2:
            quad = self._filter(quad_from_hands(hands, 1.0, 1.0), timestamp_ms, s.smoothing)
        else:
            self._filter.reset()
            if self.tracker is None:
                hint = HINT_NO_TRACKER
            elif len(hands) == 1:
                hint = HINT_ONE_HAND
            else:
                hint = HINT_BOTH_HANDS

        if quad is not None and too_small(quad, w, h):
            hint = HINT_SMALL
            quad = None
        if quad is not None:
            self._last_quad = quad
        elif not self.locked:
            self._last_quad = None

        twisted = bool(quad is not None and is_twisted(quad))
        return TrackResult(len(hands), tips, quad, twisted, hint, self.locked)

    def process(self, frame_bgr: np.ndarray, timestamp_ms: int) -> FrameResult:
        """Track, render the window into a copy of the frame and draw the overlay."""
        if self.renderer is None:
            raise RuntimeError("process() needs a renderer; use track() for geometry only")
        s = self.settings
        frame = cv2.flip(frame_bgr, 1) if s.mirror else frame_bgr.copy()
        h, w = frame.shape[:2]
        tracked = self._track_oriented(frame, timestamp_ms)

        scale = np.array([w, h], dtype=np.float64)
        tips = np.array(tracked.tips, dtype=np.float64).reshape(-1, 2) * scale
        quad = tracked.quad * scale if tracked.quad is not None else None
        hint = tracked.hint

        region = None
        if quad is not None:
            region = self.renderer.render(frame, quad, s)
            if region is None:
                hint = HINT_SMALL
                quad = None

        if s.show_tips:
            self._draw_overlay(frame, tips, quad)
        twisted = bool(quad is not None and is_twisted(quad))
        return FrameResult(frame, tracked.hands, tips, quad, region, twisted, hint, tracked.locked)

    def _draw_overlay(self, frame: np.ndarray, tips: np.ndarray, quad: np.ndarray | None) -> None:
        h, w = frame.shape[:2]
        scale = max(1.0, w / 640)
        thick = max(1, int(round(1.5 * scale)))
        if quad is not None:
            colour = (0, 196, 255) if self.locked else (255, 255, 255)
            pts = np.round(quad).astype(np.int32).reshape(-1, 1, 2)
            cv2.polylines(frame, [pts], True, colour, thick, cv2.LINE_AA)
        for x, y in tips:
            centre = (int(round(x)), int(round(y)))
            cv2.circle(frame, centre, int(6 * scale), (0, 0, 0), -1, cv2.LINE_AA)
            cv2.circle(frame, centre, int(6 * scale), (255, 255, 255), thick, cv2.LINE_AA)
