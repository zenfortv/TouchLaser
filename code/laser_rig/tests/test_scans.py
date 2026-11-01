# Runs outside TouchDesigner: python tests/test_scans.py
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import scans as sc

FULL = np.ones((64, 64), np.uint8)
ROWS = 8


def lines(pts):
    return pts.reshape(-1, 2, 2)


def test_head_snakes_down_the_rows():
    assert sc.head(0.0, ROWS)[:2] == (0, -1)
    row, x, y = sc.head(1.5 / ROWS, ROWS)
    assert row == 1 and abs(x) < 1e-9 and abs(y - 0.625) < 1e-9
    assert sc.head(1.01 / ROWS, ROWS)[1] > 0.9              # row 1 starts on the right
    assert sc.head(1.999, ROWS)[0] == ROWS - 1


def test_engrave_starts_with_nothing_burnt():
    pts, ids = sc.engrave(FULL, 0.0, ROWS, 100)
    assert len(pts) == 0 and len(ids) == 0


def test_engrave_burns_finished_rows_and_part_of_the_current():
    pts, ids = sc.engrave(FULL, 2.5 / ROWS, ROWS, 100)
    a = lines(pts)
    assert len(a) == 3 and ids.tolist() == [0, 0, 1, 1, 2, 2]
    assert np.allclose(a[0], [(-1, 0.875), (1, 0.875)])
    assert np.allclose(a[1], [(1, 0.625), (-1, 0.625)])     # back the other way
    assert np.allclose(a[2], [(-1, 0.375), (0, 0.375)])


def test_engrave_part_row_going_left_is_on_the_right():
    a = lines(sc.engrave(FULL, 1.5 / ROWS, ROWS, 100)[0])
    assert np.allclose(a[1], [(1, 0.625), (0, 0.625)])


def test_engrave_is_whole_at_the_end_then_clears_from_the_top():
    assert len(lines(sc.engrave(FULL, 0.9999, ROWS, 100)[0])) == ROWS
    a = lines(sc.engrave(FULL, 1 + 2.5 / ROWS, ROWS, 100)[0])
    assert np.allclose(a[0], [(0, 0.375), (1, 0.375)])
    assert len(a) == ROWS - 2


def test_engrave_follows_the_image():
    m = np.zeros((64, 64), np.uint8)
    m[:, 16:32] = 1
    m[:, 48:] = 1
    a = lines(sc.engrave(m, 0.9999, ROWS, 100)[0])
    assert len(a) == ROWS * 2
    assert np.allclose(a[0], [(-0.5, 0.875), (0, 0.875)])
    assert np.allclose(a[1], [(0.5, 0.875), (1, 0.875)])
    assert np.allclose(a[2], [(1, 0.625), (0.5, 0.625)])    # the snake takes the near one first


def test_engrave_reads_the_top_of_the_image_first():
    m = np.zeros((64, 64), np.uint8)
    m[32:] = 1                                              # row 0 is the bottom
    assert (lines(sc.engrave(m, 0.9999, ROWS, 100)[0])[:, :, 1] > 0).all()


def test_budget_drops_the_shortest_and_keeps_the_order():
    m = np.zeros((64, 64), np.uint8)
    m[:, :32] = 1
    m[:, 40:44] = 1
    pts, ids = sc.engrave(m, 0.9999, ROWS, ROWS * 1.01)
    a = lines(pts)
    assert len(a) == ROWS and np.abs(a[:, 1, 0] - a[:, 0, 0]).min() > 0.9
    assert ids.tolist() == sorted(ids.tolist())


def test_noise_is_not_burnt():
    m = np.zeros((256, 256), np.uint8)
    m[:, 8] = 1
    assert len(sc.engrave(m, 0.9999, ROWS, 100)[0]) == 0
    assert len(sc.engrave(np.zeros((64, 64), np.uint8), 0.5, ROWS, 100)[0]) == 0


def test_sweeps_match_the_shader():
    assert np.allclose(sc.beam('down', 0.0, ROWS)[0], [(-sc.EDGE, 1), (sc.EDGE, 1)])
    assert np.allclose(sc.beam('up', 0.0, ROWS)[0], [(-sc.EDGE, -1), (sc.EDGE, -1)])
    assert np.allclose(sc.beam('right', 1.25, ROWS)[0], [(-0.5, -sc.EDGE), (-0.5, sc.EDGE)])
    assert np.allclose(sc.beam('left', 0.25, ROWS)[0], [(0.5, -sc.EDGE), (0.5, sc.EDGE)])


def test_radar_runs_clockwise_from_twelve():
    assert np.allclose(sc.beam('radar', 0.0, ROWS)[0][1], (0, sc.EDGE))
    assert np.allclose(sc.beam('radar', 0.25, ROWS)[0][1], (sc.EDGE, 0))
    assert np.allclose(sc.beam('radar', 0.125, ROWS)[0][1], (sc.EDGE, sc.EDGE))


def test_iris_opens_and_stays_inside():
    small, closed = sc.beam('iris', 0.1, ROWS)
    assert closed and np.allclose(np.hypot(*small.T), 0.1 * 2 ** 0.5)
    assert np.abs(sc.beam('iris', 0.99, ROWS)[0]).max() <= sc.EDGE


def test_engrave_beam_is_the_head():
    (a, b), closed = sc.beam('engrave', 2.5 / ROWS, ROWS)
    assert not closed and abs((a[0] + b[0]) / 2) < 1e-9 and a[1] == 0.375


def test_no_beam_when_off():
    assert sc.beam('off', 0.3, ROWS) is None


def speed():
    m = (np.random.rand(256, 256) > 0.5).astype(np.uint8)
    a = time.perf_counter()
    for _ in range(200):
        sc.engrave(m, 0.9, 24, 32)
    return (time.perf_counter() - a) / 200 * 1000


for name, t in sorted(globals().copy().items()):
    if name.startswith('test_'):
        t()
        print('ok', name)
print('engrave worst case: {:.2f} ms'.format(speed()))
