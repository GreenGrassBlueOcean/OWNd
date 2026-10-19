"""WHO 14: Special commands (actuator lock and unlock).

Defines WHO 14 Point-to-Point (APL) actuator lock (``*14*0*WHERE##``) and
unlock (``*14*1*WHERE##``) command and event frames, including optional
2-digit local bus interface routing (``*14*WHAT*WHERE#4#01..09##``).
"""

from __future__ import annotations

from .base import (
    OWNCommand,
    OWNEvent,
    register_command_parser,
    register_event_parser,
    require_non_empty_where,
)
from .lighting import is_apl_address

ACTUATOR_STATE_LOCKED = 0
ACTUATOR_STATE_UNLOCKED = 1

ACTUATOR_LOCK_STATE_NAMES: dict[int, str] = {
    ACTUATOR_STATE_LOCKED: "locked",
    ACTUATOR_STATE_UNLOCKED: "unlocked",
}


def _format_actuator_where(
    where: str | int, interface: str | int | None = None
) -> str:
    """Validate and format a WHO 14 Point-to-Point (APL) WHERE with optional #4#01..09 routing."""
    if isinstance(where, bool):
        raise ValueError(
            "WHO 14 actuator WHERE must be a Point-to-Point (APL) address, not bool"
        )
    target = require_non_empty_where(where)
    if target.startswith("#"):
        raise ValueError(
            f"WHO 14 actuator lock requires an actuator WHERE address, not group '{target}'"
        )

    iface_raw: str | None = None
    if "#" in target:
        parts = target.split("#")
        if len(parts) != 3 or parts[1] != "4":
            raise ValueError(f"Invalid WHO 14 actuator WHERE address: '{target}'")
        if interface is not None:
            raise ValueError(
                f"where '{target}' already contains a #4# interface suffix"
            )
        base, iface_raw = parts[0], parts[2]
    else:
        base = target

    if not base.isascii() or not is_apl_address(base):
        raise ValueError(
            f"Invalid WHO 14 Point-to-Point (APL) actuator WHERE address: '{base}'"
        )

    if interface is not None:
        if isinstance(interface, bool):
            raise ValueError(
                "WHO 14 local bus interface must be an integer or numeric string (01..09), not bool"
            )
        iface_raw = require_non_empty_where(interface)

    if iface_raw is not None:
        if not iface_raw.isascii() or not iface_raw.isdigit() or len(iface_raw) > 2:
            raise ValueError(
                f"Invalid WHO 14 local bus interface '{iface_raw}'; expected 01..09"
            )
        iface_num = int(iface_raw)
        if not 1 <= iface_num <= 9:
            raise ValueError(
                f"WHO 14 local bus interface must be between 1 and 9 (01..09), got '{iface_raw}'"
            )
        return f"{base}#4#{iface_num:02d}"

    return base


class OWNActuatorLockEvent(OWNEvent):
    """WHO 14 actuator lock / special command event."""

    def __init__(self, data: str) -> None:
        super().__init__(data)
        self._state: int | None = None

        if self._what is not None and self._what != 1000:
            if self._what in ACTUATOR_LOCK_STATE_NAMES:
                self._state = self._what
                state_name = ACTUATOR_LOCK_STATE_NAMES[self._what]
                self._human_readable_log = (
                    f"Actuator {self._where}{self._interface_log_text} is {state_name}."
                )
            else:
                self._human_readable_log = (
                    f"Actuator {self._where}{self._interface_log_text} "
                    f"received unknown lock state: {self._what}."
                )

    @property
    def effective_what(self) -> int | None:
        """The effective 'what' ID, unwrapping Command Translation (1000#WHAT) frames."""
        if self._what == 1000 and self._what_param:
            return int(self._what_param[0])
        return self._what

    @property
    def state(self) -> int | None:
        """0 (locked), 1 (unlocked), or None for unknown/dimension/translation frames."""
        return self._state

    @property
    def state_name(self) -> str | None:
        """'locked', 'unlocked', or None."""
        return (
            ACTUATOR_LOCK_STATE_NAMES[self._state]
            if self._state is not None
            else None
        )

    @property
    def is_locked(self) -> bool:
        """True if actuator is locked (*14*0*WHERE##)."""
        return self._state == ACTUATOR_STATE_LOCKED

    @property
    def is_unlocked(self) -> bool:
        """True if actuator is unlocked (*14*1*WHERE##)."""
        return self._state == ACTUATOR_STATE_UNLOCKED


class OWNActuatorLockCommand(OWNCommand):
    """WHO 14 special commands (actuator lock and unlock).

    Builders are provided for the two commands established by
    ``ScenarioDevices`` and verified to reach the SCS bus in the firmware
    oracle: ``lock`` (``*14*0*WHERE##`` / ``*14*0*WHERE#4#I##``) and ``unlock``
    (``*14*1*WHERE##`` / ``*14*1*WHERE#4#I##``).
    """

    def __init__(self, data: str) -> None:
        super().__init__(data)
        eff_what = self.effective_what
        if eff_what == ACTUATOR_STATE_LOCKED:
            self._human_readable_log = (
                f"Locking actuator {self._where}{self._interface_log_text}."
            )
        elif eff_what == ACTUATOR_STATE_UNLOCKED:
            self._human_readable_log = (
                f"Unlocking actuator {self._where}{self._interface_log_text}."
            )
        elif self._message_type == "STATUS_REQUEST":
            self._human_readable_log = (
                f"Requesting lock status for actuator "
                f"{self._where}{self._interface_log_text}."
            )

    @property
    def effective_what(self) -> int | None:
        """The effective 'what' ID, unwrapping Command Translation (1000#WHAT) frames."""
        if self._what == 1000 and self._what_param:
            return int(self._what_param[0])
        return self._what

    @property
    def is_status_request(self) -> bool:
        """True if this frame is a status request (*#14*WHERE##)."""
        return self._message_type == "STATUS_REQUEST"

    @property
    def state(self) -> int | None:
        """0 (locked), 1 (unlocked), or None for status requests / unknown WHAT."""
        eff_what = self.effective_what
        return eff_what if eff_what in ACTUATOR_LOCK_STATE_NAMES else None

    @property
    def state_name(self) -> str | None:
        """'locked', 'unlocked', or None."""
        st = self.state
        return ACTUATOR_LOCK_STATE_NAMES[st] if st is not None else None

    @property
    def is_locked(self) -> bool:
        """True if command locks the actuator (*14*0*WHERE##)."""
        return self.effective_what == ACTUATOR_STATE_LOCKED

    @property
    def is_unlocked(self) -> bool:
        """True if command unlocks the actuator (*14*1*WHERE##)."""
        return self.effective_what == ACTUATOR_STATE_UNLOCKED

    @classmethod
    def lock(
        cls, where: str | int, interface: str | int | None = None
    ) -> OWNActuatorLockCommand:
        """Lock actuator controls (*14*0*WHERE## or *14*0*WHERE#4#01..09##)."""
        target = _format_actuator_where(where, interface)
        return cls(f"*14*{ACTUATOR_STATE_LOCKED}*{target}##")

    @classmethod
    def unlock(
        cls, where: str | int, interface: str | int | None = None
    ) -> OWNActuatorLockCommand:
        """Unlock actuator controls (*14*1*WHERE## or *14*1*WHERE#4#01..09##)."""
        target = _format_actuator_where(where, interface)
        return cls(f"*14*{ACTUATOR_STATE_UNLOCKED}*{target}##")

    @classmethod
    def set_locked(
        cls,
        where: str | int,
        locked: bool,
        interface: str | int | None = None,
    ) -> OWNActuatorLockCommand:
        """Lock (locked=True) or unlock (locked=False) actuator controls."""
        if not isinstance(locked, bool):
            raise ValueError("locked must be a boolean")
        return (
            cls.lock(where, interface=interface)
            if locked
            else cls.unlock(where, interface=interface)
        )

    @classmethod
    def disable(
        cls, where: str | int, interface: str | int | None = None
    ) -> OWNActuatorLockCommand:
        """Alias for lock() (*14*0*WHERE## or *14*0*WHERE#4#01..09##)."""
        return cls.lock(where, interface=interface)

    @classmethod
    def enable(
        cls, where: str | int, interface: str | int | None = None
    ) -> OWNActuatorLockCommand:
        """Alias for unlock() (*14*1*WHERE## or *14*1*WHERE#4#01..09##)."""
        return cls.unlock(where, interface=interface)


# Aliases matching the OPEN.db EN_SYSTEM name ("Special commands").
OWNSpecialEvent = OWNActuatorLockEvent
OWNSpecialCommand = OWNActuatorLockCommand

register_event_parser(14, OWNActuatorLockEvent)
register_command_parser(14, OWNActuatorLockCommand)
