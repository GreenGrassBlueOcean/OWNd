"""WHO 18: Energy management events, commands, and consumption types."""

from __future__ import annotations

import datetime
from typing import Any

from dateutil.relativedelta import relativedelta

from .base import OWNCommand, OWNEvent, register_command_parser, register_event_parser

MESSAGE_TYPE_ACTIVE_POWER = "active_power"
MESSAGE_TYPE_ENERGY_TOTALIZER = "energy_totalizer"
MESSAGE_TYPE_HOURLY_CONSUMPTION = "hourly_consumption"
MESSAGE_TYPE_DAILY_CONSUMPTION = "daily_consumption"
MESSAGE_TYPE_MONTHLY_CONSUMPTION = "monthly_consumption"
MESSAGE_TYPE_CURRENT_DAY_CONSUMPTION = "current_day_partial_consumption"
MESSAGE_TYPE_CURRENT_MONTH_CONSUMPTION = "current_month_partial_consumption"
MESSAGE_TYPE_BREAKER = "breaker"
MESSAGE_TYPE_TEST_INTERVAL = "test_interval"
MESSAGE_TYPE_BREAKER_STATUS = "breaker_status"
MESSAGE_TYPE_LINE_STATUS = "line_status"
MESSAGE_TYPE_FAILURE_COUNT = "failure_count"
MESSAGE_TYPE_ACTUATOR = "actuator"
MESSAGE_TYPE_ACTUATOR_STATUS = "actuator_status"
MESSAGE_TYPE_ACTUATOR_TOTALIZER = "actuator_totalizer"
MESSAGE_TYPE_DIFFERENTIAL_CURRENT = "differential_current"


def _integer_value(
    values: list[str], index: int, default: int = 0
) -> int:
    """Read an integer field without letting an empty telemetry value crash."""
    try:
        return int(values[index])
    except (IndexError, TypeError, ValueError):
        return default


class OWNEnergyEvent(OWNEvent):
    """Energy telemetry, Stop&Go breaker states, and actuator events."""

    def __init__(self, data: str) -> None:
        super().__init__(data)

        self._type: str | None = None
        where = self._where or ""
        self._sensor = where[1:] if len(where) > 1 else where
        self._active_power = 0
        self._total_consumption = 0
        # Values are heterogeneous: dates, hours (int) and Wh readings (int).
        self._hourly_consumption: dict[str, Any] = {}
        self._daily_consumption: dict[str, Any] = {}
        self._current_day_partial_consumption = 0
        self._monthly_consumption: dict[str, Any] = {}
        self._current_month_partial_consumption = 0

        if not where.startswith(("1", "5", "7")):
            return

        # Stop&Go attributes
        self._is_breaker_open: bool | None = None
        self._is_test_positive: bool | None = None
        self._auto_reset_active: bool | None = None
        self._tracking_active: bool | None = None
        self._test_interval_days: int | None = None
        self._breaker_status_mask: int | None = None
        self._line_status: int | None = None
        self._failure_count: int | None = None

        # Actuator attributes
        self._actuator_action: str | None = None
        self._differential_current: int | None = None

        what = self._what
        dim = self._dimension

        # WHAT command events (Stop&Go and Actuators)
        if what is not None:
            if what in (21, 22, 23, 24, 26, 27, 28, 29):
                self._type = MESSAGE_TYPE_BREAKER
                if what == 21:
                    self._is_breaker_open = True
                    self._human_readable_log = f"Stop&Go breaker {where} is open."
                elif what == 22:
                    self._is_breaker_open = False
                    self._human_readable_log = f"Stop&Go breaker {where} is closed."
                elif what == 23:
                    self._is_test_positive = True
                    self._human_readable_log = f"Stop&Go breaker {where} differential test positive."
                elif what == 24:
                    self._is_test_positive = False
                    self._human_readable_log = f"Stop&Go breaker {where} differential test negative."
                elif what == 26:
                    self._auto_reset_active = True
                    self._human_readable_log = f"Stop&Go breaker {where} auto-reset activated."
                elif what == 27:
                    self._auto_reset_active = False
                    self._human_readable_log = f"Stop&Go breaker {where} auto-reset deactivated."
                elif what == 28:
                    self._tracking_active = True
                    self._human_readable_log = f"Stop&Go breaker {where} line tracking activated."
                else:
                    self._tracking_active = False
                    self._human_readable_log = f"Stop&Go breaker {where} line tracking deactivated."
                return

            if what in (71, 73, 74, 75):
                self._type = MESSAGE_TYPE_ACTUATOR
                if what == 71:
                    self._actuator_action = "enable"
                    self._human_readable_log = f"Energy actuator {where} enabled."
                elif what == 73:
                    self._actuator_action = "force_off"
                    self._human_readable_log = f"Energy actuator {where} forced OFF."
                elif what == 74:
                    self._actuator_action = "end_force_off"
                    self._human_readable_log = f"Energy actuator {where} forced OFF ended."
                else:
                    self._actuator_action = "reset_totalizer"
                    self._human_readable_log = f"Energy actuator {where} totalizer reset."
                return

        # Dimension readings
        if dim is not None:
            if dim == 212:
                self._type = MESSAGE_TYPE_TEST_INTERVAL
                self._test_interval_days = _integer_value(self._dimension_value, 0)
                self._human_readable_log = f"Stop&Go breaker {where} self-test interval: {self._test_interval_days} days."
                return
            if dim == 250:
                self._type = MESSAGE_TYPE_BREAKER_STATUS
                self._breaker_status_mask = _integer_value(self._dimension_value, 0)
                self._human_readable_log = f"Stop&Go breaker {where} status mask: {self._breaker_status_mask}."
                return
            if dim == 251:
                self._type = MESSAGE_TYPE_LINE_STATUS
                self._line_status = _integer_value(self._dimension_value, 0)
                self._human_readable_log = f"Stop&Go breaker {where} line status: {self._line_status}."
                return
            if dim == 258:
                self._type = MESSAGE_TYPE_FAILURE_COUNT
                self._failure_count = _integer_value(self._dimension_value, 0)
                self._human_readable_log = f"Stop&Go breaker {where} failure count: {self._failure_count}."
                return
            if dim == 71:
                self._type = MESSAGE_TYPE_ACTUATOR_STATUS
                self._human_readable_log = f"Energy actuator {where} status reported."
                return
            if dim == 72:
                self._type = MESSAGE_TYPE_ACTUATOR_TOTALIZER
                self._total_consumption = _integer_value(self._dimension_value, 0)
                self._human_readable_log = f"Energy actuator {where} totalizer: {self._total_consumption} Wh."
                return
            if dim == 73:
                self._type = MESSAGE_TYPE_DIFFERENTIAL_CURRENT
                self._differential_current = _integer_value(self._dimension_value, 0)
                self._human_readable_log = f"Energy actuator {where} differential current: {self._differential_current}."
                return
            if dim == 1 or dim == 113:
                self._type = MESSAGE_TYPE_ACTIVE_POWER
                self._active_power = _integer_value(self._dimension_value, 0)
                self._human_readable_log = f"Sensor {self._sensor} is reporting an active power draw of {self._active_power} W."  # pylint: disable=line-too-long
            elif dim == 511:
                _now = datetime.date.today()
                try:
                    _raw_message_date = datetime.date(
                        _now.year,
                        int(self._dimension_param[0]),
                        int(self._dimension_param[1]),
                    )
                    if _raw_message_date > _now:
                        _message_date = datetime.date(
                            _now.year - 1,
                            int(self._dimension_param[0]),
                            int(self._dimension_param[1]),
                        )
                    else:
                        _message_date = _raw_message_date
                except (ValueError, IndexError):
                    return

                if len(self._dimension_value) < 2 or not all(
                    self._dimension_value[:2]
                ):
                    return
                if int(self._dimension_value[0]) != 25:
                    self._type = MESSAGE_TYPE_HOURLY_CONSUMPTION
                    self._hourly_consumption["date"] = _message_date
                    self._hourly_consumption["hour"] = int(self._dimension_value[0]) - 1
                    self._hourly_consumption["value"] = int(self._dimension_value[1])
                    self._human_readable_log = f"Sensor {self._sensor} is reporting a power consumption of {self._hourly_consumption['value']} Wh for {self._hourly_consumption['date']} at {self._hourly_consumption['hour']}."  # pylint: disable=line-too-long
                else:
                    self._type = MESSAGE_TYPE_DAILY_CONSUMPTION
                    self._daily_consumption["date"] = _message_date
                    self._daily_consumption["value"] = int(self._dimension_value[1])
                    self._human_readable_log = f"Sensor {self._sensor} is reporting a power consumption of {self._daily_consumption['value']} Wh for {self._daily_consumption['date']}."  # pylint: disable=line-too-long
            elif dim == 513 or dim == 514:
                if len(self._dimension_value) < 2 or not all(
                    self._dimension_value[:2]
                ):
                    return
                _now = datetime.date.today()
                try:
                    _raw_message_date = datetime.date(
                        _now.year, int(self._dimension_param[0]), 1
                    )
                    if dim == 513 and _raw_message_date > _now:
                        _message_date = datetime.date(
                            _now.year - 1,
                            int(self._dimension_param[0]),
                            int(self._dimension_value[0]),
                        )
                    elif dim == 514:
                        if _raw_message_date > _now:
                            _message_date = datetime.date(
                                _now.year - 2,
                                int(self._dimension_param[0]),
                                int(self._dimension_value[0]),
                            )
                        else:
                            _message_date = datetime.date(
                                _now.year - 1,
                                int(self._dimension_param[0]),
                                int(self._dimension_value[0]),
                            )
                    else:
                        _message_date = datetime.date(
                            _now.year,
                            int(self._dimension_param[0]),
                            int(self._dimension_value[0]),
                        )
                except (ValueError, IndexError):
                    return
                self._type = MESSAGE_TYPE_DAILY_CONSUMPTION
                self._daily_consumption["date"] = _message_date
                self._daily_consumption["value"] = int(self._dimension_value[1])
                self._human_readable_log = f"Sensor {self._sensor} is reporting a power consumption of {self._daily_consumption['value']} Wh for {self._daily_consumption['date']}."  # pylint: disable=line-too-long
            elif dim == 51 or dim == 11:
                self._type = MESSAGE_TYPE_ENERGY_TOTALIZER
                self._total_consumption = _integer_value(self._dimension_value, 0)
                self._human_readable_log = f"Sensor {self._sensor} is reporting a total power consumption of {self._total_consumption} Wh."  # pylint: disable=line-too-long
            elif dim == 54 or dim == 3:
                self._type = MESSAGE_TYPE_CURRENT_DAY_CONSUMPTION
                self._current_day_partial_consumption = _integer_value(
                    self._dimension_value, 0
                )
                self._human_readable_log = f"Sensor {self._sensor} is reporting a power consumption of {self._current_day_partial_consumption} Wh up to now today."  # pylint: disable=line-too-long
            elif dim == 52 or dim == 4:
                self._type = MESSAGE_TYPE_MONTHLY_CONSUMPTION
                try:
                    if len(self._dimension_param) >= 2:
                        _message_date = datetime.date(
                            int(f"20{self._dimension_param[0]}"),
                            int(self._dimension_param[1]),
                            1,
                        )
                    else:
                        _now = datetime.date.today()
                        _message_date = datetime.date(_now.year, _now.month, 1)
                except (ValueError, IndexError):
                    return
                self._monthly_consumption["date"] = _message_date
                self._monthly_consumption["value"] = _integer_value(
                    self._dimension_value, 0
                )
                self._human_readable_log = f"Sensor {self._sensor} is reporting a power consumption of {self._monthly_consumption['value']} Wh for {self._monthly_consumption['date'].strftime('%B %Y')}."  # pylint: disable=line-too-long
            elif dim == 53:
                self._type = MESSAGE_TYPE_CURRENT_MONTH_CONSUMPTION
                self._current_month_partial_consumption = _integer_value(
                    self._dimension_value, 0
                )
                self._human_readable_log = f"Sensor {self._sensor} is reporting a power consumption of {self._current_month_partial_consumption} Wh up to now this month."  # pylint: disable=line-too-long

    @property
    def message_type(self) -> str | None:
        return self._type

    @property
    def sensor(self) -> str:
        return self._sensor

    @property
    def active_power(self) -> int:
        return self._active_power

    @property
    def total_consumption(self) -> int:
        return self._total_consumption

    @property
    def hourly_consumption(self) -> dict[str, Any]:
        return self._hourly_consumption

    @property
    def daily_consumption(self) -> dict[str, Any]:
        return self._daily_consumption

    @property
    def current_day_partial_consumption(self) -> int:
        return self._current_day_partial_consumption

    @property
    def monthly_consumption(self) -> dict[str, Any]:
        return self._monthly_consumption

    @property
    def current_month_partial_consumption(self) -> int:
        return self._current_month_partial_consumption

    @property
    def is_breaker_open(self) -> bool | None:
        return self._is_breaker_open

    @property
    def is_test_positive(self) -> bool | None:
        return self._is_test_positive

    @property
    def auto_reset_active(self) -> bool | None:
        return self._auto_reset_active

    @property
    def tracking_active(self) -> bool | None:
        return self._tracking_active

    @property
    def test_interval_days(self) -> int | None:
        return self._test_interval_days

    @property
    def breaker_status_mask(self) -> int | None:
        return self._breaker_status_mask

    @property
    def line_status(self) -> int | None:
        return self._line_status

    @property
    def failure_count(self) -> int | None:
        return self._failure_count

    @property
    def actuator_action(self) -> str | None:
        return self._actuator_action

    @property
    def differential_current(self) -> int | None:
        return self._differential_current

    @property
    def human_readable_log(self) -> str:
        return self._human_readable_log


class OWNEnergyCommand(OWNCommand):
    """WHO 18 commands for power meters, Stop&Go breakers, and actuators."""

    @classmethod
    def start_sending_instant_power(
        cls, where: str | int, duration: int = 65
    ) -> OWNEnergyCommand:
        where = f"{where}#0" if str(where).startswith("7") else str(where)
        duration = 255 if duration > 255 else duration
        message = cls(f"*#18*{where}*#1200#1*{duration}##")
        message._human_readable_log = f"Requesting instant power draw update from sensor {where} for {duration} minutes."  # pylint: disable=line-too-long
        return message

    @classmethod
    def stop_sending_instant_power(cls, where: str | int) -> OWNEnergyCommand:
        """Stop periodic reporting of instant power draw."""
        where = f"{where}#0" if str(where).startswith("7") else str(where)
        message = cls(f"*#18*{where}*#1200#1*0##")
        message._human_readable_log = f"Stopping instant power draw updates from sensor {where}."
        return message

    @classmethod
    def get_hourly_consumption(
        cls, where: str | int, date: datetime.date
    ) -> OWNEnergyCommand | None:
        where = f"{where}#0" if str(where).startswith("7") else str(where)
        today = datetime.date.today()
        one_year_ago = today - relativedelta(years=1)
        if date < one_year_ago:
            return None
        message = cls(f"*#18*{where}*511#{date.month}#{date.day}##")
        message._human_readable_log = (
            f"Requesting hourly power consumption from sensor {where} for {date}."
        )
        return message

    @classmethod
    def get_partial_daily_consumption(cls, where: str | int) -> OWNEnergyCommand:
        where = f"{where}#0" if str(where).startswith("7") else str(where)
        message = cls(f"*#18*{where}*54##")
        message._human_readable_log = (
            f"Requesting today's partial power consumption from sensor {where}."
        )
        return message

    @classmethod
    def get_daily_consumption(
        cls, where: str | int, year: int, month: int
    ) -> OWNEnergyCommand | None:
        where = f"{where}#0" if str(where).startswith("7") else str(where)
        today = datetime.date.today()
        one_year_ago = today - relativedelta(years=1)
        two_year_ago = today - relativedelta(years=2)
        target = datetime.date(year=year, month=month, day=1)
        if target > today:
            return None
        if target > one_year_ago:
            message = cls(f"*18*59#{month}*{where}##")
        elif target > two_year_ago:
            message = cls(f"*18*510#{month}*{where}##")
        else:
            return None
        message._human_readable_log = f"Requesting daily power consumption for {year}-{month} from sensor {where}."  # pylint: disable=line-too-long
        return message

    @classmethod
    def get_partial_monthly_consumption(cls, where: str | int) -> OWNEnergyCommand:
        where = f"{where}#0" if str(where).startswith("7") else str(where)
        message = cls(f"*#18*{where}*53##")
        message._human_readable_log = (
            f"Requesting this month's partial power consumption from sensor {where}."
        )
        return message

    @classmethod
    def get_monthly_consumption(
        cls, where: str | int, year: int, month: int
    ) -> OWNEnergyCommand:
        where = f"{where}#0" if str(where).startswith("7") else str(where)
        message = cls(f"*#18*{where}*52#{str(year)[2:]}#{month}##")
        message._human_readable_log = f"Requesting monthly power consumption for {year}-{month} from sensor {where}."  # pylint: disable=line-too-long
        return message

    @classmethod
    def get_total_consumption(cls, where: str | int) -> OWNEnergyCommand:
        where = f"{where}#0" if str(where).startswith("7") else str(where)
        message = cls(f"*#18*{where}*51##")
        message._human_readable_log = (
            f"Requesting total power consumption from sensor {where}."
        )
        return message

    @classmethod
    def get_totalizer_query(cls, where: str | int) -> OWNEnergyCommand:
        """Query totalizer counter (Dim 516)."""
        where = f"{where}#0" if str(where).startswith("7") else str(where)
        message = cls(f"*#18*{where}*516##")
        message._human_readable_log = f"Requesting totalizer query from sensor {where}."
        return message

    # Stop&Go commands
    @classmethod
    def open_breaker(cls, where: str | int) -> OWNEnergyCommand:
        """Open Stop&Go differential breaker."""
        message = cls(f"*18*21*{where}##")
        message._human_readable_log = f"Opening Stop&Go breaker {where}."
        return message

    @classmethod
    def close_breaker(cls, where: str | int) -> OWNEnergyCommand:
        """Close Stop&Go differential breaker."""
        message = cls(f"*18*22*{where}##")
        message._human_readable_log = f"Closing Stop&Go breaker {where}."
        return message

    @classmethod
    def test_breaker_positive(cls, where: str | int) -> OWNEnergyCommand:
        """Trigger differential self-test (positive result expected)."""
        message = cls(f"*18*23*{where}##")
        message._human_readable_log = f"Triggering positive differential test on Stop&Go breaker {where}."
        return message

    @classmethod
    def test_breaker_negative(cls, where: str | int) -> OWNEnergyCommand:
        """Trigger differential self-test (negative result expected)."""
        message = cls(f"*18*24*{where}##")
        message._human_readable_log = f"Triggering negative differential test on Stop&Go breaker {where}."
        return message

    @classmethod
    def activate_auto_reset(cls, where: str | int) -> OWNEnergyCommand:
        """Activate automatic reset on Stop&Go breaker."""
        message = cls(f"*18*26*{where}##")
        message._human_readable_log = f"Activating auto-reset on Stop&Go breaker {where}."
        return message

    @classmethod
    def deactivate_auto_reset(cls, where: str | int) -> OWNEnergyCommand:
        """Deactivate automatic reset on Stop&Go breaker."""
        message = cls(f"*18*27*{where}##")
        message._human_readable_log = f"Deactivating auto-reset on Stop&Go breaker {where}."
        return message

    @classmethod
    def activate_line_tracking(cls, where: str | int) -> OWNEnergyCommand:
        """Activate line tracking mode on Stop&Go breaker."""
        message = cls(f"*18*28*{where}##")
        message._human_readable_log = f"Activating line tracking on Stop&Go breaker {where}."
        return message

    @classmethod
    def deactivate_line_tracking(cls, where: str | int) -> OWNEnergyCommand:
        """Deactivate line tracking mode on Stop&Go breaker."""
        message = cls(f"*18*29*{where}##")
        message._human_readable_log = f"Deactivating line tracking on Stop&Go breaker {where}."
        return message

    @classmethod
    def get_test_interval(cls, where: str | int) -> OWNEnergyCommand:
        """Request Stop&Go differential test interval in days."""
        message = cls(f"*#18*{where}*212##")
        message._human_readable_log = f"Requesting test interval from Stop&Go breaker {where}."
        return message

    @classmethod
    def set_test_interval(cls, where: str | int, days: int) -> OWNEnergyCommand:
        """Set Stop&Go differential test interval in days (1..90)."""
        if not 1 <= int(days) <= 90:
            raise ValueError(f"Test interval days must be between 1 and 90, got {days}")
        message = cls(f"*#18*{where}*#212*{days}##")
        message._human_readable_log = f"Setting Stop&Go breaker {where} test interval to {days} days."
        return message

    @classmethod
    def get_breaker_status(cls, where: str | int) -> OWNEnergyCommand:
        """Request Stop&Go breaker status mask."""
        message = cls(f"*#18*{where}*250##")
        message._human_readable_log = f"Requesting status mask from Stop&Go breaker {where}."
        return message

    @classmethod
    def get_line_status(cls, where: str | int) -> OWNEnergyCommand:
        """Request Stop&Go line status."""
        message = cls(f"*#18*{where}*251##")
        message._human_readable_log = f"Requesting line status from Stop&Go breaker {where}."
        return message

    @classmethod
    def get_failure_count(cls, where: str | int) -> OWNEnergyCommand:
        """Request Stop&Go breaker trip / failure counter."""
        message = cls(f"*#18*{where}*258##")
        message._human_readable_log = f"Requesting failure count from Stop&Go breaker {where}."
        return message

    # TS10 WHAT graph series requests
    @classmethod
    def get_daily_graph(cls, where: str | int, month: int, day: int) -> OWNEnergyCommand:
        """Request 8-bit daily graph (TS10 WHAT 52#M#D)."""
        message = cls(f"*18*52#{month}#{day}*{where}##")
        message._human_readable_log = f"Requesting daily graph for month {month} day {day} from sensor {where}."
        return message

    @classmethod
    def get_daily_average_graph(cls, where: str | int, month: int) -> OWNEnergyCommand:
        """Request 8-bit daily average graph (TS10 WHAT 53#M)."""
        message = cls(f"*18*53#{month}*{where}##")
        message._human_readable_log = f"Requesting daily average graph for month {month} from sensor {where}."
        return message

    @classmethod
    def get_monthly_graph(cls, where: str | int, month: int) -> OWNEnergyCommand:
        """Request 8-bit monthly graph (TS10 WHAT 56#M)."""
        message = cls(f"*18*56#{month}*{where}##")
        message._human_readable_log = f"Requesting monthly graph for month {month} from sensor {where}."
        return message

    @classmethod
    def get_cumulative_daily_graph(cls, where: str | int, month: int, day: int) -> OWNEnergyCommand:
        """Request 16-bit cumulative daily graph (TS10 WHAT 57#M#D)."""
        message = cls(f"*18*57#{month}#{day}*{where}##")
        message._human_readable_log = f"Requesting cumulative daily graph for month {month} day {day} from sensor {where}."
        return message

    @classmethod
    def get_cumulative_daily_average_graph(cls, where: str | int, month: int) -> OWNEnergyCommand:
        """Request 16-bit daily average graph (TS10 WHAT 58#M)."""
        message = cls(f"*18*58#{month}*{where}##")
        message._human_readable_log = f"Requesting cumulative daily average graph for month {month} from sensor {where}."
        return message

    @classmethod
    def get_cumulative_monthly_graph(cls, where: str | int, month: int) -> OWNEnergyCommand:
        """Request 32-bit cumulative monthly graph (TS10 WHAT 59#M)."""
        message = cls(f"*18*59#{month}*{where}##")
        message._human_readable_log = f"Requesting cumulative monthly graph for month {month} from sensor {where}."
        return message

    @classmethod
    def get_cumulative_monthly_series(cls, where: str | int, month: int) -> OWNEnergyCommand:
        """Request cumulative monthly series (TS10 WHAT 510#M)."""
        message = cls(f"*18*510#{month}*{where}##")
        message._human_readable_log = f"Requesting cumulative monthly series for month {month} from sensor {where}."
        return message

    # Energy Actuator commands
    @classmethod
    def enable_actuator(cls, where: str | int) -> OWNEnergyCommand:
        """Enable energy actuator."""
        message = cls(f"*18*71*{where}##")
        message._human_readable_log = f"Enabling energy actuator {where}."
        return message

    @classmethod
    def force_actuator_off(cls, where: str | int, minutes: int | None = None) -> OWNEnergyCommand:
        """Force energy actuator OFF (timed in minutes or indefinite)."""
        if minutes is not None:
            message = cls(f"*18*73#{minutes}*{where}##")
            message._human_readable_log = f"Forcing energy actuator {where} OFF for {minutes} minutes."
        else:
            message = cls(f"*18*73*{where}##")
            message._human_readable_log = f"Forcing energy actuator {where} OFF indefinitely."
        return message

    @classmethod
    def end_force_actuator(cls, where: str | int) -> OWNEnergyCommand:
        """End forced OFF on energy actuator."""
        message = cls(f"*18*74*{where}##")
        message._human_readable_log = f"Ending forced OFF on energy actuator {where}."
        return message

    @classmethod
    def reset_actuator_totalizer(cls, where: str | int, totalizer: int = 1) -> OWNEnergyCommand:
        """Reset energy actuator totalizer."""
        message = cls(f"*18*75#{totalizer}*{where}##")
        message._human_readable_log = f"Resetting totalizer {totalizer} on energy actuator {where}."
        return message

    @classmethod
    def get_actuator_status(cls, where: str | int) -> OWNEnergyCommand:
        """Request energy actuator status."""
        message = cls(f"*#18*{where}*71##")
        message._human_readable_log = f"Requesting status from energy actuator {where}."
        return message

    @classmethod
    def get_actuator_differential_current(cls, where: str | int) -> OWNEnergyCommand:
        """Request differential current level from energy actuator."""
        message = cls(f"*#18*{where}*73##")
        message._human_readable_log = f"Requesting differential current from energy actuator {where}."
        return message


register_event_parser(18, OWNEnergyEvent)
register_command_parser(18, OWNEnergyCommand)
