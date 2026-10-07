"""WHO 16 and WHO 22: Sound diffusion and audio/video door entry events and commands."""

from __future__ import annotations

import re
from typing import Any

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


# WHO 22: Advanced Sound Diffusion message types
MESSAGE_TYPE_AUDIO_STATE = "audio_state"
MESSAGE_TYPE_VOLUME = "volume"
MESSAGE_TYPE_SOURCE_SELECT = "source_select"
MESSAGE_TYPE_FOLLOW_ME = "follow_me"
MESSAGE_TYPE_TRACK_STATION = "track_station"
MESSAGE_TYPE_TUNER = "tuner"
MESSAGE_TYPE_TONE = "tone"
MESSAGE_TYPE_BALANCE = "balance"
MESSAGE_TYPE_PRESET = "preset"
MESSAGE_TYPE_LOUDNESS = "loudness"
MESSAGE_TYPE_DEVICE_STATE = "device_state"
MESSAGE_TYPE_RDS = "rds"
MESSAGE_TYPE_ACTIVE_AREAS = "active_areas"


def _format_who22_where(where: str | None, where_param: list[str]) -> str:
    """Format structured address for WHO 22 (e.g. 2#1, 3#1#1, 4#1, 5#3#1#1, 6)."""
    if where is None:
        return ""
    if where_param:
        return f"{where}#{'#'.join(where_param)}"
    return where


class _OWNMultiroomMixin:
    """Shared state parsing and properties for WHO 22 multi-room audio messages."""

    _where: str | None
    _where_param: list[str]
    _what: int | None
    _what_param: list[str]
    _dimension: int | None
    _dimension_value: list[str]

    def _init_multiroom(self) -> None:
        self._type: str | None = None
        self._target_address = _format_who22_where(self._where, self._where_param)
        self._target_type: str = "general"
        self._source_id: int | None = None
        self._area: int | None = None
        self._point: int | None = None
        self._is_on: bool | None = None
        self._is_off: bool | None = None
        self._volume: int | None = None
        self._volume_step: int | None = None
        self._device_state: int | None = None
        self._multimedia_type: int | None = None
        self._balance: int | None = None
        self._high_tones: int | None = None
        self._mid_tones: int | None = None
        self._low_tones: int | None = None
        self._loudness: bool | None = None
        self._preset: int | None = None
        self._station_or_track: int | None = None
        self._is_follow_me: bool = False
        self._is_source_select: bool = False
        self._rds_reporting: bool | None = None
        self._frequency_step: int | None = None
        self._active_areas: int | None = None

        addr = self._target_address
        if addr.startswith("5#"):
            sub = addr[2:]
            if sub.startswith("2#"):
                self._target_type = "source"
            elif sub.startswith("3#"):
                self._target_type = "speaker"
            elif sub.startswith("4#"):
                self._target_type = "area"
            else:
                self._target_type = "general"
        elif addr.startswith("2#"):
            self._target_type = "source"
        elif addr.startswith("3#"):
            self._target_type = "speaker"
        elif addr.startswith("4#"):
            self._target_type = "area"
        elif addr == "6":
            self._target_type = "all_sources"
        else:
            self._target_type = "general"

        m_src = re.match(r"^(?:5#)?2#(\d+)$", addr)
        if m_src:
            self._source_id = int(m_src.group(1))

        m_spk = re.match(r"^(?:5#)?3#(\d+)#(\d+)$", addr)
        if m_spk:
            self._area = int(m_spk.group(1))
            self._point = int(m_spk.group(2))
        else:
            m_area = re.match(r"^(?:5#)?4#(\d+)$", addr)
            if m_area:
                self._area = int(m_area.group(1))

        what = self._what
        params = self._what_param
        dim = self._dimension
        vals = self._dimension_value

        if what is not None:
            if what == 0:
                self._type = MESSAGE_TYPE_AUDIO_STATE
                self._is_on = False
                self._is_off = True
                if len(params) >= 2:
                    self._multimedia_type = int(params[0])
                    self._area = int(params[1])
                self._human_readable_log = f"Audio target {addr} is switched OFF."
            elif what in (1, 2):
                self._type = MESSAGE_TYPE_AUDIO_STATE
                self._is_on = True
                self._is_off = False
                if len(params) >= 2:
                    self._multimedia_type = int(params[0])
                    self._area = int(params[1])
                self._human_readable_log = f"Audio target {addr} is switched ON."
            elif what == 3:
                self._type = MESSAGE_TYPE_VOLUME
                self._volume_step = int(params[0]) if params else 1
                self._human_readable_log = (
                    f"Audio target {addr} volume increased by {self._volume_step} step(s)."
                )
            elif what == 4:
                self._type = MESSAGE_TYPE_VOLUME
                self._volume_step = int(params[0]) if params else 1
                self._human_readable_log = (
                    f"Audio target {addr} volume decreased by {self._volume_step} step(s)."
                )
            elif what == 5:
                self._type = MESSAGE_TYPE_TUNER
                self._frequency_step = int(params[0]) if params else None
                step_str = (
                    f" by {self._frequency_step} step(s)" if self._frequency_step else ""
                )
                self._human_readable_log = f"Audio target {addr} tuner search UP{step_str}."
            elif what == 6:
                self._type = MESSAGE_TYPE_TUNER
                self._frequency_step = int(params[0]) if params else None
                step_str = (
                    f" by {self._frequency_step} step(s)" if self._frequency_step else ""
                )
                self._human_readable_log = f"Audio target {addr} tuner search DOWN{step_str}."
            elif what == 9:
                self._type = MESSAGE_TYPE_TRACK_STATION
                self._human_readable_log = f"Audio target {addr} tuned to next station."
            elif what == 10:
                self._type = MESSAGE_TYPE_TRACK_STATION
                self._human_readable_log = f"Audio target {addr} tuned to previous station."
            elif what == 11:
                self._type = MESSAGE_TYPE_TRACK_STATION
                self._human_readable_log = f"Audio target {addr} next track."
            elif what == 12:
                self._type = MESSAGE_TYPE_TRACK_STATION
                self._human_readable_log = f"Audio target {addr} previous track."
            elif what == 31:
                self._type = MESSAGE_TYPE_RDS
                self._rds_reporting = True
                self._human_readable_log = f"Audio target {addr} RDS reporting started."
            elif what == 32:
                self._type = MESSAGE_TYPE_RDS
                self._rds_reporting = False
                self._human_readable_log = f"Audio target {addr} RDS reporting stopped."
            elif what == 33:
                self._type = MESSAGE_TYPE_TRACK_STATION
                if params:
                    self._station_or_track = int(params[0])
                self._human_readable_log = (
                    f"Audio target {addr} tuned frequency stored as station {self._station_or_track}."
                )
            elif what == 34:
                self._type = MESSAGE_TYPE_FOLLOW_ME
                self._is_follow_me = True
                self._is_on = True
                self._is_off = False
                if len(params) >= 2:
                    self._multimedia_type = int(params[0])
                    self._area = int(params[1])
                self._human_readable_log = f"Audio target {addr} turned ON using Follow Me."
            elif what == 35:
                self._type = MESSAGE_TYPE_SOURCE_SELECT
                self._is_source_select = True
                self._is_on = True
                self._is_off = False
                if len(params) >= 3:
                    self._multimedia_type = int(params[0])
                    self._area = int(params[1])
                    self._source_id = int(params[2])
                self._human_readable_log = (
                    f"Audio target {addr} turned ON routed to source {self._source_id}."
                )
            elif what == 36:
                self._type = MESSAGE_TYPE_TONE
                self._human_readable_log = f"Audio target {addr} low tones increased."
            elif what == 37:
                self._type = MESSAGE_TYPE_TONE
                self._human_readable_log = f"Audio target {addr} low tones decreased."
            elif what == 38:
                self._type = MESSAGE_TYPE_TONE
                self._human_readable_log = f"Audio target {addr} mid tones increased."
            elif what == 39:
                self._type = MESSAGE_TYPE_TONE
                self._human_readable_log = f"Audio target {addr} mid tones decreased."
            elif what == 40:
                self._type = MESSAGE_TYPE_TONE
                self._human_readable_log = f"Audio target {addr} high tones increased."
            elif what == 41:
                self._type = MESSAGE_TYPE_TONE
                self._human_readable_log = f"Audio target {addr} high tones decreased."
            elif what == 42:
                self._type = MESSAGE_TYPE_BALANCE
                self._human_readable_log = f"Audio target {addr} balance shifted right."
            elif what == 43:
                self._type = MESSAGE_TYPE_BALANCE
                self._human_readable_log = f"Audio target {addr} balance shifted left."
            elif what == 55:
                self._type = MESSAGE_TYPE_PRESET
                self._human_readable_log = f"Audio target {addr} next preset."
            elif what == 56:
                self._type = MESSAGE_TYPE_PRESET
                self._human_readable_log = f"Audio target {addr} previous preset."
            else:
                self._type = MESSAGE_TYPE_AUDIO_STATE
                self._human_readable_log = f"Audio target {addr} command {what}."

        elif dim is not None:
            if dim == 1:
                self._type = MESSAGE_TYPE_VOLUME
                if vals:
                    self._volume = int(vals[0])
                self._human_readable_log = f"Audio target {addr} volume: {self._volume}."
            elif dim == 2:
                self._type = MESSAGE_TYPE_TONE
                if vals:
                    self._high_tones = int(vals[0])
                self._human_readable_log = f"Audio target {addr} high tones: {self._high_tones}."
            elif dim == 3:
                self._type = MESSAGE_TYPE_TONE
                if vals:
                    self._mid_tones = int(vals[0])
                self._human_readable_log = f"Audio target {addr} mid tones: {self._mid_tones}."
            elif dim == 4:
                self._type = MESSAGE_TYPE_TONE
                if vals:
                    self._low_tones = int(vals[0])
                self._human_readable_log = f"Audio target {addr} low tones: {self._low_tones}."
            elif dim in (5, 11):
                self._type = MESSAGE_TYPE_TUNER
                self._human_readable_log = f"Audio target {addr} tuner frequency."
            elif dim == 6:
                self._type = MESSAGE_TYPE_TRACK_STATION
                if vals:
                    self._station_or_track = int(vals[0])
                self._human_readable_log = (
                    f"Audio target {addr} track/station: {self._station_or_track}."
                )
            elif dim == 12:
                self._type = MESSAGE_TYPE_DEVICE_STATE
                if vals:
                    self._device_state = int(vals[0])
                    self._is_on = self._device_state == 1
                    self._is_off = self._device_state == 0
                    if len(vals) > 1:
                        self._multimedia_type = int(vals[1])
                self._human_readable_log = (
                    f"Audio target {addr} device state: {self._device_state}."
                )
            elif dim == 13:
                self._type = MESSAGE_TYPE_ACTIVE_AREAS
                if vals:
                    self._active_areas = int(vals[0])
                self._human_readable_log = (
                    f"Audio target {addr} active areas: {self._active_areas}."
                )
            elif dim == 17:
                self._type = MESSAGE_TYPE_BALANCE
                if vals:
                    self._balance = int(vals[0])
                self._human_readable_log = f"Audio target {addr} balance: {self._balance}."
            elif dim == 19:
                self._type = MESSAGE_TYPE_PRESET
                if vals:
                    self._preset = int(vals[0])
                self._human_readable_log = f"Audio target {addr} preset: {self._preset}."
            elif dim == 20:
                self._type = MESSAGE_TYPE_LOUDNESS
                if vals:
                    self._loudness = bool(int(vals[0]))
                self._human_readable_log = (
                    f"Audio target {addr} loudness: {'ON' if self._loudness else 'OFF'}."
                )
            else:
                self._human_readable_log = f"Audio target {addr} dimension {dim}."

    @property
    def target_address(self) -> str:
        return self._target_address

    @property
    def target_type(self) -> str:
        return self._target_type

    @property
    def source_id(self) -> int | None:
        return self._source_id

    @property
    def area(self) -> int | None:
        return self._area

    @property
    def point(self) -> int | None:
        return self._point

    @property
    def is_on(self) -> bool | None:
        return self._is_on

    @property
    def is_off(self) -> bool | None:
        return self._is_off

    @property
    def volume(self) -> int | None:
        return self._volume

    @property
    def volume_step(self) -> int | None:
        return self._volume_step

    @property
    def frequency_step(self) -> int | None:
        return self._frequency_step

    @property
    def device_state(self) -> int | None:
        return self._device_state

    @property
    def multimedia_type(self) -> int | None:
        return self._multimedia_type

    @property
    def balance(self) -> int | None:
        return self._balance

    @property
    def high_tones(self) -> int | None:
        return self._high_tones

    @property
    def mid_tones(self) -> int | None:
        return self._mid_tones

    @property
    def low_tones(self) -> int | None:
        return self._low_tones

    @property
    def loudness(self) -> bool | None:
        return self._loudness

    @property
    def preset(self) -> int | None:
        return self._preset

    @property
    def station_or_track(self) -> int | None:
        return self._station_or_track

    @property
    def is_follow_me(self) -> bool:
        return self._is_follow_me

    @property
    def is_source_select(self) -> bool:
        return self._is_source_select

    @property
    def rds_reporting(self) -> bool | None:
        return self._rds_reporting

    @property
    def active_areas(self) -> int | None:
        return self._active_areas

    @property
    def message_type(self) -> str | None:
        return self._type


class OWNMultiroomEvent(_OWNMultiroomMixin, OWNEvent):
    """WHO 22: Advanced sound diffusion (diffusione sonora avanzata) event."""

    def __init__(self, data: str) -> None:
        super().__init__(data)
        self._init_multiroom()


class OWNMultiroomCommand(_OWNMultiroomMixin, OWNCommand):
    """WHO 22: Advanced sound diffusion (diffusione sonora avanzata) commands."""

    def __init__(self, data: str) -> None:
        super().__init__(data)
        self._init_multiroom()

    @classmethod
    def turn_on(
        cls, where: str | int, multimedia_type: int = 4, area: int | None = None
    ) -> OWNMultiroomCommand:
        """Turn audio target ON."""
        cmd_str = (
            f"*22*1#{multimedia_type}#{area}*{where}##"
            if area is not None
            else f"*22*1*{where}##"
        )
        msg = cls(cmd_str)
        msg._human_readable_log = f"Turning ON audio target {where}."
        return msg

    @classmethod
    def turn_off(
        cls, where: str | int, multimedia_type: int = 4, area: int | None = None
    ) -> OWNMultiroomCommand:
        """Turn audio target OFF."""
        cmd_str = (
            f"*22*0#{multimedia_type}#{area}*{where}##"
            if area is not None
            else f"*22*0*{where}##"
        )
        msg = cls(cmd_str)
        msg._human_readable_log = f"Turning OFF audio target {where}."
        return msg

    @classmethod
    def volume_up(cls, where: str | int, step: int = 1) -> OWNMultiroomCommand:
        """Increase volume by step(s)."""
        msg = cls(f"*22*3#{step}*{where}##")
        msg._human_readable_log = f"Increasing volume on {where} by {step} step(s)."
        return msg

    @classmethod
    def volume_down(cls, where: str | int, step: int = 1) -> OWNMultiroomCommand:
        """Decrease volume by step(s)."""
        msg = cls(f"*22*4#{step}*{where}##")
        msg._human_readable_log = f"Decreasing volume on {where} by {step} step(s)."
        return msg

    @classmethod
    def set_volume(cls, where: str | int, level: int) -> OWNMultiroomCommand:
        """Set absolute volume (0..31)."""
        lvl = int(level)
        if not 0 <= lvl <= 31:
            raise ValueError(f"Volume level must be between 0 and 31, got {level}")
        msg = cls(f"*#22*{where}*#1*{lvl}##")
        msg._human_readable_log = f"Setting volume on {where} to {lvl}."
        return msg

    @classmethod
    def request_volume(cls, where: str | int) -> OWNMultiroomCommand:
        """Request current volume."""
        msg = cls(f"*#22*{where}*1##")
        msg._human_readable_log = f"Requesting volume of {where}."
        return msg

    @classmethod
    def select_source(
        cls,
        where: str | int,
        source_id: int,
        area: int = 1,
        multimedia_type: int = 4,
    ) -> OWNMultiroomCommand:
        """Route audio target in area to specified sound source."""
        src = int(source_id)
        msg = cls(f"*22*35#{multimedia_type}#{area}#{src}*{where}##")
        msg._human_readable_log = (
            f"Routing audio {where} in area {area} to source {src}."
        )
        return msg

    @classmethod
    def follow_me(
        cls,
        where: str | int,
        area: int = 1,
        multimedia_type: int = 4,
    ) -> OWNMultiroomCommand:
        """Turn audio target ON using Follow Me."""
        msg = cls(f"*22*34#{multimedia_type}#{area}*{where}##")
        msg._human_readable_log = (
            f"Activating Follow Me on {where} in area {area}."
        )
        return msg

    @classmethod
    def next_track(cls, where: str | int) -> OWNMultiroomCommand:
        """Skip to next track."""
        msg = cls(f"*22*11*{where}##")
        msg._human_readable_log = f"Skipping to next track on {where}."
        return msg

    @classmethod
    def prev_track(cls, where: str | int) -> OWNMultiroomCommand:
        """Skip to previous track."""
        msg = cls(f"*22*12*{where}##")
        msg._human_readable_log = f"Skipping to previous track on {where}."
        return msg

    @classmethod
    def next_station(cls, where: str | int) -> OWNMultiroomCommand:
        """Tune to next radio station."""
        msg = cls(f"*22*9*{where}##")
        msg._human_readable_log = f"Tuning to next station on {where}."
        return msg

    @classmethod
    def prev_station(cls, where: str | int) -> OWNMultiroomCommand:
        """Tune to previous radio station."""
        msg = cls(f"*22*10*{where}##")
        msg._human_readable_log = f"Tuning to previous station on {where}."
        return msg

    @classmethod
    def store_station(cls, where: str | int, station: int) -> OWNMultiroomCommand:
        """Store tuned frequency as station memory."""
        stn = int(station)
        msg = cls(f"*22*33#{stn}*{where}##")
        msg._human_readable_log = f"Storing tuned frequency as station {stn} on {where}."
        return msg

    @classmethod
    def search_frequency_up(
        cls, where: str | int, step: int | None = None
    ) -> OWNMultiroomCommand:
        """Search radio frequency UP."""
        cmd_str = f"*22*5#{step}*{where}##" if step is not None else f"*22*5*{where}##"
        msg = cls(cmd_str)
        msg._human_readable_log = f"Searching frequency UP on {where}."
        return msg

    @classmethod
    def search_frequency_down(
        cls, where: str | int, step: int | None = None
    ) -> OWNMultiroomCommand:
        """Search radio frequency DOWN."""
        cmd_str = f"*22*6#{step}*{where}##" if step is not None else f"*22*6*{where}##"
        msg = cls(cmd_str)
        msg._human_readable_log = f"Searching frequency DOWN on {where}."
        return msg

    @classmethod
    def request_frequency(cls, where: str | int) -> OWNMultiroomCommand:
        """Request tuner frequency."""
        msg = cls(f"*#22*{where}*5##")
        msg._human_readable_log = f"Requesting frequency of {where}."
        return msg

    @classmethod
    def request_track_or_station(cls, where: str | int) -> OWNMultiroomCommand:
        """Request track or station number."""
        msg = cls(f"*#22*{where}*6##")
        msg._human_readable_log = f"Requesting track or station of {where}."
        return msg

    @classmethod
    def set_track_or_station(cls, where: str | int, track: int) -> OWNMultiroomCommand:
        """Set track or station number."""
        trk = int(track)
        msg = cls(f"*#22*{where}*#6*{trk}##")
        msg._human_readable_log = f"Setting track or station on {where} to {trk}."
        return msg

    @classmethod
    def request_device_state(cls, where: str | int) -> OWNMultiroomCommand:
        """Request device state."""
        msg = cls(f"*#22*{where}*12##")
        msg._human_readable_log = f"Requesting device state of {where}."
        return msg

    @classmethod
    def request_active_areas(cls, where: str | int) -> OWNMultiroomCommand:
        """Request active sound diffusion areas."""
        msg = cls(f"*#22*{where}*13##")
        msg._human_readable_log = f"Requesting active areas of {where}."
        return msg

    @classmethod
    def set_balance(cls, where: str | int, balance: int) -> OWNMultiroomCommand:
        """Set audio balance (1..63)."""
        bal = int(balance)
        if not 1 <= bal <= 63:
            raise ValueError(f"Balance must be between 1 and 63, got {balance}")
        msg = cls(f"*#22*{where}*#17*{bal}##")
        msg._human_readable_log = f"Setting balance on {where} to {bal}."
        return msg

    @classmethod
    def request_balance(cls, where: str | int) -> OWNMultiroomCommand:
        """Request audio balance."""
        msg = cls(f"*#22*{where}*17##")
        msg._human_readable_log = f"Requesting balance of {where}."
        return msg

    @classmethod
    def move_balance_right(cls, where: str | int, step: int = 1) -> OWNMultiroomCommand:
        """Shift balance right by step."""
        msg = cls(f"*22*42#{step}*{where}##")
        msg._human_readable_log = f"Shifting balance right on {where}."
        return msg

    @classmethod
    def move_balance_left(cls, where: str | int, step: int = 1) -> OWNMultiroomCommand:
        """Shift balance left by step."""
        msg = cls(f"*22*43#{step}*{where}##")
        msg._human_readable_log = f"Shifting balance left on {where}."
        return msg

    @classmethod
    def set_preset(cls, where: str | int, preset: int) -> OWNMultiroomCommand:
        """Set equalizer preset."""
        p = int(preset)
        msg = cls(f"*#22*{where}*#19*{p}##")
        msg._human_readable_log = f"Setting preset on {where} to {p}."
        return msg

    @classmethod
    def request_preset(cls, where: str | int) -> OWNMultiroomCommand:
        """Request equalizer preset."""
        msg = cls(f"*#22*{where}*19##")
        msg._human_readable_log = f"Requesting preset of {where}."
        return msg

    @classmethod
    def next_preset(cls, where: str | int) -> OWNMultiroomCommand:
        """Select next equalizer preset."""
        msg = cls(f"*22*55*{where}##")
        msg._human_readable_log = f"Selecting next preset on {where}."
        return msg

    @classmethod
    def prev_preset(cls, where: str | int) -> OWNMultiroomCommand:
        """Select previous equalizer preset."""
        msg = cls(f"*22*56*{where}##")
        msg._human_readable_log = f"Selecting previous preset on {where}."
        return msg

    @classmethod
    def set_loudness(cls, where: str | int, enabled: bool | int) -> OWNMultiroomCommand:
        """Set loudness ON or OFF."""
        val = 1 if enabled else 0
        msg = cls(f"*#22*{where}*#20*{val}##")
        msg._human_readable_log = (
            f"Setting loudness on {where} to {'ON' if val else 'OFF'}."
        )
        return msg

    @classmethod
    def request_loudness(cls, where: str | int) -> OWNMultiroomCommand:
        """Request loudness status."""
        msg = cls(f"*#22*{where}*20##")
        msg._human_readable_log = f"Requesting loudness of {where}."
        return msg

    @classmethod
    def set_treble(cls, where: str | int, value: int) -> OWNMultiroomCommand:
        """Set high tones (1..63)."""
        val = int(value)
        if not 1 <= val <= 63:
            raise ValueError(f"High tones value must be between 1 and 63, got {value}")
        msg = cls(f"*#22*{where}*#2*{val}##")
        msg._human_readable_log = f"Setting high tones on {where} to {val}."
        return msg

    @classmethod
    def request_treble(cls, where: str | int) -> OWNMultiroomCommand:
        """Request high tones."""
        msg = cls(f"*#22*{where}*2##")
        msg._human_readable_log = f"Requesting high tones of {where}."
        return msg

    @classmethod
    def set_mid_tones(cls, where: str | int, value: int) -> OWNMultiroomCommand:
        """Set medium tones (1..63)."""
        val = int(value)
        if not 1 <= val <= 63:
            raise ValueError(f"Medium tones value must be between 1 and 63, got {value}")
        msg = cls(f"*#22*{where}*#3*{val}##")
        msg._human_readable_log = f"Setting medium tones on {where} to {val}."
        return msg

    @classmethod
    def request_mid_tones(cls, where: str | int) -> OWNMultiroomCommand:
        """Request medium tones."""
        msg = cls(f"*#22*{where}*3##")
        msg._human_readable_log = f"Requesting medium tones of {where}."
        return msg

    @classmethod
    def set_bass(cls, where: str | int, value: int) -> OWNMultiroomCommand:
        """Set low tones (1..63)."""
        val = int(value)
        if not 1 <= val <= 63:
            raise ValueError(f"Low tones value must be between 1 and 63, got {value}")
        msg = cls(f"*#22*{where}*#4*{val}##")
        msg._human_readable_log = f"Setting low tones on {where} to {val}."
        return msg

    @classmethod
    def request_bass(cls, where: str | int) -> OWNMultiroomCommand:
        """Request low tones."""
        msg = cls(f"*#22*{where}*4##")
        msg._human_readable_log = f"Requesting low tones of {where}."
        return msg

    @classmethod
    def tone_up(
        cls, where: str | int, band: str = "bass", step: int = 1
    ) -> OWNMultiroomCommand:
        """Increment tone band (bass, mid, treble)."""
        b = band.strip().lower()
        opcode_map = {
            "bass": 36,
            "low": 36,
            "mid": 38,
            "medium": 38,
            "treble": 40,
            "high": 40,
        }
        if b not in opcode_map:
            raise ValueError(
                f"band must be one of {list(opcode_map.keys())}, got '{band}'"
            )
        opcode = opcode_map[b]
        msg = cls(f"*22*{opcode}#{step}*{where}##")
        msg._human_readable_log = f"Increasing {b} tones on {where} by {step} step(s)."
        return msg

    @classmethod
    def tone_down(
        cls, where: str | int, band: str = "bass", step: int = 1
    ) -> OWNMultiroomCommand:
        """Decrement tone band (bass, mid, treble)."""
        b = band.strip().lower()
        opcode_map = {
            "bass": 37,
            "low": 37,
            "mid": 39,
            "medium": 39,
            "treble": 41,
            "high": 41,
        }
        if b not in opcode_map:
            raise ValueError(
                f"band must be one of {list(opcode_map.keys())}, got '{band}'"
            )
        opcode = opcode_map[b]
        msg = cls(f"*22*{opcode}#{step}*{where}##")
        msg._human_readable_log = f"Decreasing {b} tones on {where} by {step} step(s)."
        return msg

    @classmethod
    def start_rds(cls, where: str | int) -> OWNMultiroomCommand:
        """Start RDS reporting."""
        msg = cls(f"*22*31*{where}##")
        msg._human_readable_log = f"Starting RDS reporting on {where}."
        return msg

    @classmethod
    def stop_rds(cls, where: str | int) -> OWNMultiroomCommand:
        """Stop RDS reporting."""
        msg = cls(f"*22*32*{where}##")
        msg._human_readable_log = f"Stopping RDS reporting on {where}."
        return msg

    @classmethod
    def status(cls, where: str | int) -> OWNMultiroomCommand:
        """Request multiroom status."""
        msg = cls(f"*#22*{where}##")
        msg._human_readable_log = f"Requesting multiroom status of {where}."
        return msg


register_event_parser(22, OWNMultiroomEvent)
register_command_parser(22, OWNMultiroomCommand)
