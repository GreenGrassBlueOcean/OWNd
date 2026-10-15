"""Findings from a physical BTicino F461 (firmware 2.0.11), captured 2026-10-15.

The frames live in ``tests/fixtures/f461_live_2026-10-15/frames.jsonl`` (see its README for
the plant and the file format). Three OWNd behaviours were wrong against that plant:

1. ``*#4*Z*19*5*1##`` (cooling side "fan coil off", heating valve ON) parsed as *not active*,
   because the fan-coil branch of the dimension 19 parser overwrote ``_is_active`` after the
   valve states had set it. The plant reports this frame on every heating-season read.
2. ``set_mode(zone, "protection" | "antifreeze" | "thermal_protection", standalone=True)``
   produced the ``#Z`` form, which the gateway forwards to a central unit (emulated
   ``bt_termo``: ``*4*302*#23##`` -> ``D1 00 03 02 C2 17 07 00``) and which a standalone
   thermostat ignores; the plain form (``93 17 30 04``) is the one that works. Only
   ``311`` (automatic) is a central-unit-only command (``*4*311*Z##`` is NACKed).
3. WHO 13 device type ``200`` was labelled ``F454`` although F454, MyHomeServer1, MH202,
   F461 and H4890 all answer it.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from OWNd.message import OWNCommand, OWNEvent, OWNHeatingCommand, OWNMessage

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "f461_live_2026-10-15" / "frames.jsonl"


@pytest.fixture(scope="module")
def rows() -> list[dict]:
    assert FIXTURE.is_file(), FIXTURE
    return [json.loads(line) for line in FIXTURE.open(encoding="utf-8")]


def _rx(rows: list[dict]) -> list[str]:
    return [r["frame"] for r in rows if r["dir"] == "rx"]


def _probe_tx(rows: list[dict], frame: str) -> list[dict]:
    return [r for r in rows if r["dir"] == "tx" and r["frame"] == frame and "utc" in r]


# ---------------------------------------------------------------------- the capture itself

def test_every_frame_the_gateway_sent_parses(rows: list[dict]) -> None:
    unparsed = []
    for raw in set(_rx(rows)):
        if raw in ("*#*1##", "*#*0##"):
            continue
        msg = OWNMessage.parse(raw)
        if msg is None or not msg.is_valid:
            unparsed.append(raw)
    assert unparsed == []


def test_capture_shows_the_zone_status_request_is_answered(rows: list[dict]) -> None:
    """``*#4*2##`` is answered with five frames on this F461 (MyHOME #674 says it times out on an F455)."""
    answered = [r for r in rows if r["dir"] == "result" and r["frame"] == "*#4*2##" and r["ack"]]
    assert answered, "no ACKed *#4*2## in the capture"
    assert answered[0]["replies"] == [
        "*#4*2*0*0241##", "*#4*2*12*0245*3##", "*4*1*2##", "*#4*2*14*0245*3##", "*#4*2*13*00##",
    ]
    assert str(OWNHeatingCommand.status("2")) == "*#4*2##"
    refused = [r for r in rows if r["dir"] == "result" and r["frame"] == "*#4*0##"]
    assert refused and not any(r["ack"] for r in refused), "*#4*0## was expected to be NACKed"


# ---------------------------------------------------------------------- 1. dimension 19

@pytest.mark.parametrize(
    "frame, active, heating, cooling, cooling_fan_on, fan_on",
    [
        ("*#4*2*19*5*1##", True, True, False, False, None),   # captured: heating season, valve open
        ("*#4*2*19*5*0##", False, False, False, False, None),  # captured: cooling season, idle
        ("*#4*2*19*8*0##", True, False, True, True, None),    # captured: cooling season, fan coil speed 3
        ("*#4*2*19*1*5##", True, False, True, None, False),   # mirror of the first one
        ("*#4*2*19*5*5##", False, False, False, False, False),
        ("*#4*2*19*0*6##", True, True, False, None, True),
        ("*#4*2*19*0*1##", True, True, False, None, None),    # valve-only plants, unchanged
        ("*#4*2*19*1*0##", True, False, True, None, None),
        ("*#4*2*19*0*0##", False, False, False, None, None),
    ],
)
def test_dimension_19_is_active_combines_both_sides(frame, active, heating, cooling, cooling_fan_on, fan_on) -> None:
    msg = OWNEvent.parse(frame)
    assert msg.is_active() is active, msg.human_readable_log
    assert msg.is_heating() is heating
    assert msg.is_cooling() is cooling
    assert msg.cooling_fan_on is cooling_fan_on
    assert msg.fan_on is fan_on


def test_captured_dimension_19_frames_are_active_whenever_a_valve_or_fan_is_on(rows: list[dict]) -> None:
    seen = {raw for raw in _rx(rows) if raw.startswith("*#4*2*19*")}
    assert {"*#4*2*19*5*1##", "*#4*2*19*5*0##", "*#4*2*19*8*0##"} <= seen
    for raw in seen:
        msg = OWNEvent.parse(raw)
        cooling_value, heating_value = (int(v) for v in raw[:-2].split("*")[4:6])
        # 1 on, 2 opened, 6/7/8 fan coil running: anything else on both sides is idle
        expected = any(v in (1, 2, 6, 7, 8) for v in (cooling_value, heating_value))
        assert msg.is_active() is expected, raw


# ---------------------------------------------------------------------- 2. protection addressing

def test_protection_follows_standalone_but_automatic_stays_central() -> None:
    assert str(OWNHeatingCommand.set_mode("2", "protection", standalone=True)) == "*4*302*2##"
    assert str(OWNHeatingCommand.set_mode("2", "antifreeze", standalone=True)) == "*4*102*2##"
    assert str(OWNHeatingCommand.set_mode("2", "thermal_protection", standalone=True)) == "*4*202*2##"
    assert str(OWNHeatingCommand.set_protection("2", standalone=True)) == "*4*302*2##"
    # a zone under a central unit keeps the #Z form
    assert str(OWNHeatingCommand.set_mode("2", "protection")) == "*4*302*#2##"
    assert str(OWNHeatingCommand.set_mode("#2#1", "protection")) == "*4*302*#2#1##"
    # automatic is the central unit's program whatever the flag says
    assert str(OWNHeatingCommand.set_mode("2", "auto", standalone=True)) == "*4*311*#2##"
    assert str(OWNHeatingCommand.set_mode("2", "off", standalone=True)) == "*4*303*2##"


def test_capture_shows_only_the_plain_protection_form_acts(rows: list[dict]) -> None:
    plain = _probe_tx(rows, "*4*302*2##")
    hashed = _probe_tx(rows, "*4*302*#2##")
    assert plain and hashed
    assert plain[0]["ack"] and "*4*202*2##" in plain[0]["events_after"], plain[0]
    assert hashed[0]["ack"] and not any(e.startswith("*4*202*") or e.startswith("*4*302*") for e in hashed[0]["events_after"]), hashed[0]
    auto = _probe_tx(rows, "*4*311*#2##")
    assert auto and auto[0]["ack"] and not any(e.startswith("*4*311*") for e in auto[0]["events_after"])
    nacked = [r for r in rows if r["dir"] == "result" and r["frame"] == "*4*311*2##"]
    assert nacked and not nacked[0]["ack"]


# ---------------------------------------------------------------------- 3. WHO 13 device type 200

def test_device_type_200_is_not_a_single_model() -> None:
    msg = OWNEvent.parse("*#13**15*200##")
    assert msg.device_type_code == "200"
    assert "F454" in msg.device_type and "F461" in msg.device_type
    assert msg.human_readable_log == f"Gateway device type is: {msg.device_type}."
    assert OWNEvent.parse("*#13**15*2##").device_type == "MHServer"
    assert OWNEvent.parse("*#13**16*2*0*11##").device_type_code is None
    assert OWNEvent.parse("*#1013**1*134*15*5*0##") is not None


def test_capture_identity_sequence(rows: list[dict]) -> None:
    rx = _rx(rows)
    assert "*#13**15*200##" in rx
    assert "*#1013**1*134*15*5*0##" in rx  # pushed on the event session right after the type reply
    assert "*#13**16*2*0*11##" in rx


# ---------------------------------------------------------------------- what still works

def test_builders_used_by_myhome_match_frames_the_plant_accepted(rows: list[dict]) -> None:
    acked = {r["frame"] for r in rows if r["dir"] in ("result", "tx") and r.get("ack")}
    for cmd in (
        OWNHeatingCommand.set_temperature("2", 21.0, "heat", standalone=True),
        OWNHeatingCommand.set_temperature("2", 25.0, "cool", standalone=True),
        OWNHeatingCommand.set_temperature("2", 22.0, "auto", standalone=True),
        OWNHeatingCommand.set_mode("2", "off", standalone=True),
        OWNHeatingCommand.set_fan_speed("2", 1),
        OWNCommand.parse("*#1*01##"),
        OWNCommand.parse("*1*1*01##"),
        OWNCommand.parse("*1*20*01##"),
        OWNCommand.parse("*#1*00##"),
    ):
        assert str(cmd) in acked, str(cmd)
