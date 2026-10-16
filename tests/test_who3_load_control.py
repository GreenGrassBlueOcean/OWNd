"""WHO 3 load control, pinned to the firmware oracle first and the specification second.

Firmware: ``bt_energia`` v2.0.2 (2003-05-08) ARM binary and
``tests/golden/firmware_oracle.json``, suite ``energy-ts10``
(https://github.com/OpenWebNet-HA/own-firmware-oracle/blob/main/oracle/cases/energy-ts10.cases#L69-L86).
All seven gateways packaging ``bt_energia`` (F453AV, F454, F459, H4684, MH200,
MH200N, MH202) agree on every WHO 3 input in the oracle fixture: ``*3*2*#N##``
is ACKed and emits ``$04B70N1300``, while ``*#3*#N##`` and ``*#3*10*D##``
put their ``$03AA0016xx`` register reads on the bus and reply NACK on the
command session (when no F421 answers within the 4 s bus timeout, opposite to
``WHO_3.pdf`` p. 6 "ACK if command is sent to Bus"). Gateways without
``bt_energia`` (MyHomeServer1, F461, F460, F450) silently NACK all 15 WHO 3
inputs.

Specification: WHO 3 Load Control v1.0.0 (2006-08-30, archived at
https://archive.openwebnet-ha.org/sha256/4f/68/4f685a6ee3b16e6a7994a338186687bcea1dabba74dc5d24d22a07becb24dea1.pdf,
pp. 4, 6-7) via the OpenWebNet Encyclopedia
(https://github.com/OpenWebNet-HA/OpenWebNet-Encyclopedia/blob/main/functional/who-3-load-management/README.md#measurement-dimension-values).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from OWNd.message import (
    LOAD_DIMENSION_ALL,
    LOAD_DIMENSION_CURRENT,
    LOAD_DIMENSION_ENERGY,
    LOAD_DIMENSION_POWER,
    LOAD_DIMENSION_VOLTAGE,
    LOAD_STATE_DISABLED,
    LOAD_STATE_ENABLED,
    LOAD_STATE_FORCED,
    LOAD_STATE_FORCING_REMOVED,
    OWNCommand,
    OWNEvent,
    OWNLoadCommand,
    OWNLoadEvent,
    OWNMessage,
)
from OWNd.message.load import _safe_int

ORACLE = json.loads(
    (Path(__file__).parent / "golden" / "firmware_oracle.json").read_text(encoding="utf-8")
)["verdicts"]
BT_ENERGIA_GATEWAYS = (
    "F453AV",
    "F454",
    "F459",
    "H4684",
    "MH200",
    "MH200N",
    "MH202",
)
WITHOUT_BT_ENERGIA_GATEWAYS = ("F450", "F460", "F461", "MyHomeServer1")
WHO3_INPUTS = sorted(f for f in ORACLE if f.startswith(("*3*", "*#3*")))


def _bt_energia_rows(frame: str) -> list[dict[str, Any]]:
    rows = [r for r in ORACLE[frame] if r["product"] in BT_ENERGIA_GATEWAYS]
    assert {r["product"] for r in rows} == set(BT_ENERGIA_GATEWAYS)
    return rows


def _forwarded(frame: str) -> bool:
    """Put on the bus with at least one SCS telegram by every bt_energia gateway."""
    return all(
        r["verdict"] == "out" and bool(r["bus_frames"]) for r in _bt_energia_rows(frame)
    )


def _refused(frame: str) -> bool:
    return all(
        r["reply"] == "nack" and r["verdict"] == "silent" for r in _bt_energia_rows(frame)
    )


def _bus_text(row: dict[str, Any]) -> list[str]:
    return [bytes.fromhex(b.replace(" ", "")).decode().strip() for b in row["bus_frames"]]


def _all_builder_frames() -> set[str]:
    frames = {str(OWNLoadCommand.force(p)) for p in range(1, 9)}
    frames |= {str(OWNLoadCommand.status(p)) for p in range(1, 9)}
    frames |= {str(OWNLoadCommand.request_measurement(d)) for d in range(5)}
    return frames


def test_gateways_without_bt_energia_refuse_all_who3_frames():
    assert len(BT_ENERGIA_GATEWAYS) == 7
    for frame in WHO3_INPUTS:
        rows = {r["product"]: r for r in ORACLE[frame]}
        for gw in WITHOUT_BT_ENERGIA_GATEWAYS:
            assert rows[gw]["reply"] == "nack"
            assert rows[gw]["verdict"] == "silent"
            assert rows[gw]["bus_frames"] == []


def test_oracle_covers_who3():
    assert len(WHO3_INPUTS) == 15


@pytest.mark.parametrize("frame", WHO3_INPUTS)
def test_every_oracle_input_dispatches_to_load_classes(frame: str):
    parsed = OWNMessage.parse(frame)
    expected = OWNLoadEvent if frame.startswith("*3*") else OWNLoadCommand
    assert isinstance(parsed, expected)
    assert parsed.is_valid
    assert isinstance(OWNCommand.parse(frame), OWNLoadCommand)


@pytest.mark.parametrize("priority", [1, 2])
def test_force_is_forwarded_with_priority_in_the_telegram(priority: int):
    frame = str(OWNLoadCommand.force(priority))
    assert frame == f"*3*2*#{priority}##"
    rows = _bt_energia_rows(frame)
    for row in rows:
        assert row["reply"] == "ack"
        assert row["verdict"] == "out"
        assert _bus_text(row) == [f"$04B70{priority}1300"]
    echoing_gateways = {r["product"] for r in rows if r["emitted_own"] == [frame]}
    assert echoing_gateways == {"F453AV", "F459", "H4684", "MH200", "MH200N", "MH202"}


def test_force_echo_on_event_session_parses_as_forced():
    echoed = {own for rows in ORACLE.values() for r in rows for own in r["emitted_own"]}
    load_echoes = sorted(e for e in echoed if e.startswith("*3*"))
    assert load_echoes == ["*3*2*#1##", "*3*2*#2##"]
    for frame in load_echoes:
        event = OWNEvent.parse(frame)
        assert isinstance(event, OWNLoadEvent)
        assert event.is_forced is True
        assert event.priority == int(frame[-3])


def test_every_oracle_backed_builder_frame_reaches_the_bus():
    in_oracle = _all_builder_frames() & set(ORACLE)
    assert in_oracle == {
        "*3*2*#1##",
        "*3*2*#2##",
        "*#3*#1##",
        "*#3*#2##",
        "*#3*10*0##",
        "*#3*10*1##",
        "*#3*10*2##",
        "*#3*10*3##",
        "*#3*10*4##",
    }
    assert all(_forwarded(f) for f in in_oracle)


@pytest.mark.parametrize(
    ("frame", "expected_bus"),
    [
        ("*#3*#1##", ["$03AA001614"]),
        ("*#3*#2##", ["$03AA001614"]),
        (
            "*#3*10*0##",
            [
                "$03AA001613",
                "$03AA001612",
                "$03AA001610",
                "$03AA001611",
                "$03AA001606",
                "$03AA001607",
                "$03AA001608",
                "$03AA001609",
            ],
        ),
        ("*#3*10*1##", ["$03AA001613"]),
        ("*#3*10*2##", ["$03AA001612"]),
        ("*#3*10*3##", ["$03AA001610", "$03AA001611"]),
        (
            "*#3*10*4##",
            ["$03AA001606", "$03AA001607", "$03AA001608", "$03AA001609"],
        ),
    ],
)
def test_status_and_measurement_requests_reply_nack_while_forwarding_to_bus(
    frame: str, expected_bus: list[str]
):
    """In the oracle fixture, *#3*#N## and *#3*10*D## reply NACK while emitting bus telegrams."""
    for row in _bt_energia_rows(frame):
        assert row["reply"] == "nack"
        assert row["verdict"] == "out"
        assert _bus_text(row) == expected_bus


def test_no_builder_emits_a_frame_the_gateways_refuse():
    refused = {f for f in WHO3_INPUTS if _refused(f)}
    assert refused == {
        "*#3*0##",
        "*3*0*#1##",
        "*3*0*0##",
        "*3*1*#1##",
        "*3*1*0##",
        "*3*3*#1##",
    }
    assert not refused & _all_builder_frames()


def test_measurement_requests_read_distinct_registers():
    """Each dimension maps to its own register run; dimension 0 reads the others.

    In ``bt_energia`` v2.0.2 (``0x00b140`` / ``0x00a63c``), register widths
    1/1/2/4 bytes are decoded as 8/8/16/32-bit integers formatted with ``%d``,
    matching the specification's Voltage (1) / Current (2) / Power (3) /
    Energy (4) order.
    """
    assert LOAD_DIMENSION_ALL == 0
    assert LOAD_DIMENSION_VOLTAGE == 1
    assert LOAD_DIMENSION_CURRENT == 2
    assert LOAD_DIMENSION_POWER == 3
    assert LOAD_DIMENSION_ENERGY == 4
    for gateway in BT_ENERGIA_GATEWAYS:
        registers = {
            d: next(
                _bus_text(r)
                for r in _bt_energia_rows(f"*#3*10*{d}##")
                if r["product"] == gateway
            )
            for d in range(5)
        }
        assert registers[LOAD_DIMENSION_VOLTAGE] == ["$03AA001613"]
        assert registers[LOAD_DIMENSION_CURRENT] == ["$03AA001612"]
        assert registers[LOAD_DIMENSION_POWER] == ["$03AA001610", "$03AA001611"]
        assert registers[LOAD_DIMENSION_ENERGY] == [
            "$03AA001606",
            "$03AA001607",
            "$03AA001608",
            "$03AA001609",
        ]
        others = (
            registers[LOAD_DIMENSION_VOLTAGE]
            + registers[LOAD_DIMENSION_CURRENT]
            + registers[LOAD_DIMENSION_POWER]
            + registers[LOAD_DIMENSION_ENERGY]
        )
        assert registers[LOAD_DIMENSION_ALL] == others


@pytest.mark.parametrize(
    ("frame", "state", "text"),
    [
        ("*3*0*#3##", LOAD_STATE_DISABLED, "Load priority 3 is disabled."),
        ("*3*1*#8##", LOAD_STATE_ENABLED, "Load priority 8 is enabled."),
        ("*3*2*#1##", LOAD_STATE_FORCED, "Load priority 1 is forced."),
        ("*3*3*#5##", LOAD_STATE_FORCING_REMOVED, "Load priority 5 is no longer forced."),
        ("*3*1*0##", LOAD_STATE_ENABLED, "All load priorities are enabled."),
    ],
)
def test_specified_state_frames(frame: str, state: int, text: str):
    event = OWNEvent.parse(frame)
    assert isinstance(event, OWNLoadEvent)
    assert event.state == state
    assert event.is_forced is (state == LOAD_STATE_FORCED)
    assert event.human_readable_log == text


def test_priority_keeps_its_hash_and_rejects_out_of_range():
    assert OWNLoadEvent("*3*2*#4##").where == "#4"
    assert OWNLoadEvent("*3*2*#4##").priority == 4
    assert OWNLoadEvent("*3*2*#9##").priority is None
    assert OWNLoadEvent("*3*2*4##").priority is None
    assert OWNLoadEvent("*3*2*4##").human_readable_log == "Load 4 is forced."


def test_unknown_what_keeps_the_raw_frame():
    event = OWNLoadEvent("*3*7*#1##")
    assert event.state is None
    assert event.is_forced is None
    assert event.priority == 1
    assert event.human_readable_log == "*3*7*#1##"


def test_measurement_reply_all_measurements():
    event = OWNEvent.parse("*#3*10*0*230*12*2760*1520##")
    assert isinstance(event, OWNLoadEvent)
    assert event.is_control_unit
    assert event.dimension == 0
    assert event.measurement_values == ["230", "12", "2760", "1520"]
    assert event.voltage == 230
    assert event.current == 12
    assert event.power == 2760
    assert event.energy == 1520
    assert event.state is None
    assert event.human_readable_log == (
        "Load control unit all measurements: voltage=230 V, current=12 A, "
        "power=2760 W, energy=1520."
    )


@pytest.mark.parametrize(
    ("frame", "dim", "attr", "expected_value", "log_phrase"),
    [
        ("*#3*10*1*230##", LOAD_DIMENSION_VOLTAGE, "voltage", 230, "voltage: 230 V."),
        ("*#3*10*2*12##", LOAD_DIMENSION_CURRENT, "current", 12, "current: 12 A."),
        ("*#3*10*3*2760##", LOAD_DIMENSION_POWER, "power", 2760, "power: 2760 W."),
        ("*#3*10*4*1520##", LOAD_DIMENSION_ENERGY, "energy", 1520, "energy: 1520."),
    ],
)
def test_measurement_reply_individual_dimensions(
    frame: str, dim: int, attr: str, expected_value: int, log_phrase: str
):
    event = OWNEvent.parse(frame)
    assert isinstance(event, OWNLoadEvent)
    assert event.is_control_unit
    assert event.dimension == dim
    assert getattr(event, attr) == expected_value
    assert log_phrase in event.human_readable_log


def test_safe_int():
    assert _safe_int(None) is None
    assert _safe_int("not_a_number") is None
    assert _safe_int("100") == 100


def test_measurement_reply_empty_or_partial():
    empty_voltage = OWNEvent.parse("*#3*10*1*##")
    assert isinstance(empty_voltage, OWNLoadEvent)
    assert empty_voltage.voltage is None

    empty_power = OWNEvent.parse("*#3*10*3*##")
    assert isinstance(empty_power, OWNLoadEvent)
    assert empty_power.power is None

    partial = OWNEvent.parse("*#3*10*0*230##")
    assert isinstance(partial, OWNLoadEvent)
    assert partial.voltage == 230
    assert partial.current is None
    assert partial.power is None
    assert partial.energy is None


def test_unnamed_dimension_and_other_where_are_not_measurements():
    assert OWNLoadEvent("*#3*10*9*1##").human_readable_log == (
        "Load control unit dimension 9: raw values ['1']."
    )
    other = OWNLoadEvent("*#3*#1*1*5##")
    assert other.measurement_values == []
    assert not other.is_control_unit


@pytest.mark.parametrize(
    ("command", "frame", "text"),
    [
        (OWNLoadCommand.force(3), "*3*2*#3##", "Forcing load priority 3."),
        (OWNLoadCommand.status(8), "*#3*#8##", "Requesting load priority 8 status."),
        (OWNLoadCommand.request_measurement(), "*#3*10*0##", "Requesting load control unit dimension 0."),
        (OWNLoadCommand.request_measurement(4), "*#3*10*4##", "Requesting load control unit dimension 4."),
    ],
)
def test_builders(command: OWNLoadCommand, frame: str, text: str):
    assert str(command) == frame
    assert command.is_valid
    assert command.human_readable_log == text


@pytest.mark.parametrize("frame", ["*3*2*0##", "*#3*0##", "*#3*#1*1##", "*3*1*#1##"])
def test_parsed_commands_without_a_specific_log_keep_the_raw_frame(frame: str):
    assert OWNLoadCommand(frame).human_readable_log == frame


@pytest.mark.parametrize("priority", [0, 9, -1])
def test_priority_validation(priority: int):
    with pytest.raises(ValueError, match="between 1 and 8"):
        OWNLoadCommand.force(priority)
    with pytest.raises(ValueError, match="between 1 and 8"):
        OWNLoadCommand.status(priority)


@pytest.mark.parametrize("dimension", [-1, 5])
def test_dimension_validation(dimension: int):
    with pytest.raises(ValueError, match="between 0 and 4"):
        OWNLoadCommand.request_measurement(dimension)
