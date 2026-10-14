"""Tests for WHO 18 Stop&Go automatic reset breakers (F16EB).

Firmware provenance: findings/MyHomeServer1/energy-ts10.md
Empirical verification across MyHomeServer1 (028206), MH202 (010024), and F454 (020051).
"""

from __future__ import annotations

import pytest

from OWNd.message import (
    MESSAGE_TYPE_STOP_AND_GO,
    STOP_AND_GO_AUTORESET_DISABLE,
    STOP_AND_GO_AUTORESET_ENABLE,
    STOP_AND_GO_CLOSE,
    STOP_AND_GO_DIM_STATUS_MASK,
    STOP_AND_GO_DIM_TEST_FREQUENCY,
    STOP_AND_GO_OPEN,
    STOP_AND_GO_TEST_NEGATIVE,
    STOP_AND_GO_TEST_POSITIVE,
    STOP_AND_GO_TRACKING_DISABLE,
    STOP_AND_GO_TRACKING_ENABLE,
    OWNCommand,
    OWNEnergyCommand,
    OWNEnergyEvent,
    OWNEvent,
    OWNMessage,
    OWNStopAndGoCommand,
    OWNStopAndGoEvent,
)


@pytest.mark.parametrize(
    ("frame", "what", "is_open", "is_closed", "log_phrase"),
    [
        ("*18*21*11##", STOP_AND_GO_OPEN, True, False, "is open"),
        ("*18*22*11##", STOP_AND_GO_CLOSE, False, True, "is closed"),
    ],
)
def test_stop_and_go_breaker_open_close_status(
    frame: str, what: int, is_open: bool, is_closed: bool, log_phrase: str
) -> None:
    event = OWNEvent.parse(frame)
    assert isinstance(event, OWNStopAndGoEvent)
    assert event.who == 18
    assert event.where == "11"
    assert event.line == 1
    assert event.state == what
    assert event.is_open is is_open
    assert event.is_closed is is_closed
    assert event.message_type == MESSAGE_TYPE_STOP_AND_GO
    assert log_phrase in event.human_readable_log


@pytest.mark.parametrize(
    ("frame", "passed", "result"),
    [
        ("*18*23*11##", True, "positive"),
        ("*18*24*11##", False, "negative"),
    ],
)
def test_stop_and_go_differential_test_events(
    frame: str, passed: bool, result: str
) -> None:
    event = OWNEvent.parse(frame)
    assert isinstance(event, OWNStopAndGoEvent)
    assert event.differential_test_passed is passed
    assert event.differential_test_result == result
    assert "differential test" in event.human_readable_log


@pytest.mark.parametrize(
    ("frame", "active"),
    [
        ("*18*26*12##", True),
        ("*18*27*12##", False),
    ],
)
def test_stop_and_go_autoreset_events(frame: str, active: bool) -> None:
    event = OWNEvent.parse(frame)
    assert isinstance(event, OWNStopAndGoEvent)
    assert event.line == 2
    assert event.is_auto_reset_active is active
    assert "auto-reset" in event.human_readable_log


@pytest.mark.parametrize(
    ("frame", "active"),
    [
        ("*18*28*19##", True),
        ("*18*29*19##", False),
    ],
)
def test_stop_and_go_tracking_events(frame: str, active: bool) -> None:
    event = OWNEvent.parse(frame)
    assert isinstance(event, OWNStopAndGoEvent)
    assert event.line == 9
    assert event.is_tracking_active is active
    assert "tracking" in event.human_readable_log


def test_stop_and_go_dimension_test_frequency_event() -> None:
    event = OWNEvent.parse("*#18*11*212*10##")
    assert isinstance(event, OWNStopAndGoEvent)
    assert event.line == 1
    assert event.test_frequency_days == 10
    assert "test frequency is 10 days" in event.human_readable_log


def test_stop_and_go_dimension_status_mask_event() -> None:
    event = OWNEvent.parse("*#18*11*250*1##")
    assert isinstance(event, OWNStopAndGoEvent)
    assert event.line == 1
    assert event.status_mask == "1"
    assert "status mask is 1" in event.human_readable_log


@pytest.mark.parametrize(
    ("builder", "expected_frame"),
    [
        (OWNStopAndGoCommand.open_breaker(11), "*18*21*11##"),
        (OWNStopAndGoCommand.open_breaker(1), "*18*21*11##"),
        (OWNStopAndGoCommand.close_breaker("12"), "*18*22*12##"),
        (OWNStopAndGoCommand.close_breaker(2), "*18*22*12##"),
        (OWNStopAndGoCommand.test_differential_positive(11), "*18*23*11##"),
        (OWNStopAndGoCommand.test_differential_negative(11), "*18*24*11##"),
        (OWNStopAndGoCommand.enable_auto_reset(11), "*18*26*11##"),
        (OWNStopAndGoCommand.disable_auto_reset(11), "*18*27*11##"),
        (OWNStopAndGoCommand.set_auto_reset(11, True), "*18*26*11##"),
        (OWNStopAndGoCommand.set_auto_reset(11, False), "*18*27*11##"),
        (OWNStopAndGoCommand.enable_tracking(11), "*18*28*11##"),
        (OWNStopAndGoCommand.disable_tracking(11), "*18*29*11##"),
        (OWNStopAndGoCommand.set_tracking(11, True), "*18*28*11##"),
        (OWNStopAndGoCommand.set_tracking(11, False), "*18*29*11##"),
        (OWNStopAndGoCommand.set_test_frequency(11, 10), "*#18*11*#212*10##"),
        (OWNStopAndGoCommand.request_test_frequency(11), "*#18*11*212##"),
        (OWNStopAndGoCommand.request_status_mask(11), "*#18*11*250##"),
    ],
)
def test_stop_and_go_command_builders(
    builder: OWNStopAndGoCommand, expected_frame: str
) -> None:
    assert str(builder) == expected_frame
    parsed = OWNCommand.parse(expected_frame)
    assert isinstance(parsed, OWNStopAndGoCommand)


def test_stop_and_go_address_validation() -> None:
    with pytest.raises(ValueError, match="Stop&Go line address"):
        OWNStopAndGoCommand.open_breaker(0)
    with pytest.raises(ValueError, match="Stop&Go line address"):
        OWNStopAndGoCommand.open_breaker(10)
    with pytest.raises(ValueError, match="Stop&Go line address"):
        OWNStopAndGoCommand.open_breaker(20)
    with pytest.raises(ValueError, match="Stop&Go line address"):
        OWNStopAndGoCommand.open_breaker("invalid")


def test_stop_and_go_test_frequency_validation() -> None:
    with pytest.raises(ValueError, match="between 1 and 255"):
        OWNStopAndGoCommand.set_test_frequency(11, 0)
    with pytest.raises(ValueError, match="between 1 and 255"):
        OWNStopAndGoCommand.set_test_frequency(11, 256)


def test_energy_meter_events_not_diverted() -> None:
    """Ensure standard WHO 18 power and totalizer frames still parse as OWNEnergyEvent."""
    power_event = OWNEvent.parse("*#18*51*113*1500##")
    assert isinstance(power_event, OWNEnergyEvent)
    assert not isinstance(power_event, OWNStopAndGoEvent)
    assert power_event.active_power == 1500

    total_event = OWNEvent.parse("*#18*11*51*2500##")
    assert isinstance(total_event, OWNEnergyEvent)
    assert not isinstance(total_event, OWNStopAndGoEvent)
    assert total_event.total_consumption == 2500

    auto_event = OWNEvent.parse("*#18*51*1200#1*60##")
    assert isinstance(auto_event, OWNEnergyEvent)
    assert not isinstance(auto_event, OWNStopAndGoEvent)
    assert auto_event.stream_duration == 60


def test_energy_commands_not_diverted() -> None:
    """Ensure standard WHO 18 power commands still parse as OWNEnergyCommand."""
    cmd = OWNCommand.parse("*#18*51*113##")
    assert isinstance(cmd, OWNEnergyCommand)
    assert not isinstance(cmd, OWNStopAndGoCommand)
