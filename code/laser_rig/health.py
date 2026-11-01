# Project health. Lives in laser_rig/health (Text DAT synced to this file).
# Turns frame times and memory into one verdict and a line of text, once a second.
# No TD calls in here, so tests/test_health.py can run it outside TouchDesigner.

import collections
import ctypes
import sys

WINDOW = 5.0                   # seconds of frames behind the numbers
LEVELS = ('OK', 'WATCH', 'SLOW', 'DANGER')
COLORS = ((0.3, 0.9, 0.5), (0.95, 0.85, 0.3), (1.0, 0.55, 0.15), (1.0, 0.2, 0.2))


class Meter:
    """Frame times of the last WINDOW seconds, fed once per frame."""

    def __init__(self):
        self.frames = collections.deque()
        self.last = None
        self.reported = 0.0

    def tick(self, now):
        """Records a frame. True once a second, when it is time to report."""
        if self.last is not None:
            self.frames.append((now, now - self.last))
        self.last = now
        while self.frames and now - self.frames[0][0] > WINDOW:
            self.frames.popleft()
        if now - self.reported >= 1.0:
            self.reported = now
            return True
        return False

    def fps(self):
        total = sum(d for _, d in self.frames)
        return len(self.frames) / total if total else 0.0

    def worst(self):
        return max((d for _, d in self.frames), default=0.0) * 1000


def verdict(m):
    """(level 0-3, reason) from fps, worst (ms), target (fps), drops (per second), gpu and ram
    (used share, 0-1). The most serious problem wins."""
    if m['ram'] > 0.92:
        return 3, 'PC ALMOST OUT OF RAM'
    if m['gpu'] > 0.9:
        return 3, 'GPU MEMORY NEARLY FULL'
    if m['fps'] < 15:
        return 3, 'VERY LOW FPS'
    if m['ram'] > 0.85:
        return 2, 'RAM GETTING FULL'
    if m['gpu'] > 0.75:
        return 2, 'GPU MEMORY GETTING FULL'
    if m['fps'] < m['target'] * 0.5:
        return 2, 'LOW FPS'
    if m['worst'] > 250:
        return 2, 'BIG FREEZES'
    if m['fps'] < m['target'] * 0.8:
        return 1, 'BELOW TARGET'
    if m['drops'] > 2 or m['worst'] > 100:
        return 1, 'STUTTERS'
    return 0, ''


def text(m):
    level, reason = verdict(m)
    word = LEVELS[level] + (': ' + reason if reason else '')
    temp = '   GPU {:.0f}C'.format(m['temp']) if m.get('temp', 0) > 0 else ''
    return '{}   FPS {:.0f}/{:.0f}   WORST {:.0f}ms   DROPS {:.0f}/s   CPU {:.0f}ms   GPU {:.0f}%   RAM {:.0f}%{}'.format(
        word, m['fps'], m['target'], m['worst'], m['drops'], m['cpu'], m['gpu'] * 100,
        m['ram'] * 100, temp)


def ram_used():
    """Share of the PC's whole memory in use, 0-1; 0 where it cannot be read."""
    if sys.platform != 'win32':
        return 0.0

    class Status(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + \
                   [(n, ctypes.c_ulonglong) for n in ('total', 'free', 'pagetotal', 'pagefree',
                                                      'virtual', 'virtualfree', 'extended')]

    s = Status()
    s.length = ctypes.sizeof(Status)
    return s.load / 100.0 if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s)) else 0.0
