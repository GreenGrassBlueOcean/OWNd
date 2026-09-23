"""Tests for WHO 16 sound messages."""

import pytest

from OWNd.message import OWNMessage, OWNSoundCommand, OWNSoundEvent


def test_sound_source_and_zone_events_are_distinct() -> None:
    source = OWNMessage.parse("*16*3*102##")
    zone = OWNMessage.parse("*16*13*21##")
    volume = OWNMessage.parse("*#16*21*1*37##")

    assert isinstance(source, OWNSoundEvent)
    assert source.is_source_event
    assert source.source_id == "2"
    assert source.is_on
    assert "Audio Source 2 is switched ON" in source.human_readable_log
    assert isinstance(zone, OWNSoundEvent)
    assert zone.is_off
    assert "Audio Zone 21 is switched OFF" in zone.human_readable_log
    assert isinstance(volume, OWNSoundEvent)
    assert volume.volume == 37


def test_unknown_sound_command_has_diagnostic_log() -> None:
    message = OWNMessage.parse("*16*30*22##")

    assert isinstance(message, OWNSoundEvent)
    assert "received command: 30" in message.human_readable_log


def test_sound_commands_validate_ranges() -> None:
    assert str(OWNSoundCommand.set_volume("21", 40)) == "*#16*21*#1*40##"
    assert [str(command) for command in OWNSoundCommand.select_source("21", 2)] == [
        "*16*3*102##",
        "*16*3*122##",
    ]

    with pytest.raises(ValueError):
        OWNSoundCommand.set_volume("21", 101)
    with pytest.raises(ValueError):
        OWNSoundCommand.select_source("21", 0)


def test_select_source_uses_environment_of_the_amplifier_address() -> None:
    """Routing is addressed by environment, not by amplifier.

    Amplifier addresses are `EA`: the first digit is the environment, the
    second the amplifier within it. The matrix is routed with `1ES`, so both
    amplifiers 21 and 23 route through environment 2.
    """
    assert [str(command) for command in OWNSoundCommand.select_source("23", 2)] == [
        "*16*3*102##",
        "*16*3*122##",
    ]
    assert [str(command) for command in OWNSoundCommand.select_source("23", 1)] == [
        "*16*3*101##",
        "*16*3*121##",
    ]
    assert [str(command) for command in OWNSoundCommand.select_source("41", 3)] == [
        "*16*3*103##",
        "*16*3*143##",
    ]
    # Single-digit, environment 0, and non-numeric addresses cannot be routed to a matrix source.
    with pytest.raises(ValueError, match="two-digit amplifier address"):
        OWNSoundCommand.select_source("2", 2)
    with pytest.raises(ValueError, match="two-digit amplifier address"):
        OWNSoundCommand.select_source("01", 2)
    with pytest.raises(ValueError, match="two-digit amplifier address"):
        OWNSoundCommand.select_source("#1", 2)
    with pytest.raises(ValueError, match="two-digit amplifier address"):
        OWNSoundCommand.select_source("20", 2)
    # Non-ASCII digits pass str.isdigit() but are not an address
    with pytest.raises(ValueError, match="two-digit amplifier address"):
        OWNSoundCommand.select_source("٢٣", 2)


def test_status_request_uses_dimension_5() -> None:
    """WHO 16 status is `*#16*WHERE*5##`; an MH201 NACKs `*#16*WHERE##`."""
    assert str(OWNSoundCommand.status("21")) == "*#16*21*5##"
    assert str(OWNSoundCommand.status("0")) == "*#16*0*5##"


def test_routing_event_exposes_environment_and_source() -> None:
    routing = OWNMessage.parse("*16*3*122##")

    assert isinstance(routing, OWNSoundEvent)
    assert routing.is_routing_event
    assert not routing.is_source_event
    assert routing.environment == "2"
    assert routing.routed_source == "2"
    assert routing.source_id is None
    assert routing.zone == "122"
    assert (
        "Routing of environment 2 to source 2 is switched ON"
        in routing.human_readable_log
    )

    other = OWNMessage.parse("*16*3*141##")
    assert other.environment == "4"
    assert other.routed_source == "1"


@pytest.mark.parametrize(
    "frame",
    [
        "*16*3*102##",  # source 2 powering on
        "*16*13*21##",  # amplifier 21
        "*16*3*100##",  # general source
        "*16*3*120##",  # no source 0
        "*16*3*0##",  # general amplifiers
    ],
)
def test_non_routing_events_have_no_environment(frame: str) -> None:
    event = OWNMessage.parse(frame)

    assert isinstance(event, OWNSoundEvent)
    assert not event.is_routing_event
    assert event.environment is None
    assert event.routed_source is None
