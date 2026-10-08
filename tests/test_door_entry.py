"""Tests for WHO 6 and WHO 8 door entry and lock messages."""

from __future__ import annotations

from OWNd.message import (
    OWNDoorEntryCommand,
    OWNDoorEntryEvent,
    OWNLockCommand,
    OWNLockEvent,
    OWNMessage,
)


def test_door_entry_event_incoming_call() -> None:
    event = OWNDoorEntryEvent("*6*6*1##")
    assert event.is_incoming_call is True
    assert event.is_call is True
    assert event.is_broadcast_call is False
    assert event.where == "1"
    assert event.human_readable_log == "Incoming door entry call to handset 1."


def test_door_entry_event_broadcast_call() -> None:
    event = OWNDoorEntryEvent("*6*6*4100##")
    assert event.is_incoming_call is True
    assert event.is_call is True
    assert event.is_broadcast_call is True
    assert event.where == "4100"
    assert event.human_readable_log == "Incoming door entry broadcast call."


def test_door_entry_event_chime() -> None:
    event = OWNDoorEntryEvent("*6*20*1##")
    assert event.is_chime is True
    assert event.is_call is True
    assert event.is_incoming_call is False
    assert event.where == "1"
    assert event.human_readable_log == "Door entry chime active at 1."


def test_door_entry_event_lock_open() -> None:
    event1 = OWNDoorEntryEvent("*6*10*4001##")
    assert event1.is_lock_open is True
    assert event1.is_call is False
    assert event1.human_readable_log == "Door lock released at entrance panel 4001."

    event2 = OWNDoorEntryEvent("*6*22*4001##")
    assert event2.is_lock_open is True
    assert (
        event2.human_readable_log
        == "Door lock released during conversation with entrance panel 4001."
    )


def test_door_entry_event_staircase() -> None:
    on_event = OWNDoorEntryEvent("*6*12*1##")
    assert on_event.is_staircase_on is True
    assert on_event.is_staircase_off is False
    assert (
        on_event.human_readable_log
        == "Staircase light switched ON from door entry at 1."
    )

    off_event = OWNDoorEntryEvent("*6*11*1##")
    assert off_event.is_staircase_on is False
    assert off_event.is_staircase_off is True
    assert (
        off_event.human_readable_log
        == "Staircase light switched OFF from door entry at 1."
    )


def test_door_entry_event_camera() -> None:
    cam_on = OWNDoorEntryEvent("*6*0*4001##")
    assert cam_on.human_readable_log == "Door entry camera switched ON at 4001."

    cam_off = OWNDoorEntryEvent("*6*9##")
    assert cam_off.human_readable_log == "Door entry camera switched OFF."


def test_door_entry_commands() -> None:
    cmd_lock = OWNDoorEntryCommand.open_lock(4001)
    assert str(cmd_lock) == "*6*10*4001##"
    assert (
        cmd_lock.human_readable_log == "Opening door lock at entrance panel 4001."
    )

    cmd_riser = OWNDoorEntryCommand.open_lock("4001#2")
    assert str(cmd_riser) == "*6*10*4001#2##"

    cmd_light_on = OWNDoorEntryCommand.staircase_light_on(1)
    assert str(cmd_light_on) == "*6*12*1##"

    cmd_light_off = OWNDoorEntryCommand.staircase_light_off(1)
    assert str(cmd_light_off) == "*6*11*1##"

    cmd_cam_on = OWNDoorEntryCommand.camera_on(4001)
    assert str(cmd_cam_on) == "*6*0*4001##"

    cmd_cam_off = OWNDoorEntryCommand.camera_off()
    assert str(cmd_cam_off) == "*6*9##"


def test_lock_actuator_event_and_command() -> None:
    evt_unlock = OWNLockEvent("*8*19*20##")
    assert evt_unlock.is_unlocked is True
    assert evt_unlock.is_locked is False
    assert evt_unlock.human_readable_log == "Lock actuator 20 unlocked / open."

    evt_lock = OWNLockEvent("*8*20*20##")
    assert evt_lock.is_locked is True
    assert evt_lock.is_unlocked is False
    assert evt_lock.human_readable_log == "Lock actuator 20 locked / released."

    cmd_unlock = OWNLockCommand.unlock(20)
    assert str(cmd_unlock) == "*8*19*20##"

    cmd_lock = OWNLockCommand.lock(20)
    assert str(cmd_lock) == "*8*20*20##"


def test_message_registry_parsing() -> None:
    msg6_lock = OWNMessage.parse("*6*10*4001##")
    assert isinstance(msg6_lock, OWNDoorEntryEvent)

    msg6_call = OWNMessage.parse("*6*6*1##")
    assert isinstance(msg6_call, OWNDoorEntryEvent)
