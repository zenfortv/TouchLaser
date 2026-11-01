# Runs outside TouchDesigner: python tests/test_knobs.py
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import knobs as k

ITEMS = k.controls()


def test_everything_stays_inside_the_panel_and_apart():
    for c in ITEMS:
        half_w, half_h = c.get('r', c.get('hw')), c.get('r', c.get('hh'))
        low = half_h + (18 if c['kind'] == k.KNOB else 0)
        assert half_w <= c['x'] <= k.WIDTH - half_w and low <= c['y'] <= k.HEIGHT - half_h, c
    for c in ITEMS:
        assert k.hit(ITEMS, c['x'], c['y']) is c, c


def test_position_clamps_and_inverts():
    assert k.norm(5, 0, 10) == 0.5 and k.norm(-1, 0, 10) == 0 and k.norm(11, 0, 10) == 1
    assert k.norm(1, 1, 1) == 0
    assert k.from_norm(0.5, -1, 1) == 0 and k.from_norm(2, 0, 10) == 10
    assert k.from_norm(0.26, 1, 8, whole=True) == 3


def test_nothing_is_hit_between_controls():
    assert k.hit(ITEMS, 2, k.HEIGHT - 2) is None


def test_drag_covers_the_range_in_one_stroke():
    assert k.dragged(0.0, k.DRAG_PIXELS, 2.0) == 2.0
    assert k.dragged(1.0, -k.DRAG_PIXELS / 2, 2.0) == 0.0


def test_values_fit_inside_a_knob():
    assert k.text(800) == '800' and k.text(0.3276) == '0.33' and k.text(123.4) == '123'


def test_data_image_for_the_shader():
    a = k.data(ITEMS, [(0.25, True)] * len(ITEMS))
    assert a.shape == (2, len(ITEMS), 4) and a.dtype.name == 'float32'
    assert a[0, 0, 3] == 0.25 and a[1, 0, 1] == 1 and a[0, 0, 2] == k.HERO_R
    assert a[1, -1, 0] == k.BUTTON and a[1, -1, 2] == 13


def test_labels_name_and_value_for_knobs_one_line_for_buttons():
    rows = k.labels(ITEMS, ['1'] * len(ITEMS), lambda words: (10, 8))
    knobs = sum(c['kind'] == k.KNOB for c in ITEMS)
    assert rows[0] == ['x', 'y', 'text'] and len(rows) == 1 + 2 * knobs + len(ITEMS) - knobs
    assert rows[1][2] == 'softness' and rows[2][2] == '1' and rows[-1][2] == 'FRAME'
    assert rows[2][:2] == [round(ITEMS[0]['x'] - 5), round(ITEMS[0]['y'] - 4) + k.TEXT_LIFT]


def test_knob_labels_clear_the_buttons():
    lowest = min(c['y'] - c['r'] - 22 for c in ITEMS if c['kind'] == k.KNOB)
    highest = max(c['y'] + c['hh'] for c in ITEMS if c['kind'] == k.BUTTON)
    assert lowest > highest


for name, t in sorted(globals().copy().items()):
    if name.startswith('test_'):
        t()
        print('ok', name)
