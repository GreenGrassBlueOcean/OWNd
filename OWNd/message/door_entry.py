"""WHO 6 and WHO 8: Door entry and lock events and commands."""

from __future__ import annotations

from .base import OWNCommand, OWNEvent, register_command_parser, register_event_parser


class OWNDoorEntryEvent(OWNEvent):
    """Event reported by a WHO 6 door entry system or lock."""

    def __init__(self, data: str) -> None:
        super().__init__(data)

        self._where = self._where or ""
        self._is_incoming_call = self._what == 6
        self._is_broadcast_call = self._what == 6 and self._where == "4100"
        self._is_chime = self._what == 20
        self._is_call = self._is_incoming_call or self._is_chime
        self._is_lock_open = self._what in (10, 22)
        self._is_staircase_on = self._what == 12
        self._is_staircase_off = self._what == 11
        self._is_camera_on = self._what == 0
        self._is_camera_off = self._what == 9

        if self._is_broadcast_call:
            self._human_readable_log = "Incoming door entry broadcast call."
        elif self._is_incoming_call:
            self._human_readable_log = (
                f"Incoming door entry call to handset {self._where}."
            )
        elif self._is_chime:
            self._human_readable_log = f"Door entry chime active at {self._where}."
        elif self._what == 10:
            self._human_readable_log = (
                f"Door lock released at entrance panel {self._where}."
            )
        elif self._what == 22:
            self._human_readable_log = (
                f"Door lock released during conversation with entrance panel {self._where}."
            )
        elif self._is_staircase_on:
            self._human_readable_log = (
                f"Staircase light switched ON from door entry at {self._where}."
            )
        elif self._is_staircase_off:
            self._human_readable_log = (
                f"Staircase light switched OFF from door entry at {self._where}."
            )
        elif self._is_camera_on:
            self._human_readable_log = (
                f"Door entry camera switched ON at {self._where}."
            )
        elif self._is_camera_off:
            self._human_readable_log = "Door entry camera switched OFF."
        elif self._what is not None:
            self._human_readable_log = (
                f"Door entry device {self._where} received event: {self._what}."
            )

    @property
    def is_call(self) -> bool:
        """True if the event represents an incoming call or active chime."""
        return self._is_call

    @property
    def is_incoming_call(self) -> bool:
        """True if an incoming call frame (*6*6*WHERE##) was received."""
        return self._is_incoming_call

    @property
    def is_broadcast_call(self) -> bool:
        """True if a broadcast call frame (*6*6*4100##) was received."""
        return self._is_broadcast_call

    @property
    def is_chime(self) -> bool:
        """True if a chime event (*6*20*WHERE##) was received."""
        return self._is_chime

    @property
    def is_lock_open(self) -> bool:
        """True if a door lock open event (*6*10*WHERE## or *6*22*WHERE##) was received."""
        return self._is_lock_open

    @property
    def is_staircase_on(self) -> bool:
        """True if a staircase light ON event (*6*12*WHERE##) was received."""
        return self._is_staircase_on

    @property
    def is_staircase_off(self) -> bool:
        """True if a staircase light OFF event (*6*11*WHERE##) was received."""
        return self._is_staircase_off


class OWNDoorEntryCommand(OWNCommand):
    """WHO 6 commands for door locks, staircase lighting, and cameras."""

    @classmethod
    def open_lock(cls, where: str | int = 0) -> OWNDoorEntryCommand:
        """Open / release door lock at the specified entrance panel address."""
        ep = str(where).strip()
        message = cls(f"*6*10*{ep}##")
        message._human_readable_log = (
            f"Opening door lock at entrance panel {ep}."
        )
        return message

    @classmethod
    def staircase_light_on(cls, where: str | int = 0) -> OWNDoorEntryCommand:
        """Switch ON the staircase light from the door entry system."""
        ep = str(where).strip()
        message = cls(f"*6*12*{ep}##")
        message._human_readable_log = (
            f"Switching ON staircase light from door entry at {ep}."
        )
        return message

    @classmethod
    def staircase_light_off(cls, where: str | int = 0) -> OWNDoorEntryCommand:
        """Switch OFF the staircase light from the door entry system."""
        ep = str(where).strip()
        message = cls(f"*6*11*{ep}##")
        message._human_readable_log = (
            f"Switching OFF staircase light from door entry at {ep}."
        )
        return message

    @classmethod
    def camera_on(cls, where: str | int) -> OWNDoorEntryCommand:
        """Switch ON video door entry camera at entrance panel."""
        ep = str(where).strip()
        message = cls(f"*6*0*{ep}##")
        message._human_readable_log = (
            f"Switching ON camera at entrance panel {ep}."
        )
        return message

    @classmethod
    def camera_off(cls) -> OWNDoorEntryCommand:
        """Switch OFF video door entry camera."""
        message = cls("*6*9##")
        message._human_readable_log = "Switching OFF video door entry camera."
        return message


class OWNLockEvent(OWNEvent):
    """Event reported by a WHO 8 video door entry / lock actuator."""

    def __init__(self, data: str) -> None:
        super().__init__(data)

        self._where = self._where or ""
        self._is_unlocked = self._what == 19
        self._is_locked = self._what == 20

        if self._is_unlocked:
            self._human_readable_log = f"Lock actuator {self._where} unlocked / open."
        elif self._is_locked:
            self._human_readable_log = f"Lock actuator {self._where} locked / released."
        elif self._what is not None:
            self._human_readable_log = (
                f"Lock actuator {self._where} received event: {self._what}."
            )

    @property
    def is_unlocked(self) -> bool:
        """True if lock actuator is unlocked (*8*19*WHERE##)."""
        return self._is_unlocked

    @property
    def is_locked(self) -> bool:
        """True if lock actuator is locked (*8*20*WHERE##)."""
        return self._is_locked


class OWNLockCommand(OWNCommand):
    """WHO 8 commands for lock actuators."""

    @classmethod
    def unlock(cls, where: str | int) -> OWNLockCommand:
        """Activate / unlock door lock actuator at address WHERE."""
        target = str(where).strip()
        message = cls(f"*8*19*{target}##")
        message._human_readable_log = (
            f"Unlocking lock actuator at address {target}."
        )
        return message

    @classmethod
    def lock(cls, where: str | int) -> OWNLockCommand:
        """Release / lock door lock actuator at address WHERE."""
        target = str(where).strip()
        message = cls(f"*8*20*{target}##")
        message._human_readable_log = (
            f"Releasing lock actuator at address {target}."
        )
        return message


register_event_parser(6, OWNDoorEntryEvent)
register_command_parser(6, OWNDoorEntryCommand)
