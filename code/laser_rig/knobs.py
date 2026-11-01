# Video Knobs panel, in the style of 404.zero's Zerror: dark round knobs with thin ring arcs that
# turn red once moved off their default. Lives in laser_rig/knobs (Text DAT synced to this file).
# One shader (knobs.glsl) draws them all from a small data image and one Text TOP writes all the
# labels, so a panel at rest costs nothing. Here: where things go, and what the mouse does.
# No TD calls in here, so tests/test_knobs.py can run it outside TouchDesigner.

import numpy as np

WIDTH = 400
HEIGHT = 492
HERO_R, KNOB_R = 44, 29
KNOB, BUTTON = 0.0, 1.0
DRAG_PIXELS = 220.0            # dragging this far covers the whole range
DOUBLE_CLICK = 0.35            # seconds
TEXT_LIFT = 3                  # the measured height includes room below the letters

HERO = (('Edgeblur', 'softness'), ('Edgethreshold', 'floor'))
ROWS = ((('Contrast', 'contrast'), ('Levels', 'levels'), ('Shift', 'shift'), ('Drift', 'drift')),
        (('Stability', 'stability'), ('Audiopulse', 'audio'), ('Edgestep', 'detail'), ('Maxpoints', 'points')),
        (('Colorboost', 'boost'), ('Colorsat', 'satur'), ('Wipespeed', 'speed'), ('Engraverows', 'rows')))
SCANS = (('off', 'OFF'), ('down', 'LINE'), ('engrave', 'ENGRAVE'), ('radar', 'RADAR'), ('iris', 'IRIS'))
SWITCHES = (('Invert', 'INVERT'), ('Hold', 'HOLD'), ('Beam', 'BEAM'), ('Frame', 'FRAME'))


def controls():
    """Every control: par, label, kind, centre x, y (0 at the bottom), then radius for a knob, or
    half width and half height for a button, whose value is what it sets its par to."""
    out = []
    for i, (par, label) in enumerate(HERO):
        out.append(dict(par=par, label=label, kind=KNOB, x=WIDTH * (0.28 + 0.44 * i), y=HEIGHT - 60, r=HERO_R))
    for row, knobs in enumerate(ROWS):
        y = HEIGHT - 170 - row * 96
        for i, (par, label) in enumerate(knobs):
            out.append(dict(par=par, label=label, kind=KNOB, x=WIDTH * (0.125 + 0.25 * i), y=y, r=KNOB_R))
    for i, (value, label) in enumerate(SCANS):
        out.append(dict(par='Wipe', label=label, kind=BUTTON, value=value, x=WIDTH * (0.1 + 0.2 * i), y=52,
                        hw=36, hh=13))
    for i, (par, label) in enumerate(SWITCHES):
        out.append(dict(par=par, label=label, kind=BUTTON, value=True, x=WIDTH * (0.125 + 0.25 * i), y=20,
                        hw=46, hh=13))
    return out


def norm(value, low, high):
    return max(0.0, min(1.0, (value - low) / (high - low))) if high > low else 0.0


def from_norm(n, low, high, whole=False):
    value = low + (high - low) * max(0.0, min(1.0, n))
    return int(round(value)) if whole else value


def text(value):
    """A value short enough to sit inside a knob."""
    if isinstance(value, int):
        return str(value)
    return '{:.0f}'.format(value) if abs(value) >= 100 else '{:.2f}'.format(value)


def hit(items, x, y):
    """The control under a pixel, or None."""
    for c in items:
        if c['kind'] == KNOB and np.hypot(x - c['x'], y - c['y']) <= c['r'] + 4:
            return c
        if c['kind'] == BUTTON and abs(x - c['x']) <= c['hw'] and abs(y - c['y']) <= c['hh']:
            return c
    return None


def dragged(start, moved_pixels, whole_range):
    """Knob position after a drag, up or right for more."""
    return start + moved_pixels / DRAG_PIXELS * whole_range


def data(items, states):
    """The shader's data image, 2 x N x 4 float. states gives (position 0-1, is lit) per control.
    Row 0: x, y, radius or half width, position. Row 1: kind, lit, half height, unused."""
    out = np.zeros((2, len(items), 4), np.float32)
    for i, (c, (position, lit)) in enumerate(zip(items, states)):
        out[0, i] = c['x'], c['y'], c.get('r', c.get('hw')), position
        out[1, i] = c['kind'], float(lit), c.get('hh', 0.0), 0.0
    return out


def labels(items, shown, measure):
    """Rows for the Text TOP's Specification DAT, which places text by its lower left corner.
    shown gives the text inside each knob, measure a text's width and height."""
    def centred(x, y, words):
        w, h = measure(words)
        return [round(x - w / 2), round(y - h / 2) + TEXT_LIFT, words]

    rows = [['x', 'y', 'text']]
    for c, inside in zip(items, shown):
        if c['kind'] == KNOB:
            rows.append(centred(c['x'], c['y'] - c['r'] - 14, c['label']))
            rows.append(centred(c['x'], c['y'], inside))
        else:
            rows.append(centred(c['x'], c['y'], c['label']))
    return rows
