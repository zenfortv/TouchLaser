# Video colour for traced contours. Lives in laser_rig/colors (Text DAT synced to this file).
# Each contour point takes the colour of the video under it. A laser line has no dark grey:
# a dim pixel just gives a dim line, so Boost lifts every colour to full strength.
# No TD calls in here, so tests/test_colors.py can run it outside TouchDesigner.

import numpy as np

DARK = 0.03                    # darker than this has no colour worth keeping: use white
LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)


def sample(img, xs, ys, boost=1.0, saturation=1.0):
    """RGB in 0-1 for points in the [-1, 1] box. img is a TOP array: row 0 at the bottom,
    channels r g b (a). boost 0 keeps the video level, 1 lifts each colour to full."""
    h, w = img.shape[:2]
    col = np.clip(((np.asarray(xs) + 1) / 2 * w).astype(np.int32), 0, w - 1)
    row = np.clip(((np.asarray(ys) + 1) / 2 * h).astype(np.int32), 0, h - 1)
    rgb = img[row, col, :3].astype(np.float32)
    grey = rgb @ LUMA
    rgb = np.clip(grey[:, None] + (rgb - grey[:, None]) * saturation, 0, 1)
    peak = rgb.max(axis=1, keepdims=True)
    full = rgb / np.maximum(peak, 1e-6)
    out = rgb + (full - rgb) * boost
    out[peak[:, 0] < DARK] = 1.0
    return out
