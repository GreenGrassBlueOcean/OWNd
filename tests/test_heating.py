"""Regression tests for WHO 4 heating messages."""

from OWNd.message import (
    LOCAL_CONTROL_NORMAL,
    LOCAL_CONTROL_OFF,
    LOCAL_CONTROL_OFFSET,
    LOCAL_CONTROL_OVERRIDE,
    LOCAL_CONTROL_PROTECTION,
    LOCAL_CONTROL_UNKNOWN,
    MESSAGE_TYPE_ACTION,
    MESSAGE_TYPE_LOCAL_TARGET_TEMPERATURE,
    MESSAGE_TYPE_TARGET_TEMPERATURE,
    MESSAGE_TYPE_SECONDARY_TEMPERATURE,
    OWNHeatingCommand,
    OWNHeatingEvent,
)


def test_local_and_central_targets_remain_distinct() -> None:
    local = OWNHeatingEvent("*#4*3*12*0350*3##")
    central = OWNHeatingEvent("*#4*3*14*0250*3##")

    assert local.message_type == MESSAGE_TYPE_LOCAL_TARGET_TEMPERATURE
    assert local.local_set_temperature == 35.0
    assert central.message_type == MESSAGE_TYPE_TARGET_TEMPERATURE
    assert central.set_temperature == 25.0


def test_local_control_states_preserve_raw_values() -> None:
    expected = {
        "00": (0, LOCAL_CONTROL_NORMAL),
        "03": (3, LOCAL_CONTROL_OFFSET),
        "13": (-3, LOCAL_CONTROL_OFFSET),
        "4": (None, LOCAL_CONTROL_OFF),
        "5": (None, LOCAL_CONTROL_PROTECTION),
        "6": (None, LOCAL_CONTROL_OVERRIDE),
        "7": (None, LOCAL_CONTROL_UNKNOWN),
    }

    for raw, state in expected.items():
        event = OWNHeatingEvent(f"*#4*3*13*{raw}##")
        assert (event.local_offset, event.local_control_state) == state
        assert event.local_offset_raw == raw


def test_valve_status_reply_and_request() -> None:
    event = OWNHeatingEvent("*#4*3*19*0*0##")
    command = OWNHeatingCommand.valves_status("3")

    assert event.message_type == MESSAGE_TYPE_ACTION
    assert not event.is_active()
    assert str(command) == "*#4*3*19##"


def test_probe_temperature_dimension_15_events() -> None:
    # Frame 1 from Issue #264: *#4*100*15*1*0200*0001## (probe 1 of zone 0 at 20.0C)
    event1 = OWNHeatingEvent("*#4*100*15*1*0200*0001##")
    assert event1.message_type == MESSAGE_TYPE_SECONDARY_TEMPERATURE
    assert event1.zone == 0
    assert event1.secondary_temperature == [1, 20.0]
    assert event1.probe_temperature == 20.0
    assert "20.0°C" in event1.human_readable_log

    # Frame 2 from Issue #264: *#4*100*15*1*0196*0001## (probe 1 of zone 0 at 19.6C)
    event2 = OWNHeatingEvent("*#4*100*15*1*0196*0001##")
    assert event2.message_type == MESSAGE_TYPE_SECONDARY_TEMPERATURE
    assert event2.secondary_temperature == [1, 19.6]
    assert event2.probe_temperature == 19.6
    assert "19.6°C" in event2.human_readable_log

    # Negative temperature handling
    neg_event = OWNHeatingEvent("*#4*100*15*1*1050*0001##")
    assert neg_event.message_type == MESSAGE_TYPE_SECONDARY_TEMPERATURE
    assert neg_event.secondary_temperature == [1, -5.0]
    assert neg_event.probe_temperature == -5.0

    # Dimension 15 without status parameter
    event_no_status = OWNHeatingEvent("*#4*2*15*1*0215##")
    assert event_no_status.message_type == MESSAGE_TYPE_SECONDARY_TEMPERATURE
    assert event_no_status.secondary_temperature == [1, 21.5]

    # Dimension 15 single value
    event_single = OWNHeatingEvent("*#4*2*15*0215##")
    assert event_single.message_type == MESSAGE_TYPE_SECONDARY_TEMPERATURE
    assert event_single.probe_temperature == 21.5

    # Dimension 15 malformed value
    event_malformed = OWNHeatingEvent("*#4*2*15*9##")
    assert event_malformed.message_type == MESSAGE_TYPE_SECONDARY_TEMPERATURE
    assert event_malformed.probe_temperature is None

    # Dimension 15 with no dimension values
    event_no_val = OWNHeatingEvent("*#4*100*15##")
    assert event_no_val.message_type == MESSAGE_TYPE_SECONDARY_TEMPERATURE
    assert event_no_val.probe_temperature is None

    # Dimension 15 negative zero 1000
    event_neg_zero = OWNHeatingEvent("*#4*100*15*1*1000##")
    assert event_neg_zero.probe_temperature == 0.0


def test_probe_temperature_command() -> None:
    cmd = OWNHeatingCommand.get_probe_temperature("100")
    assert str(cmd) == "*#4*100*15##"
    assert "probe temperature" in cmd.human_readable_log


def test_where_zero_actuator_is_a_pump_not_a_zone() -> None:
    """``0#N`` is actuator N of zone 0 (a pump), not zone N (OpenWebNet-HA/MyHOME#431)."""
    pump = OWNHeatingEvent("*#4*0#2*20*1##")
    call = OWNHeatingEvent("*4*4001#1*0#3##")
    zone_actuator = OWNHeatingEvent("*#4*1#2*20*1##")
    central_zone = OWNHeatingEvent("*4*101*#0#1##")

    assert pump.message_type == MESSAGE_TYPE_ACTION
    assert pump.zone == 0
    assert pump.is_active()
    assert pump.human_readable_log == "Zone 0's actuator 2 is on."
    assert pump.unique_id == "4-#0"
    assert call.zone == 0
    assert zone_actuator.zone == 1
    assert central_zone.zone == 1
    assert central_zone.unique_id == "4-1"


def test_where_zero_with_parameter_stays_zone_zero() -> None:
    """No unhashed ``0#<p>`` parameter becomes the zone; ``#0`` is the central unit."""
    for frame in (
        "*#4*0#0*20*0##",  # all actuators
        "*#4*0#4#01*20*1##",  # 0#4 was read as zone 4 (F422 form in MyHOME#432)
        "*4*1*#0##",  # central unit
    ):
        event = OWNHeatingEvent(frame)
        assert event.zone == 0, frame
        assert event.unique_id == "4-#0", frame


def test_zone_calls_pump_names_the_calling_zone_and_the_pump() -> None:
    """``*4*4001#Z*0#N##``: zone Z calls pump N; 4002 releases it (OpenWebNet-HA/MyHOME#431)."""
    call = OWNHeatingEvent("*4*4001#1*0#3##")
    release = OWNHeatingEvent("*4*4002#6*0#3##")

    assert call.calling_zone == 1
    assert call.actuator == 3
    assert call.zone == 0
    assert call.unique_id == "4-#0"
    assert call.mode is None
    assert call.human_readable_log == "Zone 1 calls pump 3."
    assert release.calling_zone == 6
    assert release.actuator == 3
    assert release.human_readable_log == "Zone 6 stops calling pump 3."


def test_zone_calls_pump_without_a_pump_or_zone_parameter() -> None:
    """Captured ``*4*4002*1##`` and ``*4*4001#5*0##`` name no pump; the log still reads."""
    bare = OWNHeatingEvent("*4*4002*1##")
    general = OWNHeatingEvent("*4*4001#5*0##")
    no_zone = OWNHeatingEvent("*4*4001*0#3##")

    assert bare.calling_zone is None
    assert bare.actuator is None
    assert bare.human_readable_log == "Zone 1 stops calling the pump."
    assert general.calling_zone == 5
    assert general.actuator is None
    assert general.human_readable_log == "Zone 5 calls the pump."
    assert no_zone.calling_zone is None
    assert no_zone.actuator == 3
    assert no_zone.human_readable_log == "Zone 0 calls pump 3."


def test_actuator_status_names_the_actuator() -> None:
    """``Z#N`` is actuator N of zone Z; a bare zone reports its actuator 1."""
    pump = OWNHeatingEvent("*#4*0#3*20*1##")
    zone_actuator = OWNHeatingEvent("*#4*1#2*20*0##")
    bare_zone = OWNHeatingEvent("*#4*1*20*1##")

    assert pump.actuator == 3
    assert zone_actuator.actuator == 2
    assert zone_actuator.human_readable_log == "Zone 1's actuator 2 is off."
    assert bare_zone.actuator == 1
    assert bare_zone.zone == 1
    assert bare_zone.human_readable_log == "Zone 1's actuator 1 is on."
