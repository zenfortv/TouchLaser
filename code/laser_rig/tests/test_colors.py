# Runs outside TouchDesigner: python tests/test_colors.py
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import colors


def image():
    """Left half green, right half purple, bottom row red. Row 0 is the bottom."""
    img = np.zeros((16, 16, 4), np.float32)
    img[:, :8] = (0, 1, 0, 1)
    img[:, 8:] = (0.5, 0, 1, 1)
    img[0] = (1, 0, 0, 1)
    return img


def test_position_picks_the_right_pixel():
    c = colors.sample(image(), [-0.5, 0.5, 0.0], [0.5, 0.5, -1.0])
    assert c[0].tolist() == [0, 1, 0]
    assert np.allclose(c[1], [0.5, 0, 1])
    assert c[2].tolist() == [1, 0, 0]


def test_points_on_the_far_edge_stay_in_the_image():
    assert colors.sample(image(), [1.0, -1.0], [1.0, 1.0]).shape == (2, 3)


def test_boost_lifts_dim_colours_to_full():
    img = np.zeros((2, 2, 4), np.float32)
    img[..., :3] = (0.2, 0.1, 0.0)
    assert np.allclose(colors.sample(img, [0], [0], boost=1), [1, 0.5, 0])
    assert np.allclose(colors.sample(img, [0], [0], boost=0), [0.2, 0.1, 0])


def test_black_gives_white_not_a_dead_line():
    img = np.zeros((2, 2, 4), np.float32)
    assert colors.sample(img, [0], [0])[0].tolist() == [1, 1, 1]


def test_saturation_zero_is_grey_and_two_is_stronger():
    img = np.zeros((2, 2, 4), np.float32)
    img[..., :3] = (0.8, 0.4, 0.4)
    c = colors.sample(img, [0], [0], boost=0, saturation=0)[0]
    assert abs(c[0] - c[1]) < 1e-6 and abs(c[1] - c[2]) < 1e-6
    strong = colors.sample(img, [0], [0], boost=0, saturation=2)[0]
    assert strong[0] - strong[1] > 0.4


def test_white_stays_white():
    img = np.ones((2, 2, 4), np.float32)
    assert np.allclose(colors.sample(img, [0], [0]), [1, 1, 1])


def speed():
    img = np.random.rand(128, 128, 4).astype(np.float32)
    xs = np.random.uniform(-1, 1, 1000)
    a = time.perf_counter()
    for _ in range(200):
        colors.sample(img, xs, xs)
    return (time.perf_counter() - a) / 200 * 1000


for name, t in sorted(globals().copy().items()):
    if name.startswith('test_'):
        t()
        print('ok', name)
print('sample 1000 points {:.2f} ms'.format(speed()))
