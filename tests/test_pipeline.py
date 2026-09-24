import cv2
import numpy as np

from ascii_prism.ascii import AsciiRenderer, find_font
from ascii_prism.hands import Hand, HandTracker
from ascii_prism.pipeline import HINT_BOTH_HANDS, HINT_ONE_HAND, Pipeline, quad_from_hands
from ascii_prism.settings import Settings


def make_hand(index, thumb, center):
    return Hand(thumb=thumb, index=index, center=center)


class FakeTracker:
    def __init__(self, hands):
        self.hands = hands

    def detect(self, frame_rgb, timestamp_ms, mirrored=True):
        return self.hands


def test_quad_from_hands_follows_fingers():
    left = make_hand(index=(0.2, 0.2), thumb=(0.2, 0.8), center=(0.25, 0.5))
    right = make_hand(index=(0.8, 0.2), thumb=(0.8, 0.8), center=(0.75, 0.5))
    quad = quad_from_hands([right, left], 100, 100)  # order of detection must not matter
    np.testing.assert_allclose(quad, [(20, 20), (80, 20), (80, 80), (20, 80)])


def test_flipped_hand_makes_a_twisted_window():
    left = make_hand(index=(0.2, 0.2), thumb=(0.2, 0.8), center=(0.25, 0.5))
    flipped_right = make_hand(index=(0.8, 0.8), thumb=(0.8, 0.2), center=(0.75, 0.5))
    frame = np.full((300, 400, 3), 180, dtype=np.uint8)
    pipeline = Pipeline(FakeTracker([left, flipped_right]), AsciiRenderer(find_font()),
                        Settings(mirror=False, show_tips=False, smoothing=0, charset="█ ", background="#ff0000"))
    result = pipeline.process(frame, 0)
    assert result.hands == 2
    assert result.twisted is True
    assert result.region is not None
    # Both lobes of the hourglass are rendered, the pinch point region between them is not.
    assert tuple(result.frame[150, 120]) == (0, 0, 255)
    assert tuple(result.frame[150, 280]) == (0, 0, 255)
    assert tuple(result.frame[60, 200]) == (180, 180, 180)


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
        # The rendered frame differs from the mirrored input inside the quad's box.
        mirrored = cv2.flip(photo, 1)
        q = np.round(result.quad).astype(int)
        y0, y1 = q[:, 1].min(), q[:, 1].max()
        x0, x1 = q[:, 0].min(), q[:, 0].max()
        assert np.any(result.frame[y0:y1, x0:x1] != mirrored[y0:y1, x0:x1])

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


def test_one_hand_hint():
    one = make_hand(index=(0.2, 0.2), thumb=(0.2, 0.8), center=(0.25, 0.5))
    pipeline = Pipeline(FakeTracker([one]), AsciiRenderer(find_font()), Settings(show_tips=False))
    result = pipeline.process(np.zeros((120, 160, 3), np.uint8), 0)
    assert result.region is None and result.hint == HINT_ONE_HAND


def test_pipeline_without_tracker_shows_plain_video():
    frame = np.full((120, 160, 3), 90, dtype=np.uint8)
    pipeline = Pipeline(None, AsciiRenderer(find_font()), Settings(mirror=False, show_tips=False))
    result = pipeline.process(frame, 0)
    assert result.region is None
    assert np.array_equal(result.frame, frame)
