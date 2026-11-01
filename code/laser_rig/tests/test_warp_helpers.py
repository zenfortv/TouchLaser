# Point in polygon, shared by the warp and canvas tests.


def inside(quad, p, tol=1e-6):
    """Point in polygon by winding, with a tolerance band along the edges."""
    w = False
    for i in range(4):
        a, b = quad[i], quad[(i + 1) % 4]
        d = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
        if d:
            t = max(0, min(1, ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / d ** 2))
            if ((p[0] - a[0] - t * (b[0] - a[0])) ** 2 + (p[1] - a[1] - t * (b[1] - a[1])) ** 2) ** 0.5 < tol:
                return True
        if (a[1] > p[1]) != (b[1] > p[1]) and p[0] < a[0] + (p[1] - a[1]) / (b[1] - a[1]) * (b[0] - a[0]):
            w = not w
    return w
