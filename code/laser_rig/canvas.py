# Shapes from source to laser, in bulk. Lives in laser_rig/canvas (Text DAT synced to this file).
# A shape is (pts, rgb, corners, ids): N x 2 positions, N x 3 colours, N corner flags, N line
# ids; one shape can hold many lines, and is warped as one array. The Laser CHOP is a CPU
# signal, so points stay here: a trip through the GPU costs far more in waiting for the readback
# than the maths it saves. The GPU keeps the image work and draws the preview.
# No TD calls in here, so tests/test_canvas.py can run it outside TouchDesigner.

import numpy as np

CHANNELS = 8                   # x, y, r, g, b, id, lascorner, line start
DENT_STEP = 0.08               # longest segment on a dented surface
KNEE = 0.8                     # routines.KNEE
POINT_GAP = 0.09               # canvas distance between points along a line
POINT_LEN = 0.012              # length of one point: a tiny stroke, so the beam never sits still
MAX_POINTS = 150               # the most points in a shape; the gap opens to fit
EMPTY = (np.zeros((2, 2), np.float32), np.zeros((2, 3), np.float32), np.ones(2, np.float32),
         np.zeros(2, np.float32))    # one dark line, so the laser always has something to read


def shape(pts, rgb, closed=False, corners=None):
    """A shape from a point list. rgb is one colour, or one per point."""
    pts = np.asarray(pts, np.float32).reshape(-1, 2)
    flags = np.ones(len(pts), np.float32) if corners is None else np.asarray(corners, np.float32)
    colors = np.asarray(rgb, np.float32)
    if colors.ndim == 1:
        colors = np.tile(colors, (len(pts), 1))
    if closed and len(pts):
        pts, colors = np.vstack((pts, pts[:1])), np.vstack((colors, colors[:1]))
        flags = np.append(flags, flags[0])
    return pts, colors, flags, np.zeros(len(pts), np.float32)


def join(shapes):
    """Many shapes as one, every line keeping its own id."""
    shapes = [s for s in shapes if len(s[0]) > 1]
    if not shapes:
        return EMPTY
    offsets = np.cumsum([0] + [s[3].max() + 1 for s in shapes[:-1]])
    return (np.concatenate([s[0] for s in shapes]), np.concatenate([s[1] for s in shapes]),
            np.concatenate([s[2] for s in shapes]),
            np.concatenate([s[3] + d for s, d in zip(shapes, offsets)]))


def divide(s, step):
    """Adds points so no segment of a line is longer than step, so straight lines can follow
    a crease."""
    pts, rgb, flags, ids = s
    if len(pts) < 2:
        return s
    extra = np.ceil(np.hypot(*np.diff(pts, axis=0).T) / step).astype(np.int64)
    extra[np.diff(ids) != 0] = 1                # nothing between two lines
    if extra.max() <= 1:
        return s
    index = np.repeat(np.arange(len(pts) - 1), extra)
    t = np.concatenate([np.arange(n) / n for n in extra]).astype(np.float32)
    mix = t[:, None]
    new_pts = np.vstack((pts[index] * (1 - mix) + pts[index + 1] * mix, pts[-1:]))
    new_rgb = np.vstack((rgb[index] * (1 - mix) + rgb[index + 1] * mix, rgb[-1:]))
    new_flags = np.append(np.where(t == 0, flags[index], 0), flags[-1])
    return new_pts, new_rgb, new_flags.astype(np.float32), np.append(ids[index], ids[-1])


def _blend(quad, p):
    u, v = (p[:, 0:1] + 1) / 2, (p[:, 1:2] + 1) / 2
    bl, br, tr, tl = (np.asarray(c, np.float32) for c in quad)
    return bl * (1 - u) * (1 - v) + br * u * (1 - v) + tr * u * v + tl * (1 - u) * v


def view(s, yaw, pitch, fly, panx, pany, home=2.25):
    """A flat shape (the video) seen through the camera. yaw and pitch in turns, fly the camera's
    distance, drawn at true size from home."""
    pts, rgb, flags, ids = s
    if not (yaw or pitch or panx or pany) and fly == home:
        return s
    cy, sy, cp, sp = np.cos(yaw * 2 * np.pi), np.sin(yaw * 2 * np.pi), np.cos(pitch * 2 * np.pi), np.sin(pitch * 2 * np.pi)
    x, z = pts[:, 0] * cy, -pts[:, 0] * sy
    y, z = pts[:, 1] * cp - z * sp, z * cp + pts[:, 1] * sp
    depth = fly - z
    k = home / np.maximum(depth, 0.08)
    out = np.stack((x * k + panx, y * k + pany), axis=1)
    r = np.maximum(np.hypot(out[:, 0], out[:, 1]), 1e-9)   # same soft edge as routines.soft
    over = r > KNEE
    out[over] *= ((KNEE + (1 - KNEE) * (1 - np.exp((KNEE - r[over]) / (1 - KNEE)))) / r[over])[:, None]
    return (out.astype(np.float32), np.where(depth[:, None] < 0.08, 0.0, rgb).astype(np.float32), flags, ids)


def points(s):
    """A shape as points along its lines: same place, same colours, far less lit length. Each
    point is a tiny stroke with its own id, so the Laser CHOP blanks between them, and carries no
    corner flag, so it adds no hold. Dark stretches give no points."""
    pts, rgb, flags, ids = s
    if len(pts) < 2:
        return s
    seg = np.hypot(*np.diff(pts, axis=0).T)
    seg[np.diff(ids) != 0] = 0                  # no travel between two lines
    along = np.concatenate(([0.0], np.cumsum(seg)))
    gap = max(POINT_GAP, along[-1] / MAX_POINTS)
    marks = np.arange(0.0, along[-1], gap)
    if not len(marks):
        return EMPTY
    at = np.clip(np.searchsorted(along, marks, side='right') - 1, 0, len(pts) - 2)
    keep = (ids[at] == ids[at + 1]) & (seg[at] > 0) & (rgb[at].sum(axis=1) > 0)
    at, marks = at[keep], marks[keep]
    if not len(at):
        return EMPTY
    d = (pts[at + 1] - pts[at]) / seg[at, None]
    start = pts[at] + d * (marks - along[at])[:, None]
    n = len(at)
    out = np.empty((n * 2, 2), np.float32)
    out[::2], out[1::2] = start, start + d * POINT_LEN
    return (out, np.repeat(rgb[at], 2, axis=0), np.zeros(n * 2, np.float32),
            np.repeat(np.arange(n, dtype=np.float32), 2))


def warp(s, quad, wp, clip=False, tint=(1.0, 1.0, 1.0)):
    """A shape in the [-1, 1] box onto a surface's corners. wp is the warp module, for dented
    surfaces. clip blanks what leaves the box, for sources that can."""
    k = wp.dent(quad)
    if k is not None:
        s = divide(s, DENT_STEP)
    pts, rgb, flags, ids = s
    rgb = rgb * np.asarray(tint, np.float32)
    if clip:
        inside = np.clip(pts, -1, 1)
        rgb = np.where((inside == pts).all(axis=1, keepdims=True), rgb, 0)
        pts = inside
    if k is None:
        return _blend(quad, pts), rgb, flags, ids
    n = wp.normal(k)
    side = (pts[:, 0] * n[0] + pts[:, 1] * n[1] >= 0)[:, None]
    return np.where(side, _blend(wp.half(quad, k, 1), pts), _blend(wp.half(quad, k, -1), pts)), rgb, flags, ids


def paint(s, mix):
    """Every lit point in one colour, each keeping its brightness, dark stays dark."""
    pts, rgb, flags, ids = s
    return pts, rgb.max(axis=1, keepdims=True) * np.asarray(mix, np.float32), flags, ids


def pack(shape_, rect=None, flip=(1, 1)):
    """8 x N array for the laser and its preview. rect (x, y, w, h) maps that part of the canvas to
    the scan area, and what falls outside goes dark at its edge."""
    pts, rgb, flags, ids = shape_
    if rect is not None:
        pts = (pts - np.array(rect[:2], np.float32)) * 2 / np.array(rect[2:], np.float32)
        inside = np.clip(pts, -1, 1)
        rgb = np.where((inside == pts).all(axis=1, keepdims=True), rgb, 0)
        pts = inside * np.array(flip, np.float32)
    out = np.vstack((pts.T, rgb.T, ids, flags, starts(ids)))
    return np.ascontiguousarray(out, dtype=np.float32)      # copyNumpyArray needs tight rows


def starts(ids):
    """1 at the first point of each shape, for the preview's line strips."""
    return np.concatenate(([1.0], (np.diff(ids) != 0).astype(np.float32)))
