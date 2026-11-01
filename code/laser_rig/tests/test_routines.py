# Runs outside TouchDesigner: python tests/test_routines.py
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import routines

RAW = dict(pattern=0, variant=7, palette=0, width=0.5, phase=0.3, rot=0.0, size=1.0)
AUDIO = dict(low=1.0, mid=1.0, high=1.0, nx=0.3, ny=-0.2, nrot=0.25, nphase=0.15, Size=1.0, Move=1.0, Change=1.0)


def every_case():
    """Every pattern and variant, at the extremes of the sticks, with and without audio."""
    for pattern in range(len(routines.ROUTINES)):
        for variant in range(8):
            for w in (0.0, 0.5, 1.0):
                for phase in (-3.7, 0.0, 0.3, 12345.678):
                    for size in (0.0, 1.0):
                        for audio in (None, AUDIO):
                            yield dict(RAW, pattern=pattern, variant=variant, width=w, phase=phase, size=size), audio


def index(name):
    return [n for n, _ in routines.ROUTINES].index(name)


def test_bad_items_are_dropped():
    def bad(c):
        return [routines.line(0, 0, float('nan'), 1), routines.curve([(0, 0)]),
                routines.line(0, 0, float('inf'), 1), routines.line(0, 0, 0.5, 0.5)]
    routines.ROUTINES.append(('bad', bad))
    try:
        items = routines.build(dict(RAW, pattern=len(routines.ROUTINES) - 1))
    finally:
        routines.ROUTINES.pop()
    assert len(items) == 1 and len(items[0].pts) == 17


def test_explicit_colour_is_kept():
    def coloured(c):
        return [routines.line(0, 0, 0.5, 0.5), routines.line(0, 0, 0.5, 0, color=5)]
    routines.ROUTINES.append(('coloured', coloured))
    try:
        items = routines.build(dict(RAW, pattern=len(routines.ROUTINES) - 1))
    finally:
        routines.ROUTINES.pop()
    assert [i.color for i in items] == [0, 5]


def test_length_includes_the_closing_side():
    square = routines.Item('t', [(0, 0), (2, 0), (2, 2), (0, 2)], closed=True)
    assert abs(square.length() - 8) < 1e-9
    assert abs(routines.line(0, 0, 1, 0).length() - 1) < 1e-9


def test_table():
    rows = routines.table(routines.build(dict(RAW, pattern=index('Sheets'))))
    assert rows[0][:2] == ['id', 'type']
    assert len(rows) == 9 and all(len(r) == 9 for r in rows)
    assert rows[1][1] == 'line' and rows[1][8] == 17


def test_keep_contours():
    mid = [(0, 0)] * 3
    assert routines.keep_contours([10, 20, 30], mid, 0) == [0, 1, 2]
    assert routines.keep_contours([], [], 100) == []
    assert routines.keep_contours([30, 30, 30, 30], [(0, 0)] * 4, 100) == [0, 1, 2]
    # a giant outer loop never pushes out the smaller contours of the face
    assert routines.keep_contours([500, 100, 100], mid, 600) == [1, 2]
    # big simple shapes are all kept while the budget has room
    assert sorted(routines.keep_contours([300, 300, 40], [(0, 0)] * 3, 800)) == [0, 1, 2]
    # central beats edge at equal length
    assert routines.keep_contours([90, 90, 90], [(0.95, 0), (0, 0), (0, 0)], 260) == [1, 2]
    # nothing fits: still draw the smallest
    assert routines.keep_contours([400, 300], [(0, 0), (0, 0)], 100) == [1]


def test_every_routine_at_every_extreme():
    for raw, audio in every_case():
        items = routines.build(raw, audio)
        assert items, raw


def test_no_drawing_is_over_budget():
    worst = 0.0
    for raw, audio in every_case():
        items = routines.build(raw, audio)
        worst = max(worst, sum(i.length() + routines.JUMP for i in items))
    assert worst <= routines.BUDGET + 1e-6, worst
    return worst


def test_nothing_is_a_held_dot():
    """Every item is a stroke at full stick travel, so no beam sits still."""
    for raw, audio in every_case():
        if raw['size'] == 1.0 and raw['width'] >= 0.5:
            for item in routines.build(raw, audio):
                assert item.length() > 0.2, (raw, item.type, item.length())


def test_stays_in_the_box():
    """At rest, with no audio pushing, the drawing is inside the surface."""
    for raw, audio in every_case():
        if audio is None:
            for item in routines.build(raw):
                assert all(abs(v) <= 1.0 + 1e-9 for pt in item.pts for v in pt), (raw, item.type)


def test_rings_have_no_hold_on_the_seam():
    ring = routines.build(dict(RAW, pattern=index('Cone')))[0]
    assert ring.closed and ring.corners() == [0] * len(ring.pts)
    assert routines.curve([(0, 0, 0), (1, 1, 0), (2, 0, 0)]).corners() == [1, 0, 1]
    assert routines.Item('t', [(0, 0, 0), (1, 1, 0)]).corners() is None


def test_audio_bends_the_form_and_not_only_the_place():
    """With every push and pump at zero, the high band alone must change the shape."""
    still = dict(low=0.0, mid=0.0, high=0.0, nx=0.0, ny=0.0, nrot=0.0, nphase=0.0, Size=0.0, Move=0.0, Change=1.0)
    for name in ('Cone', 'Vortex', 'Wave', 'Liquid Sky'):
        raw = dict(RAW, pattern=index(name), variant=3)
        quiet = routines.build(raw, still)[0].pts
        loud = routines.build(raw, dict(still, high=1.0))[0].pts
        assert len(quiet) == len(loud)
        assert max(math.dist(a, b) for a, b in zip(quiet, loud)) > 0.02, name


def test_variants_change_the_form():
    for name, _ in routines.ROUTINES:
        drawings = {tuple(pt for item in routines.build(dict(RAW, pattern=index(name), variant=v))
                          for pt in item.pts) for v in range(8)}
        assert len(drawings) > 1, name


def test_three_noise_levels_grow():
    pts = routines.build(dict(RAW, pattern=index('Cone'), ntime=1.0))[0].pts
    moved = []
    for level in (0.0, 1.0, 2.0, 3.0):
        new = routines.build(dict(RAW, pattern=index('Cone'), ntime=1.0, nlevel=level))[0].pts
        flat = routines.build(dict(RAW, pattern=index('Cone'), ntime=0.0, nlevel=level))[0].pts
        moved.append(max(math.dist(a, b) for a, b in zip(new, flat)) if len(new) == len(flat) else 9.0)
    assert moved[0] < moved[1] < moved[2] < moved[3], moved
    assert pts


def test_the_levels_blend():
    assert routines.level(1.0) == routines.LEVELS[1] and routines.level(3.0) == routines.LEVELS[3]
    assert routines.LEVELS[1][0] < routines.level(1.5)[0] < routines.LEVELS[2][0]


def test_turning_changes_the_drawing():
    flat = routines.build(dict(RAW, pattern=index('Cone')))[0].pts
    turned = routines.build(dict(RAW, pattern=index('Cone'), yaw=0.125))[0].pts
    assert max(abs(p[0]) for p in turned) < max(abs(p[0]) for p in flat)


def test_flying_in_grows_the_shape_and_stays_on_the_box():
    far = routines.build(dict(RAW, pattern=index('Cone'), variant=0, fly=6.0))[0].pts
    home = routines.build(dict(RAW, pattern=index('Cone'), variant=0, fly=3.0))[0].pts
    assert max(abs(p[0]) for p in far) < max(abs(p[0]) for p in home)
    for name, _ in routines.ROUTINES:
        for fly in (0.25, 0.5, 1.0):
            for item in routines.build(dict(RAW, pattern=index(name), fly=fly, width=1.0)):
                assert all(abs(v) <= 1.0 + 1e-9 for pt in item.pts for v in pt), name


def test_shapes_are_still_there_close_to_the_camera():
    for name, _ in routines.ROUTINES:
        for fly in (2.0, 1.0, 0.6, 0.4):
            for variant in (0, 3, 7):
                assert routines.build(dict(RAW, pattern=index(name), variant=variant, width=1.0, fly=fly)), (name, fly)


def test_the_track_point_holds_the_middle_of_every_shape_when_zoomed():
    for name, _ in routines.ROUTINES:
        for phase in (0.0, 0.13, 0.4, 0.77):
            pts = [p for i in routines.build(dict(RAW, pattern=index(name), variant=3, phase=phase, fly=1.5))
                   for p in i.pts]
            for axis in (0, 1):
                v = [p[axis] for p in pts]
                assert abs(min(v) + max(v)) / 2 < 0.25, (name, phase, axis)


def test_shapes_are_built_around_their_centre_over_a_cycle():
    for name, _ in routines.ROUTINES:
        mid = []
        for k in range(40):
            pts = [p for i in routines.build(dict(RAW, pattern=index(name), variant=3, phase=k / 10.0)) for p in i.pts]
            mid.append((sum(p[1] for p in pts) / len(pts)))
        assert abs(sum(mid) / len(mid)) < 0.1, name


def test_close_up_the_shape_spreads_over_the_whole_view_and_keeps_a_middle():
    for name in ('Tunnel', 'Vortex', 'Knot', 'Cones'):
        pts = [p for i in routines.build(dict(RAW, pattern=index(name), variant=7, width=1.0, fly=0.3)) for p in i.pts]
        assert max(abs(p[0]) for p in pts) > 0.7 and max(abs(p[1]) for p in pts) > 0.7, name
        assert all(abs(v) <= 1.0 + 1e-9 for p in pts for v in p), name
        assert name == 'Vortex' or any(math.hypot(*p) < 0.7 for p in pts), name     # its centre is behind you


def test_a_splat_stays_within_its_larger_budget():
    limit = routines.BUDGET * routines.SPLAT_BUDGET + 1e-6
    for name, _ in routines.ROUTINES:
        for fly in (1.0, 0.6, 0.3, 0.25):
            items = routines.build(dict(RAW, pattern=index(name), width=1.0, fly=fly))
            assert sum(i.length() + routines.JUMP for i in items) <= limit, (name, fly)


def test_the_lens_only_widens_up_close():
    assert routines.splat(2.25) == 0 and routines.splat(1.5) == 0
    assert 0 < routines.splat(1.0) < 1 and routines.splat(0.3) == 1 and routines.splat(0.25) == 1


def test_r3_fill_makes_every_shape_reach_the_surface_edge():
    for name, _ in routines.ROUTINES:
        for width in (0.0, 0.5, 1.0):
            raw = dict(RAW, pattern=index(name), variant=3, width=width, phase=0.13)
            scale = routines.fill(raw)
            pts = [p for i in routines.build(dict(raw, fill=scale)) for p in i.pts]
            reach = max((max(p[a] for p in pts) - min(p[a] for p in pts)) / 2 for a in (0, 1))
            assert 0.65 < reach <= 1.0, (name, width, reach)      # dense shapes stop at the length budget


def test_the_soft_edge_never_leaves_the_box():
    assert routines.soft(0.3, 0.2) == (0.3, 0.2)
    for x, y in ((5.0, 0.0), (3.0, -4.0), (0.9, 0.0)):
        assert math.hypot(*routines.soft(x, y)) < 1.0


def test_inside_a_ring_breaks_it_open():
    near = routines.build(dict(RAW, pattern=index('Tunnel'), variant=7, width=1.0, fly=1.0))
    assert near and any(not item.closed for item in near) or len(near) < 8


for t in (test_r3_fill_makes_every_shape_reach_the_surface_edge, test_close_up_the_shape_spreads_over_the_whole_view_and_keeps_a_middle, test_a_splat_stays_within_its_larger_budget,
          test_the_lens_only_widens_up_close, test_shapes_are_still_there_close_to_the_camera, test_the_track_point_holds_the_middle_of_every_shape_when_zoomed,
          test_shapes_are_built_around_their_centre_over_a_cycle, test_the_soft_edge_never_leaves_the_box,
          test_three_noise_levels_grow, test_the_levels_blend, test_turning_changes_the_drawing,
          test_flying_in_grows_the_shape_and_stays_on_the_box, test_inside_a_ring_breaks_it_open,
          test_bad_items_are_dropped, test_explicit_colour_is_kept, test_length_includes_the_closing_side,
          test_table, test_keep_contours, test_every_routine_at_every_extreme, test_no_drawing_is_over_budget,
          test_nothing_is_a_held_dot, test_stays_in_the_box, test_rings_have_no_hold_on_the_seam,
          test_audio_bends_the_form_and_not_only_the_place, test_variants_change_the_form):
    t()
    print('ok', t.__name__)
