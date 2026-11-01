# Contours from the band image, in place of the Trace SOP. Lives in laser_rig/contours
# (Text DAT synced to this file). The GPU does blur, contrast and bands; only the finished
# black and white image comes back here, and OpenCV follows its edges.
# No TD calls in here, so tests/test_contours.py can run it outside TouchDesigner.

import cv2
import numpy as np

MIN_PIXELS = 14                # shorter loops are noise, and cost scan time
POINT_UNITS = 0.04             # canvas length that one point of Max Points stands for


def extract(mask, detail):
    """Closed contours of a uint8 mask, row 0 at the bottom: (loops, lengths). A loop is an
    N x 2 float array in the [-1, 1] box; a length is in canvas units. detail is how far in
    pixels a simplified line may stray from the true edge."""
    h, w = mask.shape
    found, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    scale = np.array((2.0 / w, 2.0 / h), np.float32)
    half = np.array((0.5, 0.5), np.float32)
    loops, lengths = [], []
    for c in found:
        if len(c) < MIN_PIXELS:
            continue
        p = cv2.approxPolyDP(c, detail, True) if detail > 0 else c
        if len(p) > 2:
            loops.append((p[:, 0].astype(np.float32) + half) * scale - 1.0)
            lengths.append(cv2.arcLength(c, True) * scale[0])
    return loops, lengths


def budget(max_points):
    """Max Points as a length in canvas units, the same whatever the resolution."""
    return max_points * POINT_UNITS


def centre(loop):
    return float(loop[:, 0].mean()), float(loop[:, 1].mean())
