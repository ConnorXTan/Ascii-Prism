"""Thin wrapper around MediaPipe's Hand Landmarker.

Returns, for every detected hand, the fingertips the app needs plus a few
palm landmarks, which hand it is, and whether the palm or the back of the
hand faces the camera. Coordinates are normalized (0..1, origin top-left)
in the frame that was passed in.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

WRIST = 0
THUMB_TIP = 4
INDEX_MCP = 5
INDEX_TIP = 8
PINKY_MCP = 17

Point = tuple[float, float]


@dataclass(frozen=True)
class Hand:
    thumb: Point
    index: Point
    wrist: Point
    center: Point
    handedness: str  # "Left" or "Right": the person's own hand
    facing: str  # "palm" or "back": which side faces the camera


def hand_facing(wrist: Point, index_mcp: Point, pinky_mcp: Point, raw_label: str) -> str:
    """Palm or back, from the winding of wrist -> index knuckle -> pinky knuckle.

    MediaPipe labels handedness as if the image were a selfie (mirrored). In
    such an image a right hand with its palm to the camera has the index
    knuckle left of the pinky knuckle, which makes this cross product
    positive; the back of the hand flips the sign, and a left hand flips it
    again. Using MediaPipe's own label with the image as given keeps the
    result correct whether or not the frame is mirrored.
    """
    ax, ay = index_mcp[0] - wrist[0], index_mcp[1] - wrist[1]
    bx, by = pinky_mcp[0] - wrist[0], pinky_mcp[1] - wrist[1]
    cross = ax * by - ay * bx
    return "palm" if (cross > 0) == (raw_label == "Right") else "back"


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

    def detect(self, frame_rgb: np.ndarray, timestamp_ms: int, mirrored: bool = True) -> list[Hand]:
        """Run detection on an RGB frame.

        `mirrored` says whether the frame is selfie-style (already flipped).
        MediaPipe assumes it is; for a raw camera frame the labels are swapped.
        Timestamps must increase; we enforce it.
        """
        timestamp_ms = int(timestamp_ms)
        if timestamp_ms <= self._last_ts:
            timestamp_ms = self._last_ts + 1
        self._last_ts = timestamp_ms
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=np.ascontiguousarray(frame_rgb))
        result = self._landmarker.detect_for_video(image, timestamp_ms)
        hands = []
        for i, lm in enumerate(result.hand_landmarks):
            raw_label = "Unknown"
            if result.handedness and result.handedness[i]:
                raw_label = result.handedness[i][0].category_name
            pt = lambda idx: (lm[idx].x, lm[idx].y)  # noqa: E731
            wrist, index_mcp, pinky_mcp = pt(WRIST), pt(INDEX_MCP), pt(PINKY_MCP)
            label = raw_label
            if not mirrored and raw_label in ("Left", "Right"):
                label = "Right" if raw_label == "Left" else "Left"
            hands.append(
                Hand(
                    thumb=pt(THUMB_TIP),
                    index=pt(INDEX_TIP),
                    wrist=wrist,
                    center=(float(np.mean([p.x for p in lm])), float(np.mean([p.y for p in lm]))),
                    handedness=label,
                    facing=hand_facing(wrist, index_mcp, pinky_mcp, raw_label),
                )
            )
        return hands

    def close(self) -> None:
        self._landmarker.close()
