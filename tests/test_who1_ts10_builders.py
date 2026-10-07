"""WHO 1 commands libqtdevices TS10_1_0_23 sends (lighting_device.cpp:34-39
FIXED_TIMING_MIN/MAX = 11/18, DIMMER_INC/DEC = 30/31; :110-124 fixedTiming,
variableTiming; :131-134 requestVariableTiming; :230-245 increase/decrease/
setLevel100; :409-417 Dimmer100 increaseLevel100/decreaseLevel100).
Firmware replay on bt_luci (MyHomeServer1, F454, F459): *1*2*11## ACK bus
11 00 12 1D, *1*5*11## 4D, *1*10*11## 9D, *1*30*11## 03, *1*31*11## 04,
*1*30#20#1*11## D1 11 01 42 0D 03 14 01, *1*31#20#255*11## ... 0D 04 14 FF,
*1*11*11## 16, *1*18*11## 86, *#1*11*#2*0*1*0## D1 11 01 42 06 00 01 00,
*#1*11*2## request frame D1 11 01 43 06 00 00 00."""

import pytest

from OWNd.message import OWNLightingCommand


def test_presets():
    assert str(OWNLightingCommand.set_brightness_preset(11, 2)) == "*1*2*11##"
    assert str(OWNLightingCommand.set_brightness_preset(11, 10)) == "*1*10*11##"
    with pytest.raises(ValueError):
        OWNLightingCommand.set_brightness_preset(11, 1)
    with pytest.raises(ValueError):
        OWNLightingCommand.set_brightness_preset(11, 11)


def test_steps():
    assert str(OWNLightingCommand.step_up(11)) == "*1*30*11##"
    assert str(OWNLightingCommand.step_down(11)) == "*1*31*11##"
    assert str(OWNLightingCommand.step_up(11, 20, 1)) == "*1*30#20#1*11##"
    assert str(OWNLightingCommand.step_down(11, 20, 255)) == "*1*31#20#255*11##"
    with pytest.raises(ValueError):
        OWNLightingCommand.step_up(11, 0)
    with pytest.raises(ValueError):
        OWNLightingCommand.step_up(11, 10, 256)


def test_fixed_timers():
    assert str(OWNLightingCommand.switch_on_timed(11, 11)) == "*1*11*11##"
    assert str(OWNLightingCommand.switch_on_timed(11, 18)) == "*1*18*11##"
    with pytest.raises(ValueError):
        OWNLightingCommand.switch_on_timed(11, 19)


def test_variable_timer():
    assert str(OWNLightingCommand.set_variable_timer(11, 0, 1, 0)) == "*#1*11*#2*0*1*0##"
    assert str(OWNLightingCommand.get_variable_timer(11)) == "*#1*11*2##"
    with pytest.raises(ValueError):
        OWNLightingCommand.set_variable_timer(11, 0, 60, 0)
