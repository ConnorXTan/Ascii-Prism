import cv2
import numpy as np

from ascii_prism.warp import paste_quad, sample_quad

QUAD = np.array([[20, 20], [80, 20], [80, 60], [20, 60]], dtype=np.float64)  # 60 x 40, axis aligned


def test_sample_of_flat_colour_returns_that_colour():
    frame = np.full((90, 120, 3), (10, 200, 30), dtype=np.uint8)
    out = sample_quad(frame, [[10, 10], [100, 20], [95, 80], [12, 75]], 32, 24)
    assert out.shape == (24, 32, 3)
    assert (out == (10, 200, 30)).all()


def test_paste_lands_inside_the_quad_and_nowhere_else():
    frame = np.zeros((90, 120, 3), dtype=np.uint8)
    valid = paste_quad(frame, QUAD, np.full((10, 10, 3), 255, dtype=np.uint8))
    assert valid is not None and valid.any()
    assert (frame[22:58, 22:78] == 255).all()
    assert frame[:18].max() == 0 and frame[62:].max() == 0
    assert frame[:, :18].max() == 0 and frame[:, 82:].max() == 0


def test_round_trip_on_axis_aligned_quad_is_within_a_pixel():
    xs = np.linspace(0, 255, 120, dtype=np.float32)
    ys = np.linspace(0, 255, 90, dtype=np.float32)
    frame = np.stack([np.tile(xs, (90, 1)), np.tile(ys[:, None], (1, 120)), np.full((90, 120), 90, np.float32)], -1)
    frame = frame.astype(np.uint8)
    flat = sample_quad(frame, QUAD, 60, 40)
    out = frame.copy()
    paste_quad(out, QUAD, flat)
    inner = (slice(22, 58), slice(22, 78))
    diff = np.abs(out[inner].astype(int) - frame[inner].astype(int))
    # the gradient changes by about 2 to 3 levels per pixel, so a shift of
    # under one pixel is under 3 levels
    assert diff.max() <= 3


def test_opacity_blends_with_the_frame():
    frame = np.zeros((90, 120, 3), dtype=np.uint8)
    paste_quad(frame, QUAD, np.full((10, 10, 3), 200, dtype=np.uint8), opacity=0.5)
    assert abs(int(frame[40, 50, 0]) - 100) <= 1


def test_smaller_source_samples_the_same_region():
    frame = np.zeros((90, 120, 3), dtype=np.uint8)
    frame[30:50, 40:60] = (0, 0, 255)  # a red patch inside the quad
    small = cv2.resize(frame, (60, 45), interpolation=cv2.INTER_AREA)
    full = sample_quad(frame, QUAD, 30, 20)
    scaled = sample_quad(small, QUAD, 30, 20, frame_shape=frame.shape)
    assert full.shape == scaled.shape
    assert abs(full[..., 2].mean() - scaled[..., 2].mean()) < 6
    assert scaled[10, 15, 2] > 200 and scaled[1, 1, 2] == 0


def test_quad_entirely_off_frame_is_a_no_op():
    frame = np.zeros((90, 120, 3), dtype=np.uint8)
    off = QUAD + [500, 500]
    assert paste_quad(frame, off, np.full((4, 4, 3), 255, dtype=np.uint8)) is None
    assert frame.max() == 0
