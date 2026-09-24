import numpy as np

from ascii_prism.geometry import QuadFilter

SQUARE = np.array([(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)])


def test_zero_smoothing_passes_through():
    f = QuadFilter()
    for i in range(5):
        out = f(SQUARE + i * 0.01, i * 33, 0.0)
        np.testing.assert_allclose(out, SQUARE + i * 0.01)


def test_still_hands_lose_their_jitter():
    rng = np.random.default_rng(1)
    f = QuadFilter()
    outputs = []
    for i in range(120):
        noisy = SQUARE + rng.normal(0, 0.004, SQUARE.shape)
        outputs.append(f(noisy, i * 33, 0.6))
    settled = np.array(outputs[60:])
    assert settled.std(axis=0).max() < 0.004 * 0.5  # about half the input jitter or better
    np.testing.assert_allclose(settled.mean(axis=0), SQUARE, atol=0.003)


def test_fast_moves_follow_with_little_lag():
    f = QuadFilter()
    speed = 0.5  # frame widths per second, a brisk sweep
    out = None
    for i in range(45):
        t = i * 33
        out = f(SQUARE + [speed * t / 1000, 0], t, 0.6)
    target = SQUARE + [speed * 44 * 33 / 1000, 0]
    lag = np.abs(out - target)[:, 0].max()
    assert lag < speed * 0.06  # trails by less than 60 ms of motion


def test_reset_forgets_the_old_window():
    f = QuadFilter()
    f(SQUARE, 0, 0.6)
    f.reset()
    far = SQUARE + 0.3
    np.testing.assert_allclose(f(far, 33, 0.6), far)
