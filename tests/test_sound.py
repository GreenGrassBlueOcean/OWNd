"""Tests for WHO 16 and WHO 22 sound messages."""

import pytest

from OWNd.message import (
    MESSAGE_TYPE_ACTIVE_AREAS,
    MESSAGE_TYPE_AUDIO_STATE,
    MESSAGE_TYPE_BALANCE,
    MESSAGE_TYPE_DEVICE_STATE,
    MESSAGE_TYPE_FOLLOW_ME,
    MESSAGE_TYPE_LOUDNESS,
    MESSAGE_TYPE_PRESET,
    MESSAGE_TYPE_RDS,
    MESSAGE_TYPE_SOURCE_SELECT,
    MESSAGE_TYPE_TONE,
    MESSAGE_TYPE_TRACK_STATION,
    MESSAGE_TYPE_TUNER,
    MESSAGE_TYPE_VOLUME,
    OWNCommand,
    OWNEvent,
    OWNMessage,
    OWNMultiroomCommand,
    OWNMultiroomEvent,
    OWNSoundCommand,
    OWNSoundEvent,
)


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
    assert not zone.is_source_event
    assert not zone.is_routing_event
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
    status = OWNSoundCommand.status("22")

    assert str(status) == "*#16*22*5##"
    assert status._message_type == "DIMENSION_REQUEST"
    assert status.dimension == 5
    assert str(OWNSoundCommand.status("0")) == "*#16*0*5##"


def test_routing_event_exposes_environment_and_source() -> None:
    routing = OWNMessage.parse("*16*3*122##")

    assert isinstance(routing, OWNSoundEvent)
    assert routing.is_routing_event
    assert not routing.is_source_event
    assert routing.environment == "2"
    assert routing.routed_source == "2"
    assert routing.source_id is None
    assert (
        "Routing of environment 2 to source 2 is switched ON"
        in routing.human_readable_log
    )
    assert routing.is_on

    # A routing frame keeps its address as `zone`: MyHOME parses routing from
    # it, and a None there turned every matrix re-broadcast into a zone ON.
    assert routing.zone == "122"


@pytest.mark.parametrize(
    ("frame", "environment", "source", "log"),
    [
        ("*16*3*111##", "1", "1", "is switched ON"),
        ("*16*3*141##", "4", "1", "is switched ON"),
        ("*16*3*181##", "8", "1", "is switched ON"),
        ("*16*3*199##", "9", "9", "is switched ON"),
        ("*16*13*122##", "2", "2", "is switched OFF"),
        # Source 0 is not a matrix input, but the frame is still routing and
        # must not surface as amplifier `1E0`.
        ("*16*3*120##", "2", "0", "is switched ON"),
        ("*16*13*190##", "9", "0", "is switched OFF"),
    ],
)
def test_routing_event_decomposes_every_environment(
    frame: str, environment: str, source: str, log: str
) -> None:
    event = OWNMessage.parse(frame)

    assert isinstance(event, OWNSoundEvent)
    assert event.is_routing_event
    assert event.zone == frame.split("*")[3].rstrip("#")
    assert event.environment == environment
    assert event.routed_source == source
    assert (
        f"Routing of environment {environment} to source {source} {log}"
        in event.human_readable_log
    )


@pytest.mark.parametrize(
    "frame",
    [
        "*16*3*102##",  # source 2 powering on
        "*16*13*21##",  # amplifier 21
        "*16*3*100##",  # general source
        "*16*3*1٢٢##",  # non-ASCII digits
        "*16*3*0##",  # general amplifiers
    ],
)
def test_non_routing_events_have_no_environment(frame: str) -> None:
    event = OWNMessage.parse(frame)

    assert isinstance(event, OWNSoundEvent)
    assert not event.is_routing_event
    assert event.environment is None
    assert event.routed_source is None
    assert event.zone == event.where


def test_multiroom_power_and_routing_events() -> None:
    # Speaker ON: *22*1#4#1*3#1#1## (multimedia=4, area=1, speaker=3#1#1)
    ev_on = OWNMessage.parse("*22*1#4#1*3#1#1##")
    assert isinstance(ev_on, OWNMultiroomEvent)
    assert ev_on.message_type == MESSAGE_TYPE_AUDIO_STATE
    assert ev_on.target_type == "speaker"
    assert ev_on.target_address == "3#1#1"
    assert ev_on.area == 1
    assert ev_on.point == 1
    assert ev_on.multimedia_type == 4
    assert ev_on.is_on is True
    assert ev_on.is_off is False
    assert "switched ON" in ev_on.human_readable_log

    # Speaker OFF: *22*0#4#1*3#1#1##
    ev_off = OWNEvent.parse("*22*0#4#1*3#1#1##")
    assert isinstance(ev_off, OWNMultiroomEvent)
    assert ev_off.is_on is False
    assert ev_off.is_off is True
    assert "switched OFF" in ev_off.human_readable_log

    # Source ON: *22*2*2#1##
    ev_src = OWNEvent.parse("*22*2*2#1##")
    assert isinstance(ev_src, OWNMultiroomEvent)
    assert ev_src.target_type == "source"
    assert ev_src.source_id == 1
    assert ev_src.is_on is True

    # Follow Me: *22*34#4#1*3#1#1##
    ev_fm = OWNEvent.parse("*22*34#4#1*3#1#1##")
    assert isinstance(ev_fm, OWNMultiroomEvent)
    assert ev_fm.message_type == MESSAGE_TYPE_FOLLOW_ME
    assert ev_fm.is_follow_me is True
    assert ev_fm.is_on is True
    assert "Follow Me" in ev_fm.human_readable_log

    # Source Select: *22*35#4#1#2*3#1#1## (source 2)
    ev_ss = OWNEvent.parse("*22*35#4#1#2*3#1#1##")
    assert isinstance(ev_ss, OWNMultiroomEvent)
    assert ev_ss.message_type == MESSAGE_TYPE_SOURCE_SELECT
    assert ev_ss.is_source_select is True
    assert ev_ss.source_id == 2
    assert ev_ss.is_on is True
    assert "routed to source 2" in ev_ss.human_readable_log

    # All sources: *22*0*6##
    ev_all = OWNEvent.parse("*22*0*6##")
    assert isinstance(ev_all, OWNMultiroomEvent)
    assert ev_all.target_type == "all_sources"
    assert ev_all.is_off is True


def test_multiroom_volume_events_and_commands() -> None:
    # Volume step up: *22*3#5*3#1#1##
    ev_vup = OWNEvent.parse("*22*3#5*3#1#1##")
    assert isinstance(ev_vup, OWNMultiroomEvent)
    assert ev_vup.message_type == MESSAGE_TYPE_VOLUME
    assert ev_vup.volume_step == 5
    assert "volume increased by 5 step(s)" in ev_vup.human_readable_log

    # Volume step down: *22*4#1*3#1#1##
    ev_vdown = OWNEvent.parse("*22*4#1*3#1#1##")
    assert isinstance(ev_vdown, OWNMultiroomEvent)
    assert ev_vdown.volume_step == 1
    assert "volume decreased by 1 step(s)" in ev_vdown.human_readable_log

    # Dimension 1 volume status: *#22*3#1#1*1*17##
    ev_vol = OWNEvent.parse("*#22*3#1#1*1*17##")
    assert isinstance(ev_vol, OWNMultiroomEvent)
    assert ev_vol.message_type == MESSAGE_TYPE_VOLUME
    assert ev_vol.volume == 17
    assert "volume: 17" in ev_vol.human_readable_log

    # General prefix address: *#22*5#3#1#1*1*25##
    ev_vol_gen = OWNEvent.parse("*#22*5#3#1#1*1*25##")
    assert isinstance(ev_vol_gen, OWNMultiroomEvent)
    assert ev_vol_gen.target_type == "speaker"
    assert ev_vol_gen.area == 1
    assert ev_vol_gen.point == 1
    assert ev_vol_gen.volume == 25


def test_multiroom_tuner_and_track_events_and_commands() -> None:
    # Next station: *22*9*2#1##
    ev_next_stn = OWNEvent.parse("*22*9*2#1##")
    assert isinstance(ev_next_stn, OWNMultiroomEvent)
    assert ev_next_stn.message_type == MESSAGE_TYPE_TRACK_STATION

    # Prev station: *22*10*2#1##
    ev_prev_stn = OWNEvent.parse("*22*10*2#1##")
    assert isinstance(ev_prev_stn, OWNMultiroomEvent)

    # Next track: *22*11*2#1##
    ev_next_trk = OWNEvent.parse("*22*11*2#1##")
    assert isinstance(ev_next_trk, OWNMultiroomEvent)

    # Prev track: *22*12*2#1##
    ev_prev_trk = OWNEvent.parse("*22*12*2#1##")
    assert isinstance(ev_prev_trk, OWNMultiroomEvent)

    # Search UP: *22*5#1*2#1##
    ev_sup = OWNEvent.parse("*22*5#1*2#1##")
    assert isinstance(ev_sup, OWNMultiroomEvent)
    assert ev_sup.message_type == MESSAGE_TYPE_TUNER
    assert ev_sup.frequency_step == 1

    # Search DOWN: *22*6*2#1##
    ev_sdown = OWNEvent.parse("*22*6*2#1##")
    assert isinstance(ev_sdown, OWNMultiroomEvent)
    assert ev_sdown.frequency_step is None

    # Store station: *22*33#3*2#1##
    ev_store = OWNEvent.parse("*22*33#3*2#1##")
    assert isinstance(ev_store, OWNMultiroomEvent)
    assert ev_store.station_or_track == 3

    # RDS reporting: *22*31*2#1##, *22*32*2#1##
    ev_rds_on = OWNEvent.parse("*22*31*2#1##")
    assert isinstance(ev_rds_on, OWNMultiroomEvent)
    assert ev_rds_on.message_type == MESSAGE_TYPE_RDS
    assert ev_rds_on.rds_reporting is True

    ev_rds_off = OWNEvent.parse("*22*32*2#1##")
    assert isinstance(ev_rds_off, OWNMultiroomEvent)
    assert ev_rds_off.rds_reporting is False


def test_multiroom_tones_balance_preset_loudness() -> None:
    # High tones: dim 2
    ev_treb = OWNEvent.parse("*#22*3#1#1*2*30##")
    assert isinstance(ev_treb, OWNMultiroomEvent)
    assert ev_treb.message_type == MESSAGE_TYPE_TONE
    assert ev_treb.high_tones == 30

    # Mid tones: dim 3
    ev_mid = OWNEvent.parse("*#22*3#1#1*3*25##")
    assert isinstance(ev_mid, OWNMultiroomEvent)
    assert ev_mid.mid_tones == 25

    # Low tones: dim 4
    ev_bass = OWNEvent.parse("*#22*3#1#1*4*35##")
    assert isinstance(ev_bass, OWNMultiroomEvent)
    assert ev_bass.low_tones == 35

    # Balance: dim 17
    ev_bal = OWNEvent.parse("*#22*3#1#1*17*32##")
    assert isinstance(ev_bal, OWNMultiroomEvent)
    assert ev_bal.message_type == MESSAGE_TYPE_BALANCE
    assert ev_bal.balance == 32

    # Preset: dim 19
    ev_pre = OWNEvent.parse("*#22*3#1#1*19*2##")
    assert isinstance(ev_pre, OWNMultiroomEvent)
    assert ev_pre.message_type == MESSAGE_TYPE_PRESET
    assert ev_pre.preset == 2

    # Loudness: dim 20
    ev_loud_on = OWNEvent.parse("*#22*3#1#1*20*1##")
    assert isinstance(ev_loud_on, OWNMultiroomEvent)
    assert ev_loud_on.message_type == MESSAGE_TYPE_LOUDNESS
    assert ev_loud_on.loudness is True

    ev_loud_off = OWNEvent.parse("*#22*3#1#1*20*0##")
    assert isinstance(ev_loud_off, OWNMultiroomEvent)
    assert ev_loud_off.loudness is False

    # Tone commands: 36 (bass up), 37 (bass down), 38 (mid up), 39 (mid down), 40 (high up), 41 (high down)
    assert (
        OWNEvent.parse("*22*36#1*3#1#1##").message_type == MESSAGE_TYPE_TONE
    )
    assert (
        OWNEvent.parse("*22*37#1*3#1#1##").message_type == MESSAGE_TYPE_TONE
    )
    assert (
        OWNEvent.parse("*22*38#1*3#1#1##").message_type == MESSAGE_TYPE_TONE
    )
    assert (
        OWNEvent.parse("*22*39#1*3#1#1##").message_type == MESSAGE_TYPE_TONE
    )
    assert (
        OWNEvent.parse("*22*40#1*3#1#1##").message_type == MESSAGE_TYPE_TONE
    )
    assert (
        OWNEvent.parse("*22*41#1*3#1#1##").message_type == MESSAGE_TYPE_TONE
    )

    # Balance commands: 42 (right), 43 (left)
    assert (
        OWNEvent.parse("*22*42#1*3#1#1##").message_type == MESSAGE_TYPE_BALANCE
    )
    assert (
        OWNEvent.parse("*22*43#1*3#1#1##").message_type == MESSAGE_TYPE_BALANCE
    )

    # Preset commands: 55 (next), 56 (prev)
    assert (
        OWNEvent.parse("*22*55*3#1#1##").message_type == MESSAGE_TYPE_PRESET
    )
    assert (
        OWNEvent.parse("*22*56*3#1#1##").message_type == MESSAGE_TYPE_PRESET
    )


def test_multiroom_device_state_and_active_areas() -> None:
    # Device state: *#22*5#3#1#1*12*1*3## (state 1 ON, mm 3)
    ev_dev = OWNEvent.parse("*#22*5#3#1#1*12*1*3##")
    assert isinstance(ev_dev, OWNMultiroomEvent)
    assert ev_dev.message_type == MESSAGE_TYPE_DEVICE_STATE
    assert ev_dev.device_state == 1
    assert ev_dev.is_on is True
    assert ev_dev.multimedia_type == 3

    # Active areas: *#22*2#1*13*7##
    ev_areas = OWNEvent.parse("*#22*2#1*13*7##")
    assert isinstance(ev_areas, OWNMultiroomEvent)
    assert ev_areas.message_type == MESSAGE_TYPE_ACTIVE_AREAS
    assert ev_areas.active_areas == 7


def test_multiroom_command_builders_and_validation() -> None:
    # Power
    assert str(OWNMultiroomCommand.turn_on("3#1#1", multimedia_type=4, area=1)) == "*22*1#4#1*3#1#1##"
    assert str(OWNMultiroomCommand.turn_on("3#1#1")) == "*22*1*3#1#1##"
    assert str(OWNMultiroomCommand.turn_off("3#1#1", multimedia_type=4, area=1)) == "*22*0#4#1*3#1#1##"
    assert str(OWNMultiroomCommand.turn_off("3#1#1")) == "*22*0*3#1#1##"

    # Volume
    assert str(OWNMultiroomCommand.volume_up("3#1#1", step=5)) == "*22*3#5*3#1#1##"
    assert str(OWNMultiroomCommand.volume_down("3#1#1", step=1)) == "*22*4#1*3#1#1##"
    assert str(OWNMultiroomCommand.set_volume("3#1#1", 20)) == "*#22*3#1#1*#1*20##"
    assert str(OWNMultiroomCommand.request_volume("3#1#1")) == "*#22*3#1#1*1##"

    with pytest.raises(ValueError, match="Volume level must be between 0 and 31"):
        OWNMultiroomCommand.set_volume("3#1#1", 32)
    with pytest.raises(ValueError, match="Volume level must be between 0 and 31"):
        OWNMultiroomCommand.set_volume("3#1#1", -1)

    # Source & Follow Me
    assert str(OWNMultiroomCommand.select_source("3#1#1", source_id=2, area=1)) == "*22*35#4#1#2*3#1#1##"
    assert str(OWNMultiroomCommand.follow_me("3#1#1", area=1)) == "*22*34#4#1*3#1#1##"

    # Tracks & Stations
    assert str(OWNMultiroomCommand.next_track("2#1")) == "*22*11*2#1##"
    assert str(OWNMultiroomCommand.prev_track("2#1")) == "*22*12*2#1##"
    assert str(OWNMultiroomCommand.next_station("2#1")) == "*22*9*2#1##"
    assert str(OWNMultiroomCommand.prev_station("2#1")) == "*22*10*2#1##"
    assert str(OWNMultiroomCommand.store_station("2#1", 3)) == "*22*33#3*2#1##"
    assert str(OWNMultiroomCommand.search_frequency_up("2#1", step=1)) == "*22*5#1*2#1##"
    assert str(OWNMultiroomCommand.search_frequency_up("2#1")) == "*22*5*2#1##"
    assert str(OWNMultiroomCommand.search_frequency_down("2#1", step=1)) == "*22*6#1*2#1##"
    assert str(OWNMultiroomCommand.search_frequency_down("2#1")) == "*22*6*2#1##"
    assert str(OWNMultiroomCommand.request_frequency("2#1")) == "*#22*2#1*5##"
    assert str(OWNMultiroomCommand.request_track_or_station("2#1")) == "*#22*2#1*6##"
    assert str(OWNMultiroomCommand.set_track_or_station("2#1", 33)) == "*#22*2#1*#6*33##"

    # Device state & active areas
    assert str(OWNMultiroomCommand.request_device_state("3#1#1")) == "*#22*3#1#1*12##"
    assert str(OWNMultiroomCommand.request_active_areas("2#1")) == "*#22*2#1*13##"

    # Balance
    assert str(OWNMultiroomCommand.set_balance("3#1#1", 32)) == "*#22*3#1#1*#17*32##"
    assert str(OWNMultiroomCommand.request_balance("3#1#1")) == "*#22*3#1#1*17##"
    assert str(OWNMultiroomCommand.move_balance_right("3#1#1", step=1)) == "*22*42#1*3#1#1##"
    assert str(OWNMultiroomCommand.move_balance_left("3#1#1", step=1)) == "*22*43#1*3#1#1##"
    with pytest.raises(ValueError, match="Balance must be between 1 and 63"):
        OWNMultiroomCommand.set_balance("3#1#1", 64)

    # Preset
    assert str(OWNMultiroomCommand.set_preset("3#1#1", 2)) == "*#22*3#1#1*#19*2##"
    assert str(OWNMultiroomCommand.request_preset("3#1#1")) == "*#22*3#1#1*19##"
    assert str(OWNMultiroomCommand.next_preset("3#1#1")) == "*22*55*3#1#1##"
    assert str(OWNMultiroomCommand.prev_preset("3#1#1")) == "*22*56*3#1#1##"

    # Loudness
    assert str(OWNMultiroomCommand.set_loudness("3#1#1", True)) == "*#22*3#1#1*#20*1##"
    assert str(OWNMultiroomCommand.set_loudness("3#1#1", False)) == "*#22*3#1#1*#20*0##"
    assert str(OWNMultiroomCommand.request_loudness("3#1#1")) == "*#22*3#1#1*20##"

    # Tones
    assert str(OWNMultiroomCommand.set_treble("3#1#1", 30)) == "*#22*3#1#1*#2*30##"
    assert str(OWNMultiroomCommand.request_treble("3#1#1")) == "*#22*3#1#1*2##"
    assert str(OWNMultiroomCommand.set_mid_tones("3#1#1", 30)) == "*#22*3#1#1*#3*30##"
    assert str(OWNMultiroomCommand.request_mid_tones("3#1#1")) == "*#22*3#1#1*3##"
    assert str(OWNMultiroomCommand.set_bass("3#1#1", 30)) == "*#22*3#1#1*#4*30##"
    assert str(OWNMultiroomCommand.request_bass("3#1#1")) == "*#22*3#1#1*4##"
    with pytest.raises(ValueError, match="High tones value must be between 1 and 63"):
        OWNMultiroomCommand.set_treble("3#1#1", 70)
    with pytest.raises(ValueError, match="Medium tones value must be between 1 and 63"):
        OWNMultiroomCommand.set_mid_tones("3#1#1", 0)
    with pytest.raises(ValueError, match="Low tones value must be between 1 and 63"):
        OWNMultiroomCommand.set_bass("3#1#1", 100)

    assert str(OWNMultiroomCommand.tone_up("3#1#1", band="bass")) == "*22*36#1*3#1#1##"
    assert str(OWNMultiroomCommand.tone_down("3#1#1", band="mid")) == "*22*39#1*3#1#1##"
    with pytest.raises(ValueError, match="band must be one of"):
        OWNMultiroomCommand.tone_up("3#1#1", band="ultra")
    with pytest.raises(ValueError, match="band must be one of"):
        OWNMultiroomCommand.tone_down("3#1#1", band="ultra")

    # RDS & Status
    assert str(OWNMultiroomCommand.start_rds("2#1")) == "*22*31*2#1##"
    assert str(OWNMultiroomCommand.stop_rds("2#1")) == "*22*32*2#1##"
    assert str(OWNMultiroomCommand.status("3#1#1")) == "*#22*3#1#1##"


def test_multiroom_command_parse() -> None:
    cmd = OWNCommand.parse("*22*3#1*3#1#1##")
    assert isinstance(cmd, OWNMultiroomCommand)
    assert str(cmd) == "*22*3#1*3#1#1##"


def test_multiroom_edge_cases_and_addressing() -> None:
    from OWNd.message.sound import _format_who22_where

    assert _format_who22_where(None, []) == ""

    # Direct area address 4#1
    ev_area = OWNEvent.parse("*22*1*4#1##")
    assert isinstance(ev_area, OWNMultiroomEvent)
    assert ev_area.target_type == "area"
    assert ev_area.area == 1

    # Area address with 5# prefix: 5#4#2
    ev_gen_area = OWNEvent.parse("*22*1*5#4#2##")
    assert isinstance(ev_gen_area, OWNMultiroomEvent)
    assert ev_gen_area.target_type == "area"
    assert ev_gen_area.area == 2

    # General address with 5# prefix: 5#99
    ev_gen_other = OWNEvent.parse("*22*1*5#99##")
    assert isinstance(ev_gen_other, OWNMultiroomEvent)
    assert ev_gen_other.target_type == "general"

    # Commands without params
    ev_store_noparams = OWNEvent.parse("*22*33*2#1##")
    assert isinstance(ev_store_noparams, OWNMultiroomEvent)
    assert ev_store_noparams.station_or_track is None

    ev_fm_noparams = OWNEvent.parse("*22*34*3#1#1##")
    assert isinstance(ev_fm_noparams, OWNMultiroomEvent)
    assert ev_fm_noparams.is_follow_me is True

    ev_ss_noparams = OWNEvent.parse("*22*35*3#1#1##")
    assert isinstance(ev_ss_noparams, OWNMultiroomEvent)
    assert ev_ss_noparams.is_source_select is True

    # Device state with 1 param (no multimedia type)
    ev_dev_single = OWNEvent.parse("*#22*5#3#1#1*12*1##")
    assert isinstance(ev_dev_single, OWNMultiroomEvent)
    assert ev_dev_single.device_state == 1
    assert ev_dev_single.multimedia_type is None

    # Unexpected what
    ev_unknown_what = OWNEvent.parse("*22*99*3#1#1##")
    assert isinstance(ev_unknown_what, OWNMultiroomEvent)
    assert "command 99" in ev_unknown_what.human_readable_log

    # Unexpected dim
    ev_unknown_dim = OWNEvent.parse("*#22*3#1#1*99*1##")
    assert isinstance(ev_unknown_dim, OWNMultiroomEvent)
    assert "dimension 99" in ev_unknown_dim.human_readable_log
