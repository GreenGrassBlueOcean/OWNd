"""Tests for WHO 8 Video Door Entry and Advanced Intercom subsystem."""

from __future__ import annotations

import pytest

from OWNd.message import (
    BROADCAST_WHERE,
    END_ALL_CALLS,
    KIND_AUTOSWITCH,
    KIND_EXTERNAL_INTERCOM,
    KIND_FLOOR,
    KIND_INTERNAL_INTERCOM,
    KIND_PAGER,
    KIND_PE1,
    MESSAGE_TYPE_AMPLIFIER_MUTE,
    MESSAGE_TYPE_CALL,
    MESSAGE_TYPE_CAMERA,
    MESSAGE_TYPE_LOCK,
    MESSAGE_TYPE_PTZ,
    MESSAGE_TYPE_SESSION,
    MESSAGE_TYPE_STAIRCASE_LIGHT,
    MESSAGE_TYPE_TELELOOP,
    MESSAGE_TYPE_VCT_INIT,
    MMTYPE_AUDIO,
    MMTYPE_AUDIO_VIDEO,
    MMTYPE_VIDEO,
    PTZ_ACTION_PRESS,
    PTZ_ACTION_RELEASE,
    PTZ_MOVE_DOWN,
    PTZ_MOVE_LEFT,
    PTZ_MOVE_RIGHT,
    PTZ_MOVE_UP,
    OWNCommand,
    OWNEvent,
    OWNIntercomCommand,
    OWNIntercomEvent,
    OWNMessage,
)


def test_lock_events_and_commands() -> None:
    ev_act = OWNMessage.parse("*8*19*1##")
    assert isinstance(ev_act, OWNIntercomEvent)
    assert ev_act.message_type == MESSAGE_TYPE_LOCK
    assert ev_act.is_lock_open is True
    assert ev_act.where == "1"
    assert "activated (open)" in ev_act.human_readable_log

    ev_rel = OWNEvent.parse("*8*20*11##")
    assert isinstance(ev_rel, OWNIntercomEvent)
    assert ev_rel.is_lock_open is False
    assert ev_rel.where == "11"
    assert "released (closed)" in ev_rel.human_readable_log

    cmd_act = OWNIntercomCommand.open_door_lock("1")
    assert str(cmd_act) == "*8*19*1##"
    cmd_rel = OWNIntercomCommand.release_door_lock("11")
    assert str(cmd_rel) == "*8*20*11##"


def test_staircase_light_events_and_commands() -> None:
    ev_on = OWNEvent.parse("*8*21*11##")
    assert isinstance(ev_on, OWNIntercomEvent)
    assert ev_on.message_type == MESSAGE_TYPE_STAIRCASE_LIGHT
    assert ev_on.is_light_on is True
    assert "switched ON" in ev_on.human_readable_log

    ev_off = OWNEvent.parse("*8*22*0##")
    assert isinstance(ev_off, OWNIntercomEvent)
    assert ev_off.is_light_on is False
    assert "switched OFF" in ev_off.human_readable_log

    cmd_on = OWNIntercomCommand.turn_on_staircase_light("11")
    assert str(cmd_on) == "*8*21*11##"
    cmd_off = OWNIntercomCommand.turn_off_staircase_light("0")
    assert str(cmd_off) == "*8*22*0##"


def test_camera_auto_switch_and_cycling() -> None:
    ev_cam = OWNEvent.parse("*8*4#11*20##")
    assert isinstance(ev_cam, OWNIntercomEvent)
    assert ev_cam.message_type == MESSAGE_TYPE_CAMERA
    assert ev_cam.caller == "11"
    assert ev_cam.camera == "20"
    assert "switched ON by caller" in ev_cam.human_readable_log

    ev_cycle = OWNEvent.parse("*8*6#11*20##")
    assert isinstance(ev_cycle, OWNIntercomEvent)
    assert ev_cycle.is_cycle is True
    assert ev_cycle.caller == "11"
    assert ev_cycle.camera == "20"
    assert "External camera cycling" in ev_cycle.human_readable_log

    cmd_switch = OWNIntercomCommand.switch_camera(11, 20)
    assert str(cmd_switch) == "*8*4#11*20##"

    cmd_cycle = OWNIntercomCommand.cycle_camera("11", "20")
    assert str(cmd_cycle) == "*8*6#11*20##"


def test_ptz_movements() -> None:
    ev_ptz_up = OWNEvent.parse("*8*59#1*20##")
    assert isinstance(ev_ptz_up, OWNIntercomEvent)
    assert ev_ptz_up.message_type == MESSAGE_TYPE_PTZ
    assert ev_ptz_up.ptz_direction == "up"
    assert ev_ptz_up.ptz_action == "press"
    assert "PTZ move up (press)" in ev_ptz_up.human_readable_log

    ev_ptz_down = OWNEvent.parse("*8*60#2*20##")
    assert isinstance(ev_ptz_down, OWNIntercomEvent)
    assert ev_ptz_down.ptz_direction == "down"
    assert ev_ptz_down.ptz_action == "release"

    ev_ptz_left = OWNEvent.parse("*8*61#1*20##")
    assert isinstance(ev_ptz_left, OWNIntercomEvent)
    assert ev_ptz_left.ptz_direction == "left"
    assert ev_ptz_left.ptz_action == "press"

    ev_ptz_right = OWNEvent.parse("*8*62#2*20##")
    assert isinstance(ev_ptz_right, OWNIntercomEvent)
    assert ev_ptz_right.ptz_direction == "right"
    assert ev_ptz_right.ptz_action == "release"

    cmd_up = OWNIntercomCommand.ptz_move(20, "up", "press")
    assert str(cmd_up) == "*8*59#1*20##"
    cmd_down = OWNIntercomCommand.ptz_move(20, "down", "release")
    assert str(cmd_down) == "*8*60#2*20##"
    cmd_left = OWNIntercomCommand.ptz_move(20, "left", "press")
    assert str(cmd_left) == "*8*61#1*20##"
    cmd_right = OWNIntercomCommand.ptz_move(20, "right", "release")
    assert str(cmd_right) == "*8*62#2*20##"

    with pytest.raises(ValueError, match="direction must be one of"):
        OWNIntercomCommand.ptz_move(20, "diagonal", "press")
    with pytest.raises(ValueError, match="action must be"):
        OWNIntercomCommand.ptz_move(20, "up", "hold")


def test_intercom_calling_and_session() -> None:
    # Internal audio call: *8*1#6#2#11*16## (caller 11, callee 16, kind 6, mm 2)
    ev_call = OWNEvent.parse("*8*1#6#2#11*16##")
    assert isinstance(ev_call, OWNIntercomEvent)
    assert ev_call.message_type == MESSAGE_TYPE_CALL
    assert ev_call.call_kind == KIND_INTERNAL_INTERCOM
    assert ev_call.multimedia_type == MMTYPE_AUDIO
    assert ev_call.caller == "11"
    assert ev_call.callee == "16"
    assert "Intercom call from 11 to 16" in ev_call.human_readable_log

    # Answer call: *8*2#6#2*11##
    ev_ans = OWNEvent.parse("*8*2#6#2*11##")
    assert isinstance(ev_ans, OWNIntercomEvent)
    assert ev_ans.message_type == MESSAGE_TYPE_SESSION
    assert ev_ans.session_action == "answer"
    assert ev_ans.call_kind == KIND_INTERNAL_INTERCOM
    assert ev_ans.multimedia_type == MMTYPE_AUDIO
    assert "Call answered" in ev_ans.human_readable_log

    # End call: *8*3#6#2*411##
    ev_end = OWNEvent.parse("*8*3#6#2*411##")
    assert isinstance(ev_end, OWNIntercomEvent)
    assert ev_end.session_action == "end"
    assert "Call ended on" in ev_end.human_readable_log

    # Stop video: *8*3#1#3*11##
    ev_stop_vid = OWNEvent.parse("*8*3#1#3*11##")
    assert isinstance(ev_stop_vid, OWNIntercomEvent)
    assert ev_stop_vid.session_action == "stop_video"
    assert "Video stopped" in ev_stop_vid.human_readable_log

    # Builders
    cmd_int_audio = OWNIntercomCommand.call_internal("11", "16", video=False)
    assert str(cmd_int_audio) == "*8*1#6#2#11*16##"

    cmd_int_video = OWNIntercomCommand.call_internal("11", "16", video=True)
    assert str(cmd_int_video) == "*8*1#6#4#11*16##"

    cmd_ext_audio = OWNIntercomCommand.call_external("11", "16", video=False)
    assert str(cmd_ext_audio) == "*8*1#7#2#11*16##"

    cmd_ext_video = OWNIntercomCommand.call_external("11", "16", video=True)
    assert str(cmd_ext_video) == "*8*1#7#4#11*16##"

    cmd_pager = OWNIntercomCommand.call_pager("11", "4")
    assert str(cmd_pager) == "*8*1#14#2#11*4##"

    cmd_ans = OWNIntercomCommand.answer_call("11", kind=KIND_INTERNAL_INTERCOM, mm_type=MMTYPE_AUDIO)
    assert str(cmd_ans) == "*8*2#6#2*11##"

    cmd_end = OWNIntercomCommand.end_call("411", kind=KIND_INTERNAL_INTERCOM, mm_type=MMTYPE_AUDIO)
    assert str(cmd_end) == "*8*3#6#2*411##"

    cmd_stop_vid = OWNIntercomCommand.stop_video("11", kind=KIND_PE1)
    assert str(cmd_stop_vid) == "*8*3#1#3*11##"


def test_amplifier_mute_teleloop_and_vct() -> None:
    # Mute: *8*63*11##
    ev_mute = OWNEvent.parse("*8*63*11##")
    assert isinstance(ev_mute, OWNIntercomEvent)
    assert ev_mute.message_type == MESSAGE_TYPE_AMPLIFIER_MUTE
    assert ev_mute.is_muted is True
    assert "silenced (muted)" in ev_mute.human_readable_log

    # Unmute: *8*64*11##
    ev_unmute = OWNEvent.parse("*8*64*11##")
    assert isinstance(ev_unmute, OWNIntercomEvent)
    assert ev_unmute.is_muted is False
    assert "unmuted" in ev_unmute.human_readable_log

    # Teleloop: *8*76*11## (mode 0), *8*77#5*11## (mode 1, param 5), *8*78*11## (mode 2)
    ev_tl0 = OWNEvent.parse("*8*76*11##")
    assert isinstance(ev_tl0, OWNIntercomEvent)
    assert ev_tl0.message_type == MESSAGE_TYPE_TELELOOP
    assert ev_tl0.session_action == "teleloop_start"

    ev_tl1 = OWNEvent.parse("*8*77#5*11##")
    assert isinstance(ev_tl1, OWNIntercomEvent)
    assert ev_tl1.message_type == MESSAGE_TYPE_TELELOOP
    assert ev_tl1.session_action == "teleloop_association"
    assert ev_tl1.teleloop_mode == 5

    ev_tl2 = OWNEvent.parse("*8*78*11##")
    assert isinstance(ev_tl2, OWNIntercomEvent)
    assert ev_tl2.message_type == MESSAGE_TYPE_TELELOOP
    assert ev_tl2.session_action == "teleloop_timeout"

    # VCT init: *8*37#1*11##
    ev_vct = OWNEvent.parse("*8*37#1*11##")
    assert isinstance(ev_vct, OWNIntercomEvent)
    assert ev_vct.message_type == MESSAGE_TYPE_VCT_INIT
    assert ev_vct.vct_mode == 1

    # Builders
    cmd_mute = OWNIntercomCommand.mute_amplifier("11")
    assert str(cmd_mute) == "*8*63*11##"

    cmd_unmute = OWNIntercomCommand.unmute_amplifier("11")
    assert str(cmd_unmute) == "*8*64*11##"

    cmd_status = OWNIntercomCommand.status("11")
    assert str(cmd_status) == "*#8*11##"

    cmd_lock_status = OWNIntercomCommand.lock_status("11")
    assert str(cmd_lock_status) == "*#8*11*19##"


def test_intercom_edge_cases_and_notifications() -> None:
    # Pager call and property check
    ev_pager = OWNEvent.parse("*8*1#14#2#11*0##")
    assert isinstance(ev_pager, OWNIntercomEvent)
    assert ev_pager.is_pager is True

    ev_call = OWNEvent.parse("*8*1#6#2#11*16##")
    assert isinstance(ev_call, OWNIntercomEvent)
    assert ev_call.is_pager is False

    # Caller notification with and without params
    ev_notif = OWNEvent.parse("*8*9#6#2*11##")
    assert isinstance(ev_notif, OWNIntercomEvent)
    assert ev_notif.session_action == "caller_notification"
    assert ev_notif.caller == "11"
    assert ev_notif.call_kind == KIND_INTERNAL_INTERCOM
    assert ev_notif.multimedia_type == MMTYPE_AUDIO

    ev_notif_noparams = OWNEvent.parse("*8*9*11##")
    assert isinstance(ev_notif_noparams, OWNIntercomEvent)
    assert ev_notif_noparams.session_action == "caller_notification"

    # Answer and end without params
    ev_ans_noparams = OWNEvent.parse("*8*2*11##")
    assert isinstance(ev_ans_noparams, OWNIntercomEvent)
    assert ev_ans_noparams.session_action == "answer"

    ev_end_noparams = OWNEvent.parse("*8*3*11##")
    assert isinstance(ev_end_noparams, OWNIntercomEvent)
    assert ev_end_noparams.session_action == "end"

    # Session rearm
    ev_rearm = OWNEvent.parse("*8*40*11##")
    assert isinstance(ev_rearm, OWNIntercomEvent)
    assert ev_rearm.session_action == "rearm"
    assert ev_rearm.caller == "11"

    # Teleloop active (79) and mode 1 without params
    ev_tl_active = OWNEvent.parse("*8*79*11##")
    assert isinstance(ev_tl_active, OWNIntercomEvent)
    assert ev_tl_active.session_action == "teleloop_active"

    ev_tl_noparam = OWNEvent.parse("*8*77*11##")
    assert isinstance(ev_tl_noparam, OWNIntercomEvent)
    assert ev_tl_noparam.session_action == "teleloop_association"

    # VCT init without params
    ev_vct_noparam = OWNEvent.parse("*8*37*11##")
    assert isinstance(ev_vct_noparam, OWNIntercomEvent)
    assert ev_vct_noparam.message_type == MESSAGE_TYPE_VCT_INIT

    # Cameras without callers
    ev_cam_nocaller = OWNEvent.parse("*8*4*20##")
    assert isinstance(ev_cam_nocaller, OWNIntercomEvent)
    assert ev_cam_nocaller.caller is None

    ev_cycle_nocaller = OWNEvent.parse("*8*6*20##")
    assert isinstance(ev_cycle_nocaller, OWNIntercomEvent)
    assert ev_cycle_nocaller.caller is None

    # Unexpected what
    ev_unknown = OWNEvent.parse("*8*99*11##")
    assert isinstance(ev_unknown, OWNIntercomEvent)
    assert "Intercom event 99" in ev_unknown.human_readable_log


def test_intercom_command_parse() -> None:
    cmd = OWNCommand.parse("*8*19*1##")
    assert isinstance(cmd, OWNIntercomCommand)
    assert str(cmd) == "*8*19*1##"
