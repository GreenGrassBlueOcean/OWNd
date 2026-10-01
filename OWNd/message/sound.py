"""WHO 16 & 22: Sound diffusion and audio/video door entry events and commands."""

from __future__ import annotations

import re

from .base import OWNCommand, OWNEvent, register_command_parser, register_event_parser


class OWNSoundEvent(OWNEvent):
    """State reported by a WHO 16 sound source or amplifier zone."""

    def __init__(self, data: str) -> None:
        super().__init__(data)

        self._state = self._what
        self._zone = self._where or ""
        self._is_source_event = bool(re.fullmatch(r"10[1-9]", self._zone))
        self._source_id = (
            str(int(self._zone) - 100) if self._is_source_event else None
        )
        # `1ES` routes the amplifiers of environment E to matrix source S.
        # Environment 0 would be `10S`, the source itself, so E starts at 1.
        # S is kept as sent, `0` included: whatever it names, `1E0` is not
        # amplifier 1E0 either. A routing frame keeps its address as `zone`:
        # consumers parse routing from it, so only is_routing_event tells it
        # apart from an amplifier.
        self._is_routing_event = bool(re.fullmatch(r"1[1-9][0-9]", self._zone))
        self._environment = self._zone[1] if self._is_routing_event else None
        self._routed_source = self._zone[2] if self._is_routing_event else None
        self._volume: int | None = None

        if self._is_source_event:
            subject = f"Audio Source {self._source_id}"
        elif self._is_routing_event:
            subject = (
                f"Routing of environment {self._environment} "
                f"to source {self._routed_source}"
            )
        else:
            subject = f"Audio Zone {self._zone}"
        if self._state in (0, 3):
            self._human_readable_log = f"{subject} is switched ON."
        elif self._state in (10, 13):
            self._human_readable_log = f"{subject} is switched OFF."
        elif self._state is not None:
            self._human_readable_log = f"{subject} received command: {self._state}."
        elif self._dimension == 1 and self._dimension_value:
            try:
                self._volume = int(self._dimension_value[0])
            except ValueError:
                return
            self._human_readable_log = (
                f"Audio zone {self._zone} volume is set to {self._volume}."
            )

    @property
    def is_on(self) -> bool:
        return self._state in (0, 3)

    @property
    def is_off(self) -> bool:
        return self._state in (10, 13)

    @property
    def is_source_event(self) -> bool:
        return self._is_source_event

    @property
    def source_id(self) -> str | None:
        return self._source_id

    @property
    def is_routing_event(self) -> bool:
        """True for a `1ES` matrix routing frame."""
        return self._is_routing_event

    @property
    def environment(self) -> str | None:
        """Environment `E` of a `1ES` routing frame, otherwise None."""
        return self._environment

    @property
    def routed_source(self) -> str | None:
        """Matrix source `S` of a `1ES` routing frame, otherwise None."""
        return self._routed_source

    @property
    def zone(self) -> str:
        """The frame's address; a `1ES` routing address for routing frames."""
        return self._zone

    @property
    def volume(self) -> int | None:
        return self._volume



class OWNAVCommand(OWNCommand):
    @classmethod
    def receive_video(cls, where: str | int) -> OWNAVCommand | None:
        camera_id: str | int = where
        where_str = str(where)
        if int(where) < 100:
            where_str = f"40{camera_id}"
        elif int(where) >= 4000 and int(where) < 5000:
            camera_id = where_str[2:]
        else:
            return None

        message = cls(f"*7*0*{where_str}##")
        message._human_readable_log = f"Opening video stream for camera {camera_id}."
        return message

    @classmethod
    def close_video(cls) -> OWNAVCommand:
        message = cls("*7*9**##")
        message._human_readable_log = "Closing video stream."
        return message



class OWNSoundCommand(OWNCommand):
    """WHO 16 commands for sound sources and amplifier zones."""

    @classmethod
    def status(cls, where: str | int) -> OWNSoundCommand:
        # WHO 16 status is dimension 5: gateways NACK the bare `*#16*WHERE##`.
        message = cls(f"*#16*{where}*5##")
        message._human_readable_log = f"Requesting sound system status of {where}."
        return message

    @classmethod
    def turn_on(cls, where: str | int) -> OWNSoundCommand:
        message = cls(f"*16*3*{where}##")
        message._human_readable_log = f"Turning on audio zone {where}."
        return message

    @classmethod
    def turn_off(cls, where: str | int) -> OWNSoundCommand:
        message = cls(f"*16*13*{where}##")
        message._human_readable_log = f"Turning off audio zone {where}."
        return message

    @classmethod
    def select_source(
        cls, where: str | int, source_id: int | str
    ) -> list[OWNSoundCommand]:
        """Build the frames routing an amplifier zone to a source.

        `where` is the two-digit amplifier address `EA`, where `E` (1–9) is
        the environment and `A` (1–9) the amplifier within it. Single-digit,
        environment 0, amplifier 0, and non-numeric addresses cannot be routed
        to a matrix source and raise ValueError. Only routing rejects
        amplifier 0: the other builders pass any `WHERE` from the published
        `01`-`99` range through.

        Two frames are returned:

        * `*16*3*10S##` activates source `S` on the bus;
        * `*16*3*1ES##` routes environment `E` of the matrix to source `S`.

        For example, amplifier `23` (environment 2) on source 2 yields
        `*16*3*102##` followed by `*16*3*122##`.
        """
        source = int(source_id)
        if not 1 <= source <= 9:
            raise ValueError("source_id must be between 1 and 9")
        zone = str(where).strip()
        if not zone:
            raise ValueError("where must identify an audio zone")
        if not re.fullmatch(r"[1-9]{2}", zone):
            raise ValueError(
                f"where must be a two-digit amplifier address with environment and amplifier 1-9, got '{where}'"
            )

        source_address = 100 + source
        activate = cls(f"*16*3*{source_address}##")
        activate._human_readable_log = f"Activating audio source {source}."

        route_address = f"1{zone[0]}{source}"
        route = cls(f"*16*3*{route_address}##")
        route._human_readable_log = (
            f"Routing audio zone {where} to source {source}."
        )
        return [activate, route]

    @classmethod
    def source_cycle(cls) -> OWNSoundCommand:
        message = cls("*16*23*100##")
        message._human_readable_log = "Cycling to the next audio source."
        return message

    @classmethod
    def volume_up(cls, where: str | int) -> OWNSoundCommand:
        message = cls(f"*16*1001*{where}##")
        message._human_readable_log = f"Increasing audio zone {where} volume."
        return message

    @classmethod
    def volume_down(cls, where: str | int) -> OWNSoundCommand:
        # 1101 = volume down by one step (1101..1115); 1000 is not a WHO 16 WHAT.
        message = cls(f"*16*1101*{where}##")
        message._human_readable_log = f"Decreasing audio zone {where} volume."
        return message

    @classmethod
    def set_volume(cls, where: str | int, volume: int | str) -> OWNSoundCommand:
        level = int(volume)
        if not 0 <= level <= 100:
            raise ValueError("volume must be between 0 and 100")
        message = cls(f"*#16*{where}*#1*{level}##")
        message._human_readable_log = (
            f"Setting audio zone {where} volume to {level}."
        )
        return message


register_event_parser(16, OWNSoundEvent)
register_command_parser(16, OWNSoundCommand)
