# Laser rig manager. Lives in laser_rig/rig (Text DAT synced to this file).
# Per frame only the joystick generators run (cook_line_points, cook_linecolor):
# a few dozen values each. Everything else cooks when something is edited.
# The joystick shapes are built as an item list in laser_rig/routines (routines.py).
#
# Three kinds of item share one canvas:
#   laser    a rectangle; what falls inside it is scanned by that laser
#   surface  a quad (4 free corners) showing a source
#   line     a path drawn point by point, coloured along its length by a source

import json
import math
import os
import time

import numpy as np

RIG = me.parent()

VIEW_HALF = 1.7            # half-width of the view camera, in canvas units
HANDLE = 0.07              # pick radius of a handle
DOUBLE_CLICK = 0.4         # seconds between two clicks on a corner handle
PICK_LINE = 0.06           # pick distance from a line's path
MIN_SIZE = 0.1
LINE_STEP = 0.04           # spacing of the points along a line
LINE_SAMPLES = 64          # samples of the colour CHOPs that feed lines
CORNERS = ['bl', 'br', 'tr', 'tl']
KINDS = {'laser': ('base_lasers', 'laser_template'),
         'surface': ('base_surfaces', 'surface_template'),
         'line': ('base_surfaces', 'line_template')}
PAGES = {'laser': ('Laser', 'Rect'), 'surface': ('Surface', 'Corners'), 'line': ('Line',)}
TITLES = {'laser': 'Laser', 'surface': 'Surface', 'line': 'Line'}
RANK = {'laser': 1, 'surface': 2, 'line': 3}
BODY_H = {'laser': 610, 'surface': 300, 'line': 340}
VIEW_COLOR = {'laser': (1.0, 0.55, 0.1), 'surface': (0.2, 0.75, 1.0), 'line': (0.4, 1.0, 0.5)}

# Fixed colour sets, stepped by the palette control; lines alternate through a set.
R, G, B, W = (1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 1)
C, M, Y = (0, 1, 1), (1, 0, 1), (1, 1, 0)
PALETTES = [(W,), (R,), (G,), (B,), (C, M), (R, B), (Y, C), (R, G, B), (W, R), (G, M)]
CONTROL_CHANS = ('pattern', 'variant', 'width', 'phase', 'rot', 'size')
JOY_CHANS = ('pattern', 'variant', 'blackout', 'freeze', 'tempo', 'audiooff', 'noise', 'nlevel', 'ntime', 'spin',
             'yaw', 'pitch', 'fly', 'panx', 'tyaw', 'tpitch', 'tfly', 'tpanx', 'vyaw', 'vpitch', 'vfly', 'vpanx',
             'menuused', 'rt', 'lt', 'points', 'move', 'pany', 'tpany', 'vpany', 'fill', 'tfill')
AUDIO_CHANS = ('low', 'mid', 'high', 'nx', 'ny', 'nrot', 'nphase')
WAVE_EVERY = 6             # the monitor redraws every this many frames

_SEG = {'a': ((-0.5, 1), (0.5, 1)), 'b': ((0.5, 1), (0.5, 0)),
        'c': ((0.5, 0), (0.5, -1)), 'd': ((-0.5, -1), (0.5, -1)),
        'e': ((-0.5, 0), (-0.5, -1)), 'f': ((-0.5, 1), (-0.5, 0)),
        'g': ((-0.5, 0), (0.5, 0))}
_DIGITS = {0: 'abcdef', 1: 'bc', 2: 'abged', 3: 'abgcd', 4: 'fgbc',
           5: 'afgcd', 6: 'afgedc', 7: 'abc', 8: 'abcdefg', 9: 'abfgcd'}


# ------------------------------------------------------------- lookups

def items(kind):
    base = RIG.op(KINDS[kind][0])
    found = base.findChildren(name=kind + '[0-9]*', depth=1)
    return sorted(found, key=lambda o: o.digits)


def selected():
    path = RIG.par.Selected.eval()
    return RIG.op(path) if path else None


def _kind(o):
    for kind in KINDS:
        if o.name.startswith(kind):
            return kind
    return None


def _rect(o):
    return (o.par.Posx.eval(), o.par.Posy.eval(), o.par.Sizex.eval(), o.par.Sizey.eval())


def _quad(o):
    return [(o.par['C' + c + 'x'].eval(), o.par['C' + c + 'y'].eval()) for c in CORNERS]


def _set_quad(o, quad):
    for c, (x, y) in zip(CORNERS, quad):
        o.par['C' + c + 'x'], o.par['C' + c + 'y'] = x, y


def _points(o):
    """[(x, y, curve)] of a line, from its table_points."""
    return [(float(r[0].val), float(r[1].val), int(r[2].val))
            for r in o.op('table_points').rows()[1:]]


def _set_points(o, pts):
    tbl = o.op('table_points')
    tbl.clear()
    tbl.appendRow(['x', 'y', 'curve'])
    for x, y, c in pts:
        tbl.appendRow([round(x, 4), round(y, 4), int(c)])


def _handles(o):
    """Draggable points of an item: [(x, y)]."""
    kind = _kind(o)
    if kind == 'laser':
        x, y, w, h = _rect(o)
        return _box(x, y, w / 2, h / 2)
    if kind == 'surface':
        return _quad(o)
    return [(x, y) for x, y, _ in _points(o)]


# --------------------------------------------------------- SOP helpers

def _begin(scriptOp):
    scriptOp.clear()
    scriptOp.pointAttribs.create('Cd')
    scriptOp.pointAttribs.create('LasCorner', 1)


def _emit(scriptOp, pts, col, closed=False, corners=None):
    """One polyline. corners flags the points the Laser CHOP holds on (1); guide
    points (0) are passed through without stopping. Default: every point is a corner."""
    pts = list(pts)
    corners = list(corners) if corners else [1] * len(pts)
    if closed and pts:
        pts.append(pts[0])
        corners.append(corners[0])
    if len(pts) < 2:
        return
    poly = scriptOp.appendPoly(len(pts), closed=False, addPoints=True)
    for k, (x, y) in enumerate(pts):
        p = poly[k].point
        p.P = (x, y, 0.0)
        p.Cd = (col[0], col[1], col[2], 1.0)
        p.LasCorner = corners[k]


def _box(cx, cy, hw, hh):
    return [(cx - hw, cy - hh), (cx + hw, cy - hh), (cx + hw, cy + hh), (cx - hw, cy + hh)]


def _diamond(cx, cy, h):
    return [(cx - h, cy), (cx, cy - h), (cx + h, cy), (cx, cy + h)]


def _round(cx, cy, r):
    return [(cx + r * math.cos(a * math.pi / 6), cy + r * math.sin(a * math.pi / 6)) for a in range(12)]


def _digits(n, cx, cy, h):
    """7-segment strokes for a number, centred on (cx, cy), digit height 2h."""
    text = str(int(n))
    out = []
    for i, ch in enumerate(text):
        ox = cx + (i - (len(text) - 1) / 2.0) * h * 1.6
        for seg in _DIGITS[int(ch)]:
            a, b = _SEG[seg]
            out.append([(ox + a[0] * h, cy + a[1] * h), (ox + b[0] * h, cy + b[1] * h)])
    return out


# ------------------------------------------ joystick generators (per frame)

def _controls():
    return RIG.op('base_controller/null_controls')


def _raw():
    """The controls and the pad's state, for routines.build."""
    c = _controls()
    raw = {k: c[k].eval() for k in CONTROL_CHANS}
    raw.update(_joy())
    raw['pattern'], raw['variant'] = c['pattern'].eval(), c['variant'].eval()
    return raw


def _frame():
    """This frame's items from routines.build, plus an error text. A failing routine
    draws nothing, so a bad edit blanks the shape instead of reaching the scanners."""
    c = _controls()
    raw = _raw()
    audio = None
    au = _audio()
    if au is not None:
        ap = RIG.op('base_audio').par
        audio = {k: au[k].eval() for k in AUDIO_CHANS}
        audio.update(Size=ap.Size.eval(), Move=ap.Move.eval(), Change=ap.Change.eval())
    try:
        return RIG.op('routines').module.build(raw, audio), ''
    except Exception as e:
        return [], '{}: {}'.format(type(e).__name__, e)


def _store_stats(items, error):
    stats = (len(items), round(sum(item.length() for item in items), 1), error)
    last = RIG.fetch('Itemstats', None, search=False)
    if stats != last:
        if error and error != (last or (0, 0, ''))[2]:
            print('Laser rig routine failed ->', error)
        RIG.store('Itemstats', stats)


def cook_items(scriptOp):
    """base_lines/script_items: the current item list as a table. Cooks only while viewed."""
    scriptOp.clear()
    for row in RIG.op('routines').module.table(_frame()[0]):
        scriptOp.appendRow(row)


def _audio():
    """base_audio/null_audio when audio-reactive is on (panel Active + Menu button), else None."""
    a = RIG.op('base_audio/null_audio')
    if a is None or a['on'].eval() < 0.5:
        return None
    return a


def cook_linecolor(scriptOp):
    """Colour along a line for the joystick source: dashes running along it.
    variant = number of dashes, width = dash length, palette = colours."""
    c = _controls()
    n = int(c['variant'].eval()) % 8 + 1
    cols = np.array(PALETTES[int(c['palette'].eval()) % len(PALETTES)], dtype=np.float32)
    duty = 0.5 + 0.5 * c['width'].eval()       # never under half, or a line looks dead
    t = np.arange(LINE_SAMPLES, dtype=np.float32) / LINE_SAMPLES * n - c['phase'].eval() * n
    on = ((t % 1.0) < duty).astype(np.float32)
    rgb = cols[np.floor(t).astype(np.int64) % len(cols)] * on[:, None]
    scriptOp.clear()
    scriptOp.numSamples = LINE_SAMPLES
    for i, name in enumerate('rgb'):
        scriptOp.appendChan(name).vals = rgb[:, i].tolist()


def _extra_shapes():
    """The scan's beam and the frame."""
    e = RIG.op('base_edges')
    cv = RIG.op('canvas').module
    out = []
    if e.par.Frame.eval():
        out.append(cv.shape(_box(0.0, 0.0, 0.98, 0.98), W, closed=True))
    if e.par.Beam.eval():
        beam = RIG.op('scans').module.beam(e.par.Wipe.eval(), e.op('null_fx')['wipe'].eval(),
                                           e.par.Engraverows.eval())
        if beam:
            out.append(cv.shape(beam[0], W, closed=beam[1]))
    return out


_READS = {}


def _read(top):
    """A TOP's pixels without stalling on the GPU: a frame late, or the last ones while the
    delayed read catches up. A plain read only when there is nothing yet to show."""
    pixels = top.numpyArray(delayed=True)
    if pixels is None:
        pixels = _READS.get(top.path)
    if pixels is None:
        pixels = top.numpyArray()
    _READS[top.path] = pixels
    return pixels


def _engrave_shape(source, mask):
    """The engraver's burnt lines, coloured like the contours."""
    e = RIG.op('base_edges')
    cv = RIG.op('canvas').module
    pts, ids = RIG.op('scans').module.engrave(mask, e.op('null_fx')['wipe'].eval(), e.par.Engraverows.eval(),
                                              RIG.op('contours').module.budget(e.par.Maxpoints.eval()))
    colorset = e.par.Colorset.menuIndex
    if colorset:
        cols = np.array(PALETTES[colorset - 1], np.float32)
        rgb = cols[ids.astype(np.int64) % len(cols)]
    else:
        rgb = RIG.op('colors').module.sample(_read(e.op('null_points_' + source)), pts[:, 0], pts[:, 1],
                                             e.par.Colorboost.eval(), e.par.Colorsat.eval())
    return cv.join([(pts, rgb, np.ones(len(pts), np.float32), ids)] + _extra_shapes())


def _video_shape(source):
    """Contours of the band image within the Max Points budget, coloured from the video or
    a palette. The GPU has done the image work; this finds the lines in the finished mask."""
    e = RIG.op('base_edges')
    ct = RIG.op('contours').module
    cv = RIG.op('canvas').module
    mask = (_read(e.op('null_top_' + source))[:, :, 0] > 0.5).astype(np.uint8)
    if e.par.Wipe.eval() == 'engrave':
        return _engrave_shape(source, mask)
    loops, lengths = ct.extract(mask, e.par.Edgestep.eval() / 7.0)
    keep = RIG.op('routines').module.keep_contours(lengths, [ct.centre(p) for p in loops],
                                                   ct.budget(e.par.Maxpoints.eval()))
    loops = [loops[i] for i in sorted(keep)]
    colorset = e.par.Colorset.menuIndex
    if colorset:                                            # a palette, one colour per contour
        cols = PALETTES[colorset - 1]
        rgb = [cols[i % len(cols)] for i in range(len(loops))]
    elif loops:
        joined = np.concatenate(loops)
        rgb = np.split(RIG.op('colors').module.sample(_read(e.op('null_points_' + source)),
                                                      joined[:, 0], joined[:, 1],
                                                      e.par.Colorboost.eval(), e.par.Colorsat.eval()),
                       np.cumsum([len(p) for p in loops])[:-1])
    else:
        rgb = []
    return cv.join([cv.shape(p, c, closed=True, corners=np.zeros(len(p)))
                    for p, c in zip(loops, rgb)] + _extra_shapes())


def _lines_shape():
    """The joystick item list."""
    cv = RIG.op('canvas').module
    found, error = _frame()
    cols = PALETTES[int(_controls()['palette'].eval()) % len(PALETTES)]
    _store_stats(found, error)
    return cv.join([cv.shape(i.pts, cols[i.color % len(cols)], i.closed, i.corners()) for i in found])


_SHAPES = {}


def _source(name):
    """A source's shape, built once a frame however many surfaces show it."""
    now = absTime.frame
    if name not in _SHAPES or _SHAPES[name][0] != now:
        _SHAPES[name] = (now, _lines_shape() if name == 'lines' else _viewed_video(name))
    return _SHAPES[name][1]


def _viewed_video(name):
    """The video's contours through its own, slower camera."""
    s = _joy()
    return RIG.op('canvas').module.view(_video_shape(name), s['vyaw'], s['vpitch'], s['vfly'], s['vpanx'], s['vpany'])


def _item_shape(o):
    """A surface or a drawn line on the canvas."""
    cv = RIG.op('canvas').module
    if _kind(o) == 'line':
        points = o.op('out1').points
        if len(points) < 2:
            return cv.EMPTY
        outline = cv.shape([(p.x, p.y) for p in points], [(p.Cd[0], p.Cd[1], p.Cd[2]) for p in points],
                           corners=[p.LasCorner[0] for p in points])
        fill = o.par.Fill.eval()
        if fill != 'outline':
            filled = _chain_fill(o, fill, outline)
            outline = cv.join([filled, outline]) if o.par.Keepline.eval() else filled
        return cv.points(outline) if _joy()['points'] else outline
    p = o.par
    source = p.Source.eval()
    d = p.Dim.eval()
    shape = cv.warp(_source(source), _quad(o), RIG.op('warp').module, clip=True,
                    tint=(p.Colorr.eval() * d, p.Colorg.eval() * d, p.Colorb.eval() * d))
    return cv.points(shape) if _joy()['points'] else shape


def _chain_fill(o, fill, outline):
    """What fills a drawn line, by chains.py. The joystick plays it like a surface: variant, speed,
    rotation and colours. An open line cannot hold a mask, hatch or rings, so it bends along."""
    cv = RIG.op('canvas').module
    ch = RIG.op('chains').module
    c = _controls()
    chain = outline[0]
    closed = bool(o.par.Closed.eval()) and len(chain) > 3
    colors = PALETTES[int(c['palette'].eval()) % len(PALETTES)]
    n = int(c['variant'].eval()) % 8 + 1
    phase = c['phase'].eval()
    d = o.par.Dim.eval()
    if closed and fill == 'hatch':
        shape = ch.hatch(chain, n * 4, c['rot'].eval(), phase * n * 2, colors)
    elif closed and fill == 'rings':
        shape = ch.rings(chain, n, phase, colors)
    else:
        source = o.par.Source.eval()
        content = _source('lines' if source == 'joystick' else source)
        if closed and fill == 'mask':
            shape = ch.mask(content, chain, cv.divide)
        else:
            shape = ch.along(content, chain, closed, phase * 0.25, o.par.Fillwidth.eval(), cv.divide)
    return shape[0], shape[1] * d, shape[2], shape[3]


def _over(laser):
    """The surfaces and lines over a laser's rectangle."""
    x, y, w, h = _rect(laser)
    out = []
    for o in items('surface') + items('line'):
        pts = _handles(o)
        if pts and min(p[0] for p in pts) < x + w / 2 and max(p[0] for p in pts) > x - w / 2 \
                and min(p[1] for p in pts) < y + h / 2 and max(p[1] for p in pts) > y - h / 2:
            out.append(o)
    return out


def _painted(shape):
    """The colour buttons, over whatever the source's own colours are."""
    p = RIG.par
    if not (p.Mixred.eval() or p.Mixgreen.eval() or p.Mixblue.eval()):
        return shape
    mix = (float(p.Mixred.eval()), float(p.Mixgreen.eval()), float(p.Mixblue.eval()))
    return RIG.op('canvas').module.paint(shape, mix)


def cook_laser(scriptOp, laser):
    """laserN/script_laser: what this laser draws, in its own scan space."""
    cv = RIG.op('canvas').module
    flip = (-1 if laser.par.Flipx.eval() else 1, -1 if laser.par.Flipy.eval() else 1)
    shape = _painted(cv.join([_item_shape(o) for o in _over(laser)]))
    if _controls()['white'].eval() > 0.5:
        shape = (shape[0], np.where(shape[1].sum(axis=1, keepdims=True) > 0, 1.0, 0.0), shape[2], shape[3])
    scriptOp.copyNumpyArray(cv.pack(shape, rect=_rect(laser), flip=flip), baseName='c')


def cook_canvas(scriptOp):
    """base_preview/script_canvas: Show Canvas in View, the whole canvas."""
    cv = RIG.op('canvas').module
    shape = _painted(cv.join([_item_shape(o) for o in items('surface') + items('line')]))
    scriptOp.copyNumpyArray(cv.pack(shape), baseName='c')


def _video_state():
    """The Video Contours values the joystick plays, by joymap's names."""
    p = RIG.op('base_edges').par
    return dict(wipe=p.Wipe.eval(), hold=p.Hold.eval(), frame=p.Frame.eval(), softness=p.Edgeblur.eval(),
                floor=p.Edgethreshold.eval(), shift=p.Shift.eval(), drift=p.Drift.eval())


def _video_apply(changes):
    e = RIG.op('base_edges')
    for name, par in (('wipe', 'Wipe'), ('hold', 'Hold'), ('frame', 'Frame'), ('softness', 'Edgeblur'),
                      ('floor', 'Edgethreshold'), ('shift', 'Shift'), ('drift', 'Drift')):
        if name in changes:
            e.par[par] = changes[name]
    if changes.get('restart'):
        e.op('speed_fx').par.resetpulse.pulse()
    if changes.get('reset'):
        for par in ('Edgeblur', 'Edgethreshold', 'Shift', 'Drift'):
            e.par[par] = e.par[par].default


def _joy():
    """The pad's state, held on base_controller/constant_joy so CHOPs can read it too."""
    c = RIG.op('base_controller/constant_joy')
    return {name: c.par['const{}value'.format(i)].eval() for i, name in enumerate(JOY_CHANS)}


def _joy_set(changes):
    c = RIG.op('base_controller/constant_joy')
    for name, value in changes.items():
        par = c.par['const{}value'.format(JOY_CHANS.index(name))]
        if par.eval() != value:
            par.val = value


def _joy_home():
    jm = RIG.op('joymap').module
    _joy_set(dict(zip(JOY_CHANS, [0.0] * len(JOY_CHANS))))
    _joy_set({'tempo': 1, 'fly': jm.HOME_FLY, 'tfly': jm.HOME_FLY, 'vfly': jm.HOME_FLY, 'fill': 1.0, 'tfill': 1.0})


def joy_event(name, value, previous):
    """base_controller/chopexec_video: one press, by joymap.event. Menu is a tap for audio and a
    held second layer, so it only toggles audio if nothing else used it."""
    jm = RIG.op('joymap').module
    j = RIG.op('base_controller/joystick_in')
    if name == 'b8':
        if value > 0.5 >= previous:
            _joy_set({'menuused': 0})
        elif value <= 0.5 < previous and not _joy()['menuused']:
            _joy_set({'audiooff': 1 - _joy()['audiooff']})
        return
    way = jm.edge(value, previous)
    if not way:
        return
    shift = j['b8'].eval() > 0.5
    if shift:
        _joy_set({'menuused': 1})
    s = _joy()
    s['count'] = len(RIG.op('routines').module.ROUTINES)
    changes = jm.event(name, way, shift, RIG.par.Joymode.eval(), s)
    if changes is None:
        _video_apply(jm.press(name, way, _video_state()))
        return
    changes = dict(changes)
    if 'color' in changes:
        par = RIG.par[changes.pop('color')]
        par.val = not par.eval()
    if 'home' in changes:
        if changes.pop('home') == 'shape':
            changes.update(jm.shape_home(_joy()))
        else:
            changes.update(jm.camera_home(RIG.op('routines').module.fill(_raw())))
    _joy_set(changes)



def video_frame():
    """base_controller/execute_video, every frame: the view and the noise; in Video mode the
    sticks also move the sliders, unless Menu holds them for the camera."""
    jm = RIG.op('joymap').module
    j = RIG.op('base_controller/joystick_in')
    shift = j['b8'].eval() > 0.5
    mode = RIG.par.Joymode.eval()
    sticks = tuple(j[n].eval() for n in ('xaxis', 'yaxis', 'xrot', 'yrot'))
    s = _joy()
    if shift and any(jm.stick(v) for v in sticks):
        s['menuused'] = 1
        _joy_set({'menuused': 1})
    _, _, speed, spin = RIG.op('routines').module.level(s['nlevel'])
    _joy_set(jm.frame(s, sticks, max(j['slider1'].eval(), j['zaxis'].eval(), 0.0),
                      max(j['slider2'].eval(), j['zrot'].eval(), 0.0), absTime.stepSeconds,
                      shift, mode, (speed, spin)))
    if mode == 'video' and not shift:
        scanning = RIG.op('base_edges').par.Wipe.eval() != 'off'
        _video_apply(jm.sticks(*sticks, absTime.stepSeconds, _video_state(), scanning))


def _knob_range(c):
    p = RIG.op('base_edges').par[c['par']]
    return p.normMin, p.normMax, p.style == 'Int'


def _knob_state(c):
    """(position 0-1, lit, text inside it) of a Video Knobs control."""
    p = RIG.op('base_edges').par[c['par']]
    k = RIG.op('knobs').module
    if c['kind'] == k.BUTTON:
        return 0.0, p.eval() == c['value'], ''
    low, high, _ = _knob_range(c)
    return k.norm(p.eval(), low, high), p.eval() != p.default, k.text(p.eval())


def cook_knob_data(scriptOp):
    """panel_knobs/script_data: reads the pars, so it cooks only when one of them moves."""
    k = RIG.op('knobs').module
    found = k.controls()
    scriptOp.copyNumpyArray(k.data(found, [_knob_state(c)[:2] for c in found]))


def cook_knob_labels(scriptOp):
    """panel_knobs/script_labels: the Text TOP's specification."""
    k = RIG.op('knobs').module
    found = k.controls()
    scriptOp.clear()
    measure = scriptOp.parent().op('text_labels').evalTextSize
    for row in k.labels(found, [_knob_state(c)[2] for c in found], measure):
        scriptOp.appendRow(row)


def knob_down(panel):
    k = RIG.op('knobs').module
    x, y = panel.panel.u.val * k.WIDTH, panel.panel.v.val * k.HEIGHT
    c = k.hit(k.controls(), x, y)
    if c is None:
        return
    p = RIG.op('base_edges').par[c['par']]
    if c['kind'] == k.BUTTON:
        if c['par'] == 'Wipe':
            p.val = c['value']
            RIG.op('base_edges/speed_fx').par.resetpulse.pulse()
        else:
            p.val = not p.eval()
        return
    now = time.perf_counter()
    last = RIG.fetch('Knoblast', (None, 0.0), search=False)
    RIG.store('Knoblast', (c['par'], now))
    if last[0] == c['par'] and now - last[1] < k.DOUBLE_CLICK:
        p.val = p.default
        return
    RIG.store('Knobdrag', (c, x, y, p.eval()))


def knob_drag(panel):
    k = RIG.op('knobs').module
    drag = RIG.fetch('Knobdrag', None, search=False)
    if drag is None:
        return
    c, x, y, start = drag
    low, high, whole = _knob_range(c)
    moved = panel.panel.u.val * k.WIDTH - x + panel.panel.v.val * k.HEIGHT - y
    value = k.dragged(start, moved, high - low)
    RIG.op('base_edges').par[c['par']].val = k.from_norm(k.norm(value, low, high), low, high, whole)


def knob_up():
    RIG.unstore('Knobdrag')


def fit_window():
    """Lays panel_main out for the window, when its size has changed. Only in Perform: in the
    editor the panel keeps its size."""
    lo = RIG.op('layout').module
    size = lo.client_size() if ui.performMode else None
    size = size or lo.MIN_SIZE
    if size == RIG.fetch('Windowsize', None, search=False):
        return
    RIG.store('Windowsize', size)
    s = lo.sizes(*size)
    p = RIG.op('panel_main')
    p.par.w, p.par.h = s['w'], s['h']
    view = p.op('container_view')
    view.par.x, view.par.y, view.par.w, view.par.h = s['view_x'], s['view_y'], s['side'], s['side']
    bar = p.op('container_toolbar')
    bar.par.y, bar.par.w = s['toolbar_y'], s['column']
    column = p.op('container_settings')
    column.par.x, column.par.h = s['column'], s['h']
    p.op('container_wave').par.w = s['column']
    p.op('text_wave').par.w = p.op('text_health').par.w = s['column']
    p.op('text_readout').par.w = s['column'] - 15
    for name in ('rect_frame', 'rect_banner', 'render_view', 'text_banner'):
        top = RIG.op('base_preview').op(name)
        top.par.resolutionw, top.par.resolutionh = s['side'], s['side']


def settings_wheel(notches):
    """chopexec_wheel: the wheel scrolls the settings column while the cursor is over it."""
    column = RIG.op('panel_main/container_settings')
    if not column.panel.inside:
        return
    content = sum(c.height for c in column.children if c.isPanel and c.par.display)
    column.panel.scrollv = RIG.op('layout').module.scrolled(
        float(column.panel.scrollv), notches, content, column.height)


def health_tick():
    """execute_health, every frame: a time stamp, and once a second the numbers and the window."""
    h = RIG.op('health').module
    if not hasattr(h, 'METER'):
        h.METER = h.Meter()
    if not h.METER.tick(time.perf_counter()):
        return
    fit_window()
    p = RIG.op('base_preview/perform_fps')
    drops = p['dropped_frames'].eval()
    gpu_total = p['total_gpu_mem'].eval()
    m = dict(fps=h.METER.fps(), target=project.cookRate, worst=h.METER.worst(),
             drops=max(0.0, drops - getattr(h, 'DROPS', drops)), cpu=p['cpumsec'].eval(),
             gpu=p['gpu_mem_used'].eval() / gpu_total if gpu_total else 0.0, ram=h.ram_used())
    h.DROPS = drops
    level = h.verdict(m)[0]
    RIG.store('Health', h.text(m))
    RIG.store('Healthlevel', level)


def readout():
    """Text for panel_main/text_readout: audio bands and joystick shape speed."""
    a = RIG.op('base_audio/null_audio')
    c = _controls()
    mix = RIG.op('joymap').module.mix_text(RIG.par.Mixred.eval(), RIG.par.Mixgreen.eval(), RIG.par.Mixblue.eval())
    lines = ['JOY ' + RIG.par.Joymode.eval().upper(), 'MIX ' + mix,
             'AUDIO ' + ('ON' if a['on'].eval() > 0.5 else 'OFF')]
    for band in ('low', 'mid', 'high'):
        lines.append('{} {:.0f}%'.format(band.upper(), a[band].eval() * 100))
    trim = 16 ** RIG.op('base_audio').par.Trim.eval()
    speed = 'SPEED {:3.0f}%  x{:g}  TRIM x{:.2f}'.format(c['speed'].eval() * 100, c['tempo'].eval(), trim)
    lines.append(speed + ('  FROZEN' if c['freeze'].eval() > 0.5 else ''))
    routines = RIG.op('routines').module.ROUTINES
    joy = _joy()
    lines.append('{} V{}  NOISE {}  {}'.format(routines[int(c['pattern'].eval()) % len(routines)][0].upper(),
                                               int(c['variant'].eval()) + 1, int(joy['noise']),
                                               'POINTS' if joy['points'] else 'LINES') + ('  MOVE' if joy['move'] else '  TURN'))
    covered = [o for laser in items('laser') for o in _over(laser)]
    lines.extend('LINE {} OFF LASER'.format(o.digits) for o in items('line') if o not in covered)
    count, length, error = RIG.fetch('Itemstats', (0, 0, ''), search=False)
    lines.append('ROUTINE ERROR' if error else 'ITEMS {}  LEN {:g}'.format(count, length))
    return '  '.join(lines)                  # one line: Text COMP ignores newlines


# ------------------------------------------- monitor (only while it is shown)

def monitor_laser():
    """The laser the monitor watches: Laser par, or the first one if that number is gone."""
    lasers = items('laser')
    n = RIG.op('base_monitor').par.Laser.eval()
    return next((o for o in lasers if o.digits == n), lasers[0] if lasers else None)


def monitor_out():
    laser = monitor_laser()
    return laser.op('laser_out') if laser else None


def cook_wave(scriptOp):
    """base_monitor/script_wave, 10 times a second: laser_monitor is a private copy of the
    selected laser's Laser CHOP, so frame marks never enter the signal sent to the projector."""
    m = RIG.op('base_monitor')
    t = m.op('trail_capture')
    if t.numChans:
        t[0].eval()                                         # a channel read keeps this cooking
        if absTime.frame % WAVE_EVERY and not m.par.Hold.eval():
            return
    wf = RIG.op('waveform').module
    w, h = scriptOp.par.resolutionw.eval(), scriptOp.par.resolutionh.eval()
    if t.numSamples < 2 or t.numChans < 6:
        scriptOp.copyNumpyArray(wf.for_td(wf.render(*[np.zeros(0)] * 5, [], w, h)))
        m.store('Text', wf.text(None, 0, 0, False))
        return
    v = {c.name: c.numpyArray() for c in t.chans()}
    starts = wf.frame_starts(v['debug'])
    count = int(m.par.Frames.eval())
    a, b, total = wf.select(starts, t.numSamples, count, m.par.Back.eval())
    laser = monitor_laser()
    x, y, r, g, bl, state = (v[k][a:b] for k in ('x', 'y', 'r', 'g', 'b', 'debug'))
    r, g, bl = (np.maximum(c, 0) for c in (r, g, bl))
    marks = starts[(starts >= a) & (starts < b)] - a
    data = wf.measure(x, y, r, g, bl, state, t.rate, laser.par.Stepsize.eval())
    if data and len(marks):
        data['hz'] *= len(marks)                            # refresh rate of one frame
    scriptOp.copyNumpyArray(wf.for_td(wf.render(x, y, r, g, bl, marks, w, h)))
    armed = RIG.par.Arm.eval() and not RIG.par.Estop.eval() and laser.par.Enable.eval()
    head = wf.text(data, total - max(0, min(m.par.Back.eval(), total - 1)), total, bool(armed))
    m.store('Text', 'LASER {}   {}'.format(laser.digits, head))


# ------------------------------------------------ item geometry (on edit)

def surface_dent(surface):
    """The corner pulled past the diagonal, or -1: base_surfaces switches warp on this."""
    k = RIG.op('warp').module.dent(_quad(surface))
    return -1 if k is None else k


def _bezier(p0, h0, h1, p1, steps):
    out = []
    for k in range(1, steps + 1):
        t = k / steps
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        out.append((a * p0[0] + b * h0[0] + c * h1[0] + d * p1[0],
                    a * p0[1] + b * h0[1] + c * h1[1] + d * p1[1]))
    return out


def line_path(pts, closed):
    """Dense path through a line's points, as (path, corners). A point flagged 'curve'
    gets automatic Bezier handles (tangent through its neighbours); a normal point is
    a corner. Points added along the way are guide points."""
    n = len(pts)
    if n < 2:
        return [], []
    def P(i):
        return pts[i % n] if closed else pts[max(0, min(n - 1, i))]
    out = [(pts[0][0], pts[0][1])]
    corners = [1]
    for i in range(n if closed else n - 1):
        a, b = P(i), P(i + 1)
        h0, h1 = (a[0], a[1]), (b[0], b[1])
        if a[2]:
            h0 = (a[0] + (b[0] - P(i - 1)[0]) / 6.0, a[1] + (b[1] - P(i - 1)[1]) / 6.0)
        if b[2]:
            h1 = (b[0] - (P(i + 2)[0] - a[0]) / 6.0, b[1] - (P(i + 2)[1] - a[1]) / 6.0)
        chord = math.hypot(b[0] - a[0], b[1] - a[1])
        steps = max(1, int(math.ceil(chord * (1.3 if (a[2] or b[2]) else 1.0) / LINE_STEP)))
        out.extend(_bezier((a[0], a[1]), h0, h1, (b[0], b[1]), steps))
        corners.extend([0] * (steps - 1) + [0 if b[2] else 1])
    corners[-1] = 1 if not closed else corners[0]
    return out, corners


def cook_path(scriptOp, line):
    _begin(scriptOp)
    path, corners = line_path(_points(line), bool(line.par.Closed.eval()))
    _emit(scriptOp, path, W, corners=corners)


def cook_test(scriptOp, laser):
    """Test patterns, in scan space (static: cooks only when its settings change)."""
    _begin(scriptOp)
    pattern = laser.par.Testpattern.eval()
    if pattern == 'grid':                     # 3 + 3 lines, each starting where the last ended
        for i, c in enumerate((-0.6, 0.0, 0.6)):
            a, b = (-0.8, 0.8) if i % 2 == 0 else (0.8, -0.8)
            _emit(scriptOp, [(a, c), (b, c)], W)
        for i, c in enumerate((0.6, 0.0, -0.6)):
            a, b = (-0.8, 0.8) if i % 2 == 0 else (0.8, -0.8)
            _emit(scriptOp, [(c, a), (c, b)], W)
        return
    if pattern == 'color':                    # R, G, B and white bars for calibration
        for c, col in zip((-0.6, -0.2, 0.2, 0.6), (R, G, B, W)):
            _emit(scriptOp, [(-0.8, c), (0.8, c)], col)
        return
    _emit(scriptOp, _box(0.0, 0.0, 0.95, 0.95), W, closed=True)
    _emit(scriptOp, [(-0.95, -0.65), (-0.95, -0.95), (-0.65, -0.95)], G)
    for seg in _digits(laser.digits, 0.0, 0.0, 0.35):
        _emit(scriptOp, seg, W)


# ------------------------------------------------------------ view overlay

def cook_overlay(scriptOp):
    """Outline and number of every item, plus the handles of the selected one.
    Cooks only when a shape or the selection changes."""
    _begin(scriptOp)
    sel = selected()
    for kind in ('laser', 'surface', 'line'):
        for o in items(kind):
            on = o == sel
            col = VIEW_COLOR[kind] if on else tuple(v * 0.5 for v in VIEW_COLOR[kind])
            hs = _handles(o)
            if kind == 'line':
                if len(hs) >= 2:
                    _emit(scriptOp, hs, tuple(v * 0.35 for v in VIEW_COLOR[kind]),
                          closed=bool(o.par.Closed.eval()))
            else:
                _emit(scriptOp, hs, col, closed=True)
            if hs:
                lx, ly = (hs[3][0] + 0.09, hs[3][1] - 0.1) if kind != 'line' else (hs[0][0], hs[0][1] + 0.12)
                for seg in _digits(o.digits, lx, ly, 0.045):
                    _emit(scriptOp, seg, col)
            if on:
                curve = [c for _, _, c in _points(o)] if kind == 'line' else [0] * len(hs)
                for (hx, hy), cv in zip(hs, curve):
                    if _turning(o):
                        shape = _round(hx, hy, 0.045)
                    else:
                        shape = _diamond(hx, hy, 0.05) if cv else _box(hx, hy, 0.035, 0.035)
                    _emit(scriptOp, shape, (1.0, 1.0, 0.2), closed=True)


# ---------------------------------------------------------------- mouse

def _mouse_xy(panel):
    return ((panel.panel.u.val * 2.0 - 1.0) * VIEW_HALF,
            (panel.panel.v.val * 2.0 - 1.0) * VIEW_HALF)


def _in_quad(q, x, y):
    sign = 0
    for i in range(4):
        ax, ay = q[i]
        bx, by = q[(i + 1) % 4]
        cross = (bx - ax) * (y - ay) - (by - ay) * (x - ax)
        if cross != 0:
            if sign and (cross > 0) != (sign > 0):
                return False
            sign = cross
    return True


def _near_path(pts, x, y):
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        dx, dy = bx - ax, by - ay
        t = 0.0 if not (dx or dy) else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
        if math.hypot(ax + t * dx - x, ay + t * dy - y) < PICK_LINE:
            return True
    return False


def _hit(o, x, y):
    kind = _kind(o)
    if kind == 'line':
        hs = _handles(o)
        return _near_path(hs + (hs[:1] if o.par.Closed.eval() else []), x, y) or \
            any(math.hypot(hx - x, hy - y) < HANDLE for hx, hy in hs)
    return _in_quad(_handles(o), x, y)


def _drawing():
    o = selected()
    return o if (o is not None and _kind(o) == 'line' and o.par.Draw.eval()) else None


def _turning(o):
    """True while this surface's handles are round: dragging one spins the surface."""
    return RIG.fetch('Turning', None, search=False) == o.path


def _double_click(o, k):
    """Second quick click on the same corner of a surface: switches its handles between square
    and round, and undoes any nudge the two clicks made."""
    now = time.perf_counter()
    last = RIG.fetch('Lastclick', None, search=False)
    if last and last[:2] == (o.path, k) and now - last[2] < DOUBLE_CLICK:
        RIG.store('Lastclick', None)
        _set_quad(o, last[3])
        RIG.store('Turning', None if _turning(o) else o.path)
        RIG.store('drag', None)
        RIG.op('base_preview/script_overlay').cook(force=True)
        return True
    RIG.store('Lastclick', (o.path, k, now, _quad(o)))
    return False


def mouse_down(panel):
    """While a line is in Draw mode every click adds a point. Otherwise: a handle
    of the selected item drags that handle; anywhere else on an item selects and
    moves it. Lines are picked first, then surfaces, then lasers. A double click on
    a surface's corner makes its handles round, for turning it."""
    mx, my = _mouse_xy(panel)
    line = _drawing()
    if line is not None:
        _set_points(line, _points(line) + [(mx, my, 0)])
        RIG.store('drag', ('handle', len(_points(line)) - 1))
        return
    sel = selected()
    if sel is not None:
        hs = _handles(sel)
        for k, (hx, hy) in enumerate(hs):
            if math.hypot(hx - mx, hy - my) < HANDLE:
                if _kind(sel) == 'surface':
                    if _double_click(sel, k):
                        return
                    if _turning(sel):
                        RIG.store('drag', ('turn', mx, my, _quad(sel)))
                        return
                fx, fy = hs[(k + 2) % len(hs)]          # opposite corner, fixed in rectangle mode
                RIG.store('drag', ('handle', k, fx, fy))
                return
    for kind in ('line', 'surface', 'laser'):
        for o in reversed(items(kind)):
            if _hit(o, mx, my):
                select(o)
                RIG.store('drag', ('move', mx, my))
                return
    RIG.store('drag', None)


def mouse_drag(panel):
    drag = RIG.fetch('drag', None)
    o = selected()
    if not drag or o is None or not panel.panel.lselect.val:
        return
    mx, my = _mouse_xy(panel)
    kind = _kind(o)
    if drag[0] == 'move':
        dx, dy = mx - drag[1], my - drag[2]
        RIG.store('drag', ('move', mx, my))
        if kind == 'laser':
            o.par.Posx, o.par.Posy = o.par.Posx.eval() + dx, o.par.Posy.eval() + dy
        elif kind == 'surface':
            _set_quad(o, [(x + dx, y + dy) for x, y in _quad(o)])
        else:
            _set_points(o, [(x + dx, y + dy, c) for x, y, c in _points(o)])
        return
    if drag[0] == 'turn':                               # from the grab, so it never drifts
        o.par.Free = True                               # rectangle mode would square it up again
        _set_quad(o, RIG.op('warp').module.turned(drag[3], drag[1:3], (mx, my)))
        return
    k = drag[1]
    if kind == 'line':
        pts = _points(o)
        if k < len(pts):
            pts[k] = (mx, my, pts[k][2])
            _set_points(o, pts)
    elif kind == 'surface' and o.par.Free.eval():       # tilt: this corner only
        q = _quad(o)
        q[k] = (mx, my)
        _set_quad(o, q)
    else:                                               # rectangle: opposite corner stays
        fx, fy = drag[2], drag[3]
        w, h = max(MIN_SIZE, abs(mx - fx)), max(MIN_SIZE, abs(my - fy))
        cx, cy = fx + math.copysign(w / 2, mx - fx), fy + math.copysign(h / 2, my - fy)
        if kind == 'laser':
            o.par.Posx, o.par.Posy, o.par.Sizex, o.par.Sizey = cx, cy, w, h
        else:
            _set_quad(o, _box(cx, cy, w / 2, h / 2))


def mouse_up(panel):
    RIG.store('drag', None)


def mouse_right(panel):
    """Right click: finish drawing a line, or toggle a line point corner <-> curve."""
    line = _drawing()
    if line is not None:
        line.par.Draw = 0
        return
    o = selected()
    if o is None or _kind(o) != 'line':
        return
    mx, my = _mouse_xy(panel)
    pts = _points(o)
    for k, (x, y, c) in enumerate(pts):
        if math.hypot(x - mx, y - my) < HANDLE:
            pts[k] = (x, y, 0 if c else 1)
            _set_points(o, pts)
            return


# ------------------------------------------------- create / delete / select

def select(o):
    RIG.par.Selected = RIG.relativePath(o) if o is not None else ''


def add(kind):
    """New laser, surface or line: the COMP, its settings panel, its place in the view."""
    base_name, tpl_name = KINDS[kind]
    base = RIG.op(base_name)
    n = 1
    while base.op('%s%d' % (kind, n)) is not None:
        n += 1
    o = base.copy(base.op(tpl_name), name='%s%d' % (kind, n))
    o.allowCooking = True
    o.par.clone = tpl_name
    row = RANK[kind] - (1 if kind == 'laser' else 2)
    o.nodeX, o.nodeY = 200 * ((n - 1) % 8), -250 - 200 * row
    if kind == 'laser':
        o.par.Posx, o.par.Posy = -1.05 + 1.05 * ((n - 1) % 3), 0.55 - 1.1 * ((n - 1) // 3)
    else:
        if kind == 'surface':
            d = 0.25 * ((n - 1) % 6)
            _set_quad(o, _box(-1.05 + d, 0.55 - d, 0.4, 0.4))
        else:
            _set_points(o, [])
            o.par.Draw = 1                      # next clicks in the view place its points
    _add_panel(o)
    select(o)
    RIG.store('Itemcount', RIG.fetch('Itemcount', 0, search=False) + 1)
    return o


def reset():
    """Every new session: safety on, one laser showing its white grid. Output stays
    off until the operator clears E-STOP, arms and enables the laser."""
    RIG.par.Estop = 1
    RIG.par.Arm = 0
    RIG.par.Joymode = 'shape'
    RIG.par.Mixred = RIG.par.Mixgreen = RIG.par.Mixblue = 0
    _joy_home()
    for kind in KINDS:
        for o in items(kind):
            delete(o)
    add('laser')
    select(None)


def delete(o):
    if o is None or _kind(o) is None or o.name.endswith('template'):
        return
    panel = RIG.op('panel_main/container_settings').op('panel_' + o.name)
    if panel is not None:
        panel.destroy()
    if selected() == o:
        select(None)
    o.destroy()
    RIG.store('Itemcount', RIG.fetch('Itemcount', 0, search=False) + 1)
    RIG.op('base_preview/script_overlay').cook(force=True)


def _add_panel(o):
    """One foldable settings panel per item, stacked in the settings column."""
    kind = _kind(o)
    stack = RIG.op('panel_main/container_settings')
    p = stack.copy(stack.op('panel_template'), name='panel_' + o.name)
    p.par.display = True
    p.par.Target.expr = "parent.Rig.op('%s')" % RIG.relativePath(o)
    p.par.Title = '%s %d' % (TITLES[kind], o.digits)
    p.par.Bodyh = BODY_H[kind]
    p.par.alignorder = RANK[kind] * 100 + o.digits
    p.nodeX, p.nodeY = 250 * RANK[kind], -200 * o.digits


def _fit_laser(line):
    """The nearest laser's rectangle moved over this line, so the line fills its scan area.
    Only from the line's button: it takes the laser off whatever it covered before."""
    pts = _handles(line)
    lasers = items('laser')
    if not pts or not lasers:
        return
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    laser = min(lasers, key=lambda o: math.hypot(o.par.Posx.eval() - cx, o.par.Posy.eval() - cy))
    size = max(MIN_SIZE, max(max(xs) - min(xs), max(ys) - min(ys)) * 1.1)
    laser.par.Posx, laser.par.Posy, laser.par.Sizex, laser.par.Sizey = cx, cy, size, size


def _reset_video():
    """Every Video Contours fader and button back to its default. The sources stay: their default
    is empty, which would lose the picture."""
    e = RIG.op('base_edges')
    for p in e.customPars:
        if p.page.name == 'Video' and not p.isPulse and p.name not in ('Spoutsender', 'Ndisource'):
            p.val = p.default


def on_pulse(par):
    name, owner = par.name, par.owner
    if name in ('Addlaser', 'Addsurface', 'Addline'):
        add(name[3:])
    elif name == 'Delete':
        run("args[0].delete(op(args[1]))", me.module, owner.path, delayFrames=1)
    elif name == 'Removelast':
        _set_points(owner, _points(owner)[:-1])
    elif name == 'Square':
        xs, ys = zip(*_quad(owner))
        _set_quad(owner, _box((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2,
                              max(MIN_SIZE, max(xs) - min(xs)) / 2, max(MIN_SIZE, max(ys) - min(ys)) / 2))
    elif name == 'Resetvideo':
        _reset_video()
    elif name == 'Fitlaser':
        _fit_laser(owner)
    elif name == 'Save':
        save()
    elif name == 'Load':
        load()


# ---------------------------------------------------------- persistence

def _pars(o):
    kind = _kind(o)
    out = {p.name: p.eval() for p in o.customPars
           if p.page.name in PAGES[kind] and not p.isPulse and p.name != 'Draw'}
    if kind == 'line':
        out['points'] = _points(o)
    return out


def save():
    data = {'Masterlimit': RIG.par.Masterlimit.eval()}
    for kind in KINDS:
        data[kind] = [_pars(o) for o in items(kind)]
    full = _full(RIG.par.Setupfile.eval())
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'w') as f:
        json.dump(data, f, indent=2)
    print('Laser rig saved ->', full)


def load():
    full = _full(RIG.par.Setupfile.eval())
    if not os.path.exists(full):
        print('Laser rig: file not found:', full)
        return
    with open(full) as f:
        data = json.load(f)
    for kind in KINDS:
        for o in items(kind):
            delete(o)
    RIG.par.Masterlimit = data.get('Masterlimit', RIG.par.Masterlimit.eval())
    for kind in KINDS:
        for pars in data.get(kind, []):
            o = add(kind)
            if kind == 'line':
                _set_points(o, pars.pop('points', []))
                o.par.Draw = 0
            for name, val in pars.items():
                if name != 'Enable' and o.par[name] is not None:   # never auto-enable output
                    o.par[name] = val
    select(None)


def _full(path):
    return path if os.path.isabs(path) else os.path.join(project.folder, path)
