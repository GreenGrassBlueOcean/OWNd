# Changelog

All notable changes to `OWNd` are documented in this file.

## [2.0.0b11] - 2026-10-19

### Added
- **WHO 0 (`OWNScenarioEvent`)**: Decode `WHAT 40–46` programming and lock states (`#90`).
- **WHO 1 (`OWNLightingCommand`, `OWNLightingEvent`)**:
  - Presets, step dimming, fixed timers, and variable timer builders (`#93`).
  - `WHAT 19` anomaly / fault state modeling (`#115`).
  - Public APL normalization (`normalize_where`) and DALI / RGB / HSV / XY / colour-temperature accessors (`#123`).
- **WHO 3 (`OWNLoadControlEvent`, `OWNLoadControlCommand`)**: Load control parser, command builders, typed measurement properties for dimensions 1–4 (`voltage`, `current`, `power`, `energy`), and gateway profile gating (`#104`, `#124`).
- **WHO 4 (`OWNHeatingEvent`, `OWNHeatingCommand`)**: Consolidated firmware-validated heating support including season frames (`WHAT 0` / `WHAT 1`), central unit status (`WHAT 22–24`, `30–31`), holiday/vacation program handling (`WHAT 115#P`, `13DDD#P`, `3101–3103`), and F453AV / F461 live-plant conformance (`#83`, `#97`, `#116`, `#119`, `#120`).
- **WHO 6 & WHO 8 (`OWNDoorEntryEvent`, `OWNDoorEntryCommand`)**: Door entry, lock, camera, and intercom call dialects (`#100`).
- **WHO 13 & WHO 1013 (`OWNGatewayEvent`, `OWNGatewayCommand`)**:
  - Typed gateway clock, timezone, `kernel_version`, `distribution_version`, and diagnostic properties and builders (`#111`, `#112`).
  - H4684 / LGRH4684 / MH201 gateway identification profiles and WHO 1013 device diagnostic frame support (`#118`).
- **WHO 14 (`OWNActuatorLockEvent`, `OWNActuatorLockCommand`)**: Actuator lock and unlock (`WHAT 0` / `WHAT 1`) event parser and command builders (`#130`).
- **WHO 16 (`OWNSoundEvent`, `OWNSoundCommand`)**: Sound system media transport commands, tuner frequency/station decoding, and L4561N source selection (`#95`, `#123`).
- **WHO 17 (`OWNSceneCommand`)**: Complete scene command factory surface (`#99`).
- **WHO 18 (`OWNEnergyEvent`, `OWNEnergyCommand`)**:
  - Dimension `1200` automatic power-update stream lifecycle properties (`stream_duration`, `is_streaming_active`, `energy_type`), `stop_sending_instant_power`, and `request_active_power` / `get_instant_power` builders (`#92`, `#102`, `#107`).
  - Stop&Go (`F16EB`) automatic reset breaker commands and status flag dimensions `212`, `250`, `251–263` (`#113`, `#122`).
- **WHO 22 (`OWNSoundDiffusionEvent`, `OWNSoundDiffusionCommand`)**: Advanced sound diffusion 2.0 events and commands (power-on, atomic off, matrix routing, paging, keypad, 100 kHz tuner frequency, presets, 8-character RDS, and `MH200NProfile` support) (`#103`, `#127`).
- **WHO 25 (`OWNScenarioPlusEvent`, `OWNScenarioPlusCommand`)**: Scenario-plus `WHAT 11–15` parser and command builders (`#91`, `#106`).
- **Firmware Oracle & Documentation Conformance**:
  - Firmware oracle conformance suite across emulated gateways (`#84`, `#117`, `#126`).
  - Unified documentation synchronization sentinel (`scripts/sync_documentation.py`) verifying WHO catalog, gateway profile tables, and coverage badges (`#101`, `#105`, `#108`).

### Changed
- **Packaging & Dependencies**:
  - Normalize version string to canonical PEP 440 (`2.0.0b11`).
  - Migrate package metadata to PEP 621 `[project]` and PEP 639 `license = "Apache-2.0"` in `pyproject.toml`.
  - Drop unused `pytz` and `python-dateutil` runtime dependencies in favor of Python 3.11+ standard library `datetime` and `zoneinfo` (with `tzdata` included in `[test]` on Windows).
- **Input Validation & Connection Reliability**:
  - Harden bounds and infeasible input validation across WHO subsystems and connection sessions (`#121`, `#125`, `#127`, `#128`).
  - Only retry idempotent status queries in `OWNCommandSession` after mid-send transport loss (`#131`).
