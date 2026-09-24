import numpy as np
import pytest

from ascii_prism import lenses
from ascii_prism.ascii import AsciiRenderer, find_font
from ascii_prism.hands import Hand
from ascii_prism.lenses.ascii import AsciiLens
from ascii_prism.lenses.thermal import ThermalLens
from ascii_prism.pipeline import Pipeline
from ascii_prism.settings import Settings

QUAD = np.array([[40, 30], [280, 40], [270, 200], [30, 190]], dtype=np.float64)


@pytest.fixture(scope="module")
def renderer():
    return AsciiRenderer(find_font())


def context(renderer, frame=None, history=None):
    frame = np.full((240, 320, 3), 120, dtype=np.uint8) if frame is None else frame
    return lenses.LensContext(frame, 0, 1 / 30, renderer, history or (lambda _s: None))


def test_registry_is_consistent():
    assert lenses.LENSES[0] is AsciiLens
    assert lenses.DEFAULT_LENS_ID == "ascii"
    ids = lenses.lens_ids()
    assert len(ids) == len(set(ids))
    for cls in lenses.LENSES:
        assert cls.id and cls.label and cls.blurb
        assert lenses.by_id(cls.id) is cls
    assert lenses.by_id("no-such-lens") is None


def test_ascii_lens_matches_the_renderer_shortcut(renderer):
    frame = np.random.default_rng(0).integers(0, 256, (240, 320, 3), dtype=np.uint8)
    settings = Settings(columns=40, hue=60, opacity=0.8, background="#203040")
    via_renderer = frame.copy()
    region = renderer.render(via_renderer, QUAD, settings)
    via_lens = frame.copy()
    drawn, lens_region = lenses.render_lens(AsciiLens(), via_lens, QUAD, settings, context(renderer, via_lens))
    assert drawn and region == lens_region
    assert np.array_equal(via_renderer, via_lens)


def test_too_small_quad_draws_nothing(renderer):
    frame = np.full((240, 320, 3), 120, dtype=np.uint8)
    drawn, region = lenses.render_lens(AsciiLens(), frame, [(0, 0), (5, 0), (5, 5), (0, 5)], Settings(), context(renderer, frame))
    assert not drawn and region is None
    assert (frame == 120).all()


class FakeTracker:
    def __init__(self, hands):
        self.hands = hands

    def detect(self, frame_rgb, timestamp_ms, mirrored=True):
        return self.hands


def make_hand(index, thumb, handedness="Right"):
    centre = ((index[0] + thumb[0]) / 2, (index[1] + thumb[1]) / 2)
    return Hand(thumb=thumb, index=index, wrist=centre, center=centre, handedness=handedness, facing="palm")


TWO_HANDS = [make_hand((0.2, 0.2), (0.2, 0.8), "Left"), make_hand((0.8, 0.2), (0.8, 0.8))]


class CountingLens(ThermalLens):
    id = "counting"
    resets = 0

    def reset(self):
        CountingLens.resets += 1


def test_thermal_lens_paints_pixels_without_a_grid(renderer):
    frame = np.full((240, 320, 3), 200, dtype=np.uint8)
    drawn, region = lenses.render_lens(ThermalLens(), frame, QUAD, Settings(), context(renderer, frame))
    assert drawn and region is None
    assert not (frame[100, 150] == 200).all()  # inside the quad is false colour now
    assert (frame[5, 5] == 200).all()


def test_pipeline_switches_lens_and_resets_the_old_one(renderer, monkeypatch):
    monkeypatch.setattr(lenses, "LENSES", lenses.LENSES + [CountingLens])
    settings = Settings(mirror=False, show_tips=False, smoothing=0, lens="counting")
    pipeline = Pipeline(FakeTracker(TWO_HANDS), renderer, settings)
    frame = np.full((240, 320, 3), 150, dtype=np.uint8)
    CountingLens.resets = 0
    first = pipeline.process(frame, 0)
    assert first.lens == "counting" and first.region is None and first.hint == ""
    assert isinstance(pipeline.lens, CountingLens)

    settings.lens = "ascii"
    second = pipeline.process(frame, 33)
    assert second.lens == "ascii" and second.region is not None
    assert CountingLens.resets == 1  # the outgoing lens was reset once
    assert not np.array_equal(first.frame, second.frame)

    settings.lens = "no-such-lens"
    settings.clamp()
    assert settings.lens == "ascii"
    assert pipeline.process(frame, 66).lens == "ascii"


def test_locked_window_survives_a_lens_switch(renderer):
    settings = Settings(mirror=False, show_tips=False, smoothing=0)
    pipeline = Pipeline(FakeTracker(TWO_HANDS), renderer, settings)
    frame = np.full((240, 320, 3), 150, dtype=np.uint8)
    pipeline.process(frame, 0)
    assert pipeline.toggle_lock() is True
    pipeline.tracker = FakeTracker([])
    settings.lens = "thermal"
    result = pipeline.process(frame, 33)
    assert result.locked and result.hands == 0 and result.lens == "thermal"
    assert result.quad is not None and not (result.frame[120, 160] == 150).all()


def test_mirror_change_resets_the_lens(renderer, monkeypatch):
    monkeypatch.setattr(lenses, "LENSES", lenses.LENSES + [CountingLens])
    pipeline = Pipeline(FakeTracker(TWO_HANDS), renderer, Settings(show_tips=False, lens="counting"))
    pipeline.process(np.zeros((240, 320, 3), np.uint8), 0)
    CountingLens.resets = 0
    pipeline.reset_tracking()
    assert CountingLens.resets == 1


def test_echo_shows_the_past_and_only_keeps_history_when_needed(renderer):
    settings = Settings(mirror=False, show_tips=False, smoothing=0, lens="echo", delay=0.5)
    pipeline = Pipeline(FakeTracker(TWO_HANDS), renderer, settings)
    red = np.zeros((240, 320, 3), np.uint8)
    red[:] = (0, 0, 255)
    blue = np.zeros_like(red)
    blue[:] = (255, 0, 0)
    first = pipeline.process(red, 0)
    assert pipeline.history_size() == 1
    assert tuple(first.frame[120, 160]) == (0, 0, 255)  # nothing older yet: shows live
    for t in range(1, 16):
        result = pipeline.process(blue, t * 100)
    assert tuple(result.frame[120, 160]) == (255, 0, 0)  # 1.5 s of blue: the past is blue too
    assert pipeline.history_size() <= 11  # delay 0.5 s plus the margin, at 10 fps
    result = pipeline.process(red, 1600)
    assert tuple(result.frame[120, 160]) == (255, 0, 0)  # 0.5 s ago it was still blue
    assert tuple(result.frame[5, 5]) == (0, 0, 255)  # outside the window is live

    settings.lens = "ascii"
    pipeline.process(red, 1700)
    assert pipeline.history_size() == 0  # ascii does not need the buffer


def test_history_frames_are_stored_small(renderer):
    settings = Settings(mirror=False, show_tips=False, smoothing=0, lens="echo")
    pipeline = Pipeline(FakeTracker(TWO_HANDS), renderer, settings)
    pipeline.process(np.zeros((720, 1280, 3), np.uint8), 0)
    assert pipeline._history[0][1].shape == (360, 640, 3)
