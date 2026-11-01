# Main panel layout from the real window size. Lives in laser_rig/layout (Text DAT synced to
# this file). TD's window values keep the size the window opened at, so a maximized window just
# scales a fixed panel; Windows knows the real size. The view stays square, because the mouse and
# camera assume it, and takes what the settings column and toolbar leave.
# No TD calls in here, so tests/test_layout.py can run it outside TouchDesigner.

import ctypes
import os
import sys

SETTINGS_W = 420
TOOLBAR_H = 40
MIN_SIZE = (1180, 800)
WHEEL_STEP = 90    # pixels per wheel notch


def sizes(width, height):
    """Panel sizes for a window of this size; TD panels count y up from the bottom."""
    w, h = max(width, MIN_SIZE[0]), max(height, MIN_SIZE[1])
    column = w - SETTINGS_W
    side = min(column, h - TOOLBAR_H)
    return dict(w=w, h=h, column=column, side=side, view_x=(column - side) // 2,
                view_y=h - TOOLBAR_H - side, toolbar_y=h - TOOLBAR_H)


def scrolled(scroll, notches, content_h, view_h):
    """New scroll position (0 top, 1 bottom) after the wheel moves; away from the user is up.
    The step is in pixels, so the speed stays the same when panels fold or get added."""
    room = content_h - view_h
    if room <= 0:
        return scroll
    return min(1.0, max(0.0, scroll - notches * WHEEL_STEP / room))


def client_size():
    """Inside size of this program's visible window, or None if it has none or this is not
    Windows."""
    if sys.platform != 'win32':
        return None
    from ctypes import wintypes
    user = ctypes.windll.user32
    found = []

    def check(hwnd, _):
        pid = wintypes.DWORD()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == os.getpid() and user.IsWindowVisible(hwnd):
            rect = wintypes.RECT()
            user.GetClientRect(hwnd, ctypes.byref(rect))
            found.append((rect.right, rect.bottom))
        return True

    user.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(check), 0)
    return max(found, default=None)
