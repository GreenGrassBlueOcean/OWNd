"""Tests for conservative gateway capability profiles."""

import pytest

from OWNd.profiles import (
    DEFAULT_SUPPORTED_WHO,
    WHO_LOAD_CONTROL,
    WHO_SOUND,
    WHO_SOUND_DIFFUSION,
    MH200NProfile,
    MH200Profile,
    get_gateway_profile,
)


@pytest.mark.parametrize("name", ["MH200", "mh200", "MH-200", "MH 200"])
def test_mh200_is_not_the_mh200n(name: str) -> None:
    """A live MH200 answers *#16*0*5## with every amplifier and source (#53)."""
    profile = get_gateway_profile(name)

    assert isinstance(profile, MH200Profile)
    assert profile.model_name == "MH200"
    assert profile.supports_audio is True
    assert profile.supports_who(WHO_SOUND)


def test_mh200_keeps_the_mh200n_pacing() -> None:
    mh200 = get_gateway_profile("MH200")
    mh200n = get_gateway_profile("MH200N")

    assert isinstance(mh200n, MH200NProfile)
    assert mh200.max_command_sessions == mh200n.max_command_sessions == 1
    assert mh200.command_queue_delay == mh200n.command_queue_delay
    assert mh200.max_queue_size == mh200n.max_queue_size
    assert mh200.event_keepalive_interval == mh200n.event_keepalive_interval
    assert set(mh200.supported_who) - set(mh200n.supported_who) == {WHO_SOUND}


def test_mh200n_audio_stays_off_until_checked() -> None:
    """Unchanged until an MH200N is seen answering *#16*0*5## (#53)."""
    profile = get_gateway_profile("MH200N")

    assert profile.supports_audio is False
    assert not profile.supports_who(WHO_SOUND)


def test_profile_lookup_accepts_common_name_variants() -> None:
    profile = get_gateway_profile("MyHome Server 1")

    assert profile.model_name == "MyHomeServer1"
    assert profile.supports_session_count(4)
    assert profile.supports_who(WHO_SOUND)


def test_f461_profile_lookup() -> None:
    profile = get_gateway_profile("F461")

    assert profile.model_name == "F461"
    assert profile.supports_session_count(4)
    assert profile.supports_hmac is True
    assert profile.command_queue_delay == 0.05
    assert profile.supports_native_transitions is True


def test_unknown_gateway_uses_conservative_limits() -> None:
    profile = get_gateway_profile("Future gateway")

    assert profile.model_name == "Future gateway"
    assert profile.max_command_sessions == 1
    assert profile.event_keepalive_interval is None


def test_v2_profile_compatibility_aliases() -> None:
    profile = get_gateway_profile("MH201")

    assert profile.max_workers == profile.max_command_sessions
    assert profile.default_workers == profile.default_command_sessions
    assert profile.command_delay == profile.command_queue_delay
    assert profile.can_support_workers(1)


def test_load_control_and_sound_diffusion_have_distinct_who_codes() -> None:
    assert WHO_LOAD_CONTROL == 3
    assert WHO_SOUND_DIFFUSION == 22
    assert WHO_LOAD_CONTROL in DEFAULT_SUPPORTED_WHO
    assert WHO_SOUND_DIFFUSION in DEFAULT_SUPPORTED_WHO
