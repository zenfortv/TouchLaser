# Surface warp. Lives in laser_rig/warp (Text DAT synced to this file).
# A surface blends its 4 corners, which stays inside the frame only while the quad is convex.
# Pull a corner past the diagonal and the blend lands outside. So a dented quad is cut along
# the diagonal through the dent: each half is a triangle, mapped flat, which cannot leave it.
# No TD calls in here, so tests/test_warp.py can run it outside TouchDesigner.
#
# Corners are in rig.CORNERS order: bl, br, tr, tl.

import math

REST = [(-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)]


def _turn(a, b, c):
    return (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])


def dent(quad):
    """Index of the corner pointing inwards, or None when the quad is convex. A crossed
    quad (bow tie) has no single dent and also gives None."""
    turns = [_turn(quad[i - 1], quad[i], quad[(i + 1) % 4]) for i in range(4)]
    area = sum(quad[i][0] * quad[(i + 1) % 4][1] - quad[(i + 1) % 4][0] * quad[i][1]
               for i in range(4))
    wrong = [i for i, t in enumerate(turns) if t * area < 0]
    return wrong[0] if len(wrong) == 1 else None


def normal(k):
    """Normal of the rest-space diagonal through corner k, pointing at corner k + 1."""
    a, b, side = REST[k], REST[(k + 2) % 4], REST[(k + 1) % 4]
    n = (-(b[1] - a[1]), b[0] - a[0])
    if n[0] * side[0] + n[1] * side[1] < 0:
        n = (-n[0], -n[1])
    return n


def half(quad, k, side):
    """Lattice corners for the half of the rest square holding corner k + side (side is 1 or
    -1). The corner across the diagonal becomes the parallelogram completion, which turns the
    4-corner blend into a flat map of that triangle."""
    a, b, c = quad[k], quad[(k + 2) % 4], quad[(k + side) % 4]
    out = list(quad)
    out[(k - side) % 4] = (a[0] + b[0] - c[0], a[1] + b[1] - c[1])
    return out


def centre(quad):
    return sum(c[0] for c in quad) / 4, sum(c[1] for c in quad) / 4


def turned(quad, start, now):
    """The quad spun around its centre by the angle the cursor made going from start to now."""
    cx, cy = centre(quad)
    a = math.atan2(now[1] - cy, now[0] - cx) - math.atan2(start[1] - cy, start[0] - cx)
    cs, sn = math.cos(a), math.sin(a)
    return [(cx + (x - cx) * cs - (y - cy) * sn, cy + (x - cx) * sn + (y - cy) * cs)
            for x, y in quad]


def blend(quad, x, y):
    """The lattice map: rest point (x, y) in [-1, 1] blended from 4 corners."""
    u, v = (x + 1) / 2, (y + 1) / 2
    bl, br, tr, tl = quad
    return tuple(bl[i] * (1 - u) * (1 - v) + br[i] * u * (1 - v) + tr[i] * u * v + tl[i] * (1 - u) * v
                 for i in (0, 1))
