# What every button and stick does. Lives in laser_rig/joymap (Text DAT synced to this file).
# Full map: base_controller/README_buttons. To change a button, change event(): it takes a press
# and returns what changes. Speeds and limits are the numbers just below. Sticks and the L2, R2
# triggers are in frame(), press() and sticks() are the Video mode ones.
# No TD calls in here, so tests/test_joymap.py can run it outside TouchDesigner.

import math

COLOR_BUTTONS = {'b1': 'Mixgreen', 'b2': 'Mixred', 'b3': 'Mixblue'}     # A, B, X
SCANS = {('p1_Y', 1): 'down', ('p1_X', 1): 'engrave', ('p1_Y', -1): 'radar', ('p1_X', -1): 'iris'}
DEADZONE = 0.12
NOISE_KEYS = {'b6': 2}                   # R1; L2 and R2 are analog triggers, see frame()
HOME_FLY = 2.25                         # routines.CAMERA
FLY_MIN, FLY_MAX = 0.25, 12.0           # as laser2025; under 1 the camera is inside the shapes
PAN_MAX = 0.7                           # the shape's centre stays in the view
TURN_RATE, PAN_RATE = 1 / 6.0, 0.8     # turns a second: 60 degrees, as laser2025
FLY_IN, FLY_OUT = 0.35, 0.56            # out faster than in, in laser2025's ratio     # at full stick, a second
SHAPE_TAU, VIDEO_TAU = 0.35, 2.5        # how long the view takes to catch up with the stick
VIDEO_CAPS = dict(yaw=0.02, pitch=0.02, fly=0.1, panx=0.05, pany=0.05)       # and the video's top speed
NOISE_TAU = 0.4


def edge(value, previous):
    """-1 or 1 when a button or D-pad axis is pressed that way, else 0."""
    if value > 0.5 >= previous:
        return 1
    if value < -0.5 <= previous:
        return -1
    return 0


def stick(value):
    """Stick value with the resting wobble removed, still reaching 1 at full travel."""
    if abs(value) < DEADZONE:
        return 0.0
    sign = 1 if value > 0 else -1
    return sign * (abs(value) - DEADZONE) / (1 - DEADZONE)


def press(name, way, s):
    """New values after one press. s holds wipe, hold, frame and softness, floor, shift, drift.
    Returns only what changed; restart means run the scan from the start."""
    if (name, way) in SCANS:
        scan = SCANS[(name, way)]
        return {'wipe': 'off' if s['wipe'] == scan else scan, 'restart': True}
    if name == 'b6':
        return {'hold': not s['hold']}
    if name == 'b9':
        return {'reset': True}
    return {}



def event(name, way, shift, mode, s):
    """What one press does, before the Video mode buttons of press(). Menu held (shift) is the
    second layer. s holds pattern, count (how many patterns), noise, variant, tempo, blackout,
    freeze and points. None means the press is not handled here."""
    if name == 'b4':
        return {'blackout': 1 - s['blackout']}
    if name == 'b7':
        return {'tempo': s['tempo'] % 4 + 1}
    if name in COLOR_BUTTONS:
        return {'color': COLOR_BUTTONS[name]}
    if name == 'b5':
        return {} if shift else {'points': 1 - s['points']}
    if shift:
        if name == 'b6' and mode == 'shape':
            return {'freeze': 1 - s['freeze']}
        if name == 'b9':
            return {'move': 1 - s['move']}
        return {}
    if name == 'b10':
        return {'home': 'camera'}
    if mode != 'shape':
        return None
    if name == 'b9':
        return {'home': 'shape'}
    if name in NOISE_KEYS:
        level = NOISE_KEYS[name]
        return {'noise': 0 if s['noise'] == level else level}
    if name == 'p1_X':
        return {'pattern': (s['pattern'] + way) % s['count']}
    if name == 'p1_Y':
        return {'variant': (s['variant'] + way) % 8}
    return {}

def shape_home(s):
    """L3: the shape back in place, the left stick back on turning. A turn goes to the nearest
    whole turn, so it never unwinds through several."""
    return {'tyaw': float(round(s['tyaw'])), 'tpitch': float(round(s['tpitch'])), 'tpanx': 0.0, 'tpany': 0.0,
            'move': 0}


def camera_home(fill):
    """R3: the camera back, with the shape scaled by fill to fill the surface."""
    return {'tfly': HOME_FLY, 'tfill': fill}


def follow(value, target, dt, tau, cap=None):
    """value moved towards target, easing in over tau seconds, never faster than cap a second."""
    step = (target - value) * (1 - math.exp(-dt / tau))
    if cap is not None:
        step = max(-cap * dt, min(cap * dt, step))
    return value + step


def frame(s, sticks_now, lt, rt, dt, shift, mode, rates):
    """One frame of the view and the noise. sticks_now is (x, y, rx, ry), lt and rt the triggers,
    rates the (speed, spin) of the noise now. Shapes follow the stick quickly, the video slowly:
    the camera is shared, so in Shape mode the video drifts after the shapes."""
    x, y, rx, ry = (stick(v) for v in sticks_now)
    out = {}
    if mode == 'shape' and not shift:   # L2 level 1, R2 level 3, once per pull
        if lt > 0.5 >= s['lt']:
            out['noise'] = 0 if s['noise'] == 1 else 1
        if rt > 0.5 >= s['rt']:
            out['noise'] = 0 if s['noise'] == 3 else 3
    out['lt'], out['rt'] = lt, rt
    if (mode == 'shape') != shift:      # Video mode keeps its sticks unless Menu is held
        if s['move']:                   # L3 swaps the left stick between turning and moving
            out['tpanx'] = max(-PAN_MAX, min(PAN_MAX, s['tpanx'] + x * PAN_RATE * dt))
            out['tpany'] = max(-PAN_MAX, min(PAN_MAX, s['tpany'] + y * PAN_RATE * dt))
        else:
            out['tyaw'] = s['tyaw'] + x * TURN_RATE * dt
            out['tpitch'] = s['tpitch'] + y * TURN_RATE * dt
        out['tfly'] = max(FLY_MIN, min(FLY_MAX, s['tfly'] * math.exp(-ry * (FLY_IN if ry > 0 else FLY_OUT) * dt)))
    for name in ('yaw', 'pitch', 'fly', 'panx', 'pany'):
        target = out.get('t' + name, s['t' + name])
        out[name] = follow(s[name], target, dt, SHAPE_TAU)
        out['v' + name] = follow(s['v' + name], target, dt, VIDEO_TAU, VIDEO_CAPS[name])
    out['fill'] = follow(s['fill'], s['tfill'], dt, SHAPE_TAU)
    out['nlevel'] = follow(s['nlevel'], out.get('noise', s['noise']), dt, NOISE_TAU)
    if not s['freeze']:
        out['ntime'] = s['ntime'] + rates[0] * dt * math.tau
        out['spin'] = (s['spin'] + rates[1] * dt) % 1.0
    return out


def mix_text(red, green, blue):
    """The colour buttons as the readout shows them."""
    if not (red or green or blue):
        return 'OFF'
    names = {(1, 0, 0): 'RED', (0, 1, 0): 'GREEN', (0, 0, 1): 'BLUE', (1, 1, 0): 'YELLOW',
             (1, 0, 1): 'MAGENTA', (0, 1, 1): 'CYAN', (1, 1, 1): 'WHITE'}
    return names[(int(red), int(green), int(blue))]


def sticks(x, y, rx, ry, dt, s, scanning):
    """New values for one frame of stick movement; empty when the sticks rest.
    Left stick: X softness, Y black floor. Right stick: X level shift, and Y drift while no
    scan runs (a running scan takes right Y directly, as the scanner by hand)."""
    x, y, rx, ry = stick(x), stick(y), stick(rx), stick(ry)
    out = {}
    if x:
        out['softness'] = max(0.0, min(30.0, s['softness'] + x * 10 * dt))
    if y:
        out['floor'] = max(0.0, min(1.0, s['floor'] + y * 0.3 * dt))
    if rx:
        out['shift'] = (s['shift'] + rx * 0.5 * dt) % 1.0
    if ry and not scanning:
        out['drift'] = max(-1.0, min(1.0, s['drift'] + ry * 0.5 * dt))
    return out
