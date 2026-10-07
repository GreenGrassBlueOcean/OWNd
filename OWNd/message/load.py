"""WHO 3: Load control and shedding subsystem (F421 central unit and load actuators)."""

from __future__ import annotations

from typing import Any

from .base import OWNCommand, OWNEvent, register_command_parser, register_event_parser

MESSAGE_TYPE_LOAD_STATE = "load_state"
MESSAGE_TYPE_VOLTAGE = "voltage"
MESSAGE_TYPE_CURRENT = "current"
MESSAGE_TYPE_ACTIVE_POWER = "active_power"
MESSAGE_TYPE_ENERGY = "energy"
MESSAGE_TYPE_ALL_MEASUREMENTS = "all_measurements"


def _clean_priority(priority: int | str) -> int:
    """Normalize and validate priority line index (1..8)."""
    p_str = str(priority).lstrip("#").strip()
    if not p_str.isdigit():
        raise ValueError(f"Priority must be an integer between 1 and 8, got '{priority}'")
    val = int(p_str)
    if not 1 <= val <= 8:
        raise ValueError(f"Priority must be between 1 and 8, got {val}")
    return val


class OWNLoadEvent(OWNEvent):
    """State reported by a WHO 3 load control device or F421 central unit."""

    def __init__(self, data: str) -> None:
        super().__init__(data)

        self._type: str | None = None
        self._is_shed: bool | None = None
        self._is_forced: bool | None = None
        self._priority: int | None = None
        self._voltage: float | int | None = None
        self._current: float | int | None = None
        self._power: float | int | None = None
        self._energy: float | int | None = None

        where = self._where or ""
        if where.startswith("#") and where[1:].isdigit():
            self._priority = int(where[1:])

        what = self._what
        dim = self._dimension
        vals = self._dimension_value

        if what is not None:
            self._type = MESSAGE_TYPE_LOAD_STATE
            if what == 0:
                self._is_shed = True
                self._is_forced = False
                self._human_readable_log = f"Load on priority {where} is disabled (shed)."
            elif what == 1:
                self._is_shed = False
                self._is_forced = False
                self._human_readable_log = f"Load on priority {where} is enabled (automatic)."
            elif what == 2:
                self._is_shed = False
                self._is_forced = True
                self._human_readable_log = f"Load on priority {where} is forced (connected)."
            elif what == 3:
                self._is_forced = False
                self._human_readable_log = f"Forcing removed on priority {where}."
            else:
                self._human_readable_log = f"Load command {what} on priority {where}."

        elif dim is not None:
            if dim == 0:
                self._type = MESSAGE_TYPE_ALL_MEASUREMENTS
                if len(vals) >= 4:
                    self._voltage = float(vals[0])
                    self._current = float(vals[1])
                    self._power = float(vals[2])
                    self._energy = float(vals[3])
                self._human_readable_log = (
                    f"Central unit {where} measurements: V={self._voltage}V, "
                    f"I={self._current}A, P={self._power}W, E={self._energy}Wh."
                )
            elif dim == 1:
                self._type = MESSAGE_TYPE_VOLTAGE
                if vals:
                    self._voltage = float(vals[0])
                self._human_readable_log = f"Central unit {where} voltage: {self._voltage} V."
            elif dim == 2:
                self._type = MESSAGE_TYPE_CURRENT
                if vals:
                    self._current = float(vals[0])
                self._human_readable_log = f"Central unit {where} current: {self._current} A."
            elif dim == 3:
                self._type = MESSAGE_TYPE_ACTIVE_POWER
                if vals:
                    self._power = float(vals[0])
                self._human_readable_log = f"Central unit {where} active power: {self._power} W."
            elif dim == 4:
                self._type = MESSAGE_TYPE_ENERGY
                if vals:
                    self._energy = float(vals[0])
                self._human_readable_log = f"Central unit {where} energy: {self._energy} Wh."
            else:
                self._human_readable_log = f"Central unit {where} dimension {dim}."

    @property
    def message_type(self) -> str | None:
        return self._type

    @property
    def is_shed(self) -> bool | None:
        return self._is_shed

    @property
    def is_forced(self) -> bool | None:
        return self._is_forced

    @property
    def priority(self) -> int | None:
        return self._priority

    @property
    def voltage(self) -> float | int | None:
        return self._voltage

    @property
    def current(self) -> float | int | None:
        return self._current

    @property
    def power(self) -> float | int | None:
        return self._power

    @property
    def energy(self) -> float | int | None:
        return self._energy


class OWNLoadCommand(OWNCommand):
    """WHO 3 commands for load management and F421 central unit."""

    @classmethod
    def shed_load(cls, priority: int | str) -> OWNLoadCommand:
        """Disable/shed load on specified priority line."""
        p = _clean_priority(priority)
        msg = cls(f"*3*0*#{p}##")
        msg._human_readable_log = f"Disabling (shedding) load on priority line {p}."
        return msg

    @classmethod
    def enable_load(cls, priority: int | str) -> OWNLoadCommand:
        """Enable load on specified priority line (normal/automatic mode)."""
        p = _clean_priority(priority)
        msg = cls(f"*3*1*#{p}##")
        msg._human_readable_log = f"Enabling load on priority line {p}."
        return msg

    @classmethod
    def force_load(cls, priority: int | str) -> OWNLoadCommand:
        """Force load connection on specified priority line."""
        p = _clean_priority(priority)
        msg = cls(f"*3*2*#{p}##")
        msg._human_readable_log = f"Forcing load connection on priority line {p}."
        return msg

    @classmethod
    def remove_forcing(cls, priority: int | str) -> OWNLoadCommand:
        """Remove forcing on specified priority line."""
        p = _clean_priority(priority)
        msg = cls(f"*3*3*#{p}##")
        msg._human_readable_log = f"Removing forcing on priority line {p}."
        return msg

    @classmethod
    def get_measurements(cls, where: str | int = 10) -> OWNLoadCommand:
        """Request all central unit measurements."""
        msg = cls(f"*#3*{where}*0##")
        msg._human_readable_log = f"Requesting all measurements from central unit {where}."
        return msg

    @classmethod
    def get_voltage(cls, where: str | int = 10) -> OWNLoadCommand:
        """Request voltage from central unit."""
        msg = cls(f"*#3*{where}*1##")
        msg._human_readable_log = f"Requesting voltage from central unit {where}."
        return msg

    @classmethod
    def get_current(cls, where: str | int = 10) -> OWNLoadCommand:
        """Request current from central unit."""
        msg = cls(f"*#3*{where}*2##")
        msg._human_readable_log = f"Requesting current from central unit {where}."
        return msg

    @classmethod
    def get_power(cls, where: str | int = 10) -> OWNLoadCommand:
        """Request instantaneous active power from central unit."""
        msg = cls(f"*#3*{where}*3##")
        msg._human_readable_log = f"Requesting active power from central unit {where}."
        return msg

    @classmethod
    def get_energy(cls, where: str | int = 10) -> OWNLoadCommand:
        """Request accumulated energy from central unit."""
        msg = cls(f"*#3*{where}*4##")
        msg._human_readable_log = f"Requesting accumulated energy from central unit {where}."
        return msg

    @classmethod
    def get_priority_status(cls, priority: int | str) -> OWNLoadCommand:
        """Request status for a priority line."""
        p = _clean_priority(priority)
        msg = cls(f"*#3*#{p}##")
        msg._human_readable_log = f"Requesting status for priority line {p}."
        return msg

    @classmethod
    def request_status(
        cls, priority: int | str | None = None, where: str | int | None = None
    ) -> OWNLoadCommand:
        """Request load status for a priority line or central unit."""
        if priority is not None:
            return cls.get_priority_status(priority)
        target = "0" if where is None else where
        msg = cls(f"*#3*{target}##")
        msg._human_readable_log = f"Requesting load status for {target}."
        return msg

    shed = shed_load
    enable = enable_load
    force_reconnect = force_load
    request_measurements = get_measurements
    request_voltage = get_voltage
    request_current = get_current
    request_power = get_power
    request_energy = get_energy


register_event_parser(3, OWNLoadEvent)
register_command_parser(3, OWNLoadCommand)
