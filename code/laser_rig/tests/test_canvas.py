# Runs outside TouchDesigner: python tests/test_canvas.py
import os
import random
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import canvas as cv
import test_warp_helpers as tw
import warp as wp

RED = (1, 0, 0)
SQUARE = [(-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)]


def test_shape_closes_and_repeats_colour():
    p, c, f, _ = cv.shape([(0, 0), (1, 0), (1, 1)], RED, closed=True, corners=[0, 0, 0])
    assert len(p) == 4 and (p[0] == p[-1]).all() and c.shape == (4, 3) and f.tolist() == [0] * 4


def test_flat_surface_keeps_the_shape():
    s = cv.shape([(-1, -1), (1, 1)], RED)
    p, _, _, _ = cv.warp(s, SQUARE, wp)
    assert np.allclose(p, [(-1, -1), (1, 1)])


def test_warp_moves_to_the_corners_and_tints():
    q = [(0, 0), (2, 0), (2, 2), (0, 2)]
    p, c, _, _ = cv.warp(cv.shape([(-1, -1), (1, 1), (0, 0)], (1, 1, 1)), q, wp, tint=(0.5, 0, 1))
    assert np.allclose(p, [(0, 0), (2, 2), (1, 1)]) and np.allclose(c[0], (0.5, 0, 1))


def test_clip_blanks_what_leaves_the_box():
    p, c, _, _ = cv.warp(cv.shape([(0, 0), (3, 0)], RED), SQUARE, wp, clip=True)
    assert np.allclose(p[1], (1, 0)) and c[1].tolist() == [0, 0, 0] and c[0].tolist() == [1, 0, 0]


def test_dented_surfaces_never_leave_the_frame_along_their_lines():
    rng = random.Random(4)
    done = 0
    while done < 400:
        q = [(rng.uniform(-2, 2), rng.uniform(-2, 2)) for _ in range(4)]
        if wp.dent(q) is None:
            continue
        done += 1
        ends = [(rng.uniform(-1, 1), rng.uniform(-1, 1)) for _ in range(4)]
        p, _, _, _ = cv.warp(cv.shape(ends, RED), q, wp)
        size = max(max(abs(a[0] - b[0]), abs(a[1] - b[1])) for a in q for b in q)
        for x in p:
            assert tw.inside(q, tuple(x), size * 0.002), (q, x)


def test_divide_keeps_ends_and_corners():
    s = cv.shape([(0, 0), (1, 0)], RED)
    p, c, f, _ = cv.divide(s, 0.3)
    assert len(p) == 5 and np.allclose(p[0], (0, 0)) and np.allclose(p[-1], (1, 0))
    assert f.tolist() == [1, 0, 0, 0, 1]


def test_pack_ids_and_channels():
    a = cv.pack(cv.join([cv.shape([(0, 0), (1, 1)], RED), cv.shape([(0, 1), (1, 0), (0, 0)], (0, 1, 0))]))
    assert a.shape == (cv.CHANNELS, 5)
    assert a[5].tolist() == [0, 0, 1, 1, 1]
    assert a[2].tolist() == [1, 1, 0, 0, 0] and a[6].tolist() == [1] * 5


def test_pack_maps_a_rectangle_and_blanks_outside():
    s = cv.shape([(0, 0), (1, 0), (3, 0)], RED)
    a = cv.pack(s, rect=(0.5, 0, 1, 1), flip=(-1, 1))
    assert np.allclose(a[0], [1, -1, -1])
    assert a[2].tolist() == [1, 1, 0]


def test_pack_with_nothing_is_one_dark_shape():
    a = cv.pack(cv.join([cv.shape([(0, 0)], RED)]))
    assert a.shape == (cv.CHANNELS, 2) and a[2].sum() == 0


def test_divide_stays_inside_each_line():
    s = cv.join([cv.shape([(0, 0), (1, 0)], RED), cv.shape([(5, 5), (6, 5)], RED)])
    p, _, _, ids = cv.divide(s, 0.3)
    assert not ((p[:, 0] > 1.01) & (p[:, 0] < 4.99)).any()
    assert ids.tolist() == sorted(ids.tolist())


def test_pack_is_tightly_packed_for_td():
    a = cv.pack(cv.warp(cv.shape([(0, 0), (1, 1), (0, 1)], RED), SQUARE, wp), rect=(0, 0, 2, 2))
    assert a.dtype == np.float32 and a.strides == (a.shape[1] * 4, 4)


def test_join_keeps_lines_apart_inside_a_shape():
    a = cv.join([cv.shape([(0, 0), (1, 1)], RED), cv.shape([(2, 2), (3, 3)], RED)])
    b = cv.join([a, cv.shape([(4, 4), (5, 5)], RED)])
    assert b[3].tolist() == [0, 0, 1, 1, 2, 2]


def test_paint_mixes_and_keeps_level_and_dark():
    rgb = [(0.5, 0.2, 0.0), (0, 0, 0), (1, 1, 1)]
    s = cv.shape([(0, 0), (1, 0), (2, 0)], rgb)
    _, c, _, _ = cv.paint(s, (1, 1, 0))
    assert np.allclose(c, [(0.5, 0.5, 0), (0, 0, 0), (1, 1, 0)])


def test_starts():
    assert cv.starts(np.array([0, 0, 1, 1, 1, 4])).tolist() == [1, 0, 1, 0, 0, 1]


def speed():
    q = [(-1.4, 0.1), (-0.6, 0.1), (-0.6, 0.9), (-1.4, 0.9)]
    s = cv.join([cv.shape(np.random.rand(40, 2), np.random.rand(40, 3)) for _ in range(25)])
    a = time.perf_counter()
    for _ in range(200):
        cv.pack(cv.warp(s, q, wp), rect=(-1.05, 0.55, 0.9, 0.9))
    return (time.perf_counter() - a) / 200 * 1000


def _circle(n=200, r=0.8):
    a = np.linspace(0, 2 * np.pi, n)
    return cv.shape(np.stack((np.cos(a) * r, np.sin(a) * r), axis=1), (1.0, 0.5, 0.0))


def test_points_sit_on_the_line_with_its_colours():
    pts, rgb, flags, ids = cv.points(_circle())
    assert len(pts) % 2 == 0 and len(pts) > 20
    assert np.allclose(np.hypot(pts[:, 0], pts[:, 1]), 0.8, atol=0.01)
    assert np.allclose(rgb, (1.0, 0.5, 0.0))


def test_each_point_is_its_own_shape_with_no_hold():
    pts, _, flags, ids = cv.points(_circle())
    assert (flags == 0).all()
    assert (ids[::2] == ids[1::2]).all() and len(set(ids.tolist())) == len(ids) // 2


def test_a_point_is_a_tiny_stroke_never_a_stopped_beam():
    pts = cv.points(_circle())[0]
    assert np.allclose(np.hypot(*(pts[1::2] - pts[::2]).T), cv.POINT_LEN, atol=1e-4)


def test_points_never_exceed_the_limit():
    big = cv.join([_circle(400, 0.2 + i * 0.1) for i in range(8)])
    assert len(cv.points(big)[0]) // 2 <= cv.MAX_POINTS + 1


def test_points_cross_no_gap_between_lines():
    a, b = cv.shape([(-1, 0), (-0.5, 0)], (1, 1, 1)), cv.shape([(0.5, 0), (1, 0)], (1, 1, 1))
    pts = cv.points(cv.join([a, b]))[0]
    assert ((pts[:, 0] <= -0.49) | (pts[:, 0] >= 0.49)).all()


def test_dark_stretches_give_no_points():
    s = _circle()
    assert len(cv.points((s[0], s[1] * 0, s[2], s[3]))[0]) == len(cv.EMPTY[0])


def test_view_at_home_changes_nothing_and_flying_in_grows():
    s = _circle()
    assert cv.view(s, 0.0, 0.0, 2.25, 0.0, 0.0) is s
    near = np.hypot(*cv.view(s, 0.0, 0.0, 1.5, 0.0, 0.0)[0].T)
    assert near.max() > 0.9 and near.max() <= 1.0


for name, t in sorted(globals().copy().items()):
    if name.startswith('test_'):
        t()
        print('ok', name)
print('warp and pack 1000 points: {:.2f} ms'.format(speed()))
