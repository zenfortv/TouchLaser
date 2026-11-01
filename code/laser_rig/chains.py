# A drawn line as geometry for other content. Lives in laser_rig/chains (Text DAT synced to this file).
# A chain is the dense path of a line, N x 2 on the canvas. These turn it into a shape (see canvas.py):
# mask() cuts content by it, along() bends content along it, hatch() and rings() fill it by themselves.
# No TD calls in here, so tests/test_chains.py can run it outside TouchDesigner.
#
# To add a fill: write a function here that returns a shape, then add it to the Fill menu on
# base_surfaces/line_template and to rig._chain_fill.

import numpy as np

MAX_LENGTH = 7.0               # longest fill on the canvas, about 30 Hz at Step Size 0.02
MAX_CORNERS = 120              # the chain is thinned to this for the inside test
PIECE = 0.03                   # content is cut into steps this long, so it follows the chain closely


def _empty():
    return (np.zeros((2, 2), np.float32), np.zeros((2, 3), np.float32), np.ones(2, np.float32),
            np.zeros(2, np.float32))


def _thin(chain):
    step = max(1, len(chain) // MAX_CORNERS)
    return chain[::step]


def inside(chain, pts):
    """True for each point inside the closed chain (even-odd rule)."""
    poly = _thin(chain)
    a, b = poly, np.roll(poly, -1, axis=0)
    x, y = pts[:, 0, None], pts[:, 1, None]
    crosses = (a[:, 1] > y) != (b[:, 1] > y)
    dy = b[:, 1] - a[:, 1]
    dy = np.where(dy == 0, 1e-9, dy)
    at = a[:, 0] + (y - a[:, 1]) * (b[:, 0] - a[:, 0]) / dy
    return ((crosses & (x < at)).sum(axis=1) % 2).astype(bool)


def _split(shape, keep):
    """Only the kept points; a gap starts a new line, so the laser blanks over it."""
    pts, rgb, flags, ids = shape
    if keep.sum() < 2:
        return _empty()
    new = np.concatenate(([0], np.cumsum((np.diff(keep.astype(np.int8)) != 0) | (np.diff(ids) != 0))))[keep]
    pts, rgb, flags = pts[keep], rgb[keep], flags[keep]
    alone = np.diff(new, prepend=-1, append=new[-1] + 1)
    single = (alone[:-1] != 0) & (alone[1:] != 0)    # a lone point would be a held dot
    if (~single).sum() < 2:
        return _empty()
    return pts[~single], rgb[~single], flags[~single], new[~single].astype(np.float32)


def _fit_box(pts, chain):
    low, high = chain.min(axis=0), chain.max(axis=0)
    return low + (pts + 1) / 2 * (high - low)


def _full(shape):
    """Content grown to reach the edge of its box, so a small shape still uses the whole chain."""
    pts, rgb, flags, ids = shape
    reach = np.abs(pts).max()
    return (pts / reach if 0 < reach < 1 else pts), rgb, flags, ids


def mask(shape, chain, divide):
    """Content from the [-1, 1] box, stretched over the chain, kept only inside it."""
    pts, rgb, flags, ids = divide(_full(shape), PIECE)
    placed = _fit_box(pts, chain).astype(np.float32)
    return _split((placed, rgb, flags, ids), inside(chain, placed))


def _walk(chain):
    seg = np.hypot(*np.diff(chain, axis=0).T)
    return np.concatenate(([0.0], np.cumsum(seg)))


def _point_at(chain, s, along_s):
    return np.stack((np.interp(s, along_s, chain[:, 0]), np.interp(s, along_s, chain[:, 1])), axis=1)


def along(shape, chain, closed, offset, width, divide):
    """Content bent along the chain: box x runs along it, box y steps off it by width. offset
    slides it, in whole lengths. On an open chain what runs off the end is not drawn."""
    pts, rgb, flags, ids = divide(_full(shape), PIECE)
    walk = _walk(chain)
    total = walk[-1]
    if total <= 0:
        return _empty()
    s = ((pts[:, 0] + 1) / 2 + offset) * total
    keep = np.ones(len(s), bool)
    if closed:
        s = s % total
    else:
        keep = (s >= 0) & (s <= total)
        s = np.clip(s, 0, total)
    place = _point_at(chain, s, walk)
    ahead = _point_at(chain, np.minimum(s + 0.02, total), walk) - _point_at(chain, np.maximum(s - 0.02, 0), walk)
    size = np.maximum(np.hypot(ahead[:, 0], ahead[:, 1]), 1e-6)[:, None]
    normal = np.stack((-ahead[:, 1], ahead[:, 0]), axis=1) / size
    out = (place + normal * (pts[:, 1:2] * width)).astype(np.float32)
    jump = np.append(np.hypot(*np.diff(out, axis=0).T) > 0.25, False)   # the seam of a closed chain
    if jump.any():
        ids = ids + np.concatenate(([0], np.cumsum(jump[:-1]))).astype(np.float32)
    return _split((out, rgb, flags, ids), keep)


def hatch(chain, rows, angle, scroll, colors):
    """Parallel lines across the inside of the chain, joined by blanking. angle in turns, scroll
    in rows. Rows are cut down until the whole fill fits MAX_LENGTH."""
    poly = _thin(chain)
    c, s = np.cos(angle * 2 * np.pi), np.sin(angle * 2 * np.pi)
    turn = np.array(((c, s), (-s, c)), np.float32)
    flat = poly @ turn.T
    low, high = flat[:, 1].min(), flat[:, 1].max()
    if high - low < 1e-6:
        return _empty()
    wide = flat[:, 0].max() - flat[:, 0].min()
    rows = max(2, min(rows, int(MAX_LENGTH / max(wide * 0.8, 0.05))))
    a, b = flat, np.roll(flat, -1, axis=0)
    gap = (high - low) / rows
    pts, rgb, ids = [], [], []
    for i in range(rows):
        y = low + ((i + scroll) % rows + 0.5) * gap
        hit = (a[:, 1] > y) != (b[:, 1] > y)
        xs = np.sort(a[hit, 0] + (y - a[hit, 1]) * (b[hit, 0] - a[hit, 0]) / (b[hit, 1] - a[hit, 1]))
        for x0, x1 in zip(xs[::2], xs[1::2]):
            if x1 - x0 < 0.02:
                continue
            ends = ((x0, y), (x1, y)) if i % 2 else ((x1, y), (x0, y))     # back and forth: shorter jumps
            pts += ends
            rgb += [colors[i % len(colors)]] * 2
            ids += [len(ids) // 2] * 2
    if not pts:
        return _empty()
    out = np.asarray(pts, np.float32) @ turn
    return out.astype(np.float32), np.asarray(rgb, np.float32), np.ones(len(out), np.float32), np.asarray(ids, np.float32)


def rings(chain, n, phase, colors):
    """Copies of the chain pulsing out from its middle. n is cut down to fit MAX_LENGTH."""
    if len(chain) < 3:
        return _empty()
    middle = chain.mean(axis=0)
    total = _walk(np.vstack((chain, chain[:1])))[-1]
    n = max(1, min(n, int(2 * MAX_LENGTH / max(total, 0.05))))
    step = max(1, len(chain) // 90)
    loop = np.vstack((chain[::step], chain[:1]))
    pts, rgb, ids = [], [], []
    for i in range(n):
        scale = 0.1 + 0.9 * (((i / n) + phase) % 1.0)
        pts.append(middle + (loop - middle) * scale)
        rgb.append(np.tile(np.asarray(colors[i % len(colors)], np.float32), (len(loop), 1)))
        ids.append(np.full(len(loop), i, np.float32))
    return (np.concatenate(pts).astype(np.float32), np.concatenate(rgb), np.zeros(len(loop) * n, np.float32),
            np.concatenate(ids))
