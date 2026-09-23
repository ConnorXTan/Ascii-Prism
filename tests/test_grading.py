import numpy as np

from ascii_prism.ascii import AsciiRenderer, find_font
from ascii_prism.grading import blend, grade
from ascii_prism.settings import Settings

RED = np.array([[[0.0, 0.0, 1.0]]], dtype=np.float32)  # BGR
GREY = np.array([[[0.5, 0.5, 0.5]]], dtype=np.float32)


def test_defaults_leave_colours_alone():
    cells = np.random.default_rng(0).random((4, 5, 3)).astype(np.float32)
    np.testing.assert_array_equal(grade(cells, Settings()), cells)


def test_hue_rotation_turns_red_into_green_and_back():
    green = grade(RED, Settings(hue=120))
    np.testing.assert_allclose(green[0, 0], [0.0, 1.0, 0.0], atol=1e-5)
    blue = grade(RED, Settings(hue=-120))
    np.testing.assert_allclose(blue[0, 0], [1.0, 0.0, 0.0], atol=1e-5)
    # Grey has no hue, so it does not move.
    np.testing.assert_allclose(grade(GREY, Settings(hue=90)), GREY, atol=1e-6)


def test_saturation_zero_is_luminance_grey():
    grey = grade(RED, Settings(saturation=0.0))
    assert grey[0, 0, 0] == grey[0, 0, 1] == grey[0, 0, 2]
    assert abs(grey[0, 0, 0] - 0.2126) < 1e-4
    vivid = grade(np.array([[[0.3, 0.3, 0.6]]], dtype=np.float32), Settings(saturation=2.0))
    assert vivid[0, 0, 2] > 0.6 and vivid[0, 0, 0] < 0.3  # pushed away from grey


def test_brightness_is_a_clipped_gain():
    np.testing.assert_allclose(grade(GREY, Settings(brightness=1.5))[0, 0], [0.75] * 3)
    np.testing.assert_allclose(grade(GREY, Settings(brightness=2.0))[0, 0], [1.0] * 3)


def test_blend_mixes_rendered_over_video():
    video = np.full((2, 2, 3), 200, dtype=np.uint8)
    rendered = np.zeros((2, 2, 3), dtype=np.uint8)
    assert blend(video, rendered, 1.0) is rendered
    assert tuple(blend(video, rendered, 0.5)[0, 0]) == (100, 100, 100)
    assert tuple(blend(video, rendered, 0.0)[0, 0]) == (200, 200, 200)


def test_opacity_lets_the_video_show_through_the_window():
    renderer = AsciiRenderer(find_font())
    frame = np.full((360, 640, 3), 200, dtype=np.uint8)
    quad = np.array([(100, 60), (540, 60), (540, 300), (100, 300)], dtype=np.float64)
    # Bright input picks the space glyph, so the window is the black backdrop at 50%.
    assert renderer.render(frame, quad, Settings(columns=40, charset="█ ", opacity=0.5)) is not None
    assert tuple(frame[180, 320]) == (100, 100, 100)
    assert tuple(frame[10, 10]) == (200, 200, 200)
