import numpy as np
import pytest

from ascii_prism import lenses
from ascii_prism.ascii import AsciiRenderer, find_font
from ascii_prism.lenses.ascii import AsciiLens
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
