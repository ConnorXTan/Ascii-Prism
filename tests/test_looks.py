import cv2
import numpy as np
import pytest

from ascii_prism.ascii import AsciiRenderer, find_font
from ascii_prism.lenses import looks
from ascii_prism.warp import sample_quad

QUAD = np.array([[40, 30], [280, 40], [270, 200], [30, 190]], dtype=np.float64)


@pytest.fixture(scope="module")
def renderer():
    return AsciiRenderer(find_font())


@pytest.fixture(scope="module")
def grid(renderer):
    g = looks.grid_for(renderer, QUAD, 40, 320, 240)
    assert g is not None
    return g


def flat(colour, w=240, h=160):
    return np.full((h, w, 3), colour, dtype=np.uint8)


def test_grid_matches_the_renderer(renderer, grid):
    assert (grid.cols, grid.rows) == renderer.grid_for(QUAD, 40, 320, 240)
    assert renderer.min_glyph_h <= grid.glyph_h <= renderer.max_glyph_h
    assert grid.sample_size == (grid.cols * looks.SUPERSAMPLE, grid.rows * looks.SUPERSAMPLE)


def test_ascii_look_shape_and_background(renderer, grid):
    out = looks.ascii_look(flat((0, 0, 0), *grid.sample_size), grid, renderer, background=(7, 8, 9))
    assert out.shape == (grid.rows * grid.glyph_h, grid.cols * grid.glyph_w, 3)
    assert (out == (7, 8, 9)).all()  # black cells pick the space glyph
    bright = looks.ascii_look(flat((255, 255, 255), *grid.sample_size), grid, renderer)
    assert bright.mean() > 60


def test_ascii_glyphs_accepts_custom_ink(renderer, grid):
    cells = np.full((grid.rows, grid.cols, 3), 0.9, dtype=np.float32)
    ink = np.zeros_like(cells)
    ink[..., 2] = 1.0  # pure red
    out = looks.ascii_glyphs(cells, grid, renderer, ink=ink)
    assert out[..., 2].max() > 128 and out[..., 0].max() == 0 and out[..., 1].max() == 0


def test_thermal_black_maps_to_the_colormap_floor():
    out = looks.thermal(flat((0, 0, 0)))
    floor = cv2.applyColorMap(np.zeros((1, 1), np.uint8), cv2.COLORMAP_INFERNO)[0, 0]
    assert (out == floor).all()
    skin = looks.thermal(flat((120, 150, 230)))
    shirt = looks.thermal(flat((235, 235, 235)))
    assert looks.luminance(skin).mean() > looks.luminance(shirt).mean() * 0.9


def test_gameboy_uses_at_most_four_palette_tones():
    rng = np.random.default_rng(1)
    noise = rng.integers(0, 256, (160, 240, 3), dtype=np.uint8)
    out = looks.gameboy(cv2.GaussianBlur(noise, (0, 0), 4))
    tones = np.unique(out.reshape(-1, 3), axis=0)
    assert 2 <= len(tones) <= 4
    assert all(any((t == p).all() for p in looks.GB_PALETTE) for t in tones)


def test_sketch_of_a_flat_frame_is_paper():
    out = looks.sketch(flat((128, 128, 128)))
    paper = looks.to_u8(looks.SKETCH_PAPER)
    assert np.abs(out.astype(int) - paper.astype(int)).max() <= 2


def test_night_keeps_black_dark_and_lifts_grey():
    rng = np.random.default_rng(2)
    dark = looks.night(flat((0, 0, 0)), rng)
    lit = looks.night(flat((90, 90, 90)), rng)
    assert dark.mean() < 20
    assert lit[..., 1].mean() > lit[..., 0].mean() and lit[..., 1].mean() > lit[..., 2].mean()


def test_mirror_is_four_way_symmetric():
    rng = np.random.default_rng(3)
    src = rng.integers(0, 256, (64, 96, 3), dtype=np.uint8)
    out = looks.mirror_remap(src)
    assert (out == out[:, ::-1]).all() and (out == out[::-1]).all()
    assert (out[:32, :48] == src[:32, :48]).all()


def test_kaleido_keeps_shape_and_is_rotationally_repeated():
    rng = np.random.default_rng(4)
    src = cv2.GaussianBlur(rng.integers(0, 256, (120, 120, 3), dtype=np.uint8), (0, 0), 3)
    out = looks.kaleido_remap(src, folds=4)
    assert out.shape == src.shape
    rotated = cv2.rotate(out, cv2.ROTATE_90_CLOCKWISE)
    assert np.abs(out[20:100, 20:100].astype(int) - rotated[20:100, 20:100].astype(int)).mean() < 12


def test_rain_moves_and_follows_the_light(renderer, grid):
    chars, font = looks.RAIN_LATIN, renderer.font_path
    atlas = looks.FixedCellAtlas(font, list(chars), grid.glyph_h, grid.glyph_w)
    assert atlas.coverage.shape == (len(chars), grid.glyph_h, grid.glyph_w)
    assert atlas.coverage.max() > 0.5
    rain = looks.Rain(grid, chars, atlas.coverage, np.random.default_rng(5))
    for _ in range(30):
        rain.step(1 / 30)
    white = flat((255, 255, 255), *grid.sample_size)
    first = rain.paint(white)
    rain.step(1 / 30)
    second = rain.paint(white)
    assert first.shape == (grid.rows * grid.glyph_h, grid.cols * grid.glyph_w, 3)
    assert not np.array_equal(first, second)
    assert second[..., 1].max() > 150  # anti-aliased glyphs rarely hit full coverage
    dark = rain.paint(flat((0, 0, 0), *grid.sample_size), lift=0.0)
    assert dark.max() == 0
    faint = rain.paint(flat((0, 0, 0), *grid.sample_size))
    assert 0 < faint[..., 1].max() < 100


def test_rain_glyphs_fall_back_to_latin(monkeypatch):
    monkeypatch.setattr(looks, "find_rain_font", lambda: None)
    chars, font = looks.rain_glyphs("/some/mono.ttf")
    assert chars == looks.RAIN_LATIN and font == "/some/mono.ttf"
    monkeypatch.setattr(looks, "find_rain_font", lambda: "/cjk.ttc")
    chars, font = looks.rain_glyphs("/some/mono.ttf")
    assert chars == looks.HALFWIDTH_KATAKANA and font == "/cjk.ttc"


def test_person_look_extremes(renderer, grid):
    sampled = flat((200, 120, 60), *grid.sample_size)
    glyphs = looks.ascii_look(sampled, grid, renderer)
    all_person = looks.person_look(sampled, np.ones(sampled.shape[:2], np.float32), grid, renderer)
    assert np.array_equal(all_person, glyphs)
    none = looks.person_look(sampled, np.zeros(sampled.shape[:2], np.float32), grid, renderer)
    assert (none == (200, 120, 60)).all()
    inverted = looks.person_look(sampled, np.zeros(sampled.shape[:2], np.float32), grid, renderer, invert_bg=True)
    assert (inverted == (55, 135, 195)).all()


@pytest.fixture(scope="module")
def segmenter_model():
    try:
        return looks.ensure_segmenter(log=lambda *_: None)
    except OSError:
        pytest.skip("segmentation model unavailable (offline?)")


def test_segmenter_finds_the_person(hands_photo, segmenter_model):
    photo = cv2.imread(str(hands_photo))
    mask = looks.PersonMask(segmenter_model)(photo)
    assert mask.shape == photo.shape[:2] and mask.dtype == np.float32
    assert 0.2 < mask.mean() < 0.8
    assert mask[480:560, 260:340].mean() > 0.9  # her face
    assert mask[:80, :80].mean() < 0.1  # the wall
    quad = np.array([[150, 370], [590, 400], [575, 700], [140, 670]], dtype=np.float64)
    mask_flat = sample_quad(mask, quad, 90, 60)
    assert mask_flat.shape == (60, 90) and mask_flat.max() > 0.9
