"""Thin wrapper around MediaPipe's Hand Landmarker.

Returns, for every detected hand, the thumb and index fingertips the app
needs plus the hand's centre. Coordinates are normalized (0..1, origin
top-left) in the frame that was passed in.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

THUMB_TIP = 4
INDEX_TIP = 8

Point = tuple[float, float]


@dataclass(frozen=True)
class Hand:
    thumb: Point
    index: Point
    center: Point


class HandTracker:
    def __init__(self, model: Path, num_hands: int = 2, min_confidence: float = 0.5):
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        self._mp = mp
        options = vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(model)),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=num_hands,
            min_hand_detection_confidence=min_confidence,
            min_hand_presence_confidence=min_confidence,
            min_tracking_confidence=min_confidence,
        )
        self._landmarker = vision.HandLandmarker.create_from_options(options)
        self._last_ts = -1

    def detect(self, frame_rgb: np.ndarray, timestamp_ms: int) -> list[Hand]:
        """Run detection on an RGB frame. Timestamps must increase; we enforce it."""
        timestamp_ms = int(timestamp_ms)
        if timestamp_ms <= self._last_ts:
            timestamp_ms = self._last_ts + 1
        self._last_ts = timestamp_ms
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=np.ascontiguousarray(frame_rgb))
        result = self._landmarker.detect_for_video(image, timestamp_ms)
        hands = []
        for lm in result.hand_landmarks:
            hands.append(
                Hand(
                    thumb=(lm[THUMB_TIP].x, lm[THUMB_TIP].y),
                    index=(lm[INDEX_TIP].x, lm[INDEX_TIP].y),
                    center=(float(np.mean([p.x for p in lm])), float(np.mean([p.y for p in lm]))),
                )
            )
        return hands

    def close(self) -> None:
        self._landmarker.close()
