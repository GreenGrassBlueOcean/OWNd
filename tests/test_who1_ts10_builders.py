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


def test_apl_addressing_helpers():
    from OWNd.message import area_of_where, is_apl_address, normalize_where

    assert is_apl_address("02") is True
    assert is_apl_address("15") is True
    assert is_apl_address("0015") is True
    assert is_apl_address("0115") is True
    assert is_apl_address("1015") is True
    assert is_apl_address("00") is False
    assert is_apl_address("100") is False
    assert is_apl_address("#6") is False
    assert is_apl_address("1101") is False

    assert area_of_where("02") == "00"
    assert area_of_where("15") == "1"
    assert area_of_where("0015") == "00"
    assert area_of_where("0115") == "1"
    assert area_of_where("1015") == "100"
    assert area_of_where("#6") is None
    assert area_of_where(None) is None

    assert normalize_where("02") == "02"
    assert normalize_where("0015") == "0015"
    assert normalize_where("0021") == "21"
    assert normalize_where("15#4#01") == "15#4#01"
    assert normalize_where("#5") == "#5"
    assert normalize_where(None) == ""
    assert normalize_where("   ") == ""


def test_lighting_dimension_properties():
    from OWNd.message import OWNLightingEvent, OWNMessage

    cmd_b = OWNMessage.parse("*#1*#6*#1*150*0##")
    assert isinstance(cmd_b, OWNLightingCommand)
    assert cmd_b.brightness == 50
    assert cmd_b.dimension_value == ["150", "0"]
    assert cmd_b.where_param == []
    assert cmd_b.dimension_param == []
    assert cmd_b.what is None
    assert cmd_b.what_param == []
    assert cmd_b.color_temp is None
    assert cmd_b.color_temp_kelvin is None
    assert cmd_b.hs is None

    cmd_b_bad = OWNMessage.parse("*#1*#6*#1*50*0##")
    assert isinstance(cmd_b_bad, OWNLightingCommand)
    assert cmd_b_bad.brightness is None

    cmd_b._dimension_value = ["abc"]
    assert cmd_b.brightness is None

    cmd_ct = OWNMessage.parse("*#1*#6*#14*153##")
    assert isinstance(cmd_ct, OWNLightingCommand)
    assert cmd_ct.color_temp == 153
    assert cmd_ct.color_temp_kelvin == int(1000000 / 153)
    assert cmd_ct.brightness is None

    cmd_ct._dimension_value = ["1"]
    assert cmd_ct.color_temp is None
    cmd_ct._dimension_value = ["abc"]
    assert cmd_ct.color_temp is None

    cmd_hs = OWNMessage.parse("*#1*#6*#12*120*50*80##")
    assert isinstance(cmd_hs, OWNLightingCommand)
    assert cmd_hs.hs == (120, 50)
    assert cmd_hs.hs_color == (120, 50)

    cmd_hs._dimension_value = ["511", "127", "255"]
    assert cmd_hs.hs is None
    cmd_hs._dimension_value = ["abc", "50", "80"]
    assert cmd_hs.hs is None

    ev_ct = OWNMessage.parse("*#1*#6*14*153##")
    assert isinstance(ev_ct, OWNLightingEvent)
    assert ev_ct.color_temp_kelvin == int(1000000 / 153)

    ev_hs = OWNMessage.parse("*#1*#6*12*120*50*80##")
    assert isinstance(ev_hs, OWNLightingEvent)
    assert ev_hs.hs_color == (120, 50)
    assert ev_hs.color_temp_kelvin is None

