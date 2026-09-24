"""Thin wrapper around MediaPipe's Hand Landmarker.

Returns, for every detected hand, the fingertips the app needs plus a few
palm landmarks, which side of the frame the hand is on, and whether the palm
or the back of the hand faces the camera. Coordinates are normalized (0..1,
origin top-left) in the frame that was passed in.

Left and right come from position, not from MediaPipe's handedness
classifier: with two hands the one further left on screen is "Left", and a
lone hand is labelled by which half of the frame it is in. That is what the
viewer sees, it is the same whether or not the frame is mirrored, and it
does not depend on a classifier that is easily confused by the back of a
hand. Crossed arms therefore swap the labels.
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
    handedness: str  # "Left" or "Right": which side of the frame the hand is on
    facing: str  # "palm" or "back": which side of the hand faces the camera


def sides_for(centers_x: list[float]) -> list[str]:
    """"Left"/"Right" for each hand from its horizontal position.

    Two or more hands: the leftmost is "Left" and the others "Right". One
    hand: whichever half of the frame it is in.
    """
    if len(centers_x) == 1:
        return ["Left" if centers_x[0] < 0.5 else "Right"]
    leftmost = int(np.argmin(centers_x)) if centers_x else -1
    return ["Left" if i == leftmost else "Right" for i in range(len(centers_x))]


def hand_facing(wrist: Point, index_mcp: Point, pinky_mcp: Point, side: str) -> str:
    """Palm or back, from the winding of wrist -> index knuckle -> pinky knuckle.

    `side` is where the hand is on screen. Hold both hands up with palms to
    the camera and the thumbs point at each other: on the right-hand side of
    the frame the index knuckle is left of the pinky knuckle, which makes
    this cross product positive; the back of the hand flips the sign, and
    the other side of the frame flips it again. Mirroring the frame moves
    the hand to the other side and flips the winding, so the answer is the
    same either way. The rule is rotation invariant, so it holds with
    fingers pointing sideways or down.
    """
    ax, ay = index_mcp[0] - wrist[0], index_mcp[1] - wrist[1]
    bx, by = pinky_mcp[0] - wrist[0], pinky_mcp[1] - wrist[1]
    cross = ax * by - ay * bx
    return "palm" if (cross > 0) == (side == "Right") else "back"


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
        landmarks = [[(p.x, p.y) for p in lm] for lm in result.hand_landmarks]
        centers = [(float(np.mean([p[0] for p in lm])), float(np.mean([p[1] for p in lm]))) for lm in landmarks]
        sides = sides_for([c[0] for c in centers])
        hands = []
        for lm, center, side in zip(landmarks, centers, sides):
            wrist, index_mcp, pinky_mcp = lm[WRIST], lm[INDEX_MCP], lm[PINKY_MCP]
            hands.append(
                Hand(
                    thumb=lm[THUMB_TIP],
                    index=lm[INDEX_TIP],
                    wrist=wrist,
                    center=center,
                    handedness=side,
                    facing=hand_facing(wrist, index_mcp, pinky_mcp, side),
                )
            )
        return hands

    def close(self) -> None:
        self._landmarker.close()
