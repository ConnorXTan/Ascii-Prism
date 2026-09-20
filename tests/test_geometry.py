import numpy as np

from ascii_prism.geometry import (
    apply_homography,
    is_convex,
    order_quad,
    quad_size,
    quad_to_rect,
    rect_to_quad,
    smooth_quad,
)


def test_order_quad_is_tl_tr_br_bl_for_any_input_order():
    tl, tr, br, bl = (10, 10), (90, 12), (95, 80), (8, 85)
    for order in [(tl, tr, br, bl), (br, tl, bl, tr), (bl, br, tr, tl), (tr, bl, tl, br)]:
        np.testing.assert_allclose(order_quad(order), [tl, tr, br, bl])


def test_is_convex():
    assert is_convex([(0, 0), (1, 0), (1, 1), (0, 1)])
    assert not is_convex([(0, 0), (1, 0), (0.4, 0.4), (0, 1)])  # one corner pushed inside
    assert not is_convex([(0, 0), (1, 0), (2, 0), (0, 1)])  # collinear


def test_quad_size_averages_opposite_edges():
    w, h = quad_size([(0, 0), (10, 0), (10, 6), (0, 4)])
    assert abs(w - (10 + np.hypot(10, 2)) / 2) < 1e-9
    assert h == 5


def test_rect_to_quad_maps_corners_and_inverts():
    quad = np.array([(100, 80), (620, 120), (700, 560), (60, 480)], dtype=np.float64)
    h = rect_to_quad(1, 1, quad)
    np.testing.assert_allclose(apply_homography(h, [(0, 0), (1, 0), (1, 1), (0, 1)]), quad, atol=1e-6)
    back = quad_to_rect(quad, 1, 1)
    inner = apply_homography(h, [(0.3, 0.7)])
    np.testing.assert_allclose(apply_homography(back, inner), [(0.3, 0.7)], atol=1e-9)


def test_smooth_quad():
    prev = np.zeros((4, 2))
    new = np.full((4, 2), 10.0)
    np.testing.assert_allclose(smooth_quad(prev, new, 0.5), np.full((4, 2), 5.0))
    np.testing.assert_allclose(smooth_quad(None, new, 0.9), new)
