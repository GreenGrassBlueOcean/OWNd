"""WHO 14: Special commands (actuator lock and unlock).

Sources:

- ``OPEN.db`` (``EN_SYSTEM.id_system = 35``): names ``WHO = 14``
  ``"Special commands"`` (``managed = 0``, ``diagnostic_open_who = NULL``,
  0 ``EN_OPEN`` rows).
- ``ScenarioDevices-program-files.sqlite`` and
  ``ScenarioDevices-programdata.sqlite``: defines Object
  ``miniScenarioSuite.specialCommands.actionLockUnlockActuator.descr``
  (``WhereType = 1``, ``ChiOpen = 14``) with two scenario actions:

  - ``WHAT = 0`` (``miniScenarioSuite.specialCommands.actionLockUnlockActuator.lock``):
    ``*14*0*WHERE##`` — lock actuator (disable local commands / freeze actuator).
  - ``WHAT = 1`` (``miniScenarioSuite.specialCommands.actionLockUnlockActuator.unlock``):
    ``*14*1*WHERE##`` — unlock actuator (enable local commands / restore normal
    operation).

  Neither ``OPEN.db`` nor ``ScenarioDevices`` defines any ``DIMENSION`` codes
  or additional ``WHAT`` codes for ``WHO 14``.
- Firmware oracle (``tests/golden/firmware_oracle.json``, suites
  ``trace-corpus`` and ``interface-routing``):

  - Translated onto the SCS bus by ``bt_luci`` on F453 (``010100``), F453AV
    (``030014``), F454 (``020051``), F459 (``020105``), F460 (``020012``),
    F461 (``020011``), H4684 (``020054``), MH200 (``020102``), MH200N
    (``010108``), and MyHomeServer1 (``028206``), and by ``coso`` on MH202
    (``010024``).
  - Refused (``reply: "nack"``, ``verdict: "silent"``) on F450 (``020010``,
    BACnet gateway running ``bacclient`` + ``ebacgw`` without ``bt_luci`` or
    ``coso``).
  - Point command frames:

    - ``*14*0*32##`` (lock) emits ``$0332001100\\r`` on F453, F453AV, F454,
      F459, H4684, MH200, MH200N, and MyHomeServer1; ``$00332001100\\r`` on
      3-digit RPMsg PIC gateways (F460, F461); and ``$0432001100\\r`` on MH202
      (which also echoes ``*14*0*32##`` on the event session).
    - ``*14*1*32##`` (unlock) emits ``$0332001000\\r`` on F453, F453AV, F454,
      F459, H4684, MH200, MH200N, and MyHomeServer1; ``$00332001000\\r`` on
      F460 and F461; and ``$0432001000\\r`` on MH202 (which also echoes
      ``*14*1*32##`` on the event session).
    - Notice that ``WHAT = 0`` (lock) encodes SCS opcode ``11 00``
      (``0x11 0x00``) while ``WHAT = 1`` (unlock) encodes ``10 00``
      (``0x10 0x00``).

  - Local bus interface routing (``#4#I``):

    - ``*14*0*31#4#01##`` and ``*14*0*31#4#02##`` emit
      ``$06EC01000031001100\\r`` / ``$06EC02000031001100\\r`` on F453, F453AV,
      F454, F459, MH200, MH200N, MH202, and MyHomeServer1;
      ``$006EC01000031001100\\r`` / ``$006EC02000031001100\\r`` on F460 and
      F461; and ``$06E401000031001100\\r`` / ``$06E402000031001100\\r`` on
      H4684.

  - Command session ACK vs NACK-with-forwarding:

    - F453, F453AV, F454, F459, H4684, MH200, and MH200N reply ``ack``
      (``*#*1##``) immediately upon placing any of the four WHO 14 frames on
      the SCS bus (MH202 also replies ``ack`` on ``*14*0*32##`` and
      ``*14*1*32##``).
    - F460, F461, and MyHomeServer1 (plus MH202 on ``#4#01`` / ``#4#02``)
      place the telegram on the SCS bus (``verdict: "out"``) and reply ``nack``
      on the command session when no physical actuator at the target ``WHERE``
      answers on the simulated bus.

- Binary disassembly of ``coso`` (MH202 ``010024``) and ``bt_luci`` (MH200N
  ``010108``, F460 ``020012``, MyHomeServer1 ``028206``):

  - ``libplug_special_cmd_tr.so`` (``special_cmd_tr_translate`` at
    ``0x1504..0x187c``) and ``libplug_special_cmd_stm.so``
    (``special_cmd_stm_gest_status_from_appli`` at ``0x1490..0x150c``):
    rejects non-command frames (``msg->type != 1`` at ``0x158c``, answering
    ``*#14*WHERE##`` status requests with ``queue_nack_to_open``); parses
    ``WHAT`` via ``strtol`` at ``0x16b0`` where ``0 -> 0x11 0x00`` (lock),
    ``1 -> 0x10 0x00`` (unlock), and ``WHAT > 1`` returns ``1`` (NACK);
    encodes ``WHERE`` via ``lighting_address_open2scs`` (``liblights.so``
    ``0x14b0``, interface format ``#%d#%02d`` at ``0x1fac``); and translates
    inbound ``0x11 0x00`` / ``0x10 0x00`` SCS telegrams (``0x1600..0x16a8``)
    to ``*14*%d*%s%s##``.
  - ``bt_luci`` ``flex`` scanner (``yylex`` at ``0x575cc..0x576b4``,
    ``yy_accept`` at ``0x73e16``, rule ``58`` at ``0x59bac`` -> ``0x2007``
    ``Messaggio openwebnet comando spec`` / ``Messaggio scs illuminazione
    comando speciale``, vtable ``0x66c74`` / PIE ``0x4e0d0``): accepts only
    ``WHAT`` in ``{0, 1}`` and requires a 2-digit ``#4#01``..``#4#09`` bus
    interface suffix (``#4#%02d`` at ``0x2e8d1``), rejecting ``*14*2*...##``,
    ``*#14*...##``, 3-digit ``115``, ``PL > 15``, and 1-digit ``#4#1`` with
    ``act 92`` (syntax error -> NACK). Outbound SCS generator (``0x15a3c`` /
    PIE ``0x10520``) appends ``"1100"`` for ``WHAT == 0`` and ``"1000"`` for
    ``WHAT == 1``; inbound SCS decoders (``0x3a4d8`` / ``0x3a704`` and PIE
    ``0x1a4f4`` / ``0x1a60c``) emit ``*14*0*%s##`` for ``1100`` and
    ``*14*1*%s##`` for ``1000``.
  - Encyclopedia Machine KB (schema ``2.0.0``, ``ownkb:chunk:r000354``,
    ``ownkb:chunk:r001116``, ``ownkb:claim:c000884``, ``ownkb:claim:c000886``,
    ``ownkb:claim:c002004``..``c002017``): records ``WHO 14`` (``Special
    commands``) ``ScenarioDevices`` lock (``*14*0*WHERE##``) and unlock
    (``*14*1*WHERE##``) capabilities and ``WhereType = 1`` literal ``WHERE``
    preservation.
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
