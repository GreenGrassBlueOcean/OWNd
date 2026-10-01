"""WHO 5: Burglar alarm subsystem events and commands."""

from __future__ import annotations

import re

from .base import OWNCommand, OWNEvent, register_command_parser, register_event_parser


class OWNAlarmEvent(OWNEvent):
    def __init__(self, data: str) -> None:
        super().__init__(data)

        # Dimension replies carry no WHAT: never crash the constructor on it.
        self._state_code = int(self._what) if self._what is not None else -1
        self._state: str | None = None
        self._system = False
        # Zone may be a letter ("c", "f"), a number, or None (system-wide).
        self._zone: str | int | None = None
        self._sensor: int | None = None

        where = self._where or ""
        if where == "*":
            self._system = True
            self._human_readable_log = "System is reporting: "
        elif where.startswith("#"):
            self._zone = where[1:]
            if self._zone == "12":
                self._zone = "c"
            elif self._zone == "15":
                self._zone = "f"
            self._human_readable_log = f"Zone {self._zone} is reporting: "
        elif len(where) > 1:
            self._zone = int(where[0])
            self._sensor = int(where[1:])
            if self._zone == 0:
                self._human_readable_log = (
                    f"Device {self._sensor} in input zone is reporting: "
                )
            else:
                self._human_readable_log = (
                    f"Sensor {self._sensor} in zone {self._zone} is reporting: "
                )
        else:
            self._system = True
            self._human_readable_log = "Control panel is reporting: "

        if self._state_code == 0:
            self._state = "maintenance"
        elif self._state_code == 1:
            self._state = "activation"
        elif self._state_code == 2:
            self._state = "deactivation"
        elif self._state_code == 3:
            self._state = "delay end"
        elif self._state_code == 4:
            self._state = "system battery fault"
        elif self._state_code == 5:
            self._state = "battery ok"
        elif self._state_code == 6:
            self._state = "no network"
        elif self._state_code == 7:
            self._state = "network present"
        elif self._state_code == 8:
            self._state = "engage"
        elif self._state_code == 9:
            self._state = "disengage"
        elif self._state_code == 10:
            self._state = "battery unloads"
        elif self._state_code == 11:
            self._state = "active zone"
        elif self._state_code == 12:
            self._state = "technical alarm"
        elif self._state_code == 13:
            self._state = "reset technical alarm"
        elif self._state_code == 14:
            self._state = "no reception"
        elif self._state_code == 15:
            self._state = "intrusion alarm"
        elif self._state_code == 16:
            self._state = "tampering"
        elif self._state_code == 17:
            self._state = "anti-panic alarm"
        elif self._state_code == 18:
            self._state = "non-active zone"
        elif self._state_code == 26:
            self._state = "start programming"
        elif self._state_code == 27:
            self._state = "stop programming"
        elif self._state_code == 31:
            self._state = "silent alarm"

        if self._what is None:
            # Bare status request (e.g. *#5##): keep the raw frame as the log.
            self._human_readable_log = self._raw
        elif self._state is not None:
            self._human_readable_log = f"{self._human_readable_log}'{self._state}'."
        else:
            self._human_readable_log = (
                f"{self._human_readable_log}unknown state '{self._state_code}'."
            )

    @property
    def general(self) -> bool:
        return self._system

    @property
    def zone(self) -> str | int | None:
        return self._zone

    @property
    def sensor(self) -> int | None:
        return self._sensor

    @property
    def is_active(self) -> bool:
        return self._state_code == 1 or self._state_code == 11

    @property
    def is_engaged(self) -> bool:
        return self._state_code == 8

    @property
    def is_disarmed(self) -> bool:
        return self._state_code in (0, 2, 9)

    @property
    def is_armed_away(self) -> bool:
        return self._state_code in (1, 8)

    @property
    def is_armed_home(self) -> bool:
        return self._state_code == 11

    @property
    def state_name(self) -> str | None:
        return self._state

    @property
    def state_code(self) -> int:
        return self._state_code

    @property
    def is_alarm(self) -> bool:
        return (
            self._state_code == 12
            or self._state_code == 15
            or self._state_code == 16
            or self._state_code == 17
            or self._state_code == 31
        )



class OWNAlarmCommand(OWNCommand):
    @classmethod
    def status(cls, where: str | int | None = "0") -> OWNAlarmCommand:
        if where is None or where == "":
            message = cls("*#5##")
            message._human_readable_log = "Querying burglar alarm central status."
            return message

        where_str = str(where)
        if where_str == "0":
            message = cls("*#5*0##")
            message._human_readable_log = "Querying burglar alarm central status."
            return message

        target = where_str if where_str.startswith("#") else f"#{where_str}"
        message = cls(f"*#5*{target}##")
        message._human_readable_log = (
            f"Querying burglar alarm status for zone {where}."
        )
        return message

    @classmethod
    def disarm(cls, where: str | int = "0") -> OWNAlarmCommand:
        message = cls(f"*5*2*{where}##")
        message._human_readable_log = f"Disarming burglar alarm for zone {where}."
        return message

    @classmethod
    def arm_away(cls, where: str | int = "0") -> OWNAlarmCommand:
        message = cls(f"*5*1*{where}##")
        message._human_readable_log = (
            f"Arming burglar alarm (away) for zone {where}."
        )
        return message

    @classmethod
    def arm_home(cls, where: str | int = "0") -> OWNAlarmCommand:
        message = cls(f"*5*1*{where}##")
        message._human_readable_log = (
            f"Arming burglar alarm (home) for zone {where}."
        )
        return message

    @classmethod
    def trigger(cls, where: str | int = "0") -> OWNAlarmCommand:
        message = cls(f"*5*17*{where}##")
        message._human_readable_log = (
            f"Triggering panic burglar alarm for zone {where}."
        )
        return message

    @classmethod
    def panic(cls, where: str | int = "0") -> OWNAlarmCommand:
        return cls.trigger(where=where)


register_event_parser(5, OWNAlarmEvent)
register_command_parser(5, OWNAlarmCommand)
