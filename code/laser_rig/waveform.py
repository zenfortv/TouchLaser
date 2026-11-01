# Laser monitor. Lives in laser_rig/waveform (Text DAT synced to this file).
# Reads the samples sent to a laser: split them into frames, measure them, draw them.
# No TD calls in here, so tests/test_waveform.py can run it outside TouchDesigner.

import numpy as np

SLOW_HZ = 20.0                 # below this a frame flickers
LIT_ON = 0.02                  # any colour above this counts as lit
JUMP_FACTOR = 3.0              # a lit step this many Step Sizes long is a jump
START_STATE = -0.5             # debug channel below this marks a frame start
BLANK_STATE = 3                # debug channel from here up is blanking

BG = (9, 10, 12)
GRID = (34, 37, 42)
PULSE = (150, 155, 160)
X_COL = (64, 190, 225)
Y_COL = (205, 150, 40)
RGB_COLS = ((225, 25, 90), (120, 200, 30), (30, 190, 170))
LANE_SPLIT = 0.6               # top share of the image used by X and Y
I_GRID, I_PULSE, I_X, I_Y, I_R = 1, 2, 3, 4, 5
PALETTE = np.array([(*c, 255) for c in (BG, GRID, PULSE, X_COL, Y_COL) + RGB_COLS],
                   np.uint8).view(np.uint32).ravel()   # one word per colour: fast to look up


def frame_starts(state):
    """Sample indices of the frame start pulses in the debug channel."""
    on = np.asarray(state) < START_STATE
    return np.flatnonzero(on[1:] & ~on[:-1]) + 1


def select(starts, length, count=1, back=0):
    """Sample range (a, b) of count frames, ending back frames before the newest whole
    frame, plus how many whole frames exist. No pulses: the whole window."""
    total = len(starts) - 1
    if total < 1:
        return 0, length, 0
    last = total - min(max(back, 0), total - 1)
    first = 0 if count <= 0 else max(0, last - count)
    return int(starts[first]), int(starts[last]), total


def measure(x, y, r, g, b, state, rate, step):
    """Numbers for one sample range. step is the laser's real Step Size; state is the
    Laser CHOP debug channel (0 colour, 1-2 hold, 3 and up blanking)."""
    n = len(x)
    if n < 2:
        return None
    lit = np.maximum(np.maximum(r, g), b) > LIT_ON
    steps = np.hypot(np.diff(x), np.diff(y))
    both_lit = lit[1:] & lit[:-1]
    return {'samples': n, 'msec': n / rate * 1000.0, 'hz': rate / n,
            'lit': float(lit.mean()),
            'blank': float((state >= BLANK_STATE).mean()),
            'peak': float(max(np.abs(x).max(), np.abs(y).max())),
            'maxstep': float(steps.max()),
            'jumps': int(np.count_nonzero(steps[both_lit] > step * JUMP_FACTOR))}


def status(m):
    if m is None:
        return 'NO SIGNAL'
    if m['jumps']:
        return 'LIT JUMP'
    if m['hz'] < SLOW_HZ:
        return 'SLOW FRAME'
    return 'OK'


def text(m, picked, total, armed):
    """Header line of the monitor."""
    if m is None:
        return 'WAVEFORM   NO SIGNAL'
    word = status(m) if armed else status(m) + ' (NOT ARMED)'
    return '{}   FRAME {}/{}   {} samples   {:.0f} ms   {:.0f} Hz   lit {:.0f}%   blank {:.0f}%   jumps {}'.format(
        word, picked, total, m['samples'], m['msec'], m['hz'], m['lit'] * 100, m['blank'] * 100,
        m['jumps'])


def _columns(v, w):
    """Min and max of v in each of w columns."""
    edges = np.linspace(0, len(v), w + 1).astype(np.int64)
    left = np.minimum(edges[:-1], len(v) - 1)
    right = np.maximum(edges[1:], left + 1)
    spans = np.stack((left, right), 1).ravel()
    padded = np.append(v, v[-1])              # reduceat needs right to be a valid index
    return np.minimum.reduceat(padded, spans)[::2], np.maximum.reduceat(padded, spans)[::2]


def _trace(img, v, top, bottom, ink):
    """Draw v, range -1 to 1, between rows top and bottom."""
    h, w = bottom - top, img.shape[1]
    lo, hi = _columns(np.clip(v, -1, 1), w)
    a = np.floor((1 - hi) / 2 * (h - 1)).astype(np.int32)
    b = np.ceil((1 - lo) / 2 * (h - 1)).astype(np.int32)
    rows = np.arange(h, dtype=np.int32)[:, None]
    img[top:bottom][(rows >= a) & (rows <= b)] = ink


def _bars(img, v, top, bottom, ink):
    """Filled lane for v, range 0 to 1."""
    h, w = bottom - top, img.shape[1]
    _, hi = _columns(np.clip(v, 0, 1), w)
    a = np.round((1 - hi) * (h - 3) + 3).astype(np.int32)
    rows = np.arange(h, dtype=np.int32)[:, None]
    img[top:bottom][(rows >= a) & (hi[None, :] > 0)] = ink


def render(x, y, r, g, b, starts, w, h):
    """RGBA uint8 image, row 0 at the top: frame ticks, X and Y, then R, G and B lanes.
    starts are sample indices within this range. Drawn as palette indices, coloured last."""
    img = np.zeros((h, w), np.uint8)
    split = int(h * LANE_SPLIT)
    lane = (h - split) // 3
    for row in (10, (10 + split) // 2, split, split + lane, split + 2 * lane):
        img[row] = I_GRID
    n = len(x)
    if n > 1:
        cols = np.minimum((np.asarray(starts, np.int64) * w) // n, w - 1)
        img[:10, cols] = I_PULSE
        img[10:, cols] = I_GRID
        _trace(img, y, 14, split - 2, I_Y)
        _trace(img, x, 14, split - 2, I_X)
        for i, v in enumerate((r, g, b)):
            _bars(img, v, split + i * lane + 1, split + (i + 1) * lane, I_R + i)
    return np.take(PALETTE, img).view(np.uint8).reshape(h, w, 4)


def for_td(img):
    """Flip for copyNumpyArray, whose row 0 is the bottom. It needs a real copy: a view made
    with [::-1] has negative strides, and handing that to TD is the likely cause of a crash."""
    return np.flipud(img).copy()
