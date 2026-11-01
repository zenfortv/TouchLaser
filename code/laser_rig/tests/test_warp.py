# Runs outside TouchDesigner: python tests/test_warp.py
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import warp
from test_warp_helpers import inside

SCREENSHOT = [(38, 227), (217, 227), (81, 203), (38, 48)]     # bl, br, tr, tl from the bug report


def warped(quad, x, y):
    k = warp.dent(quad)
    if k is None:
        return warp.blend(quad, x, y)
    n = warp.normal(k)
    side = 1 if n[0] * x + n[1] * y >= 0 else -1
    return warp.blend(warp.half(quad, k, side), x, y)


def test_the_bug_is_real_and_fixed():
    assert warp.dent(SCREENSHOT) == 2
    assert not inside(SCREENSHOT, warp.blend(SCREENSHOT, 0, 0))
    assert inside(SCREENSHOT, warped(SCREENSHOT, 0, 0))


def test_convex_quads_are_left_alone():
    assert warp.dent(warp.REST) is None
    assert warp.dent([(-1, -1), (2, -1), (1.5, 0.5), (-1, 1)]) is None


def test_crossed_quad_has_no_dent():
    assert warp.dent([(-1, -1), (1, 1), (1, -1), (-1, 1)]) is None


def test_every_dent_position_and_winding():
    for k in range(4):
        q = list(warp.REST)
        q[k] = (q[(k + 2) % 4][0] * 0.3, q[(k + 2) % 4][1] * 0.3)
        assert warp.dent(q) == k
        assert warp.dent(q[::-1]) == 3 - k


def test_corners_stay_pinned():
    for k in range(4):
        q = list(warp.REST)
        q[k] = (q[k][0] * -0.3, q[k][1] * -0.3)
        for i in range(4):
            got = warped(q, *warp.REST[i])
            assert abs(got[0] - q[i][0]) < 1e-9 and abs(got[1] - q[i][1]) < 1e-9


def test_halves_join_along_the_diagonal():
    rng = random.Random(1)
    for _ in range(2000):
        q = [(rng.uniform(-2, 2), rng.uniform(-2, 2)) for _ in range(4)]
        k = warp.dent(q)
        if k is None:
            continue
        t = rng.uniform(0, 1)
        a, b = warp.REST[k], warp.REST[(k + 2) % 4]
        p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        one, two = warp.blend(warp.half(q, k, 1), *p), warp.blend(warp.half(q, k, -1), *p)
        assert abs(one[0] - two[0]) < 1e-9 and abs(one[1] - two[1]) < 1e-9


def test_random_dented_quads_never_leave_the_frame():
    rng = random.Random(2)
    done = 0
    while done < 3000:
        q = [(rng.uniform(-2, 2), rng.uniform(-2, 2)) for _ in range(4)]
        if warp.dent(q) is None:
            continue
        done += 1
        for _ in range(40):
            p = warped(q, rng.uniform(-1, 1), rng.uniform(-1, 1))
            assert inside(q, p, 1e-6), (q, p)
    return done


def test_random_convex_quads_never_leave_the_frame():
    rng = random.Random(3)
    done = 0
    while done < 3000:
        q = [(rng.uniform(-2, 2), rng.uniform(-2, 2)) for _ in range(4)]
        turns = [warp._turn(q[i - 1], q[i], q[(i + 1) % 4]) for i in range(4)]
        if not (all(t > 0 for t in turns) or all(t < 0 for t in turns)):
            continue
        done += 1
        for _ in range(40):
            assert inside(q, warped(q, rng.uniform(-1, 1), rng.uniform(-1, 1)), 1e-6)


def close(a, b):
    return all(abs(p[0] - q[0]) < 1e-9 and abs(p[1] - q[1]) < 1e-9 for p, q in zip(a, b))


def test_a_quarter_turn_moves_each_corner_to_the_next():
    q = [(0, 0), (2, 0), (2, 2), (0, 2)]
    assert close(warp.turned(q, (2, 2), (0, 2)), [(2, 0), (2, 2), (0, 2), (0, 0)])


def test_the_grabbed_corner_follows_the_cursor_round():
    q = [(-1, -0.5), (1, -0.5), (1, 0.5), (-1, 0.5)]
    r = warp.turned(q, q[2], (-q[2][1], q[2][0]))
    assert abs(r[2][0] + 0.5) < 1e-9 and abs(r[2][1] - 1) < 1e-9


def test_turning_keeps_the_shape_and_its_centre():
    q = [(38, 227), (217, 227), (81, 203), (38, 48)]
    r = warp.turned(q, (5, 1), (-3, 7))
    side = lambda s, i: warp.math.dist(s[i], s[(i + 1) % 4])
    assert all(abs(side(q, i) - side(r, i)) < 1e-9 for i in range(4))
    assert close([warp.centre(q)], [warp.centre(r)])


def test_no_movement_no_turn():
    q = [(0, 0), (2, 0), (2, 2), (0, 2)]
    assert close(warp.turned(q, (3, 3), (3, 3)), q)


for name, t in sorted(globals().copy().items()):
    if name.startswith('test_'):
        t()
        print('ok', name)
