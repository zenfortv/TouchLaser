# Runs outside TouchDesigner: python tests/test_chains.py
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import canvas as cv
import chains as ch

W = [(1.0, 1.0, 1.0)]


def square(h=0.5, n=40):
    t = np.linspace(-h, h, n, endpoint=False)
    return np.vstack((np.stack((t, -h + 0 * t), 1), np.stack((h + 0 * t, t), 1),
                      np.stack((-t, h + 0 * t), 1), np.stack((-h + 0 * t, -t), 1))).astype(np.float32)


def l_shape():
    return np.array(((0, 0), (1, 0), (1, 0.4), (0.4, 0.4), (0.4, 1), (0, 1)), np.float32)


def line_shape(x0, y0, x1, y1):
    return cv.shape([(x0, y0), (x1, y1)], (1.0, 1.0, 1.0))


def test_inside_a_concave_chain():
    pts = np.array(((0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8), (2.0, 2.0)), np.float32)
    assert ch.inside(l_shape(), pts).tolist() == [True, True, False, True, False]


def test_a_mask_keeps_only_the_inside_of_a_concave_chain():
    out = ch.mask(line_shape(-1, 0.6, 1, 0.6), l_shape(), cv.divide)
    assert len(out[0]) > 4
    assert ch.inside(l_shape(), out[0]).all()


def test_a_mask_stretches_content_over_the_chain():
    pts = ch.mask(line_shape(-0.98, 0, 0.98, 0), square(), cv.divide)[0]
    assert pts[:, 0].min() < -0.4 and pts[:, 0].max() > 0.4


def test_a_cut_starts_a_new_line_so_the_laser_blanks_over_the_gap():
    poly = np.array(((0, 0), (1, 0), (1, 1), (0.7, 1), (0.7, 0.3), (0.3, 0.3), (0.3, 1), (0, 1)), np.float32)
    pts, _, _, ids = ch.mask(line_shape(-1, 0.6, 1, 0.6), poly, cv.divide)
    first, second = sorted(set(ids.tolist()))
    assert pts[ids == first, 0].max() < 0.31 and pts[ids == second, 0].min() > 0.69


def test_a_tiny_shape_still_uses_the_whole_chain():
    pts = ch.mask(line_shape(-0.05, 0, 0.05, 0), square(), cv.divide)[0]
    assert pts[:, 0].min() < -0.4 and pts[:, 0].max() > 0.4
    assert np.ptp(ch.along(line_shape(-0.05, 0, 0.05, 0), square(), True, 0.0, 0.1, cv.divide)[0], axis=0).max() > 0.5


def test_nothing_inside_gives_a_dark_empty_shape():
    out = ch._split(line_shape(-1, 0, 1, 0), np.zeros(2, bool))
    assert len(out[0]) == 2 and not out[1].any()


def test_no_lone_point_survives_a_cut():
    pts, rgb, flags, ids = ch.mask(cv.shape([(-1, 0), (1, 0)], (1.0, 1.0, 1.0)), square(), lambda s, _: s)
    assert all((ids == i).sum() != 1 for i in set(ids.tolist()))


def test_along_follows_the_chain():
    chain = np.stack((np.linspace(0, 2, 200), 0 * np.linspace(0, 2, 200)), 1).astype(np.float32)
    pts = ch.along(line_shape(-1, 0, 1, 0), chain, False, 0.0, 0.2, cv.divide)[0]
    assert abs(pts[:, 1]).max() < 1e-3 and pts[:, 0].min() < 0.05 and pts[:, 0].max() > 1.95


def test_along_steps_off_the_chain_by_box_y():
    chain = np.stack((np.linspace(0, 2, 200), 0 * np.linspace(0, 2, 200)), 1).astype(np.float32)
    pts = ch.along(line_shape(-1, 1, 1, 1), chain, False, 0.0, 0.2, cv.divide)[0]
    assert np.allclose(abs(pts[:, 1]), 0.2, atol=1e-3)


def test_along_wraps_on_a_closed_chain_and_runs_out_on_an_open_one():
    open_chain = np.stack((np.linspace(0, 2, 200), 0 * np.linspace(0, 2, 200)), 1).astype(np.float32)
    assert ch.along(line_shape(-1, 0, 1, 0), open_chain, False, 0.5, 0.2, cv.divide)[0][:, 0].min() > 0.9
    loop = ch.along(line_shape(-1, 0, 1, 0), square(), True, 0.5, 0.2, cv.divide)
    assert len(loop[0]) > 50


def test_a_closed_seam_does_not_draw_across_the_chain():
    pts, _, _, ids = ch.along(line_shape(-1, 0, 1, 0), square(), True, 0.3, 0.2, cv.divide)
    for i in set(ids.tolist()):
        part = pts[ids == i]
        assert len(part) < 2 or np.hypot(*np.diff(part, axis=0).T).max() < 0.25


def test_hatch_stays_inside_and_alternates_direction():
    pts, _, _, ids = ch.hatch(l_shape(), 8, 0.0, 0.0, W)
    assert len(set(ids.tolist())) >= 8
    mid = (pts[::2] + pts[1::2]) / 2
    assert ch.inside(l_shape(), mid).all()


def test_hatch_is_cut_down_to_the_length_budget():
    pts = ch.hatch(square(1.0), 400, 0.1, 0.3, W)[0]
    assert np.hypot(*(pts[1::2] - pts[::2]).T).sum() <= ch.MAX_LENGTH * 1.3


def test_hatch_keeps_its_shape_at_every_angle_and_scroll():
    for angle in (0.0, 0.125, 0.3, 0.77):
        for scroll in (0.0, 0.5, 7.25):
            assert len(ch.hatch(square(), 6, angle, scroll, W)[0]) >= 4


def test_rings_are_copies_inside_the_chain():
    pts, _, flags, ids = ch.rings(square(), 3, 0.2, W)
    assert len(set(ids.tolist())) == 3
    assert abs(pts).max() <= 0.5 + 1e-5 and (flags == 0).all()


def test_rings_are_cut_down_to_the_length_budget():
    assert len(set(ch.rings(square(2.0), 50, 0.0, W)[3].tolist())) <= 2


def test_fills_can_become_points():
    assert len(cv.points(ch.rings(square(), 3, 0.2, W))[0]) > 10


for name, t in sorted(globals().copy().items()):
    if name.startswith('test_'):
        t()
        print('ok', name)
