"""Firmware Oracle Conformance Test Suite.

Verifies cross-firmware compatibility of OpenWebNet frames, OWNd parser
resilience on authentic firmware-emitted frames, and firmware rejection
guarantees against hash-pinned verdicts from own-firmware-oracle.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from OWNd.message import OWNLightingEvent, OWNMessage
from OWNd.profiles import GenericGatewayProfile, get_gateway_profile

REPO_ROOT = Path(__file__).resolve().parent.parent
ORACLE_JSON_PATH = REPO_ROOT / "tests" / "golden" / "firmware_oracle.json"
CORPUS_JSON_PATH = REPO_ROOT / "tests" / "golden" / "corpus.json"


def load_firmware_oracle() -> dict[str, Any]:
    """Load the firmware oracle verdict index."""
    if not ORACLE_JSON_PATH.is_file():
        return {"verdicts": {}, "gateways": []}
    with open(ORACLE_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


ORACLE_DATA = load_firmware_oracle()
ALL_VERDICTS: dict[str, list[dict[str, Any]]] = ORACLE_DATA.get("verdicts", {})


def test_firmware_oracle_integrity():
    """Verify cryptographic integrity and structure of firmware_oracle.json."""
    assert ORACLE_JSON_PATH.is_file(), "tests/golden/firmware_oracle.json fixture file missing"
    data = load_firmware_oracle()
    assert data["format_version"] == "1.0.0"
    assert data["generator"] == "own-firmware-oracle"
    assert data["schema_version"] == "1.1.0"

    verdicts = data["verdicts"]
    canonical_verdicts = json.dumps(verdicts, sort_keys=True, separators=(",", ":"))
    calculated_hash = hashlib.sha256(canonical_verdicts.encode("utf-8")).hexdigest()
    assert calculated_hash == data["verdicts_sha256"], (
        f"Verdicts SHA-256 digest mismatch: {calculated_hash} != {data['verdicts_sha256']}"
    )

    assert data["total_unique_inputs"] == len(verdicts) == 303
    assert len(data["gateways"]) == 10

    gateway_names = {f"{g['product']} {g['version']}" for g in data["gateways"]}
    expected_gateways = {
        "F450 020010",
        "F453AV 030014",
        "F454 020051",
        "F455 010102",
        "F459 020105",
        "F460 020012",
        "F461 020011",
        "MH200N 010108",
        "MH202 010024",
        "MyHomeServer1 028206",
    }
    assert gateway_names == expected_gateways

    # Verify 9 emulated gateways × 335 rows across 17 test suites (3,015 rows total)
    emulated_gateways = [g for g in data["gateways"] if g["status"] == "emulated"]
    assert len(emulated_gateways) == 9
    catalogued_gateways = [g for g in data["gateways"] if g["status"] == "catalogued"]
    assert len(catalogued_gateways) == 1
    assert catalogued_gateways[0]["product"] == "F455"

    total_rows = sum(len(entries) for entries in verdicts.values())
    assert total_rows == 3015

    for g in emulated_gateways:
        prod = g["product"]
        rows = [k for k, entries in verdicts.items() for e in entries if e.get("product") == prod]
        assert len(rows) == 335
        assert len(g["suites"]) == 17


def test_emitted_own_frames_parseable_by_ownd():
    """Verify that every OpenWebNet frame emitted by real firmware parses cleanly in OWNd.

    The fixture captures 43 unique authentic firmware-emitted frames across the fleet.
    Key diagnostic examples include:
    1. *1*19*74##: WHO 1 lighting diagnostic fault event (WHAT 19) emitted by MH200N.
    2. *#1001*74*11*111110111111111111110111##: WHO 1001 diagnostic device mask emitted by MH200N.
    """
    all_emitted: set[str] = set()
    for _inp, entries in ALL_VERDICTS.items():
        for entry in entries:
            for own_frame in entry.get("emitted_own", []):
                all_emitted.add(own_frame)

    assert len(all_emitted) == 43
    for frame in all_emitted:
        msg = OWNMessage.parse(frame)
        assert msg is not None, f"Failed to parse authentic emitted frame {frame}"

    assert "*1*19*74##" in all_emitted
    assert "*#1001*74*11*111110111111111111110111##" in all_emitted

    # 1. Semantic verification of WHO 1 lighting fault event
    fault_msg = OWNMessage.parse("*1*19*74##")
    assert isinstance(fault_msg, OWNLightingEvent)
    assert fault_msg.who == 1
    assert fault_msg.where == "74"
    assert fault_msg.unknown_state == 19
    assert fault_msg.is_on is None

    # 2. Semantic verification of WHO 1001 diagnostic state response
    diag_msg = OWNMessage.parse("*#1001*74*11*111110111111111111110111##")
    assert isinstance(diag_msg, OWNMessage)
    assert diag_msg.is_event is True
    assert diag_msg.who == 1001
    assert diag_msg.where == "74"
    assert getattr(diag_msg, "dimension", None) == 11
    assert getattr(diag_msg, "event_content", {}).get("dimension values") == ["111110111111111111110111"]


# Known protocol discrepancies between spec-derived/openwebnet4j corpus fixtures
# and actual gateway firmware behavior (audited in own-firmware-oracle):
KNOWN_GATEWAY_DISCREPANCIES = {
    # Central unit mode commands: MH200N accepts with ACK now that bt_termo is active
    ("thermo.cmd.central.mode.heat.cu99", "MH200N"): "ack",
    ("thermo.cmd.central.mode.cool.cu99", "MH200N"): "ack",
    ("thermo.cmd.central.mode.off.cu99", "MH200N"): "ack",
    ("thermo.cmd.central.mode.cool.cu99", "MyHomeServer1"): "ack",
    # Zone temperature request without configured probe on virtual bus:
    ("thermo.req.temp.zone1", "MH200N"): "nack",
    ("thermo.req.temp.zone1", "MyHomeServer1"): "nack",
    # Energy dimension 113: MH202 and MyHomeServer1 accept, MH200N returns NACK while forwarding to bus:
    ("energy.req.unit.meter51", "MH200N"): "nack",
    ("energy.req.unit.meter51", "MH202"): "ack",
    ("energy.req.unit.meter51", "MyHomeServer1"): "ack",
    # Bus events sent to command session (accepted on MH202 scenario programmer, refused on others):
    ("cen.event.extended_press.btn1.0001", "MH200N"): "nack",
    ("cen.event.extended_press.btn1.0001", "MH202"): "ack",
    ("cen_plus.event.short_press.btn1.21", "MH200N"): "nack",
    ("cen_plus.event.short_press.btn1.21", "MH202"): "ack",
    ("dry_contact.event.on.339", "MH200N"): "nack",
    ("dry_contact.event.on.339", "MH202"): "ack",
}


def test_golden_corpus_cross_validation_with_firmware_oracle():
    """Cross-validate golden corpus fixtures against empirical firmware oracle verdicts.

    Evaluates the intersection between declarative golden corpus fixtures and
    empirical firmware verdicts, asserting known architectural behaviors:
    - MH200N central unit mode commands (*4*...*#0##) are accepted with ACK via bt_termo.
    - MyHomeServer1 accepts central unit mode cool commands (*4*0*#0##) with ACK.
    - Bus event fixtures (CEN *15*01#3*0001##, CEN+ *25*21#1*21##) are refused with NACK
      on standard gateways when presented as command-session inputs, but accepted by MH202.
    - Energy dimension requests (*#18*51*113##) are accepted on MH202 and MyHomeServer1.
    """
    assert CORPUS_JSON_PATH.is_file(), "tests/golden/corpus.json fixture missing"
    with open(CORPUS_JSON_PATH, "r", encoding="utf-8") as f:
        corpus = json.load(f)

    # Cross-reference intersecting frames
    intersecting_fixtures: list[dict[str, Any]] = []
    for fixture in corpus:
        frame = fixture.get("frame")
        if frame in ALL_VERDICTS:
            intersecting_fixtures.append(fixture)

    # Exactly 8 fixtures in corpus.json intersect with current oracle inputs:
    assert len(intersecting_fixtures) == 8

    for fixture in intersecting_fixtures:
        fixture_id = fixture["id"]
        frame = fixture["frame"]
        entries = ALL_VERDICTS[frame]
        mcp_valid = fixture.get("mcp_valid", True)
        assert mcp_valid is True, f"Fixture {fixture_id} should be marked mcp_valid"

        for entry in entries:
            product = entry["product"]
            reply = entry["reply"]
            expected_discrepancy = KNOWN_GATEWAY_DISCREPANCIES.get((fixture_id, product))
            if expected_discrepancy is not None:
                assert reply == expected_discrepancy, (
                    f"Expected known discrepancy for {fixture_id} on {product} to be "
                    f"'{expected_discrepancy}', got '{reply}'"
                )


@pytest.mark.parametrize(
    ("frame", "expected_reply", "expected_verdict", "target_gateways"),
    [
        # Lighting brightness 100 refusal (level 100 is invalid; 101-200 are valid, 0 is switch-off)
        ("*#1*0*#1*100*0##", "nack", "silent", {"MH200N", "MyHomeServer1"}),
        ("*#1*31*#1*100*0##", "nack", "silent", {"MH200N", "MyHomeServer1"}),
        ("*#1*31*#1*100*255##", "nack", "silent", {"MH200N", "MyHomeServer1"}),
        ("*#1*31*#1*100*5##", "nack", "silent", {"MH200N", "MyHomeServer1"}),
        ("*#1*31*#1*220*0##", "nack", "silent", {"MH200N", "MyHomeServer1"}),
        # Thermo invalid central unit modes refused on both gateways
        ("*4*100*#0##", "nack", "silent", {"MH200N", "MyHomeServer1"}),
        ("*4*110*#0##", "nack", "silent", {"MH200N", "MyHomeServer1"}),
        # Matrix-refused legacy syntax (tested on MH200N target daemon)
        ("*2*1*21#4#1##", "nack", "silent", {"MH200N"}),
        ("*#1*1*#1*20##", "nack", "silent", {"MH200N"}),
        ("*#2*1*#1*50##", "nack", "silent", {"MH200N"}),
        ("*15*01*0001##", "nack", "silent", {"MH200N"}),
        ("*25*21*0001##", "nack", "silent", {"MH200N"}),
    ],
)
def test_known_firmware_rejections(
    frame: str, expected_reply: str, expected_verdict: str, target_gateways: set[str]
):
    """Verify that known protocol boundary frames produce expected rejections on target gateways."""
    assert frame in ALL_VERDICTS, f"Target frame {frame} missing from oracle verdicts"
    entries = ALL_VERDICTS[frame]
    assert len(entries) > 0

    target_entries = [e for e in entries if e["product"] in target_gateways]
    assert len(target_entries) >= len(target_gateways), (
        f"Frame {frame} missing entries for {target_gateways}"
    )

    for entry in target_entries:
        assert entry["reply"] == expected_reply, (
            f"Frame {frame} on {entry['product']} expected reply {expected_reply}, got {entry['reply']}"
        )
        assert entry["verdict"] == expected_verdict, (
            f"Frame {frame} on {entry['product']} expected verdict {expected_verdict}, got {entry['verdict']}"
        )


def test_what19_fault_emitted_event():
    """Verify that *#1*74## produces the expected WHAT 19 lighting fault event on MH200N."""
    frame = "*#1*74##"
    assert frame in ALL_VERDICTS, f"Frame {frame} missing from oracle index"
    entries = ALL_VERDICTS[frame]
    mh200n_entries = [e for e in entries if e["product"] == "MH200N"]
    assert len(mh200n_entries) > 0

    # MH200N emits bus frame and OWN event *1*19*74##
    found_fault_event = False
    for entry in mh200n_entries:
        assert entry["verdict"] == "out"
        if "*1*19*74##" in entry["emitted_own"]:
            found_fault_event = True

    assert found_fault_event, f"Expected *1*19*74## in emitted_own for {frame} on MH200N"

    # Verify OWNd parses *1*19*74## as OWNLightingEvent with unknown_state=19
    msg = OWNMessage.parse("*1*19*74##")
    assert isinstance(msg, OWNLightingEvent)
    assert msg.who == 1
    assert msg.where == "74"
    assert msg.unknown_state == 19
    assert msg.is_on is None


def test_all_gateway_responses_conform_to_openwebnet_protocol():
    """Verify that every verdict entry adheres strictly to OpenWebNet framing rules."""
    valid_replies = {"ack", "nack", "-"}
    valid_verdicts = {"out", "silent", "timeout", "crash"}

    for inp, entries in ALL_VERDICTS.items():
        assert inp.startswith("*") and inp.endswith("##"), f"Invalid input frame format: {inp}"
        for entry in entries:
            assert entry["reply"] in valid_replies, (
                f"Invalid reply '{entry['reply']}' for {inp} on {entry['product']}"
            )
            assert entry["verdict"] in valid_verdicts, (
                f"Invalid verdict '{entry['verdict']}' for {inp} on {entry['product']}"
            )
            for bus_hex in entry.get("bus_frames", []):
                # Verify bus frame consists of space-separated hex bytes
                tokens = bus_hex.split()
                assert len(tokens) > 0, f"Empty bus frame for {inp}"
                for token in tokens:
                    assert len(token) == 2, f"Invalid hex token '{token}' in bus frame '{bus_hex}'"
                    int(token, 16)  # Asserts valid hex representation
            for own_frame in entry.get("emitted_own", []):
                assert own_frame.startswith("*") and own_frame.endswith("##"), (
                    f"Invalid emitted OpenWebNet frame: {own_frame}"
                )


def test_firmware_nack_with_bus_forwarding():
    """Verify empirical cases where the gateway forwards bus frames but returns NACK.

    797 verdict rows exhibit this behavior across the fleet of 9 emulated gateways:
    - F460 forwards lighting, thermo, and sound commands to the SCS bus while returning NACK (239 rows).
    - F461 exhibits similar bus forwarding with NACK replies (238 rows).
    - MyHomeServer1 forwards lighting level writes, energy, sound, and thermo to the SCS bus (94 rows).
    - F454 forwards sound diffusion and energy commands (47 rows).
    - MH202 forwards scenario, energy, and intercom frames (44 rows).
    - F453AV forwards sound, video door entry, and energy frames (42 rows).
    - F450 forwards thermo frames (37 rows).
    - F459 forwards thermo and sound frames (36 rows).
    - MH200N forwards energy requests, thermo status, and WHO 25 frames (20 rows).
    """
    nack_and_out: list[tuple[str, str, str, list[str], list[str]]] = []
    for frame, entries in ALL_VERDICTS.items():
        for entry in entries:
            if entry.get("reply") == "nack" and entry.get("verdict") == "out":
                nack_and_out.append((
                    entry["product"],
                    entry["suite"],
                    frame,
                    entry.get("bus_frames", []),
                    entry.get("emitted_own", []),
                ))

    assert len(nack_and_out) == 797

    counts = Counter(item[0] for item in nack_and_out)
    assert counts["F460"] == 239
    assert counts["F461"] == 238
    assert counts["MyHomeServer1"] == 94
    assert counts["F454"] == 47
    assert counts["MH202"] == 44
    assert counts["F453AV"] == 42
    assert counts["F450"] == 37
    assert counts["F459"] == 36
    assert counts["MH200N"] == 20

    for _product, _suite, _frame, bus_frames, emitted_own in nack_and_out:
        assert len(bus_frames) > 0 or len(emitted_own) > 0, (
            "Expected forwarded bus frames or emitted OWN frames for verdict 'out'"
        )


def test_dimmer_level_cross_gateway_behavior():
    """Verify cross-gateway divergence on dimmer level write *1*0#1*31##.

    Both MH200N and MyHomeServer1 forward the identical SCS bus frame,
    but MH200N replies with ACK while MyHomeServer1 replies with NACK.
    """
    frame = "*1*0#1*31##"
    assert frame in ALL_VERDICTS
    entries = ALL_VERDICTS[frame]

    mh200n_entries = [e for e in entries if e["product"] == "MH200N"]
    mhs1_entries = [e for e in entries if e["product"] == "MyHomeServer1"]

    assert len(mh200n_entries) > 0, f"Missing MH200N entry for {frame}"
    assert len(mhs1_entries) > 0, f"Missing MyHomeServer1 entry for {frame}"

    # Both gateways transmit the identical bus frame to the lighting actuator:
    expected_bus = ["24 30 36 44 31 33 31 30 31 34 32 30 44 30 31 30 30 30 31 0d"]
    for e in mh200n_entries:
        assert e["bus_frames"] == expected_bus
        assert e["reply"] == "ack"
        assert e["verdict"] == "out"

    for e in mhs1_entries:
        assert e["bus_frames"] == expected_bus
        assert e["reply"] == "nack"
        assert e["verdict"] == "out"


def test_gateway_profiles_match_oracle_gateways():
    """Verify that profiles exist for all gateways catalogued in the firmware oracle."""
    data = load_firmware_oracle()
    gateways = data.get("gateways", [])
    assert len(gateways) == 10, "Expected all 10 gateway entries in oracle fixture"

    # 7 gateways have dedicated profile classes in OWNd.profiles;
    # 3 (F450, F459, F460) safely resolve to GenericGatewayProfile with conservative defaults.
    generic_gateways = {"F450", "F459", "F460"}

    for gw in gateways:
        product = gw["product"]
        profile = get_gateway_profile(product)
        assert profile is not None, f"No profile resolved for catalog gateway {product}"
        assert profile.model_name == product, (
            f"Profile model name mismatch for {product}: got {profile.model_name}"
        )
        if product in generic_gateways:
            assert isinstance(profile, GenericGatewayProfile), (
                f"Gateway {product} expected GenericGatewayProfile fallback"
            )
        else:
            assert not isinstance(profile, GenericGatewayProfile), (
                f"Gateway {product} unexpectedly resolved to GenericGatewayProfile fallback"
            )


def test_multi_gateway_emulation_coverage():
    """Verify that the 10 catalogued gateways have correct emulation status."""
    data = load_firmware_oracle()
    gateways = {g["product"]: g for g in data.get("gateways", [])}
    assert len(gateways) == 10

    # 9 gateways have full empirical emulation verdicts across all 17 test suites:
    emulated_products = {
        "F450",
        "F453AV",
        "F454",
        "F459",
        "F460",
        "F461",
        "MH200N",
        "MH202",
        "MyHomeServer1",
    }
    for p in emulated_products:
        assert gateways[p]["status"] == "emulated"
        assert len(gateways[p]["suites"]) == 17
        assert len(gateways[p]["image_sha256"]) == 64

    # F455 is catalogued and verified, pending emulation (bare-metal ARM Cortex-M):
    assert gateways["F455"]["status"] == "catalogued"
    assert gateways["F455"]["suites"] == []
    assert len(gateways["F455"]["image_sha256"]) == 64
