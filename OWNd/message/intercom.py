"""WHO 8: Video Door Entry and Advanced Intercom subsystem."""

from __future__ import annotations

import re
from typing import Any

from .base import OWNCommand, OWNEvent, register_command_parser, register_event_parser

# Call kinds
KIND_PE1 = 1
KIND_PE2 = 2
KIND_PE3 = 3
KIND_PE4 = 4
KIND_AUTOSWITCH = 5
KIND_INTERNAL_INTERCOM = 6
KIND_EXTERNAL_INTERCOM = 7
KIND_FLOOR = 13
KIND_PAGER = 14

# Multimedia types
MMTYPE_AUDIO = 2
MMTYPE_VIDEO = 3
MMTYPE_AUDIO_VIDEO = 4

# Special values
END_ALL_CALLS = 4
BROADCAST_WHERE = "4"

# PTZ opcodes and actions
PTZ_MOVE_UP = 59
PTZ_MOVE_DOWN = 60
PTZ_MOVE_LEFT = 61
PTZ_MOVE_RIGHT = 62

PTZ_ACTION_PRESS = 1
PTZ_ACTION_RELEASE = 2

# Message types
MESSAGE_TYPE_LOCK = "door_lock"
MESSAGE_TYPE_STAIRCASE_LIGHT = "staircase_light"
MESSAGE_TYPE_CAMERA = "camera"
MESSAGE_TYPE_PTZ = "ptz"
MESSAGE_TYPE_CALL = "intercom_call"
MESSAGE_TYPE_SESSION = "session"
MESSAGE_TYPE_AMPLIFIER_MUTE = "amplifier_mute"
MESSAGE_TYPE_TELELOOP = "teleloop"
MESSAGE_TYPE_VCT_INIT = "vct_init"

_PTZ_DIRECTIONS: dict[str, int] = {
    "up": PTZ_MOVE_UP,
    "down": PTZ_MOVE_DOWN,
    "left": PTZ_MOVE_LEFT,
    "right": PTZ_MOVE_RIGHT,
}
_PTZ_OPCODE_NAMES: dict[int, str] = {v: k for k, v in _PTZ_DIRECTIONS.items()}


class OWNIntercomEvent(OWNEvent):
    """State reported by a WHO 8 video door entry or intercom device."""

    def __init__(self, data: str) -> None:
        super().__init__(data)

        self._type: str | None = None
        self._is_lock_open: bool | None = None
        self._is_light_on: bool | None = None
        self._is_muted: bool | None = None
        self._call_kind: int | None = None
        self._multimedia_type: int | None = None
        self._caller: str | None = None
        self._callee: str | None = None
        self._is_pager: bool = False
        self._camera: str | None = None
        self._is_cycle: bool = False
        self._ptz_direction: str | None = None
        self._ptz_action: str | None = None
        self._session_action: str | None = None
        self._teleloop_mode: int | None = None
        self._vct_mode: int | None = None

        what = self._what
        params = self._what_param

        if what is None:
            return

        if what in (19, 20):
            self._type = MESSAGE_TYPE_LOCK
            self._is_lock_open = (what == 19)
            action = "activated (open)" if self._is_lock_open else "released (closed)"
            self._human_readable_log = f"Door lock actuator {self._where} is {action}."

        elif what in (21, 22):
            self._type = MESSAGE_TYPE_STAIRCASE_LIGHT
            self._is_light_on = (what == 21)
            action = "switched ON" if self._is_light_on else "switched OFF"
            self._human_readable_log = f"Staircase light {self._where} is {action}."

        elif what in (63, 64):
            self._type = MESSAGE_TYPE_AMPLIFIER_MUTE
            self._is_muted = (what == 63)
            action = "silenced (muted)" if self._is_muted else "restored (unmuted)"
            self._human_readable_log = f"Multimedia amplifier {self._where} is {action}."

        elif what == 4:
            self._type = MESSAGE_TYPE_CAMERA
            self._caller = params[0] if params else None
            self._camera = self._where
            self._human_readable_log = (
                f"Camera {self._camera} switched ON by caller {self._caller}."
                if self._caller
                else f"Camera {self._camera} switched ON."
            )

        elif what == 6:
            self._type = MESSAGE_TYPE_CAMERA
            self._is_cycle = True
            self._caller = params[0] if params else None
            self._camera = self._where
            self._human_readable_log = (
                f"External camera cycling triggered by caller {self._caller} (target {self._camera})."
                if self._caller
                else f"External camera cycling triggered (target {self._camera})."
            )

        elif what in (59, 60, 61, 62):
            self._type = MESSAGE_TYPE_PTZ
            self._camera = self._where
            self._ptz_direction = _PTZ_OPCODE_NAMES.get(what)
            action_code = int(params[0]) if params and params[0].isdigit() else PTZ_ACTION_PRESS
            self._ptz_action = "press" if action_code == PTZ_ACTION_PRESS else "release"
            self._human_readable_log = (
                f"Camera {self._camera} PTZ move {self._ptz_direction} ({self._ptz_action})."
            )

        elif what == 1:
            self._type = MESSAGE_TYPE_CALL
            if len(params) >= 3:
                self._call_kind = int(params[0])
                self._multimedia_type = int(params[1])
                self._caller = params[2]
            self._callee = self._where
            self._is_pager = (self._call_kind == KIND_PAGER or self._callee == BROADCAST_WHERE)
            desc = "Pager broadcast" if self._is_pager else "Intercom call"
            self._human_readable_log = (
                f"{desc} from {self._caller} to {self._callee} (kind {self._call_kind}, mm {self._multimedia_type})."
            )

        elif what == 2:
            self._type = MESSAGE_TYPE_SESSION
            self._session_action = "answer"
            if len(params) >= 2:
                self._call_kind = int(params[0])
                self._multimedia_type = int(params[1])
            self._human_readable_log = f"Call answered on {self._where}."

        elif what == 3:
            self._type = MESSAGE_TYPE_SESSION
            if len(params) >= 2 and params[1] == "3":
                self._session_action = "stop_video"
                self._human_readable_log = f"Video stopped on {self._where}."
            else:
                self._session_action = "end"
                self._human_readable_log = f"Call ended on {self._where}."
            if len(params) >= 2:
                self._call_kind = int(params[0])
                self._multimedia_type = int(params[1])

        elif what == 9:
            self._type = MESSAGE_TYPE_SESSION
            self._session_action = "caller_notification"
            self._caller = self._where
            if len(params) >= 2:
                self._call_kind = int(params[0])
                self._multimedia_type = int(params[1])
            self._human_readable_log = f"Caller notification: {self._caller}."

        elif what == 37:
            self._type = MESSAGE_TYPE_VCT_INIT
            if params:
                self._vct_mode = int(params[0])
            self._human_readable_log = f"VCT initialized on {self._where} (mode {self._vct_mode})."

        elif what == 40:
            self._type = MESSAGE_TYPE_SESSION
            self._session_action = "rearm"
            self._caller = self._where
            self._human_readable_log = f"Session rearmed for {self._caller}."

        elif what in (76, 77, 78, 79):
            self._type = MESSAGE_TYPE_TELELOOP
            if what == 76:
                self._session_action = "teleloop_start"
            elif what == 77:
                self._session_action = "teleloop_association"
                if params:
                    self._teleloop_mode = int(params[0])
            elif what == 78:
                self._session_action = "teleloop_timeout"
            else:
                self._session_action = "teleloop_active"
            self._human_readable_log = f"Teleloop event {self._session_action} on {self._where}."
        else:
            self._human_readable_log = f"Intercom event {what} on {self._where}."

    @property
    def message_type(self) -> str | None:
        return self._type

    @property
    def is_lock_open(self) -> bool | None:
        return self._is_lock_open

    @property
    def is_light_on(self) -> bool | None:
        return self._is_light_on

    @property
    def is_muted(self) -> bool | None:
        return self._is_muted

    @property
    def call_kind(self) -> int | None:
        return self._call_kind

    @property
    def multimedia_type(self) -> int | None:
        return self._multimedia_type

    @property
    def caller(self) -> str | None:
        return self._caller

    @property
    def callee(self) -> str | None:
        return self._callee

    @property
    def is_pager(self) -> bool:
        return self._is_pager

    @property
    def camera(self) -> str | None:
        return self._camera

    @property
    def is_cycle(self) -> bool:
        return self._is_cycle

    @property
    def ptz_direction(self) -> str | None:
        return self._ptz_direction

    @property
    def ptz_action(self) -> str | None:
        return self._ptz_action

    @property
    def session_action(self) -> str | None:
        return self._session_action

    @property
    def teleloop_mode(self) -> int | None:
        return self._teleloop_mode

    @property
    def vct_mode(self) -> int | None:
        return self._vct_mode


class OWNIntercomCommand(OWNCommand):
    """WHO 8 commands for video door entry and advanced intercom."""

    @classmethod
    def open_door_lock(cls, where: str | int) -> OWNIntercomCommand:
        """Activate/open door lock actuator."""
        msg = cls(f"*8*19*{where}##")
        msg._human_readable_log = f"Activating door lock actuator {where}."
        return msg

    @classmethod
    def release_door_lock(cls, where: str | int) -> OWNIntercomCommand:
        """Release/close door lock actuator."""
        msg = cls(f"*8*20*{where}##")
        msg._human_readable_log = f"Releasing door lock actuator {where}."
        return msg

    @classmethod
    def turn_on_staircase_light(cls, where: str | int) -> OWNIntercomCommand:
        """Turn ON staircase light actuator."""
        msg = cls(f"*8*21*{where}##")
        msg._human_readable_log = f"Turning ON staircase light {where}."
        return msg

    @classmethod
    def turn_off_staircase_light(cls, where: str | int) -> OWNIntercomCommand:
        """Turn OFF staircase light actuator."""
        msg = cls(f"*8*22*{where}##")
        msg._human_readable_log = f"Turning OFF staircase light {where}."
        return msg

    @classmethod
    def switch_camera(cls, caller: str | int, camera: str | int) -> OWNIntercomCommand:
        """Auto-switch / turn on a camera from a caller console."""
        msg = cls(f"*8*4#{caller}*{camera}##")
        msg._human_readable_log = f"Auto-switching camera {camera} from console {caller}."
        return msg

    @classmethod
    def cycle_camera(cls, caller: str | int, master_caller: str | int) -> OWNIntercomCommand:
        """Cycle to the next external unit / camera."""
        msg = cls(f"*8*6#{caller}*{master_caller}##")
        msg._human_readable_log = f"Cycling camera from console {caller} (master {master_caller})."
        return msg

    @classmethod
    def ptz_move(
        cls, camera: str | int, direction: str, action: str = "press"
    ) -> OWNIntercomCommand:
        """Send PTZ movement press or release to a camera."""
        direction_lower = direction.strip().lower()
        if direction_lower not in _PTZ_DIRECTIONS:
            raise ValueError(
                f"direction must be one of {list(_PTZ_DIRECTIONS.keys())}, got '{direction}'"
            )
        opcode = _PTZ_DIRECTIONS[direction_lower]
        action_lower = action.strip().lower()
        if action_lower not in ("press", "release"):
            raise ValueError("action must be 'press' or 'release'")
        action_code = PTZ_ACTION_PRESS if action_lower == "press" else PTZ_ACTION_RELEASE
        msg = cls(f"*8*{opcode}#{action_code}*{camera}##")
        msg._human_readable_log = f"PTZ move {direction_lower} ({action_lower}) on camera {camera}."
        return msg

    @classmethod
    def call_internal(
        cls, caller: str | int, callee: str | int, video: bool = False
    ) -> OWNIntercomCommand:
        """Initiate internal intercom call."""
        mm = MMTYPE_AUDIO_VIDEO if video else MMTYPE_AUDIO
        msg = cls(f"*8*1#{KIND_INTERNAL_INTERCOM}#{mm}#{caller}*{callee}##")
        msg._human_readable_log = (
            f"Initiating internal {'audio/video' if video else 'audio'} call from {caller} to {callee}."
        )
        return msg

    @classmethod
    def call_external(
        cls, caller: str | int, callee: str | int, video: bool = False
    ) -> OWNIntercomCommand:
        """Initiate external intercom call."""
        mm = MMTYPE_AUDIO_VIDEO if video else MMTYPE_AUDIO
        msg = cls(f"*8*1#{KIND_EXTERNAL_INTERCOM}#{mm}#{caller}*{callee}##")
        msg._human_readable_log = (
            f"Initiating external {'audio/video' if video else 'audio'} call from {caller} to {callee}."
        )
        return msg

    @classmethod
    def call_pager(
        cls, caller: str | int, broadcast_where: str | int = BROADCAST_WHERE
    ) -> OWNIntercomCommand:
        """Initiate pager broadcast call."""
        msg = cls(f"*8*1#{KIND_PAGER}#{MMTYPE_AUDIO}#{caller}*{broadcast_where}##")
        msg._human_readable_log = f"Initiating pager broadcast from {caller} to {broadcast_where}."
        return msg

    @classmethod
    def answer_call(
        cls, where: str | int, kind: int = KIND_INTERNAL_INTERCOM, mm_type: int = MMTYPE_AUDIO
    ) -> OWNIntercomCommand:
        """Answer an incoming call."""
        msg = cls(f"*8*2#{kind}#{mm_type}*{where}##")
        msg._human_readable_log = f"Answering call on {where}."
        return msg

    @classmethod
    def end_call(
        cls, where: str | int = END_ALL_CALLS, kind: int = KIND_INTERNAL_INTERCOM, mm_type: int = MMTYPE_AUDIO
    ) -> OWNIntercomCommand:
        """Terminate call session."""
        msg = cls(f"*8*3#{kind}#{mm_type}*{where}##")
        msg._human_readable_log = f"Ending call session on {where}."
        return msg

    @classmethod
    def stop_video(
        cls, where: str | int, kind: int = KIND_INTERNAL_INTERCOM
    ) -> OWNIntercomCommand:
        """Stop video stream for active call."""
        msg = cls(f"*8*3#{kind}#3*{where}##")
        msg._human_readable_log = f"Stopping video feed on {where}."
        return msg

    @classmethod
    def mute_amplifier(cls, where: str | int) -> OWNIntercomCommand:
        """Silence multimedia amplifier."""
        msg = cls(f"*8*63*{where}##")
        msg._human_readable_log = f"Silencing multimedia amplifier {where}."
        return msg

    @classmethod
    def unmute_amplifier(cls, where: str | int) -> OWNIntercomCommand:
        """Restore multimedia amplifier audio."""
        msg = cls(f"*8*64*{where}##")
        msg._human_readable_log = f"Restoring multimedia amplifier {where}."
        return msg

    @classmethod
    def status(cls, where: str | int) -> OWNIntercomCommand:
        """Request device/intercom status."""
        msg = cls(f"*#8*{where}##")
        msg._human_readable_log = f"Requesting intercom status for {where}."
        return msg

    @classmethod
    def lock_status(cls, where: str | int) -> OWNIntercomCommand:
        """Request door lock status."""
        msg = cls(f"*#8*{where}*19##")
        msg._human_readable_log = f"Requesting door lock status for {where}."
        return msg


register_event_parser(8, OWNIntercomEvent)
register_command_parser(8, OWNIntercomCommand)
