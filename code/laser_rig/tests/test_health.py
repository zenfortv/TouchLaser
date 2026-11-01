# Runs outside TouchDesigner: python tests/test_health.py
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import health

GOOD = dict(fps=59.0, target=60.0, worst=30.0, drops=0.0, cpu=8.0, gpu=0.2, ram=0.5, temp=60.0)


def level(**changes):
    return health.LEVELS[health.verdict(dict(GOOD, **changes))[0]]


def test_healthy_project_is_ok():
    assert level() == 'OK'


def test_fps_steps():
    assert level(fps=45) == 'WATCH' and level(fps=28) == 'SLOW' and level(fps=10) == 'DANGER'


def test_memory_steps():
    assert level(ram=0.88) == 'SLOW' and level(ram=0.95) == 'DANGER'
    assert level(gpu=0.8) == 'SLOW' and level(gpu=0.95) == 'DANGER'


def test_stutters_and_freezes():
    assert level(drops=5) == 'WATCH' and level(worst=150) == 'WATCH' and level(worst=400) == 'SLOW'


def test_memory_beats_fps_in_the_reason():
    assert health.verdict(dict(GOOD, fps=10, ram=0.95))[1] == 'PC ALMOST OUT OF RAM'


def test_text():
    t = health.text(GOOD)
    assert t.startswith('OK   FPS 59/60') and 'RAM 50%' in t and 'GPU 60C' in t
    assert health.text(dict(GOOD, fps=10)).startswith('DANGER: VERY LOW FPS')
    assert 'C' not in health.text(dict(GOOD, temp=-1)).split('RAM')[1]


def test_meter_measures_fps_and_worst_and_forgets():
    m = health.Meter()
    t = 0.0
    m.tick(t)
    for _ in range(30):
        t += 0.02
        m.tick(t)
    assert abs(m.fps() - 50) < 0.01 and abs(m.worst() - 20) < 0.01
    t += 0.5
    m.tick(t)
    assert abs(m.worst() - 500) < 0.01
    for _ in range(300):
        t += 0.02
        m.tick(t)
    assert abs(m.worst() - 20) < 0.01


def test_meter_reports_once_a_second():
    m = health.Meter()
    hits = sum(m.tick(5 + i * 0.1) for i in range(31))
    assert hits == 4


def test_ram_reading():
    assert 0 < health.ram_used() < 1


for name, t in sorted(globals().copy().items()):
    if name.startswith('test_'):
        t()
        print('ok', name)
