"""Regression tests for WHO 4 heating messages."""

import pytest

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
    MESSAGE_TYPE_ZONE_STATE,
    OWNHeatingCommand,
    OWNHeatingEvent,
    OWNMessage,
    ZONE_CONTEXT_AUTOMATIC,
    ZONE_CONTEXT_COOLING,
    ZONE_CONTEXT_GENERIC,
    ZONE_CONTEXT_HEATING,
    ZONE_STATE_COMFORT,
    ZONE_STATE_ECO,
    ZONE_STATE_OFF,
    ZONE_STATE_PROTECTION,
    ZONE_STATE_SETPOINT,
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


# DIMENSION 7 zone state (OWNd#58). Frames from MyHOME#429 captures:
# xtimmy86x (MyHomeServer1, 7 zones, heating) and TheDarkWizard
# (MyHomeServer1 + Home+Control, 4 zones, heating/cooling).
@pytest.mark.parametrize(
    ("frame", "zone", "context", "state", "temperature", "log"),
    [
        ("*#4*2*7*1*1*0170##", 2, ZONE_CONTEXT_HEATING, ZONE_STATE_SETPOINT, 17.0,
         "Zone 2 is in heating setpoint at 17.0°C."),
        ("*#4*1*7*2*1*0225##", 1, ZONE_CONTEXT_COOLING, ZONE_STATE_SETPOINT, 22.5,
         "Zone 1 is in cooling setpoint at 22.5°C."),
        ("*#4*4*7*1*2##", 4, ZONE_CONTEXT_HEATING, ZONE_STATE_PROTECTION, None,
         "Zone 4 is in heating protection."),
    ],
)
def test_dimension_7_zone_state_captures(
    frame: str, zone: int, context: str, state: str, temperature: float | None, log: str
) -> None:
    event = OWNMessage.parse(frame)

    assert isinstance(event, OWNHeatingEvent)
    assert event.message_type == MESSAGE_TYPE_ZONE_STATE
    assert event.zone == zone
    assert event.zone_context == context
    assert event.zone_state == state
    assert event.set_temperature == temperature
    assert event.human_readable_log == log


@pytest.mark.parametrize(
    ("raw", "context"),
    [("0", ZONE_CONTEXT_GENERIC), ("1", ZONE_CONTEXT_HEATING),
     ("2", ZONE_CONTEXT_COOLING), ("3", ZONE_CONTEXT_AUTOMATIC)],
)
@pytest.mark.parametrize(
    ("raw_state", "state"),
    [("2", ZONE_STATE_PROTECTION), ("3", ZONE_STATE_COMFORT),
     ("4", ZONE_STATE_ECO), ("5", ZONE_STATE_OFF)],
)
def test_dimension_7_follows_the_scenario_devices_table(
    raw: str, context: str, raw_state: str, state: str
) -> None:
    # Encyclopedia who-4-temperature-control/dimensions.md, MyHOME_Suite
    # ScenarioDevices DIMENSION 7 templates.
    event = OWNHeatingEvent(f"*#4*3*7*{raw}*{raw_state}##")

    assert event.message_type == MESSAGE_TYPE_ZONE_STATE
    assert (event.zone_context, event.zone_state) == (context, state)
    assert event.set_temperature is None


@pytest.mark.parametrize("frame", ["*#4*3*7*9*1*0200##", "*#4*3*7*1*9##", "*#4*3*7*1##"])
def test_dimension_7_unknown_values_have_no_message_type(frame: str) -> None:
    event = OWNHeatingEvent(frame)

    assert event.message_type is None
    assert event.set_temperature is None
    assert "unknown zone state" in event.human_readable_log


def test_dimension_7_setpoint_without_a_valid_temperature() -> None:
    event = OWNHeatingEvent("*#4*3*7*1*1*20##")

    assert event.message_type == MESSAGE_TYPE_ZONE_STATE
    assert event.zone_state == ZONE_STATE_SETPOINT
    assert event.set_temperature is None
    assert event.human_readable_log == "Zone 3 is in heating setpoint."


def test_dimension_7_write_echo_has_a_log() -> None:
    # MyHomeServer1 runs its schedule by writing dimension 7 (xtimmy86x trace).
    command = OWNMessage.parse("*#4*2*#7*1*1*0200##")

    assert isinstance(command, OWNHeatingCommand)
    assert command.human_readable_log == "Setting zone 2 to heating setpoint at 20.0°C."
    # MyHOME_Suite templates end non-setpoint writes with an empty value.
    assert OWNHeatingCommand("*#4*2*#7*2*3*##").human_readable_log == "Setting zone 2 to cooling comfort."
    assert OWNHeatingCommand("*#4*2*#7*9*9##").human_readable_log == "Setting zone 2 to unknown zone state 9*9."


def test_dimension_5_status_and_write_have_a_log() -> None:
    # Re-asserted on every zone every ~794 s by MyHomeServer1 (MyHOME#429).
    event = OWNMessage.parse("*#4*2*5*0##")
    command = OWNMessage.parse("*#4*2*#5*0##")

    assert isinstance(event, OWNHeatingEvent)
    assert event.message_type is None
    assert event.human_readable_log == "Zone 2's local control (dimension 5) is 0."
    assert isinstance(command, OWNHeatingCommand)
    assert command.human_readable_log == "Setting zone 2's local control (dimension 5) to 0."


def test_heating_builders_keep_their_own_log() -> None:
    assert OWNHeatingCommand.status("2").human_readable_log == "Requesting climate status update for 2."
