# Runs outside TouchDesigner: python tests/test_joymap.py
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import joymap as j

S = dict(wipe='off', hold=False, frame=False, softness=6.0, floor=0.15, shift=0.0, drift=0.0)


def test_edge_fires_once_on_press_only():
    assert j.edge(1, 0) == 1 and j.edge(-1, 0) == -1
    assert j.edge(1, 1) == 0 and j.edge(0, 1) == 0 and j.edge(0, -1) == 0


def test_each_arrow_starts_its_own_scan():
    assert j.press('p1_Y', 1, S) == {'wipe': 'down', 'restart': True}
    assert j.press('p1_X', 1, S)['wipe'] == 'engrave'
    assert j.press('p1_Y', -1, S)['wipe'] == 'radar'
    assert j.press('p1_X', -1, S)['wipe'] == 'iris'


def test_the_same_arrow_stops_it_and_another_swaps():
    assert j.press('p1_X', 1, dict(S, wipe='engrave'))['wipe'] == 'off'
    assert j.press('p1_X', -1, dict(S, wipe='engrave'))['wipe'] == 'iris'


def test_colour_buttons_are_x_blue_b_red_a_green():
    assert j.COLOR_BUTTONS == {'b3': 'Mixblue', 'b2': 'Mixred', 'b1': 'Mixgreen'}
    assert j.press('b2', 1, S) == {} and j.press('b3', 1, S) == {}


def test_mix_names():
    assert j.mix_text(False, False, False) == 'OFF'
    assert j.mix_text(True, True, False) == 'YELLOW'
    assert j.mix_text(False, True, True) == 'CYAN'
    assert j.mix_text(True, False, True) == 'MAGENTA'
    assert j.mix_text(True, True, True) == 'WHITE'


def test_toggles_and_reset():
    assert j.press('b6', 1, S) == {'hold': True}
    assert j.press('b10', 1, dict(S, frame=True)) == {}
    assert j.press('b9', 1, S) == {'reset': True}
    assert j.press('b1', 1, S) == {}


def test_stick_deadzone_and_full_travel():
    assert j.stick(0.1) == 0 and j.stick(-0.1) == 0
    assert j.stick(1) == 1 and j.stick(-1) == -1


def test_resting_sticks_change_nothing():
    assert j.sticks(0.05, -0.05, 0.1, 0, 0.02, S, False) == {}


def test_sticks_move_and_stop_at_limits():
    out = j.sticks(1, 1, 1, 1, 0.1, S, False)
    assert abs(out['softness'] - 7) < 1e-9 and abs(out['floor'] - 0.18) < 1e-9
    assert abs(out['shift'] - 0.05) < 1e-9 and abs(out['drift'] - 0.05) < 1e-9
    assert j.sticks(-1, 0, 0, 0, 10, S, False) == {'softness': 0.0}
    assert j.sticks(0, 1, 0, 0, 10, S, False) == {'floor': 1.0}


def test_shift_wraps():
    assert abs(j.sticks(0, 0, 1, 0, 0.1, dict(S, shift=0.98), False)['shift'] - 0.03) < 1e-9


def test_right_y_belongs_to_the_scanner_while_scanning():
    assert 'drift' not in j.sticks(0, 0, 0, 1, 0.1, S, True)


J = dict(fill=1.0, tfill=1.0, move=0, pany=0.0, tpany=0.0, vpany=0.0, pattern=0, count=11, noise=0, variant=0, tempo=1, blackout=0, freeze=0, points=0, rt=0.0, lt=0.0, nlevel=0.0,
         ntime=0.0, spin=0.0, yaw=0.0, pitch=0.0, fly=3.0, panx=0.0, tyaw=0.0, tpitch=0.0, tfly=3.0, tpanx=0.0,
         vyaw=0.0, vpitch=0.0, vfly=3.0, vpanx=0.0)
STILL = (0, 0, 0, 0)


def test_left_and_right_step_through_all_the_shapes_and_wrap():
    assert j.event('p1_X', 1, False, 'shape', J) == {'pattern': 1}
    assert j.event('p1_X', -1, False, 'shape', J) == {'pattern': 10}
    assert j.event('p1_X', 1, False, 'shape', dict(J, pattern=10)) == {'pattern': 0}


def test_up_and_down_change_the_variant():
    assert j.event('p1_Y', 1, False, 'shape', dict(J, variant=7)) == {'variant': 0}
    assert j.event('p1_Y', -1, False, 'shape', J) == {'variant': 7}


def test_x_y_a_b_are_the_old_ones_in_both_modes_with_or_without_menu():
    for mode in ('shape', 'video'):
        for shift in (False, True):
            assert j.event('b3', 1, shift, mode, J) == {'color': 'Mixblue'}
            assert j.event('b2', 1, shift, mode, J) == {'color': 'Mixred'}
            assert j.event('b1', 1, shift, mode, J) == {'color': 'Mixgreen'}
            assert j.event('b4', 1, shift, mode, J) == {'blackout': 1}


def test_view_is_tempo():
    assert j.event('b7', 1, False, 'shape', dict(J, tempo=4)) == {'tempo': 1}


def test_l1_swaps_lines_and_points_in_both_modes():
    assert j.event('b5', 1, False, 'shape', J) == {'points': 1}
    assert j.event('b5', 1, False, 'video', dict(J, points=1)) == {'points': 0}


def test_menu_with_l1_is_strobe_not_points():
    assert j.event('b5', 1, True, 'shape', J) == {}


def test_r1_picks_level_2_and_again_returns_to_the_base():
    assert j.event('b6', 1, False, 'shape', J) == {'noise': 2}
    assert j.event('b6', 1, False, 'shape', dict(J, noise=2)) == {'noise': 0}
    assert j.event('b6', 1, True, 'shape', J) == {'freeze': 1}


def test_l2_and_r2_pick_levels_1_and_3_once_per_pull():
    assert j.frame(J, STILL, 1.0, 0.0, 0.02, False, 'shape', (0.4, 0))['noise'] == 1
    assert j.frame(J, STILL, 0.0, 1.0, 0.02, False, 'shape', (0.4, 0))['noise'] == 3
    assert 'noise' not in j.frame(dict(J, noise=3, rt=1.0), STILL, 0.0, 1.0, 0.02, False, 'shape', (0.4, 0))
    assert j.frame(dict(J, noise=1), STILL, 1.0, 0.0, 0.02, False, 'shape', (0.4, 0))['noise'] == 0


def test_triggers_with_menu_or_in_video_are_not_noise():
    assert 'noise' not in j.frame(J, STILL, 1.0, 1.0, 0.02, True, 'shape', (0.4, 0))
    assert 'noise' not in j.frame(J, STILL, 1.0, 1.0, 0.02, False, 'video', (0.4, 0))


def test_video_mode_keeps_its_buttons():
    assert j.event('p1_X', 1, False, 'video', J) is None
    assert j.event('b6', 1, False, 'video', J) is None


def test_the_video_follows_far_slower_than_the_shape():
    s = dict(J, tfly=1.0)
    for _ in range(30):
        s.update(j.frame(s, STILL, 0.0, 0.0, 1 / 60.0, False, 'shape', (0.4, 0)))
    assert s['fly'] < 2.0 and s['vfly'] > 2.8


def test_stick_moves_the_camera_only_in_its_mode():
    assert j.frame(J, (0, 0, 0, 1), 0.0, 0.0, 0.1, False, 'shape', (0.4, 0))['tfly'] < 3
    assert 'tfly' not in j.frame(J, (0, 0, 0, 1), 0.0, 0.0, 0.1, False, 'video', (0.4, 0))
    assert j.frame(J, (0, 0, 0, 1), 0.0, 0.0, 0.1, True, 'video', (0.4, 0))['tfly'] < 3
    assert 'tfly' not in j.frame(J, (0, 0, 0, 1), 0.0, 0.0, 0.1, True, 'shape', (0.4, 0))


def test_the_camera_stops_at_its_limits():
    s = dict(J, tfly=j.FLY_MIN)
    assert j.frame(s, (0, 0, 0, 1), 0.0, 0.0, 1, False, 'shape', (0.4, 0))['tfly'] == j.FLY_MIN


def test_l3_brings_the_shape_home_by_the_nearest_whole_turn():
    assert j.event('b9', 1, False, 'shape', J) == {'home': 'shape'}
    out = j.shape_home(dict(J, tyaw=2.3, tpitch=-0.7, tpanx=0.5, tpany=-0.5, move=1))
    assert out == {'tyaw': 2.0, 'tpitch': -1.0, 'tpanx': 0.0, 'tpany': 0.0, 'move': 0}


def test_r3_brings_the_camera_home_in_both_modes_and_never_touches_the_frame():
    assert j.event('b10', 1, False, 'shape', J) == {'home': 'camera'}
    assert j.event('b10', 1, False, 'video', J) == {'home': 'camera'}
    assert j.camera_home(1.7) == {'tfly': j.HOME_FLY, 'tfill': 1.7}


def test_the_shape_grows_to_its_fill_smoothly():
    assert 1.0 < j.frame(dict(J, tfill=2.0), STILL, 0.0, 0.0, 0.1, False, 'shape', (0.4, 0))['fill'] < 2.0


def test_l3_in_video_still_resets_the_sliders():
    assert j.event('b9', 1, False, 'video', J) is None


def test_menu_l3_swaps_the_left_stick_between_turning_and_moving():
    assert j.event('b9', 1, True, 'shape', J) == {'move': 1}
    assert j.event('b9', 1, True, 'video', dict(J, move=1)) == {'move': 0}
    turning = j.frame(J, (1, 1, 0, 0), 0.0, 0.0, 0.1, False, 'shape', (0.4, 0))
    assert turning['tyaw'] > 0 and turning['tpitch'] > 0 and 'tpanx' not in turning
    moving = j.frame(dict(J, move=1), (1, 1, 0, 0), 0.0, 0.0, 0.1, False, 'shape', (0.4, 0))
    assert moving['tpanx'] > 0 and moving['tpany'] > 0 and 'tyaw' not in moving


def test_right_stick_x_leaves_the_camera_alone():
    out = j.frame(J, (0, 0, 1, 0), 0.0, 0.0, 0.1, False, 'shape', (0.4, 0))
    assert out['tfly'] == 3.0 and 'tpanx' not in out


def test_zoom_out_is_faster_than_in_and_slow_enough():
    out = j.frame(J, (0, 0, 0, -1), 0.0, 0.0, 1.0, False, 'shape', (0.4, 0))['tfly'] - 3.0
    back = 3.0 - j.frame(J, (0, 0, 0, 1), 0.0, 0.0, 1.0, False, 'shape', (0.4, 0))['tfly']
    assert out > back and back < 1.0


def test_freeze_stops_the_noise_clock():
    assert 'ntime' not in j.frame(dict(J, freeze=1), STILL, 0.0, 0.0, 0.1, False, 'shape', (0.4, 0))

for name, t in sorted(globals().copy().items()):
    if name.startswith('test_'):
        t()
        print('ok', name)
