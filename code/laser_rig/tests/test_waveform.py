# Runs outside TouchDesigner: python tests/test_waveform.py [preview.png]
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import waveform as wf


def test_frame_starts_are_rising_edges():
    s = np.array([0, -1, -1, 0, 5, -1, 1, -1])
    assert wf.frame_starts(s).tolist() == [1, 5, 7]


def test_select_newest_frame_and_stepping_back():
    starts = np.array([10, 110, 210, 310])
    assert wf.select(starts, 400) == (210, 310, 3)
    assert wf.select(starts, 400, back=1) == (110, 210, 3)
    assert wf.select(starts, 400, back=99) == (10, 110, 3)
    assert wf.select(starts, 400, count=2) == (110, 310, 3)
    assert wf.select(starts, 400, count=0) == (10, 310, 3)


def test_select_without_pulses_uses_the_window():
    assert wf.select(np.array([], int), 400) == (0, 400, 0)
    assert wf.select(np.array([5]), 400) == (0, 400, 0)


def test_measure():
    n = 600
    x = np.linspace(-0.5, 0.5, n)
    y = np.zeros(n)
    r = np.ones(n)
    z = np.zeros(n)
    m = wf.measure(x, y, r, z, z, z, 30000, 0.02)
    assert m['samples'] == 600 and abs(m['hz'] - 50) < 1e-9 and abs(m['msec'] - 20) < 1e-9
    assert m['lit'] == 1.0 and m['jumps'] == 0 and abs(m['peak'] - 0.5) < 1e-9
    assert wf.status(m) == 'OK'


def test_lit_jump_counts_only_when_both_ends_are_lit():
    x = np.array([0.0, 0.0, 0.5, 0.5, 0.9, 0.9])
    z = np.zeros(6)
    lit = wf.measure(x, z, np.ones(6), z, z, z, 30000, 0.02)
    assert lit['jumps'] == 2 and wf.status(lit) == 'LIT JUMP'
    blank = wf.measure(x, z, z, z, z, z, 30000, 0.02)
    assert blank['jumps'] == 0


def test_slow_frame():
    z = np.zeros(3000)
    m = wf.measure(z, z, z, z, z, z, 30000, 0.02)
    assert m['hz'] == 10 and wf.status(m) == 'SLOW FRAME'


def test_no_signal():
    z = np.zeros(1)
    assert wf.measure(z, z, z, z, z, z, 30000, 0.02) is None
    assert wf.status(None) == 'NO SIGNAL'
    assert 'NO SIGNAL' in wf.text(None, 0, 0, True)


def test_text_flags_an_unarmed_laser():
    z = np.zeros(600)
    m = wf.measure(z, z, z, z, z, z, 30000, 0.02)
    assert 'NOT ARMED' in wf.text(m, 1, 3, False) and 'NOT ARMED' not in wf.text(m, 1, 3, True)


def test_blank_share():
    z = np.zeros(4)
    m = wf.measure(z, z, z, z, z, np.array([0, 1, 3, 5]), 30000, 0.02)
    assert m['blank'] == 0.5


def test_render_shape_and_lanes():
    n = 1000
    t = np.linspace(0, 6, n)
    r = (t % 1 < 0.5).astype(float)
    z = np.zeros(n)
    img = wf.render(np.sin(t), np.cos(t), r, z, z, [0, 300, 600], 760, 300)
    assert img.shape == (300, 760, 4) and img.dtype == np.uint8
    assert (img[:10, 228, :3] == wf.PULSE).all()
    assert (img[:, :, :3] == wf.X_COL).all(axis=2).any()
    assert (img[180:, :, :3] == wf.RGB_COLS[0]).all(axis=2).any()
    assert not (img[220:, :, :3] == wf.RGB_COLS[1]).all(axis=2).any()


def test_render_fewer_samples_than_columns_and_empty():
    z = np.zeros(20)
    assert wf.render(z, z, z, z, z, [], 760, 300).shape == (300, 760, 4)
    e = np.zeros(0)
    assert wf.render(e, e, e, e, e, [], 760, 300).shape == (300, 760, 4)


def test_for_td_is_a_plain_flipped_copy():
    img = np.arange(24, dtype=np.uint8).reshape(2, 3, 4)
    out = wf.for_td(img)
    assert out.flags['C_CONTIGUOUS'] and out.flags['OWNDATA'] and out.strides[0] > 0
    assert (out[0] == img[1]).all()


def speed():
    n = 12000
    t = np.linspace(0, 40, n)
    v = np.sin(t)
    a = time.perf_counter()
    for _ in range(50):
        wf.measure(v, v, v, v, v, v, 30000, 0.02)
        wf.render(v, v, v, v, v, np.arange(0, n, 600), 760, 330)
    return (time.perf_counter() - a) / 50 * 1000


for name, t in sorted(globals().copy().items()):
    if name.startswith('test_'):
        t()
        print('ok', name)
print('draw and measure {:.2f} ms'.format(speed()))
if len(sys.argv) > 1:
    from PIL import Image
    n = 2400
    i = np.arange(n)
    x = np.clip(np.sin(i / 90) * 1.4, -0.9, 0.9)
    y = np.clip(np.sin(i / 37 + 1) * 1.2 + np.sin(i / 11) * 0.2, -0.9, 0.9)
    c = (np.sin(i / 60) + 1) / 2
    img = wf.render(x, y, c, c[::-1], (i % 500 < 300) * 1.0, np.arange(0, n, 600), 760, 330)
    Image.fromarray(img).save(sys.argv[1])
