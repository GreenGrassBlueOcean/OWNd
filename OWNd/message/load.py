"""WHO 3: Load control (load shedding) events and commands.

Evidence, in order of weight:

- Firmware: own-firmware-oracle suite ``energy-ts10`` (vendored in
  tests/golden/firmware_oracle.json). On F459 020105 and MH202 010024, whose
  rows are aligned, only ``*3*2*#N##`` (force) is accepted as a command. It is
  ACKed and put on the bus as ``$04B70N1300``, with the priority in the
  telegram. ``*3*0*``, ``*3*1*`` and ``*3*3*`` are NACKed with nothing on the
  bus, for a priority and for the general WHERE 0 alike. ``*#3*#N##`` and
  ``*#3*10*D##`` (D 0-4) are forwarded to the bus; ``*#3*0##`` is NACKed.
  F453AV, F454, H4684 and MH200N agree once their one-row capture lag is
  allowed for, and three of them echo ``*3*2*#N##`` on the event session.
- Specification: WHO 3 Load Control v1.0.0 (2006), as summarised by the
  OpenWebNet Encyclopedia (functional/who-3-load-management). WHAT 0 load
  disabled, 1 enabled, 2 forced, 3 forcing removed; WHERE 0 general, 10 control
  unit, #1-#8 priority; DIMENSION 0-4 at WHERE 10 are measurements.

No capture from a plant with a load-control central unit exists yet, so the
state and measurement replies (``*3*STATE*#N##``, ``*#3*10*D*VAL##``) are
parsed from the specification only. Measurement values are kept raw: the
specification names the dimensions but defines no scaling, sign or unit.
"""

from __future__ import annotations

import re

from .base import OWNCommand, OWNEvent, register_command_parser, register_event_parser

LOAD_STATE_DISABLED = 0
LOAD_STATE_ENABLED = 1
LOAD_STATE_FORCED = 2
LOAD_STATE_FORCING_REMOVED = 3

LOAD_CONTROL_UNIT = "10"
LOAD_PRIORITIES = range(1, 9)
LOAD_MEASUREMENT_DIMENSIONS = range(0, 5)

LOAD_DIMENSION_ALL = 0
LOAD_DIMENSION_POWER = 1
LOAD_DIMENSION_VOLTAGE = 2
LOAD_DIMENSION_CURRENT = 3
LOAD_DIMENSION_POWER_FACTOR = 4

_STATE_TEXT = {
    LOAD_STATE_DISABLED: "disabled",
    LOAD_STATE_ENABLED: "enabled",
    LOAD_STATE_FORCED: "forced",
    LOAD_STATE_FORCING_REMOVED: "no longer forced",
}

# Dimension mappings verified against central unit internal register polling
# in bt_energia (findings/MyHomeServer1/energy-ts10.md):
# - Dimension 1: Instantaneous Power (W) -> register $03AA001613
# - Dimension 2: Voltage (V) -> register $03AA001612
# - Dimension 3: Current (A) -> registers $03AA001610 & $03AA001611
# - Dimension 4: Power Factor (cos phi) -> registers $03AA001606 through $03AA001609
_DIMENSION_NAMES = {
    LOAD_DIMENSION_ALL: "all measurements",
    LOAD_DIMENSION_POWER: "instantaneous power",
    LOAD_DIMENSION_VOLTAGE: "voltage",
    LOAD_DIMENSION_CURRENT: "current",
    LOAD_DIMENSION_POWER_FACTOR: "power factor",
}

_PRIORITY_WHERE = re.compile(r"^#([1-8])$")


def _safe_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _priority_of(where: str | None) -> int | None:
    """Priority 1-8 for a ``#N`` WHERE; the leading ``#`` is part of the address."""
    match = _PRIORITY_WHERE.match(where or "")
    return int(match.group(1)) if match else None


def _priority_where(priority: int) -> str:
    if priority not in LOAD_PRIORITIES:
        raise ValueError("Load priority must be between 1 and 8")
    return f"#{priority}"


class OWNLoadEvent(OWNEvent):
    """A load priority state or a control-unit measurement reply."""

    def __init__(self, data: str) -> None:
        super().__init__(data)

        self._priority = _priority_of(self._where)
        self._state: int | None = None
        self._measurement_values: list[str] = []
        self._power: int | None = None
        self._voltage: int | None = None
        self._current: float | None = None
        self._power_factor: float | None = None

        if self._priority is not None:
            _target = f"Load priority {self._priority} is"
        elif self._where == "0":
            _target = "All load priorities are"
        else:
            _target = f"Load {self._where} is"

        if self._message_type == "STATUS" and self._what in _STATE_TEXT:
            self._state = self._what
            self._human_readable_log = f"{_target} {_STATE_TEXT[self._what]}."
        elif (
            self._message_type == "DIMENSION_REQUEST_REPLY"
            and self._where == LOAD_CONTROL_UNIT
            and self._dimension is not None
        ):
            self._measurement_values = list(self._dimension_value)
            if self._dimension == LOAD_DIMENSION_POWER and self._dimension_value:
                self._power = _safe_int(self._dimension_value[0])
                self._human_readable_log = (
                    f"Load control unit power draw: {self._power} W."
                )
            elif self._dimension == LOAD_DIMENSION_VOLTAGE and self._dimension_value:
                self._voltage = _safe_int(self._dimension_value[0])
                self._human_readable_log = (
                    f"Load control unit voltage: {self._voltage} V."
                )
            elif self._dimension == LOAD_DIMENSION_CURRENT and self._dimension_value:
                self._current = _safe_float(self._dimension_value[0])
                self._human_readable_log = (
                    f"Load control unit current: {self._current} A."
                )
            elif (
                self._dimension == LOAD_DIMENSION_POWER_FACTOR
                and self._dimension_value
            ):
                self._power_factor = _safe_float(self._dimension_value[0])
                self._human_readable_log = (
                    f"Load control unit power factor: {self._power_factor}."
                )
            elif self._dimension == LOAD_DIMENSION_ALL:
                if len(self._dimension_value) >= 1:
                    self._power = _safe_int(self._dimension_value[0])
                if len(self._dimension_value) >= 2:
                    self._voltage = _safe_int(self._dimension_value[1])
                if len(self._dimension_value) >= 3:
                    self._current = _safe_float(self._dimension_value[2])
                if len(self._dimension_value) >= 4:
                    self._power_factor = _safe_float(self._dimension_value[3])
                self._human_readable_log = (
                    f"Load control unit all measurements: "
                    f"power={self._power} W, voltage={self._voltage} V, "
                    f"current={self._current} A, power factor={self._power_factor}."
                )
            else:
                _name = _DIMENSION_NAMES.get(self._dimension)
                _label = f" ({_name})" if _name else ""
                self._human_readable_log = (
                    f"Load control unit dimension {self._dimension}{_label}: "
                    f"raw values {self._measurement_values}."
                )

    @property
    def priority(self) -> int | None:
        """Load priority 1-8 from a ``#N`` WHERE, None for any other target."""
        return self._priority

    @property
    def state(self) -> int | None:
        """WHAT 0-3 of a state frame (see ``LOAD_STATE_*``), None otherwise."""
        return self._state

    @property
    def is_forced(self) -> bool | None:
        """Whether the load is forced, None when the frame carries no state."""
        return None if self._state is None else self._state == LOAD_STATE_FORCED

    @property
    def is_control_unit(self) -> bool:
        return self._where == LOAD_CONTROL_UNIT

    @property
    def measurement_values(self) -> list[str]:
        """Raw values of a control-unit measurement reply, unscaled and unitless."""
        return self._measurement_values

    @property
    def power(self) -> int | None:
        """Instantaneous power draw in W (dimension 1), None if not reported."""
        return self._power

    @property
    def voltage(self) -> int | None:
        """Voltage in V (dimension 2), None if not reported."""
        return self._voltage

    @property
    def current(self) -> float | None:
        """Current in A (dimension 3), None if not reported."""
        return self._current

    @property
    def power_factor(self) -> float | None:
        """Power factor cos phi (dimension 4), None if not reported."""
        return self._power_factor


class OWNLoadCommand(OWNCommand):
    """WHO 3 commands and requests.

    Only frames that the firmware oracle shows reaching the bus get a builder.
    WHAT 0, 1 and 3, the general WHERE 0 and the general status request
    ``*#3*0##`` are refused by the gateways, so there is no builder for them.
    """

    def __init__(self, data: str) -> None:
        super().__init__(data)
        _priority = _priority_of(self._where)
        if self._message_type == "STATUS" and self._what == LOAD_STATE_FORCED:
            if _priority is not None:
                self._human_readable_log = f"Forcing load priority {_priority}."
        elif self._message_type == "STATUS_REQUEST" and _priority is not None:
            self._human_readable_log = f"Requesting load priority {_priority} status."
        elif (
            self._message_type == "DIMENSION_REQUEST"
            and self._where == LOAD_CONTROL_UNIT
            and self._dimension is not None
        ):
            self._human_readable_log = (
                f"Requesting load control unit dimension {self._dimension}."
            )

    @classmethod
    def force(cls, priority: int) -> OWNLoadCommand:
        """Force the load on ``priority`` 1-8 (``*3*2*#N##``)."""
        return cls(f"*3*{LOAD_STATE_FORCED}*{_priority_where(priority)}##")

    @classmethod
    def status(cls, priority: int) -> OWNLoadCommand:
        """Request the state of load ``priority`` 1-8 (``*#3*#N##``)."""
        return cls(f"*#3*{_priority_where(priority)}##")

    @classmethod
    def request_measurement(cls, dimension: int = 0) -> OWNLoadCommand:
        """Request control-unit measurement ``dimension`` 0-4 (``*#3*10*D##``)."""
        if dimension not in LOAD_MEASUREMENT_DIMENSIONS:
            raise ValueError("Load measurement dimension must be between 0 and 4")
        return cls(f"*#3*{LOAD_CONTROL_UNIT}*{dimension}##")


register_event_parser(3, OWNLoadEvent)
register_command_parser(3, OWNLoadCommand)
