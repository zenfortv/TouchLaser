# Item list. Lives in laser_rig/routines (Text DAT synced to this file).
# A routine turns the controls into a list of Items, in a [-1, 1] box; build() runs the
# selected routine, then rotates, scales and places the result. No TD calls in here, so
# tests/test_routines.py can run it outside TouchDesigner.
#
# The patterns are beam geometry, seen in haze rather than on a wall: a ring is a cone in the
# air, a line is a sheet. Nothing is a held dot: a beam that stops concentrates all its power
# in one spot, so every beam here is a stroke the scanners keep moving along.
#
# To add a shape: copy a small function below, Wave is a good start, and give it a new
# @routine('Name'). It joins D-pad left / right by itself, nothing else to wire.
# It gets c: c.n variant 1-8, c.w length stick 0-1, c.p running phase, c.L half length, c.b audio
# bend 0-1. It returns a list of line(), curve() and ring(), with points (x, y, z) around 0, 0, 0.

import math
from collections import namedtuple

TAU = 2 * math.pi
RING = 48                      # points on a ring; the Laser CHOP fills the steps between
SPLAT_FROM, SPLAT_FULL = 1.5, 0.3      # camera distances where the lens starts to widen, and is widest
SPLAT = 1.2                    # how much of a splatted shape stays in the middle of the view; less pushes it out
SPLAT_BUDGET = 1.5             # a splat may draw this much longer: about 20 Hz, the edge of looking solid
KNEE = 0.8                     # from here to the edge of the box the view compresses instead of clipping
BUDGET = 16.0                  # longest drawing: 30 k at Step Size 0.02 is about 30 Hz
JUMP = 0.15                    # what one blanked move costs, as length
KNOTS = ((1, 1), (1, 2), (2, 3), (1, 3), (3, 4), (2, 5), (3, 5), (4, 5))
CAMERA = 2.25                  # home distance, z = 0 at true size from here: the 47.9 degree lens of laser2025
FILLED = 1.15                  # what fill() aims for before the soft edge: just under the surface edge
FILL_MIN, FILL_MAX = 0.25, 8.0
NEAR = 0.08                    # closer to the camera than this is not drawn
MIN_PART = 0.45                # shorter scraps of a clipped shape are dropped: they would be hot spots
LEVELS = ((0.012, 2.0, 0.4, 0.0),      # amp, freq, speed, spin (turns a second)
          (0.05, 3.0, 0.5, 0.06),      # L1: slow rotation, light bubbling
          (0.14, 2.5, 1.1, 0.18),      # R1: medium
          (0.38, 1.8, 2.2, 0.4))       # R2: heavy

Ctl = namedtuple('Ctl', 'n w p L b')   # variant count 1-8, width, phase, half length, audio bend 0-1


class Item:
    """One object the laser draws. color indexes the palette; None takes the list position."""
    __slots__ = ('type', 'pts', 'closed', 'curved', 'color')

    def __init__(self, type, pts, closed=False, curved=False, color=None):
        self.type = type
        self.pts = pts
        self.closed = closed
        self.curved = curved
        self.color = color

    def corners(self):
        """Curves pass through their inner points; a ring has no ends, so nothing holds at
        its seam. None means every point is a corner."""
        if not self.curved:
            return None
        if self.closed:
            return [0] * len(self.pts)
        return [1] + [0] * (len(self.pts) - 2) + [1]

    def length(self):
        pts = self.pts + self.pts[:1] if self.closed else self.pts
        return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def line(x0, y0, x1, y1, z0=0.0, z1=0.0, steps=17, color=None):
    """Straight, with points along it so noise and perspective can bend it."""
    return Item('line', [(x0 + (x1 - x0) * k / (steps - 1), y0 + (y1 - y0) * k / (steps - 1),
                          z0 + (z1 - z0) * k / (steps - 1)) for k in range(steps)], curved=True, color=color)


def curve(pts, color=None):
    return Item('curve', pts, curved=True, color=color)


def ring(point, steps=RING, color=None):
    """A closed curve. point(a) gives the position at angle a."""
    return Item('ring', [point(TAU * k / steps) for k in range(steps)], closed=True, curved=True, color=color)


def circle(cx, cy, r, z=0.0):
    return ring(lambda a: (cx + r * math.cos(a), cy + r * math.sin(a), z))


# ---------------------------------------------------------------- routines

ROUTINES = []


def routine(name):
    def add(fn):
        ROUTINES.append((name, fn))
        return fn
    return add


@routine('Cone')
def cone(c):                                  # one cone; variants fold its wall into lobes
    depth = (0.0 if c.n == 1 else 0.14) + 0.3 * c.b
    cx = 0.15 * (1 - min(1.0, c.L)) * math.sin(TAU * c.p * 0.3)

    def point(a):
        fold = math.sin((c.n - 1) * a + TAU * c.p)
        r = c.L * (1 + depth * fold) / (1 + depth)
        return (cx + r * math.cos(a), r * math.sin(a), 0.5 * depth * fold)
    return [ring(point)]


@routine('Cones')
def cones(c):                                 # a crown of thin cones, each one breathing
    orbit = 0.0 if c.n == 1 else 0.6 * c.L + 0.1
    out = []
    for i in range(c.n):
        a = TAU * (i / c.n + c.p * 0.25)
        r = (0.1 + 0.12 * c.L) * (1 + 0.35 * math.sin(TAU * (c.p + i / c.n)))
        out.append(circle(orbit * math.cos(a), orbit * math.sin(a), r, 0.5 * math.sin(a * 2)))
    return out


@routine('Tunnel')
def tunnel(c):                                # rings along the view axis: the camera flies through
    return [circle(0.0, 0.0, 0.65 * c.L, 1.5 - 3.0 * ((i / c.n - c.p * 0.5) % 1.0)) for i in range(c.n)]


@routine('Vortex')
def vortex(c):                                # one stroke winding down a funnel
    turns = 1 + (c.n - 1) / 2.0
    steps = int(RING * turns)
    pts = []
    for k in range(steps + 1):
        t = k / steps
        r = c.L * (0.08 + 0.92 * t) * (1 - 0.25 * c.b * math.sin(TAU * (3 * t + c.p)))
        a = TAU * (turns * t + c.p)
        pts.append((r * math.cos(a), r * math.sin(a), 1.0 - 2.0 * t))
    return [curve(pts)]


@routine('Fan')
def fan(c):                                   # short blades in a row, a wave running through
    blades = c.n + 2
    spread = 0.3 + 0.45 * c.w
    sweep = 0.25 * math.sin(TAU * c.p * 0.5)
    h = 0.08 + 0.25 * c.L
    out = []
    for i in range(blades):
        x = sweep + spread * (2 * i / (blades - 1) - 1)
        y = 0.3 * math.sin(TAU * (c.p + i / blades))
        z = 0.5 * math.cos(TAU * (c.p + i / blades))
        out.append(line(x, y - h, x, y + h, z, z, 7))
    return out


@routine('Scissors')
def scissors(c):                              # sheets crossing and opening
    out = []
    for i in range((c.n + 1) // 2):
        y = 0.8 * math.sin(TAU * (c.p + i / (c.n + 1)))
        z = 0.6 * math.cos(TAU * (c.p + i / (c.n + 1)))
        out += [line(-c.L, -y, c.L, y, -z, z), line(-c.L, y, c.L, -y, z, -z)]
    return out


@routine('Sheets')
def sheets(c):                                # a false ceiling, rising and falling
    out = []
    for i in range(c.n):
        phase = TAU * (c.p * 0.5 + i / c.n)
        y, tilt = 0.45 * math.sin(phase), 0.12 * math.cos(phase)
        out.append(line(-c.L, y - tilt, c.L, y + tilt, 0.8 * math.cos(phase), 0.8 * math.cos(phase)))
    return out


@routine('Wave')
def wave(c):                                  # one sheet with a wave travelling along it
    amp = 0.12 + 0.38 * c.w + 0.15 * c.b
    return [curve([(c.L * (2 * k / 64.0 - 1), amp * math.sin(TAU * (c.n * 0.5 * k / 64.0 + c.p)),
                    0.5 * math.cos(TAU * (c.n * 0.25 * k / 64.0 + c.p)))
                   for k in range(65)])]


@routine('Liquid Sky')
def liquid_sky(c):                            # a flat sheet with a slow ripple: the haze does the rest
    amp = 0.05 + 0.12 * c.w + 0.2 * c.b
    rise = 0.1 * math.sin(TAU * c.p * 0.2)

    def y(t):
        return rise + amp * (0.6 * math.sin(TAU * (c.n * 0.5 * t + c.p))
                             + 0.4 * math.sin(TAU * (c.n * 1.3 * t - c.p * 0.7)))
    return [curve([(c.L * (2 * k / 64.0 - 1), y(k / 64.0), 0.3 * math.sin(TAU * (k / 64.0 + c.p * 0.3)))
                   for k in range(65)])]


@routine('Curtain')
def curtain(c):                               # hanging sheets, swaying out of step
    sway = min(0.15, 0.25 / c.n)              # never as wide as the gap, or the sheets clump
    out = []
    for i in range(c.n):
        x = 0.7 * ((2 * i + 1) / c.n - 1) + sway * math.sin(TAU * (c.p + i / c.n))
        bow = 0.8 * sway * math.sin(TAU * (c.p * 0.7 + i / c.n))
        z = 0.5 * math.sin(TAU * (c.p * 0.5 + i / c.n))
        out.append(curve([(x + bow * math.sin(math.pi * k / 16.0), c.L * (2 * k / 16.0 - 1), z)
                          for k in range(17)]))
    return out


@routine('Knot')
def knot(c):                                  # one closed stroke in depth, always changing form
    a, b = KNOTS[c.n - 1]
    return [ring(lambda t: (c.L * math.sin(a * t + TAU * c.p), c.L * math.sin(b * t),
                            0.6 * c.L * math.cos((a + b) * t + TAU * c.p * 0.5)), steps=96)]

LOOP_SHARE = 0.35              # the most of the budget one contour may take


def keep_contours(lengths, centres, budget):
    """Indices of the contours worth drawing within the point budget, at least one if any
    exist. Traced contours are evenly spaced, so point count stands for length. Long and
    central ones win, but none may take over: a huge outer loop must not push out a face."""
    if not budget or not lengths:
        return list(range(len(lengths)))
    cap = budget * LOOP_SHARE

    def score(i):
        return min(lengths[i], cap) * max(0.05, 1 - min(1.0, math.hypot(*centres[i])) ** 2)

    keep, used = [], 0
    ranked = sorted(range(len(lengths)), key=score, reverse=True)
    for fits in (lambda n: n <= cap, lambda n: True):      # big loops take what is left
        for i in ranked:
            if i not in keep and fits(lengths[i]) and used + lengths[i] <= budget:
                keep.append(i)
                used += lengths[i]
    return keep or [min(range(len(lengths)), key=lambda k: lengths[k])]


# ------------------------------------------------------------------- build

def level(value):
    """(amp, freq, speed, spin) of the noise at a level, 0-3 with blends between."""
    i = min(2, int(value))
    t = value - i
    return tuple(a + (b - a) * t for a, b in zip(LEVELS[i], LEVELS[i + 1]))


def soft(x, y):
    """Keeps a point on the box: straight up to KNEE, then easing towards the edge and never
    past it, so a shape close to the camera wraps the view instead of being cut off."""
    r = math.hypot(x, y)
    if r <= KNEE:
        return x, y
    k = (KNEE + (1 - KNEE) * (1 - math.exp((KNEE - r) / (1 - KNEE)))) / r
    return x * k, y * k


def splat(fly):
    """0 at normal distance, 1 with the lens at its widest."""
    return max(0.0, min(1.0, (SPLAT_FROM - fly) / (SPLAT_FROM - SPLAT_FULL)))


def wide(x, y, near):
    """soft() opening into a wide lens as near goes to 1: the shape spreads over the whole square
    instead of crowding the edge."""
    sx, sy = soft(x, y)
    if not near:
        return sx, sy
    return (sx + (math.atan(x * SPLAT) * 2 / math.pi - sx) * near,
            sy + (math.atan(y * SPLAT) * 2 / math.pi - sy) * near)


def track(items, strength):
    """The track point: the middle of the drawing, moved to the centre of the view by strength
    0-1, so turning and zooming pivot on the shape itself."""
    pts = [pt for item in items for pt in item.pts]
    if not pts or not strength:
        return
    mid = [(min(p[i] for p in pts) + max(p[i] for p in pts)) / 2 * strength for i in range(3)]
    for item in items:
        item.pts = [(x - mid[0], y - mid[1], z - mid[2]) for x, y, z in item.pts]


def _view(item, raw, amp, freq, t, size, ox, oy):
    """Noise, turn and camera on one item. Only what passes behind the camera ends a part, so a
    shape is lost only when the camera reaches it."""
    d = raw.get('fly', CAMERA)
    near = splat(d)
    measuring = raw.get('measuring', False)
    across = size * raw.get('fill', 1.0)
    turn = TAU * (raw.get('yaw', 0.0) + raw.get('spin', 0.0))
    tilt = TAU * raw.get('pitch', 0.0)
    roll = TAU * raw['rot'] + raw.get('audio_rot', 0.0)
    cy, sy = math.cos(turn), math.sin(turn)
    cp, sp = math.cos(tilt), math.sin(tilt)
    cr, sr = math.cos(roll), math.sin(roll)
    panx, pany = raw.get('panx', 0.0), raw.get('pany', 0.0)
    parts, run = [], []
    closed = item.closed
    pts = item.pts + item.pts[:1] if closed else item.pts
    for x, y, z in pts:
        x, y, z = (x + amp * (math.sin(freq * y + t) + 0.5 * math.sin(2.3 * freq * z + 1.7 * t)),
                   y + amp * (math.sin(freq * z + 1.3 * t + 1.0) + 0.5 * math.sin(2.3 * freq * x - 1.1 * t)),
                   z + amp * (math.sin(freq * x - 0.9 * t + 2.0) + 0.5 * math.sin(2.3 * freq * y + 0.7 * t)))
        x, y, z = x * across, y * across, z * size   # fill never pushes depth past the camera
        x, z = x * cy + z * sy, z * cy - x * sy
        y, z = y * cp - z * sp, z * cp + y * sp
        x, y = x * cr - y * sr, x * sr + y * cr
        depth = d - z
        if depth > NEAR:
            k = CAMERA / depth
            px, py = x * k + ox + panx, y * k + oy + pany
            run.append((px, py) if measuring else wide(px, py, near))
            continue
        if len(run) > 1:
            parts.append(run)
        run = []
    if len(run) > 1:
        parts.append(run)
    if len(parts) == 1 and len(parts[0]) == len(pts):
        return [Item(item.type, parts[0][:-1] if closed else parts[0], closed, item.curved, item.color)]
    found = [Item(item.type, p, False, item.curved, item.color) for p in parts]
    return [i for i in found if i.length() >= MIN_PART]


def fit(items, ox, oy, budget=BUDGET):
    """Shrinks a drawing around (ox, oy) until it fits BUDGET, so a dense variant gets smaller
    instead of flickering. Blanked moves count too, and they do not shrink with it."""
    room = budget - JUMP * len(items)
    drawn = sum(item.length() for item in items)
    if drawn > room:
        k = room / drawn
        for item in items:
            item.pts = [(ox + (x - ox) * k, oy + (y - oy) * k) for x, y in item.pts]


def fill(raw):
    """The scale that makes this drawing fill the surface from the home camera, measured there
    with the soft edge off and no noise. Depth bends the size, so it takes a few passes."""
    scale = 1.0
    for _ in range(4):
        look = dict(raw, fly=CAMERA, fill=scale, nlevel=0.0, panx=0.0, pany=0.0, measuring=True)
        pts = [p for item in build(look) for p in item.pts]
        if not pts:
            break
        reach = max((max(p[i] for p in pts) - min(p[i] for p in pts)) / 2 for i in (0, 1))
        scale = max(FILL_MIN, min(FILL_MAX, scale * FILLED / max(reach, 1e-6)))
    return scale


def build(raw, audio=None):
    """Items of the selected routine, ready to draw in 2D. raw holds the controls by channel name
    (the camera and noise channels are optional); audio holds the band and noise channels plus
    Size, Move and Change, or is None when off."""
    w = raw['width']
    p = raw['phase']
    L = 0.15 + 0.85 * w
    size = 0.2 + 0.8 * raw['size']
    ox = oy = 0.0
    bend = 0.0
    amp, freq, _, _ = level(raw.get('nlevel', 0.0))
    if audio is not None:                     # low pumps, mid moves, high changes
        size *= 1 + 0.3 * audio['Size'] * audio['low']     # more goes off the box, and a kick blacks it out
        mv = audio['Move'] * (0.3 + 0.7 * audio['mid'])
        raw = dict(raw, audio_rot=mv * audio['nrot'] * math.pi)
        ox, oy = mv * 0.4 * audio['nx'], mv * 0.4 * audio['ny']
        ch = audio['Change'] * audio['high']
        p += ch * audio['nphase']
        L *= 1 + ch * 0.8 * audio['ny']
        bend = min(1.0, ch)
        amp *= 0.5 + 1.5 * audio['mid'] + raw.get('nlevel', 0.0) * 0.5 * audio['low']
        freq /= 1 + audio['low']              # bass makes the movement larger, as in laser2025
    fn = ROUTINES[int(raw['pattern']) % len(ROUTINES)][1]
    items = fn(Ctl(int(raw['variant']) % 8 + 1, w, p, L, bend))
    t = raw.get('ntime', 0.0)
    good = []
    for i, item in enumerate(items):
        item.pts = [pt if len(pt) == 3 else (pt[0], pt[1], 0.0) for pt in item.pts]
        if item.color is None:
            item.color = i
        if len(item.pts) > 1 and all(math.isfinite(v) for pt in item.pts for v in pt):
            good.append(item)                 # never hand a bad coordinate on
    fly = raw.get('fly', CAMERA)
    track(good, max(0.0, min(1.0, (CAMERA - fly) / (CAMERA - 1.5))))      # shapes keep their moves until you zoom
    out = []
    for item in good:
        out += _view(item, raw, amp, freq, t, size, ox, oy)
    fit(out, ox, oy, BUDGET * (1 + (SPLAT_BUDGET - 1) * splat(fly)))
    return out

def table(items):
    """Rows for the item table: one header, one row per item."""
    rows = [['id', 'type', 'color', 'x', 'y', 'x1', 'y1', 'length', 'points']]
    for i, item in enumerate(items):
        a, b = item.pts[0], item.pts[-1]
        rows.append([i, item.type, item.color, *(round(v, 4) for v in (*a, *b, item.length())),
                     len(item.pts)])
    return rows
