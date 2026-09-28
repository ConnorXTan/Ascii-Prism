"""Per-frame processing: hand tracking, region geometry, the lens render and
the fingertip overlay. No windows or input handling here, so it is easy to
test and to drive from a file instead of a camera.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import cv2
import numpy as np

from .ascii import AsciiRenderer, RegionInfo
from .geometry import is_twisted, smooth_quad
from .hands import Hand, HandTracker
from .lenses import DEFAULT_LENS_ID, Lens, LensContext, by_id, render_lens
from .settings import Settings

HINT_BOTH_HANDS = "Show both hands with thumbs and index fingers out. The four fingertips frame the ASCII window."
HINT_ONE_HAND = "One hand found. Show the other hand too."
HINT_SMALL = "Move your hands apart to open a larger window."

MAX_DT = 0.25  # seconds; a stall or a seek is not one long frame
HISTORY_WIDTH = 640  # history frames are stored this wide
HISTORY_MARGIN_S = 0.5  # kept beyond the current delay so a longer delay has frames ready


@dataclass
class FrameResult:
    frame: np.ndarray
    hands: int
    tips: np.ndarray  # (N, 2) fingertip pixels in display space
    quad: np.ndarray | None
    region: RegionInfo | None  # the character grid, when the lens draws one
    twisted: bool
    hint: str
    locked: bool
    lens: str = DEFAULT_LENS_ID


def quad_from_hands(hands: list[Hand], width: int, height: int) -> np.ndarray:
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


class Pipeline:
    def __init__(self, tracker: HandTracker | None, renderer: AsciiRenderer, settings: Settings):
        self.tracker = tracker
        self.renderer = renderer
        self.settings = settings
        self.locked = False
        self._smoothed: np.ndarray | None = None
        self._last_quad: np.ndarray | None = None
        self._lens: Lens | None = None
        self._last_ts: int | None = None
        self._history: deque[tuple[int, np.ndarray]] = deque()  # (timestamp_ms, small clean frame)

    def toggle_lock(self) -> bool:
        if not self.locked and self._last_quad is None:
            return False
        self.locked = not self.locked
        return self.locked

    def reset_tracking(self) -> None:
        self._smoothed = None
        if self._lens is not None:
            self._lens.reset()

    @property
    def lens(self) -> Lens:
        """The active lens, created on first use and swapped when the setting changes."""
        wanted = self.settings.lens
        if self._lens is None or self._lens.id != wanted:
            cls = by_id(wanted) or by_id(DEFAULT_LENS_ID)
            if self._lens is not None:
                self._lens.reset()
            self._lens = cls()
        return self._lens

    def process(self, frame_bgr: np.ndarray, timestamp_ms: int) -> FrameResult:
        s = self.settings
        frame = cv2.flip(frame_bgr, 1) if s.mirror else frame_bgr.copy()
        h, w = frame.shape[:2]
        dt = 0.0 if self._last_ts is None else min(MAX_DT, max(0.0, (timestamp_ms - self._last_ts) / 1000.0))
        self._last_ts = timestamp_ms

        hands: list[Hand] = []
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
        elif len(hands) >= 2:
            self._smoothed = smooth_quad(self._smoothed, quad_from_hands(hands, w, h), s.smoothing)
            quad = self._smoothed
        else:
            self._smoothed = None
            if self.tracker is None:
                hint = "Hand tracking unavailable."
            elif len(hands) == 1:
                hint = HINT_ONE_HAND
            else:
                hint = HINT_BOTH_HANDS

        lens = self.lens
        if lens.needs_history:
            self._remember(frame, timestamp_ms, s.delay)
        elif self._history:
            self._history.clear()
        region = None
        if quad is not None:
            ctx = LensContext(frame, timestamp_ms, dt, self.renderer, self._history_at)
            drawn, region = render_lens(lens, frame, quad, s, ctx)
            if not drawn:
                hint = HINT_SMALL
                quad = None
        if quad is not None:
            self._last_quad = quad
        elif not self.locked:
            self._last_quad = None

        if s.show_tips:
            self._draw_overlay(frame, tips, quad)
        twisted = bool(quad is not None and is_twisted(quad))
        return FrameResult(frame, len(hands), tips, quad, region, twisted, hint, self.locked, lens.id)

    def _remember(self, frame: np.ndarray, timestamp_ms: int, delay: float) -> None:
        """Keep a small copy of the clean frame and drop the ones older than needed."""
        h, w = frame.shape[:2]
        if w > HISTORY_WIDTH:
            small = cv2.resize(frame, (HISTORY_WIDTH, max(1, round(h * HISTORY_WIDTH / w))), interpolation=cv2.INTER_AREA)
        else:
            small = frame.copy()
        self._history.append((timestamp_ms, small))
        keep_ms = (delay + HISTORY_MARGIN_S) * 1000
        while self._history and timestamp_ms - self._history[0][0] > keep_ms:
            self._history.popleft()

    def history_size(self) -> int:
        return len(self._history)

    def _history_at(self, seconds: float) -> np.ndarray | None:
        """The remembered frame nearest `seconds` ago, or None if there is none.
        Right after a switch the buffer is short, so the echo starts close to
        live and drifts back to the full delay as frames accumulate."""
        if not self._history or self._last_ts is None:
            return None
        target = self._last_ts - seconds * 1000
        return min(self._history, key=lambda item: abs(item[0] - target))[1]

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
