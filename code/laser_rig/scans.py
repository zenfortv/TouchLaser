# Scan shapes for Video mode. Lives in laser_rig/scans (Text DAT synced to this file).
# down, up, right, left, radar and iris reveal the image in contour_bands.glsl; here is the
# beam that leads them. engrave has no contours at all: like a laser engraving machine, a head
# runs along the rows one way then back, and burns a straight line wherever the image is lit.
# Phase runs 0-2 as in the shader: 0-1 reveals, 1-2 hides.
# No TD calls in here, so tests/test_scans.py can run it outside TouchDesigner.

import numpy as np

EDGE = 0.98                    # beams stop just inside the surface
HEAD = 0.03                    # half the length of the engraver's head
CIRCLE_POINTS = 48
MIN_LINE = 0.02                # shorter burns are noise


def _progress(phase):
    p = phase % 2.0
    return (p, False) if p < 1 else (p - 1, True)


def head(phase, rows):
    """Where the engraver is: row counted from the top, and x, y in the [-1, 1] box. Odd rows
    run right to left."""
    t, _ = _progress(phase)
    row = min(int(t * rows), rows - 1)
    along = t * rows - row
    x = 2 * along - 1
    return row, x if row % 2 == 0 else -x, 1 - (row + 0.5) * 2 / rows


def beam(kind, phase, rows):
    """The line that leads a scan: (points, closed), or None."""
    t, _ = _progress(phase)
    c = 2 * t - 1
    if kind == 'down':
        return [(-EDGE, -c), (EDGE, -c)], False
    if kind == 'up':
        return [(-EDGE, c), (EDGE, c)], False
    if kind == 'right':
        return [(c, -EDGE), (c, EDGE)], False
    if kind == 'left':
        return [(-c, -EDGE), (-c, EDGE)], False
    if kind == 'radar':                       # a spoke, clockwise from twelve o'clock
        a = t * 2 * np.pi
        s, k = float(np.sin(a)), float(np.cos(a))
        reach = EDGE / max(abs(s), abs(k))
        return [(0.0, 0.0), (s * reach, k * reach)], False
    if kind == 'iris':                        # a ring from the centre to the corners
        a = np.arange(CIRCLE_POINTS) / CIRCLE_POINTS * 2 * np.pi
        ring = np.stack((np.cos(a), np.sin(a)), axis=1) * t * 2 ** 0.5
        return np.clip(ring, -EDGE, EDGE), True
    if kind == 'engrave':
        _, x, y = head(phase, rows)
        return [(x - HEAD, y), (x + HEAD, y)], False
    return None


def engrave(mask, phase, rows, budget):
    """Burnt lines of a mask (uint8, row 0 at the bottom) as (points, ids): two points per line,
    in the head's order, so the scanners snake down the image. budget is the longest total
    of line, in canvas units; the shortest lines go first when there is too much."""
    h, w = mask.shape
    now, x, _ = head(phase, rows)
    _, hiding = _progress(phase)
    shown = np.arange(now + 1, rows) if hiding else np.arange(now + 1)
    if hiding:
        shown = np.append(now, shown)
    ys = 1 - (shown + 0.5) * 2 / rows
    picked = mask[np.clip(((ys + 1) / 2 * h).astype(np.int32), 0, h - 1)]

    edges = np.diff(np.pad(picked > 0, ((0, 0), (1, 1))).astype(np.int8), axis=1)
    on_row, on = np.nonzero(edges == 1)
    off_row, off = np.nonzero(edges == -1)
    row = shown[on_row]
    a = on * 2.0 / w - 1
    b = off * 2.0 / w - 1

    # the row under the head is only part done
    done_to_the_left = (now % 2 == 0) != hiding
    current = row == now
    if done_to_the_left:
        b = np.where(current, np.minimum(b, x), b)
    else:
        a = np.where(current, np.maximum(a, x), a)
    keep = b - a >= MIN_LINE
    row, a, b = row[keep], a[keep], b[keep]

    length = b - a
    if length.sum() > budget:
        longest = np.argsort(-length)
        fits = np.cumsum(length[longest]) <= budget
        chosen = np.sort(longest[fits])
        row, a, b = row[chosen], a[chosen], b[chosen]

    back = row % 2 == 1
    order = np.lexsort((np.where(back, -a, a), row))
    row, a, b, back = row[order], a[order], b[order], back[order]
    y = 1 - (row + 0.5) * 2 / rows
    first = np.where(back, b, a)
    last = np.where(back, a, b)
    pts = np.stack((first, y, last, y), axis=1).reshape(-1, 2).astype(np.float32)
    return pts, np.repeat(np.arange(len(a), dtype=np.float32), 2)
