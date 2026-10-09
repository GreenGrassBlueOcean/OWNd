"""WHO 0 WHAT 40-46 are scenario-module programming / lock states, not scenarios.

Evidence: libqtdevices TS10_1_0_23 scenario_device.cpp:27-34 (START_PROG = 40,
STOP_PROG = 41, DELETE = 42, LOCK = 43, UNLOCK = 44) and :93-156 (parseFrame);
firmware replay on bt_luci (MyHomeServer1, F454, F459): *0*40#1*W## ACK bus
11 00 1C 41, *0*41#1*W## 1C 61, *0*42*W## 1C 00, *0*42#1*W## 1C 21, *0*43*W##
1C FF, *0*44*W## 1C E0; emitted by the firmware for bus frames: *0*42*31##,
*0*43*31##, *0*45*99##, *0*46#9*99##.
"""

import pytest

from OWNd.message import OWNEvent, OWNScenarioEvent


@pytest.mark.parametrize(
    ("frame", "event", "target"),
    [
        ("*0*40#1*11##", "programming started", 1),
        ("*0*41#1*11##", "programming stopped", 1),
        ("*0*42*31##", "deleted", None),
        ("*0*42#1*11##", "deleted", 1),
        ("*0*43*31##", "locked", None),
        ("*0*44*11##", "unlocked", None),
        ("*0*45*99##", "unavailable", None),
        ("*0*46#9*99##", "memory full", 9),
    ],
)
def test_programming_and_lock_states(frame: str, event: str, target: int | None):
    msg = OWNEvent.parse(frame)
    assert isinstance(msg, OWNScenarioEvent)
    assert msg.event == event
    assert msg.programming_scenario == target
    assert msg.scenario is None
    assert "launched" not in msg.human_readable_log


def test_plain_scenario_is_still_launched():
    msg = OWNEvent.parse("*0*3*11##")
    assert isinstance(msg, OWNScenarioEvent)
    assert msg.scenario == 3
    assert msg.event == "launched"
    assert msg.programming_scenario is None
    assert msg.human_readable_log == "Scenario 3 from control panel 11 has been launched."


@pytest.mark.parametrize("frame", ["*#0*11##", "*#0##"])
def test_status_request_is_not_a_launch(frame: str):
    msg = OWNEvent.parse(frame)
    assert isinstance(msg, OWNScenarioEvent)
    assert msg.scenario is None
    assert msg.event is None
    assert msg.programming_scenario is None
    assert "launched" not in msg.human_readable_log
