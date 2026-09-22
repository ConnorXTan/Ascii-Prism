import numpy as np

from ascii_prism.geometry import bilinear_map, inverse_bilinear, is_twisted, quad_size, smooth_quad

CONVEX = np.array([(100, 80), (620, 120), (700, 560), (60, 480)], dtype=np.float64)
# Right hand flipped: its thumb (bottom-right corner) is above its index (top-right).
TWISTED = np.array([(100, 100), (600, 500), (600, 100), (100, 500)], dtype=np.float64)


def test_quad_size_averages_opposite_edges():
    w, h = quad_size([(0, 0), (10, 0), (10, 6), (0, 4)])
    assert abs(w - (10 + np.hypot(10, 2)) / 2) < 1e-9
    assert h == 5


def test_smooth_quad():
    prev = np.zeros((4, 2))
    new = np.full((4, 2), 10.0)
    np.testing.assert_allclose(smooth_quad(prev, new, 0.5), np.full((4, 2), 5.0))
    np.testing.assert_allclose(smooth_quad(None, new, 0.9), new)


def test_is_twisted():
    assert not is_twisted(CONVEX)
    assert is_twisted(TWISTED)
    # Left/right crossing (hands crossed over) also counts.
    assert is_twisted([(600, 100), (100, 100), (600, 500), (100, 500)])


def test_bilinear_map_hits_corners():
    x, y = bilinear_map(CONVEX, [0, 1, 1, 0], [0, 0, 1, 1])
    np.testing.assert_allclose(np.stack([x, y], axis=1), CONVEX)


def test_inverse_bilinear_round_trips_inside_a_convex_quad():
    u = np.linspace(0.02, 0.98, 25)[None, :]
    v = np.linspace(0.02, 0.98, 17)[:, None]
    x, y = bilinear_map(CONVEX, u, v)
    u2, v2, valid = inverse_bilinear(CONVEX, x, y)
    assert valid.all()
    np.testing.assert_allclose(u2, np.broadcast_to(u, u2.shape), atol=1e-9)
    np.testing.assert_allclose(v2, np.broadcast_to(v, v2.shape), atol=1e-9)


def test_inverse_bilinear_rejects_points_outside():
    _, _, valid = inverse_bilinear(CONVEX, [10, 700, 350], [10, 80, 300])
    assert list(valid) == [False, False, True]


def test_inverse_bilinear_handles_parallelogram():
    quad = [(0, 0), (200, 0), (300, 100), (100, 100)]
    x, y = bilinear_map(quad, 0.25, 0.5)
    u, v, valid = inverse_bilinear(quad, x, y)
    assert valid and abs(u - 0.25) < 1e-9 and abs(v - 0.5) < 1e-9


def test_inverse_bilinear_covers_both_lobes_of_a_twisted_quad():
    # Points in each lobe map back onto the surface; points above the pinch
    # and outside the quad's box do not.
    xs = np.array([200.0, 500.0, 350.0, 450.0, 50.0])
    ys = np.array([300.0, 300.0, 120.0, 300.0, 300.0])
    u, v, valid = inverse_bilinear(TWISTED, xs, ys)
    assert list(valid) == [True, True, False, True, False]
    fx, fy = bilinear_map(TWISTED, u[valid], v[valid])
    np.testing.assert_allclose(fx, xs[valid], atol=1e-6)
    np.testing.assert_allclose(fy, ys[valid], atol=1e-6)
