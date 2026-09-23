import numpy as np
import pytest

from ascii_prism.ascii import AsciiRenderer, GlyphAtlas, find_font
from ascii_prism.charsets import CHARSETS
from ascii_prism.settings import Settings

FONT = find_font()


def test_font_found():
    assert FONT is not None, "no monospace TrueType font found on this machine"


@pytest.mark.parametrize("glyph_h", [6, 9, 14, 24, 32, 48])
def test_block_glyph_fills_its_cell(glyph_h):
    atlas = GlyphAtlas(FONT, [" ", "\u2588"], glyph_h)
    space, block = atlas.coverage
    assert space.max() == 0
    assert block.min() > 0.9, f"block has gaps at glyph height {glyph_h}"
    # Edge rows and columns are covered too, so there are no seams between cells.
    for edge in (block[0], block[-1], block[:, 0], block[:, -1]):
        assert edge.min() > 0.9


def test_every_preset_builds_an_atlas():
    for cs in CHARSETS:
        atlas = GlyphAtlas(FONT, list(cs.chars), 24)
        assert atlas.coverage.shape[0] == len(cs.chars)
        # The brightest character must be denser than the darkest one.
        assert atlas.coverage[-1].mean() > atlas.coverage[0].mean()


def test_render_replaces_quad_interior_only():
    renderer = AsciiRenderer(FONT)
    frame = np.full((360, 640, 3), 200, dtype=np.uint8)  # bright grey everywhere
    original = frame.copy()
    quad = np.array([(150, 80), (480, 90), (500, 300), (130, 280)], dtype=np.float64)
    settings = Settings(columns=40, charset="█ ", background="#ff0000")
    region = renderer.render(frame, quad, settings)
    assert region is not None and region.cols == 40 and region.rows > 1
    # Bright input picks the space glyph, which shows the pure red backdrop (BGR 0,0,255).
    assert tuple(frame[190, 320]) == (0, 0, 255)
    # Outside the quad nothing changed.
    assert np.array_equal(frame[10, 10], original[10, 10])
    assert np.array_equal(frame[350, 630], original[350, 630])


def test_dark_input_uses_darkest_glyph():
    renderer = AsciiRenderer(FONT)
    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    quad = np.array([(100, 60), (540, 60), (540, 300), (100, 300)], dtype=np.float64)
    renderer.render(frame, quad, Settings(columns=40, charset=" @", background="#102030"))
    assert tuple(frame[180, 320]) == (0x30, 0x20, 0x10)  # background, since ' ' has no coverage


def test_tiny_quad_is_rejected():
    renderer = AsciiRenderer(FONT)
    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    assert renderer.render(frame, [(0, 0), (5, 0), (5, 5), (0, 5)], Settings()) is None


def test_twisted_quad_renders_as_a_ribbon():
    renderer = AsciiRenderer(FONT)
    frame = np.full((360, 640, 3), 200, dtype=np.uint8)
    # Right-hand corners swapped vertically: edges cross in the middle.
    quad = np.array([(100, 60), (540, 300), (540, 60), (100, 300)], dtype=np.float64)
    settings = Settings(columns=40, charset="\u2588 ", background="#0000ff")
    assert renderer.render(frame, quad, settings) is not None
    assert tuple(frame[180, 150]) == (255, 0, 0)  # left lobe
    assert tuple(frame[180, 490]) == (255, 0, 0)  # right lobe
    assert tuple(frame[70, 320]) == (200, 200, 200)  # above the pinch, untouched
