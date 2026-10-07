"""Tests for WHO 3 Load control and shedding subsystem."""

from __future__ import annotations

import pytest

from OWNd.message import (
    MESSAGE_TYPE_ALL_MEASUREMENTS,
    MESSAGE_TYPE_CURRENT,
    MESSAGE_TYPE_LOAD_ACTIVE_POWER,
    MESSAGE_TYPE_LOAD_ENERGY,
    MESSAGE_TYPE_LOAD_STATE,
    MESSAGE_TYPE_VOLTAGE,
    OWNCommand,
    OWNEvent,
    OWNLoadCommand,
    OWNLoadEvent,
    OWNMessage,
)


def test_load_state_events() -> None:
    # Shed load: *3*0*#1##
    ev_shed = OWNMessage.parse("*3*0*#1##")
    assert isinstance(ev_shed, OWNLoadEvent)
    assert ev_shed.message_type == MESSAGE_TYPE_LOAD_STATE
    assert ev_shed.is_shed is True
    assert ev_shed.is_forced is False
    assert ev_shed.priority == 1
    assert "disabled (shed)" in ev_shed.human_readable_log

    # Enable load: *3*1*#1##
    ev_en = OWNEvent.parse("*3*1*#1##")
    assert isinstance(ev_en, OWNLoadEvent)
    assert ev_en.is_shed is False
    assert ev_en.is_forced is False
    assert ev_en.priority == 1
    assert "enabled (automatic)" in ev_en.human_readable_log

    # Force connect: *3*2*#1##
    ev_force = OWNEvent.parse("*3*2*#1##")
    assert isinstance(ev_force, OWNLoadEvent)
    assert ev_force.is_shed is False
    assert ev_force.is_forced is True
    assert ev_force.priority == 1
    assert "forced (connected)" in ev_force.human_readable_log

    # Remove forcing: *3*3*#1##
    ev_unforce = OWNEvent.parse("*3*3*#1##")
    assert isinstance(ev_unforce, OWNLoadEvent)
    assert ev_unforce.is_forced is False
    assert ev_unforce.priority == 1
    assert "Forcing removed" in ev_unforce.human_readable_log


def test_central_unit_measurements() -> None:
    # All measurements: *#3*10*0*230*15*3450*1200##
    ev_all = OWNEvent.parse("*#3*10*0*230*15*3450*1200##")
    assert isinstance(ev_all, OWNLoadEvent)
    assert ev_all.message_type == MESSAGE_TYPE_ALL_MEASUREMENTS
    assert ev_all.voltage == 230.0
    assert ev_all.current == 15.0
    assert ev_all.power == 3450.0
    assert ev_all.energy == 1200.0
    assert "V=230.0V, I=15.0A, P=3450.0W, E=1200.0Wh" in ev_all.human_readable_log

    # Voltage: *#3*10*1*230##
    ev_v = OWNEvent.parse("*#3*10*1*230##")
    assert isinstance(ev_v, OWNLoadEvent)
    assert ev_v.message_type == MESSAGE_TYPE_VOLTAGE
    assert ev_v.voltage == 230.0

    # Current: *#3*10*2*15##
    ev_i = OWNEvent.parse("*#3*10*2*15##")
    assert isinstance(ev_i, OWNLoadEvent)
    assert ev_i.message_type == MESSAGE_TYPE_CURRENT
    assert ev_i.current == 15.0

    # Power: *#3*10*3*3450##
    ev_p = OWNEvent.parse("*#3*10*3*3450##")
    assert isinstance(ev_p, OWNLoadEvent)
    assert ev_p.message_type == MESSAGE_TYPE_LOAD_ACTIVE_POWER
    assert ev_p.power == 3450.0

    # Energy: *#3*10*4*1200##
    ev_e = OWNEvent.parse("*#3*10*4*1200##")
    assert isinstance(ev_e, OWNLoadEvent)
    assert ev_e.message_type == MESSAGE_TYPE_LOAD_ENERGY
    assert ev_e.energy == 1200.0


def test_load_commands_and_builders() -> None:
    cmd_shed = OWNLoadCommand.shed(1)
    assert str(cmd_shed) == "*3*0*#1##"

    cmd_enable = OWNLoadCommand.enable(1)
    assert str(cmd_enable) == "*3*1*#1##"

    cmd_force = OWNLoadCommand.force_reconnect(1)
    assert str(cmd_force) == "*3*2*#1##"

    cmd_remove = OWNLoadCommand.remove_forcing(1)
    assert str(cmd_remove) == "*3*3*#1##"

    # Status requests
    cmd_st_pri = OWNLoadCommand.request_status(priority=1)
    assert str(cmd_st_pri) == "*#3*#1##"

    cmd_st_glob = OWNLoadCommand.request_status()
    assert str(cmd_st_glob) == "*#3*0##"

    # Measurement requests
    cmd_meas_all = OWNLoadCommand.request_measurements("10")
    assert str(cmd_meas_all) == "*#3*10*0##"

    cmd_meas_v = OWNLoadCommand.request_voltage("10")
    assert str(cmd_meas_v) == "*#3*10*1##"

    cmd_meas_i = OWNLoadCommand.request_current("10")
    assert str(cmd_meas_i) == "*#3*10*2##"

    cmd_meas_p = OWNLoadCommand.request_power("10")
    assert str(cmd_meas_p) == "*#3*10*3##"

    cmd_meas_e = OWNLoadCommand.request_energy("10")
    assert str(cmd_meas_e) == "*#3*10*4##"


def test_load_priority_validation() -> None:
    with pytest.raises(ValueError, match="Priority must be between 1 and 8"):
        OWNLoadCommand.shed(0)
    with pytest.raises(ValueError, match="Priority must be between 1 and 8"):
        OWNLoadCommand.shed(9)
    with pytest.raises(ValueError, match="Priority must be an integer"):
        OWNLoadCommand.shed("invalid")


def test_load_command_parse() -> None:
    cmd = OWNCommand.parse("*3*2*#1##")
    assert isinstance(cmd, OWNLoadCommand)
    assert str(cmd) == "*3*2*#1##"


def test_load_unexpected_what_and_dimension() -> None:
    ev_what = OWNEvent.parse("*3*99*#1##")
    assert isinstance(ev_what, OWNLoadEvent)
    assert "Load command 99 on priority #1." in ev_what.human_readable_log

    ev_dim = OWNEvent.parse("*#3*10*99*1##")
    assert isinstance(ev_dim, OWNLoadEvent)
    assert "Central unit 10 dimension 99." in ev_dim.human_readable_log
