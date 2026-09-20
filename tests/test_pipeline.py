import cv2
import numpy as np

from ascii_prism.ascii import AsciiRenderer, find_font
from ascii_prism.hands import HandTracker
from ascii_prism.pipeline import HINT_BOTH_HANDS, Pipeline
from ascii_prism.settings import Settings


def test_pipeline_tracks_both_hands_and_renders(hands_photo, hand_model):
    photo = cv2.imread(str(hands_photo))
    tracker = HandTracker(hand_model)
    try:
        pipeline = Pipeline(tracker, AsciiRenderer(find_font()), Settings(columns=80))
        result = pipeline.process(photo, 0)
        assert result.hands == 2
        assert result.tips.shape == (4, 2)
        assert result.quad is not None and result.region is not None
        assert result.region.cols == 80
        assert result.hint == ""
        # The rendered frame differs from the mirrored input inside the quad.
        mirrored = cv2.flip(photo, 1)
        mask = np.zeros(photo.shape[:2], np.uint8)
        cv2.fillConvexPoly(mask, np.round(result.quad).astype(np.int32), 255)
        inside = mask > 0
        assert np.mean(np.any(result.frame[inside] != mirrored[inside], axis=1)) > 0.2

        # Locking keeps the region even when the hands disappear.
        assert pipeline.toggle_lock() is True
        blank = np.zeros_like(photo)
        locked = pipeline.process(blank, 40)
        assert locked.hands == 0 and locked.region is not None and locked.locked
        assert pipeline.toggle_lock() is False
        gone = pipeline.process(blank, 80)
        assert gone.region is None and gone.hint == HINT_BOTH_HANDS
    finally:
        tracker.close()


def test_pipeline_without_tracker_shows_plain_video():
    frame = np.full((120, 160, 3), 90, dtype=np.uint8)
    pipeline = Pipeline(None, AsciiRenderer(find_font()), Settings(mirror=False, show_tips=False))
    result = pipeline.process(frame, 0)
    assert result.region is None
    assert np.array_equal(result.frame, frame)
