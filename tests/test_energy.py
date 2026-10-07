"""Regression tests for energy edge cases."""

import datetime
from unittest.mock import patch

import pytest

from OWNd.message import OWNEnergyCommand, OWNEnergyEvent


class FixedLeapDay(datetime.date):
    @classmethod
    def today(cls) -> "FixedLeapDay":
        return cls(2024, 2, 29)


def test_unsupported_energy_address_is_fully_initialized() -> None:
    event = OWNEnergyEvent("*#18*923*113*50##")

    assert event.message_type is None
    assert event.active_power == 0
    assert event.total_consumption == 0
    assert event.hourly_consumption == {}
    assert event.daily_consumption == {}
    assert event.monthly_consumption == {}


def test_hourly_consumption_window_handles_leap_day() -> None:
    with patch("OWNd.message.datetime.date", FixedLeapDay):
        command = OWNEnergyCommand.get_hourly_consumption(
            "51", datetime.date(2023, 2, 28)
        )
        too_old = OWNEnergyCommand.get_hourly_consumption(
            "51", datetime.date(2023, 2, 27)
        )

    assert str(command) == "*#18*51*511#2#28##"
    assert too_old is None


def test_stop_and_go_breaker_events_and_commands() -> None:
    # Breaker open event: *18*21*11##
    ev_open = OWNEnergyEvent("*18*21*11##")
    assert ev_open.is_breaker_open is True
    assert ev_open.sensor == "1"
    assert "Stop&Go breaker" in ev_open.human_readable_log

    # Breaker closed: *18*22*11##
    ev_close = OWNEnergyEvent("*18*22*11##")
    assert ev_close.is_breaker_open is False

    # Breaker test positive / negative
    assert OWNEnergyEvent("*18*23*11##").is_test_positive is True
    assert OWNEnergyEvent("*18*24*11##").is_test_positive is False

    # Breaker auto-reset & tracking
    assert OWNEnergyEvent("*18*26*11##").auto_reset_active is True
    assert OWNEnergyEvent("*18*27*11##").auto_reset_active is False
    assert OWNEnergyEvent("*18*28*11##").tracking_active is True
    assert OWNEnergyEvent("*18*29*11##").tracking_active is False

    # Breaker dimension 212 (test interval)
    ev_212 = OWNEnergyEvent("*#18*11*212*10##")
    assert ev_212.test_interval_days == 10

    # Breaker dimensions 250, 251, 258
    assert OWNEnergyEvent("*#18*11*250*1##").breaker_status_mask == 1
    assert OWNEnergyEvent("*#18*11*251*2##").line_status == 2
    assert OWNEnergyEvent("*#18*11*258*5##").failure_count == 5

    # Builders
    assert str(OWNEnergyCommand.open_breaker("11")) == "*18*21*11##"
    assert str(OWNEnergyCommand.close_breaker("11")) == "*18*22*11##"
    assert str(OWNEnergyCommand.test_breaker_positive("11")) == "*18*23*11##"
    assert str(OWNEnergyCommand.test_breaker_negative("11")) == "*18*24*11##"
    assert str(OWNEnergyCommand.activate_auto_reset("11")) == "*18*26*11##"
    assert str(OWNEnergyCommand.deactivate_auto_reset("11")) == "*18*27*11##"
    assert str(OWNEnergyCommand.activate_line_tracking("11")) == "*18*28*11##"
    assert str(OWNEnergyCommand.deactivate_line_tracking("11")) == "*18*29*11##"
    assert str(OWNEnergyCommand.get_test_interval("11")) == "*#18*11*212##"
    assert str(OWNEnergyCommand.set_test_interval("11", 10)) == "*#18*11*#212*10##"
    assert str(OWNEnergyCommand.get_breaker_status("11")) == "*#18*11*250##"
    assert str(OWNEnergyCommand.get_line_status("11")) == "*#18*11*251##"
    assert str(OWNEnergyCommand.get_failure_count("11")) == "*#18*11*258##"


def test_energy_actuator_events_and_commands() -> None:
    # Actuator enable: *18*71*71#0##
    ev_en = OWNEnergyEvent("*18*71*71#0##")
    assert ev_en.actuator_action == "enable"
    assert "Energy actuator" in ev_en.human_readable_log

    # Force off: *18*73#15*71#0##
    ev_fo = OWNEnergyEvent("*18*73#15*71#0##")
    assert ev_fo.actuator_action == "force_off"

    # End force off: *18*74*71#0##
    ev_efo = OWNEnergyEvent("*18*74*71#0##")
    assert ev_efo.actuator_action == "end_force_off"

    # Reset totalizer: *18*75#1*71#0##
    ev_rt = OWNEnergyEvent("*18*75#1*71#0##")
    assert ev_rt.actuator_action == "reset_totalizer"

    # Actuator dimensions: 71, 72, 73
    ev_dim71 = OWNEnergyEvent("*#18*71#0*71*1##")
    assert ev_dim71.message_type == "actuator_status"

    ev_dim72 = OWNEnergyEvent("*#18*71#0*72*100##")
    assert ev_dim72.total_consumption == 100

    ev_dim73 = OWNEnergyEvent("*#18*71#0*73*1##")
    assert ev_dim73.differential_current == 1

    # Builders
    assert str(OWNEnergyCommand.enable_actuator("71#0")) == "*18*71*71#0##"
    assert str(OWNEnergyCommand.force_actuator_off("71#0", minutes=15)) == "*18*73#15*71#0##"
    assert str(OWNEnergyCommand.force_actuator_off("71#0")) == "*18*73*71#0##"
    assert str(OWNEnergyCommand.end_force_actuator("71#0")) == "*18*74*71#0##"
    assert str(OWNEnergyCommand.reset_actuator_totalizer("71#0", 1)) == "*18*75#1*71#0##"
    assert str(OWNEnergyCommand.get_actuator_status("71#0")) == "*#18*71#0*71##"
    assert str(OWNEnergyCommand.get_actuator_differential_current("71#0")) == "*#18*71#0*73##"


def test_ts10_graph_series_and_totalizer_queries() -> None:
    # TS10 graph series: *18*52#10#1*51##
    cmd_52 = OWNEnergyCommand.get_daily_graph("51", month=10, day=1)
    assert str(cmd_52) == "*18*52#10#1*51##"

    cmd_53 = OWNEnergyCommand.get_daily_average_graph("51", month=10)
    assert str(cmd_53) == "*18*53#10*51##"

    cmd_56 = OWNEnergyCommand.get_monthly_graph("51", month=10)
    assert str(cmd_56) == "*18*56#10*51##"

    cmd_57 = OWNEnergyCommand.get_cumulative_daily_graph("51", month=10, day=1)
    assert str(cmd_57) == "*18*57#10#1*51##"

    cmd_58 = OWNEnergyCommand.get_cumulative_daily_average_graph("51", month=10)
    assert str(cmd_58) == "*18*58#10*51##"

    cmd_59 = OWNEnergyCommand.get_cumulative_monthly_graph("51", month=10)
    assert str(cmd_59) == "*18*59#10*51##"

    cmd_510 = OWNEnergyCommand.get_cumulative_monthly_series("51", month=10)
    assert str(cmd_510) == "*18*510#10*51##"

    # Totalizer query
    cmd_tot = OWNEnergyCommand.get_totalizer_query("51")
    assert str(cmd_tot) == "*#18*51*516##"

    # Stop periodic reporting: *#18*51*#1200#1*0##
    cmd_stop = OWNEnergyCommand.stop_sending_instant_power("51")
    assert str(cmd_stop) == "*#18*51*#1200#1*0##"


def test_set_test_interval_invalid_range() -> None:
    with pytest.raises(ValueError, match="Test interval days must be between 1 and 90"):
        OWNEnergyCommand.set_test_interval("11", 0)
    with pytest.raises(ValueError, match="Test interval days must be between 1 and 90"):
        OWNEnergyCommand.set_test_interval("11", 91)
