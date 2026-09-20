"""Thin wrapper around MediaPipe's Hand Landmarker.

Returns just what the app needs: the thumb tip and index-finger tip of every
detected hand, in normalized image coordinates (0..1, origin top-left).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

THUMB_TIP = 4
INDEX_TIP = 8


@dataclass(frozen=True)
class HandTips:
    thumb: tuple[float, float]
    index: tuple[float, float]
    handedness: str


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

    def detect(self, frame_rgb: np.ndarray, timestamp_ms: int) -> list[HandTips]:
        """Run detection on an RGB frame. Timestamps must increase; we enforce it."""
        timestamp_ms = int(timestamp_ms)
        if timestamp_ms <= self._last_ts:
            timestamp_ms = self._last_ts + 1
        self._last_ts = timestamp_ms
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=np.ascontiguousarray(frame_rgb))
        result = self._landmarker.detect_for_video(image, timestamp_ms)
        tips = []
        for i, lm in enumerate(result.hand_landmarks):
            label = "Unknown"
            if result.handedness and result.handedness[i]:
                label = result.handedness[i][0].category_name
            tips.append(
                HandTips(
                    thumb=(lm[THUMB_TIP].x, lm[THUMB_TIP].y),
                    index=(lm[INDEX_TIP].x, lm[INDEX_TIP].y),
                    handedness=label,
                )
            )
        return tips

    def close(self) -> None:
        self._landmarker.close()
