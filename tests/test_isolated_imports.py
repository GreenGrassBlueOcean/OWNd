"""Tests verifying isolated imports of OWNd.message modules and dispatcher hardening."""
from __future__ import annotations

import subprocess
import sys
import pytest

from OWNd.message.base import _ensure_all_subsystems_registered


def test_ensure_all_subsystems_registered_idempotent() -> None:
    """Verify that _ensure_all_subsystems_registered can be called repeatedly safely."""
    _ensure_all_subsystems_registered()
    _ensure_all_subsystems_registered()


def test_isolated_import_base_subprocesses() -> None:
    """Verify clean isolated import of OWNd.message.base parses all WHO frames."""
    code = """
import sys
from OWNd.message.base import OWNMessage, OWNEvent, OWNCommand

# Heating WHO 4
evt_heat = OWNEvent.parse("*4*0*1##")
assert type(evt_heat).__name__ == "OWNHeatingEvent", f"Expected OWNHeatingEvent, got {type(evt_heat)}"

cmd_heat = OWNCommand.parse("*#4*1##")
assert type(cmd_heat).__name__ == "OWNHeatingCommand", f"Expected OWNHeatingCommand, got {type(cmd_heat)}"

# Alarm WHO 5
evt_alarm = OWNEvent.parse("*5*1*1##")
assert type(evt_alarm).__name__ == "OWNAlarmEvent", f"Expected OWNAlarmEvent, got {type(evt_alarm)}"

cmd_alarm = OWNCommand.parse("*#5*1##")
assert type(cmd_alarm).__name__ == "OWNAlarmCommand", f"Expected OWNAlarmCommand, got {type(cmd_alarm)}"

# CEN WHO 15
evt_cen = OWNEvent.parse("*15*1*1##")
assert type(evt_cen).__name__ == "OWNCENEvent", f"Expected OWNCENEvent, got {type(evt_cen)}"

# Automation WHO 2
evt_auto = OWNEvent.parse("*2*1*1##")
assert type(evt_auto).__name__ == "OWNAutomationEvent", f"Expected OWNAutomationEvent, got {type(evt_auto)}"

# Lighting WHO 1
evt_light = OWNEvent.parse("*1*1*1##")
assert type(evt_light).__name__ == "OWNLightingEvent", f"Expected OWNLightingEvent, got {type(evt_light)}"

# Sound WHO 16
evt_sound = OWNEvent.parse("*16*1*1##")
assert type(evt_sound).__name__ == "OWNSoundEvent", f"Expected OWNSoundEvent, got {type(evt_sound)}"

# Energy WHO 18
evt_energy = OWNEvent.parse("*#18*1*113*100##")
assert type(evt_energy).__name__ == "OWNEnergyEvent", f"Expected OWNEnergyEvent, got {type(evt_energy)}"

# Gateway WHO 13
evt_gw = OWNEvent.parse("*#13**15*4##")
assert type(evt_gw).__name__ == "OWNGatewayEvent", f"Expected OWNGatewayEvent, got {type(evt_gw)}"

# Top-level OWNMessage.parse
msg_heat = OWNMessage.parse("*4*0*1##")
assert type(msg_heat).__name__ == "OWNHeatingEvent", f"Expected OWNHeatingEvent, got {type(msg_heat)}"
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"Subprocess failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"


def test_isolated_import_single_who_submodule() -> None:
    """Verify importing only OWNd.message.lighting still parses other subsystems."""
    code = """
import sys
from OWNd.message.lighting import OWNLightingEvent
from OWNd.message.base import OWNEvent, OWNCommand

# Parse heating event (WHO 4)
evt_heat = OWNEvent.parse("*4*0*1##")
assert type(evt_heat).__name__ == "OWNHeatingEvent", f"Expected OWNHeatingEvent, got {type(evt_heat)}"

# Parse heating command (WHO 4)
cmd_heat = OWNCommand.parse("*#4*1##")
assert type(cmd_heat).__name__ == "OWNHeatingCommand", f"Expected OWNHeatingCommand, got {type(cmd_heat)}"

# Parse alarm event (WHO 5)
evt_alarm = OWNEvent.parse("*5*1*1##")
assert type(evt_alarm).__name__ == "OWNAlarmEvent", f"Expected OWNAlarmEvent, got {type(evt_alarm)}"

# Parse CEN event (WHO 15)
evt_cen = OWNEvent.parse("*15*1*1##")
assert type(evt_cen).__name__ == "OWNCENEvent", f"Expected OWNCENEvent, got {type(evt_cen)}"
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"Subprocess failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"


def test_isolated_import_cen_submodule() -> None:
    """Verify importing only OWNd.message.cen still parses other subsystems."""
    code = """
import sys
from OWNd.message.cen import OWNCENEvent
from OWNd.message.base import OWNEvent, OWNCommand

# Parse automation event (WHO 2)
evt_auto = OWNEvent.parse("*2*1*1##")
assert type(evt_auto).__name__ == "OWNAutomationEvent", f"Expected OWNAutomationEvent, got {type(evt_auto)}"

# Parse energy event (WHO 18)
evt_energy = OWNEvent.parse("*#18*1*113*100##")
assert type(evt_energy).__name__ == "OWNEnergyEvent", f"Expected OWNEnergyEvent, got {type(evt_energy)}"
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"Subprocess failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
