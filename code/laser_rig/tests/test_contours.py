# Runs outside TouchDesigner: python tests/test_contours.py
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import contours as ct


def square(size=128, a=32, b=96):
    m = np.zeros((size, size), np.uint8)
    m[a:b, a:b] = 1
    return m


def test_finds_a_shape_in_the_right_place():
    loops, lengths = ct.extract(square(), 1.0)
    assert len(loops) == 1
    x, y = loops[0][:, 0], loops[0][:, 1]
    assert abs(x.min() + 0.5) < 0.03 and abs(x.max() - 0.5) < 0.03
    assert abs(y.min() + 0.5) < 0.03 and abs(y.max() - 0.5) < 0.03
    assert 3.8 < lengths[0] < 4.2


def test_row_zero_is_the_bottom():
    m = np.zeros((64, 64), np.uint8)
    m[2:12, 20:44] = 1
    assert ct.extract(m, 1.0)[0][0][:, 1].mean() < -0.5


def test_specks_are_dropped():
    m = square()
    m[5:7, 5:7] = 1
    assert len(ct.extract(m, 1.0)[0]) == 1


def test_a_hole_gives_a_second_loop():
    m = square()
    m[56:72, 56:72] = 0
    assert len(ct.extract(m, 1.0)[0]) == 2


def test_more_detail_means_more_points():
    yy, xx = np.mgrid[0:128, 0:128]
    m = (((xx - 64) ** 2 + (yy - 64) ** 2) < 40 ** 2).astype(np.uint8)
    fine, coarse = ct.extract(m, 0.5)[0][0], ct.extract(m, 3.0)[0][0]
    assert len(fine) > len(coarse) >= 3


def test_empty_image():
    assert ct.extract(np.zeros((32, 32), np.uint8), 1.0) == ([], [])


def test_length_does_not_depend_on_resolution():
    assert abs(ct.extract(square(128, 32, 96), 1.0)[1][0] - ct.extract(square(256, 64, 192), 1.0)[1][0]) < 0.1


def test_budget_and_centre():
    assert abs(ct.budget(800) - 32) < 1e-9
    assert ct.centre(np.array([[0, 0], [1, 1]], np.float32)) == (0.5, 0.5)


def speed():
    rng = np.random.default_rng(1)
    noise = rng.random((256, 256)).astype(np.float32)
    import cv2
    m = (cv2.GaussianBlur(noise, (0, 0), 6) > 0.5).astype(np.uint8)
    a = time.perf_counter()
    for _ in range(100):
        ct.extract(m, 1.0)
    return (time.perf_counter() - a) / 100 * 1000


for name, t in sorted(globals().copy().items()):
    if name.startswith('test_'):
        t()
        print('ok', name)
print('extract 256 x 256: {:.2f} ms'.format(speed()))
