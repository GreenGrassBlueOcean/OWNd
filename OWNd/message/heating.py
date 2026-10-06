"""WHO 4: Heating / Thermoregulation events, commands, and helpers."""

from __future__ import annotations

import re

from .base import OWNCommand, OWNEvent, register_command_parser, register_event_parser
from .lighting import MESSAGE_TYPE_ACTION

MESSAGE_TYPE_MAIN_TEMPERATURE = "main_temperature"
MESSAGE_TYPE_MAIN_HUMIDITY = "main_humidity"
MESSAGE_TYPE_SECONDARY_TEMPERATURE = "secondary_temperature"
MESSAGE_TYPE_TARGET_TEMPERATURE = "target_temperature"
MESSAGE_TYPE_LOCAL_OFFSET = "local_offset"
MESSAGE_TYPE_LOCAL_TARGET_TEMPERATURE = "local_target_temperature"
MESSAGE_TYPE_MODE = "hvac_mode"
MESSAGE_TYPE_MODE_TARGET = "hvac_mode_target"

MESSAGE_TYPE_FAN_SPEED = "fan_speed"
MESSAGE_TYPE_ZONE_STATE = "zone_state"

CLIMATE_MODE_OFF = "off"
CLIMATE_MODE_HEAT = "heat"
CLIMATE_MODE_COOL = "cool"
CLIMATE_MODE_AUTO = "auto"

LOCAL_CONTROL_NORMAL = "normal"
LOCAL_CONTROL_OFFSET = "offset"
LOCAL_CONTROL_OFF = "local_off"
LOCAL_CONTROL_PROTECTION = "local_protection"
LOCAL_CONTROL_OVERRIDE = "local_override"
LOCAL_CONTROL_UNKNOWN = "unknown"

# WHO 4 DIMENSION 7, *#4*ZONE*7*CONTEXT*STATE[*TTTT]##: not in the public WHO 4
# document; the values follow the MyHOME_Suite ScenarioDevices templates.
ZONE_CONTEXT_GENERIC = "generic"
ZONE_CONTEXT_HEATING = "heating"
ZONE_CONTEXT_COOLING = "cooling"
ZONE_CONTEXT_AUTOMATIC = "automatic"

ZONE_STATE_SETPOINT = "setpoint"
ZONE_STATE_PROTECTION = "protection"
ZONE_STATE_COMFORT = "comfort"
ZONE_STATE_ECO = "eco"
ZONE_STATE_OFF = "off"

_ZONE_CONTEXTS = {
    "0": ZONE_CONTEXT_GENERIC,
    "1": ZONE_CONTEXT_HEATING,
    "2": ZONE_CONTEXT_COOLING,
    "3": ZONE_CONTEXT_AUTOMATIC,
}
_ZONE_STATES = {
    "1": ZONE_STATE_SETPOINT,
    "2": ZONE_STATE_PROTECTION,
    "3": ZONE_STATE_COMFORT,
    "4": ZONE_STATE_ECO,
    "5": ZONE_STATE_OFF,
}


_WHO4_TEMP_REGEX = re.compile(r"^[01][0-9]{3}$")


def who4_temperature(raw: str) -> float | None:
    """Decode WHO 4 temperature ``SXXX`` (tenths of a degree)."""
    if not _WHO4_TEMP_REGEX.match(raw):
        return None
    magnitude = int(raw[1:]) / 10.0
    if raw[0] == "1" and magnitude != 0.0:
        return -magnitude
    return magnitude


def _zone_state(
    values: list[str],
) -> tuple[str | None, str | None, float | None]:
    """Decode DIMENSION 7 values into (context, state, setpoint temperature).

    Unknown context or state codes decode to None; the temperature is only
    read for the setpoint state.
    """
    context = _ZONE_CONTEXTS.get(values[0]) if values else None
    state = _ZONE_STATES.get(values[1]) if len(values) > 1 else None
    temperature = None
    if state == ZONE_STATE_SETPOINT and len(values) > 2:
        temperature = who4_temperature(values[2])
    return context, state, temperature


def _zone_state_text(values: list[str]) -> str | None:
    """'heating setpoint at 17.0°C', 'cooling protection', or None if unknown."""
    context, state, temperature = _zone_state(values)
    if context is None or state is None:
        return None
    if temperature is not None:
        return f"{context} {state} at {temperature}°C"
    return f"{context} {state}"



class OWNHeatingEvent(OWNEvent):
    def __init__(self, data: str) -> None:
        super().__init__(data)

        self._type = None

        where = self._where or "0"
        self._zone = (
            int(where[1:]) if where.startswith("#") else int(where)
        )
        # ``#0#N`` is zone N of a 4-zone central unit; ``0#N`` is actuator N
        # of zone 0 (a pump the zones share), not zone N.
        if self._zone == 0 and self._where_param and where.startswith("#"):
            self._zone = int(self._where_param[0])
        self._sensor = None
        if self._zone > 99:
            self._sensor = int(str(self._zone)[:1])
            self._zone = int(str(self._zone)[1:])
        self._actuator = None

        self._mode = None
        self._mode_name = None
        self._zone_context: str | None = None
        self._zone_state: str | None = None
        self._set_temperature = None
        self._local_offset = None
        self._local_offset_raw = None
        self._local_control_state = None
        self._local_set_temperature = None
        self._measured_temperature = None
        self._secondary_temperature = None
        self._measured_humidity = None

        self._is_active = None
        self._is_heating = None
        self._is_cooling = None

        self._fan_on = None
        self._fan_speed = None
        self._cooling_fan_on = None
        self._cooling_fan_speed = None

        _valve_active_states = ["1", "2", "6", "7", "8"]
        _actuator_active_states = ["1", "2", "6", "7", "8", "9"]

        if self._what is not None:
            self._mode = int(self._what)
            if self._mode in [103, 203, 303, 102, 202, 302]:
                self._type = MESSAGE_TYPE_MODE
                self._mode_name = CLIMATE_MODE_OFF
                self._human_readable_log = (
                    f"Zone {self._zone}'s mode is set to '{self._mode_name}'"
                )
            elif (
                self._mode in [0, 210, 211, 215]
                or (self._mode >= 2101 and self._mode <= 2103)
                or (self._mode >= 2201 and self._mode <= 2216)
            ):
                self._type = MESSAGE_TYPE_MODE
                self._mode_name = CLIMATE_MODE_COOL
                self._human_readable_log = (
                    f"Zone {self._zone}'s mode is set to '{self._mode_name}'"
                )
            elif (
                self._mode in [1, 110, 111, 115]
                or (self._mode >= 1101 and self._mode <= 1103)
                or (self._mode >= 1201 and self._mode <= 1216)
            ):
                self._type = MESSAGE_TYPE_MODE
                self._mode_name = CLIMATE_MODE_HEAT
                self._human_readable_log = (
                    f"Zone {self._zone}'s mode is set to '{self._mode_name}'"
                )
            elif (
                self._mode in [310, 311, 315]
                or (self._mode >= 23001 and self._mode <= 23255)
                or (self._mode >= 13001 and self._mode <= 13255)
            ):
                self._type = MESSAGE_TYPE_MODE
                self._mode_name = CLIMATE_MODE_AUTO
                self._human_readable_log = (
                    f"Zone {self._zone}'s mode is set to '{self._mode_name}'"
                )
            elif self._mode == 20:
                self._mode_name = None
                self._human_readable_log = (
                    f"Zone {self._zone}'s remote control is disabled"
                )
            elif self._mode == 21:
                self._mode_name = None
                self._human_readable_log = (
                    f"Zone {self._zone}'s remote control is enabled"
                )
            else:
                self._mode_name = None
                self._human_readable_log = f"Zone {self._zone}'s mode is unknown"

            if (
                self._type == MESSAGE_TYPE_MODE
                and self._what_param
                and self._what_param[0] is not None
            ):
                self._type = MESSAGE_TYPE_MODE_TARGET
                self._set_temperature = who4_temperature(self._what_param[0])
                if self._set_temperature is not None:
                    self._human_readable_log += f" at {self._set_temperature}°C."
                else:
                    self._human_readable_log += "."
            else:
                self._human_readable_log += "."

        if self._dimension == 0:  # Temperature
            temp = (
                who4_temperature(self._dimension_value[0])
                if self._dimension_value
                else None
            )
            if self._sensor is None:
                self._type = MESSAGE_TYPE_MAIN_TEMPERATURE
                self._measured_temperature = temp
                if self._measured_temperature is not None:
                    self._human_readable_log = f"Zone {self._zone}'s main sensor is reporting a temperature of {self._measured_temperature}°C."  # pylint: disable=line-too-long
            else:
                self._type = MESSAGE_TYPE_SECONDARY_TEMPERATURE
                self._secondary_temperature = temp
                if self._secondary_temperature is not None:
                    self._human_readable_log = f"Zone {self._zone}'s secondary sensor {self._sensor} is reporting a temperature of {self._secondary_temperature}°C."  # pylint: disable=line-too-long

        elif self._dimension == 5 and self._dimension_value:  # Local control
            # MyHOME_Suite writes *#4*Z*#5*val##; the meaning of val is not
            # published, so only log it.
            self._human_readable_log = f"Zone {self._zone}'s local control (dimension 5) is {self._dimension_value[0]}."  # pylint: disable=line-too-long

        elif (
            self._dimension == 7
            and self._dimension_value
            and self._message_type != "DIMENSION_WRITING"
        ):  # Zone state
            # MyHomeServer1 / Home+Control plants carry the zone's operating
            # state and setpoint here, and never in the reply to *#4*Z##.
            # The zone_* properties are only set with the message type, so a
            # half-known frame never looks like a valid state.
            # Dimension writes (*#4*Z*#7*...##) are commands handled by
            # OWNHeatingCommand; skipping them keeps write echoes typeless in
            # OWNEvent, agreeing with OWNMessage.parse.
            context, state, temperature = _zone_state(self._dimension_value)
            text = _zone_state_text(self._dimension_value)
            if text is None:
                self._human_readable_log = f"Zone {self._zone} reports an unknown zone state {'*'.join(self._dimension_value)}."  # pylint: disable=line-too-long
            else:
                self._type = MESSAGE_TYPE_ZONE_STATE
                self._zone_context = context
                self._zone_state = state
                self._set_temperature = temperature
                self._human_readable_log = f"Zone {self._zone} is in {text}."

        elif self._dimension == 11:  # Fan speed
            self._type = MESSAGE_TYPE_FAN_SPEED
            _fan_mode = int(self._dimension_value[0])
            if _fan_mode < 4:
                self._fan_on = True
                self._is_active = True
                self._fan_speed = _fan_mode
                if _fan_mode > 0:
                    self._human_readable_log = (
                        f"Zone {self._zone}'s fan is on at speed {self._fan_speed}."
                    )
                else:
                    self._human_readable_log = (
                        f"Zone {self._zone}'s fan is on at 'Auto' speed."
                    )
            else:
                self._fan_on = False
                self._is_active = False
                self._human_readable_log = f"Zone {self._zone}'s fan is off."

        elif self._dimension == 12:  # Local set temperature (set+offset)
            self._type = MESSAGE_TYPE_LOCAL_TARGET_TEMPERATURE
            self._local_set_temperature = (
                who4_temperature(self._dimension_value[0])
                if self._dimension_value
                else None
            )
            if self._local_set_temperature is not None:
                self._human_readable_log = f"Zone {self._zone}'s local target temperature is set to {self._local_set_temperature}°C."  # pylint: disable=line-too-long

        elif self._dimension == 13:  # Local offset
            self._type = MESSAGE_TYPE_LOCAL_OFFSET
            self._local_offset_raw = self._dimension_value[0]
            if self._local_offset_raw in ("0", "00"):
                self._local_offset = 0
                self._local_control_state = LOCAL_CONTROL_NORMAL
            elif self._local_offset_raw in ("01", "02", "03"):
                self._local_offset = int(self._local_offset_raw[1:])
                self._local_control_state = LOCAL_CONTROL_OFFSET
            elif self._local_offset_raw in ("11", "12", "13"):
                self._local_offset = -int(self._local_offset_raw[1:])
                self._local_control_state = LOCAL_CONTROL_OFFSET
            elif self._local_offset_raw == "4":
                self._local_control_state = LOCAL_CONTROL_OFF
            elif self._local_offset_raw == "5":
                self._local_control_state = LOCAL_CONTROL_PROTECTION
            elif self._local_offset_raw == "6":
                # Observed on 3550 systems when the local/manual override is active.
                self._local_control_state = LOCAL_CONTROL_OVERRIDE
            else:
                self._local_control_state = LOCAL_CONTROL_UNKNOWN

            if self._local_offset is not None:
                self._human_readable_log = f"Zone {self._zone}'s local offset is set to {self._local_offset}°C."
            else:
                self._human_readable_log = f"Zone {self._zone}'s local control state is '{self._local_control_state}' (raw value {self._local_offset_raw})."

        elif self._dimension == 14:  # Set temperature
            self._type = MESSAGE_TYPE_TARGET_TEMPERATURE
            self._set_temperature = (
                who4_temperature(self._dimension_value[0])
                if self._dimension_value
                else None
            )
            if self._set_temperature is not None:
                self._human_readable_log = f"Zone {self._zone}'s target temperature is set to {self._set_temperature}°C."  # pylint: disable=line-too-long

        elif self._dimension == 15:  # Probe temperature reading
            self._type = MESSAGE_TYPE_SECONDARY_TEMPERATURE
            if self._dimension_value:
                if len(self._dimension_value) >= 2:
                    self._sensor = int(self._dimension_value[0])
                    temp_raw = self._dimension_value[1]
                else:
                    temp_raw = self._dimension_value[0]

                self._secondary_temperature = who4_temperature(temp_raw)

            if self._secondary_temperature is not None:
                if self._sensor is not None:
                    self._human_readable_log = f"Zone {self._zone}'s secondary probe {self._sensor} is reporting a temperature of {self._secondary_temperature}°C."
                else:
                    self._human_readable_log = f"Zone {self._zone}'s temperature probe is reporting a temperature of {self._secondary_temperature}°C."

        elif (
            self._dimension == 19
            and len(self._dimension_value) >= 2
            and all(self._dimension_value[:2])
        ):  # Valves status
            self._type = MESSAGE_TYPE_ACTION
            self._is_cooling = self._dimension_value[0] in _valve_active_states
            self._is_heating = self._dimension_value[1] in _valve_active_states
            self._is_active = self._is_cooling | self._is_heating
            # Handle cooling valve status relative to fan speed/status
            _cooling_value = int(self._dimension_value[0])
            if _cooling_value == 0:
                self._human_readable_log = f"Zone {self._zone}'s cooling valve is off"
            elif _cooling_value == 1:
                self._human_readable_log = f"Zone {self._zone}'s cooling valve is on"
            elif _cooling_value == 2:
                self._human_readable_log = (
                    f"Zone {self._zone}'s cooling valve is opened"
                )
            elif _cooling_value == 3:
                self._human_readable_log = (
                    f"Zone {self._zone}'s cooling valve is closed"
                )
            elif _cooling_value == 4:
                self._human_readable_log = (
                    f"Zone {self._zone}'s cooling valve is stopped"
                )
            else:
                _fan_mode = _cooling_value - 5
                if _fan_mode > 0:
                    self._cooling_fan_on = True
                    self._is_active = True
                    self._cooling_fan_speed = _fan_mode
                    self._human_readable_log = f"Zone {self._zone}'s cooling fan is on at speed {self._cooling_fan_speed}"  # pylint: disable=line-too-long
                else:
                    self._cooling_fan_on = False
                    self._is_active = False
                    self._human_readable_log = f"Zone {self._zone}'s cooling fan is off"
            # Handle heating valve status relative to fan speed/status
            _heating_value = int(self._dimension_value[1])
            if _heating_value == 0:
                self._human_readable_log += "; heating valve is off."
            elif _heating_value == 1:
                self._human_readable_log += "; heating valve is on."
            elif _heating_value == 2:
                self._human_readable_log += "; heating valve is opened."
            elif _heating_value == 3:
                self._human_readable_log += "; heating valve is closed."
            elif _heating_value == 4:
                self._human_readable_log += "; heating valve is stopped."
            else:
                _fan_mode = _heating_value - 5
                if _fan_mode > 0:
                    self._fan_on = True
                    self._is_active = True
                    self._fan_speed = _fan_mode
                    self._human_readable_log += (
                        f"; heating fan is on at speed {self._fan_speed}."
                    )
                else:
                    self._fan_on = False
                    self._is_active = False
                    self._human_readable_log += "; heating fan is off."

        elif (
            self._dimension == 20
            and self._dimension_value
            and self._dimension_value[0]
        ):  # Actuator status
            self._type = MESSAGE_TYPE_ACTION
            self._is_active = self._dimension_value[0] in _actuator_active_states
            self._actuator = (
                self._where_param[0] if self._where_param else "1"
            )
            _value = int(self._dimension_value[0])
            if _value == 0:
                self._human_readable_log = (
                    f"Zone {self._zone}'s actuator {self._actuator} is off."
                )
            elif _value == 1:
                self._human_readable_log = (
                    f"Zone {self._zone}'s actuator {self._actuator} is on."
                )
            elif _value == 2:
                self._human_readable_log = (
                    f"Zone {self._zone}'s actuator {self._actuator} is opened."
                )
            elif _value == 3:
                self._human_readable_log = (
                    f"Zone {self._zone}'s actuator {self._actuator} is closed."
                )
            elif _value == 4:
                self._human_readable_log = (
                    f"Zone {self._zone}'s actuator {self._actuator} is stopped."
                )
            else:
                _fan_mode = _value - 5
                if _fan_mode > 0:
                    self._fan_on = True
                    self._is_active = True
                    if _fan_mode < 4:
                        self._fan_speed = _fan_mode
                        self._human_readable_log = (
                            f"Zone {self._zone}'s fan is on at speed {self._fan_speed}."
                        )
                    else:
                        self._human_readable_log = (
                            f"Zone {self._zone}'s fan is on at 'Auto' speed."
                        )
                else:
                    self._fan_on = False
                    self._is_active = False
                    self._human_readable_log = f"Zone {self._zone}'s fan is off."

        elif self._dimension == 60:  # Humidity
            self._type = MESSAGE_TYPE_MAIN_HUMIDITY
            self._measured_humidity = float(self._dimension_value[0])
            self._human_readable_log = f"Zone {self._zone}'s main sensor is reporting a humidity of {self._measured_humidity}%."  # pylint: disable=line-too-long

    @property
    def unique_id(self) -> str:
        """The ID of the subject of this message"""
        if self._zone == 0:
            return f"{self._who}-#0"
        if self._sensor is not None:
            return f"{self._who}-{self._where}"
        return f"{self._who}-{self._zone}"

    @property
    def message_type(self) -> str | None:
        return self._type

    @property
    def zone(self) -> int:
        return self._zone

    @property
    def mode(self) -> str | None:
        return self._mode_name

    @property
    def zone_context(self) -> str | None:
        """DIMENSION 7 thermal context (ZONE_CONTEXT_*), else None."""
        return self._zone_context

    @property
    def zone_state(self) -> str | None:
        """DIMENSION 7 operating state (ZONE_STATE_*), else None.

        For ZONE_STATE_SETPOINT the temperature is in set_temperature.
        ZONE_STATE_PROTECTION is the wire name for both cases: MyHOME_Suite
        calls it antifreeze in the heating context (the zone also reports
        *4*102*Z##) and thermal protection in cooling (*4*202*Z##).
        """
        return self._zone_state

    def is_active(self) -> bool | None:
        return self._is_active

    def is_heating(self) -> bool | None:
        return self._is_heating

    def is_cooling(self) -> bool | None:
        return self._is_cooling

    @property
    def main_temperature(self) -> float | None:
        return self._measured_temperature

    @property
    def main_humidity(self) -> float | None:
        return self._measured_humidity

    @property
    def secondary_temperature(self) -> list[int | float | None]:
        return [self._sensor, self._secondary_temperature]

    @property
    def probe_temperature(self) -> float | None:
        return self._secondary_temperature

    @property
    def set_temperature(self) -> float | None:
        return self._set_temperature

    @property
    def local_offset(self) -> int | None:
        return self._local_offset

    @property
    def local_offset_raw(self) -> str | None:
        return self._local_offset_raw

    @property
    def local_control_state(self) -> str | None:
        return self._local_control_state

    @property
    def local_set_temperature(self) -> float | None:
        return self._local_set_temperature

    @property
    def fan_speed(self) -> int | None:
        return self._fan_speed

    @property
    def fan_on(self) -> bool | None:
        return self._fan_on

    @property
    def cooling_fan_speed(self) -> int | None:
        return self._cooling_fan_speed

    @property
    def cooling_fan_on(self) -> bool | None:
        return self._cooling_fan_on



class OWNHeatingCommand(OWNCommand):
    def __init__(self, data: str) -> None:
        super().__init__(data)
        # A dimension write seen on the event session: MyHomeServer1 runs its
        # schedule by writing DIMENSION 7 and re-asserts DIMENSION 5.  The
        # dimension 7 status that follows is the authoritative state.
        if self._message_type == "DIMENSION_WRITING" and self._dimension_value:
            if self._dimension == 7:
                text = _zone_state_text(self._dimension_value)
                if text is None:
                    text = f"unknown zone state {'*'.join(self._dimension_value)}"
                self._human_readable_log = f"Setting zone {self._where} to {text}."
            elif self._dimension == 5:
                self._human_readable_log = f"Setting zone {self._where}'s local control (dimension 5) to {self._dimension_value[0]}."  # pylint: disable=line-too-long

    @classmethod
    def status(cls, where: str | int) -> OWNHeatingCommand:
        message = cls(f"*#4*{where}##")
        message._human_readable_log = f"Requesting climate status update for {message._where}{message._interface_log_text}."
        return message

    @classmethod
    def valves_status(cls, where: str | int) -> OWNHeatingCommand:
        message = cls(f"*#4*{where}*19##")
        message._human_readable_log = f"Requesting climate valve status update for {message._where}{message._interface_log_text}."
        return message

    @classmethod
    def get_temperature(cls, where: str | int) -> OWNHeatingCommand:
        message = cls(f"*#4*{where}*0##")
        message._human_readable_log = f"Requesting climate status update for {message._where}{message._interface_log_text}."
        return message

    @classmethod
    def get_probe_temperature(cls, where: str | int) -> OWNHeatingCommand:
        message = cls(f"*#4*{where}*15##")
        message._human_readable_log = f"Requesting probe temperature status update for {message._where}{message._interface_log_text}."
        return message

    @classmethod
    def set_mode(
        cls, where: str | int, mode: str, standalone: bool = False
    ) -> OWNHeatingCommand | None:
        central_local = re.compile(r"^#0#\d+$")
        zone: str
        if central_local.match(str(where)):
            zone = str(where)
            zone_name = f"zone {int(str(where).split('#')[-1])}"
        else:
            zone_number = (
                int(str(where).split("#")[-1]) if str(where).startswith("#") else int(where)
            )
            zone_name = f"zone {zone_number}" if zone_number > 0 else "general"

            if standalone:
                zone = f"#{zone_number}" if zone_number == 0 else str(zone_number)
            else:
                zone = f"#{zone_number}"

        mode_name = mode
        if mode == CLIMATE_MODE_OFF:
            mode_code = 303
        elif mode == CLIMATE_MODE_AUTO:
            # The firmware forwards 311 only as *4*311*#Z## (OWNd#77, A3), the
            # form libqtdevices sends too, so ``standalone`` does not apply.
            if not zone.startswith("#"):
                zone = f"#{zone}"
            mode_code = 311
        else:
            return None

        message = cls(f"*4*{mode_code}*{zone}##")
        message._human_readable_log = f"Setting {zone_name} mode to '{mode_name}'."
        return message

    @classmethod
    def turn_off(
        cls, where: str | int, standalone: bool = False
    ) -> OWNHeatingCommand | None:
        return cls.set_mode(where=where, mode=CLIMATE_MODE_OFF, standalone=standalone)

    @classmethod
    def set_temperature(
        cls, where: str | int, temperature: float, mode: str, standalone: bool = False
    ) -> OWNHeatingCommand:
        central_local = re.compile(r"^#0#\d+$")
        zone: str
        if central_local.match(str(where)):
            zone = str(where)
            zone_name = f"zone {int(str(where).split('#')[-1])}"
        else:
            zone_number = (
                int(str(where).split("#")[-1]) if str(where).startswith("#") else int(where)
            )
            zone_name = f"zone {zone_number}" if zone_number > 0 else "general"

            if standalone:
                zone = f"#{zone_number}" if zone_number == 0 else str(zone_number)
            else:
                zone = f"#{zone_number}"

        temperature = round(temperature * 2) / 2
        if temperature < 5.0:
            temperature = 5.0
        elif temperature > 40.0:
            temperature = 40.0
        temperature_print = f"{temperature}"
        temperature_code = int(temperature * 10)

        mode_name = mode
        mode_code = 3
        if mode == CLIMATE_MODE_HEAT:
            mode_code = 1
        elif mode == CLIMATE_MODE_COOL:
            mode_code = 2

        message = cls(f"*#4*{zone}*#14*{temperature_code:04d}*{mode_code}##")
        message._human_readable_log = (
            f"Setting {zone_name} to {temperature_print}°C in mode '{mode_name}'."
        )
        return message

    @classmethod
    def set_fan_speed(
        cls, where: str | int, speed: int, standalone: bool = False
    ) -> OWNHeatingCommand:
        """Build a fan speed command; ``standalone`` is ignored (kept for compatibility)."""
        where_str = str(where)
        if where_str in ("#0", "0") or where_str.startswith("#0#"):
            raise ValueError(
                f"Fan speed cannot be set on central unit or general zone: {where}"
            )
        # The zone is the first field: a probe or actuator address such as
        # ``#23#1`` or ``23#1`` still sets the fan coil of zone 23, the plain
        # address libqtdevices sends (``*#4*23*#11*3##`` for probe ``#23#1``).
        try:
            zone_number = int(where_str.lstrip("#").split("#")[0])
        except (ValueError, TypeError):
            raise ValueError(f"Invalid zone address: {where}")
        if not (1 <= zone_number <= 99):
            raise ValueError(f"Invalid zone number: {zone_number}. Zone must be 1..99")
        try:
            speed_code = int(speed)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid fan speed: {speed}")
        if not (0 <= speed_code <= 3):
            raise ValueError(f"Invalid fan speed: {speed_code}. Speed must be 0..3")

        message = cls(f"*#4*{zone_number}*#11*{speed_code}##")
        message._human_readable_log = (
            f"Setting zone {zone_number} fan speed to {speed_code}."
        )
        return message

    @classmethod
    def set_central_mode(
        cls, where: str = "#0", mode: str = CLIMATE_MODE_HEAT
    ) -> OWNHeatingCommand:
        """Set operation mode for Central Unit (3550 99-zone or 4695 4-zone).

        The codes are the ones BTicino's touch-screen client sends to a central
        unit (libqtdevices ``thermal_device.cpp``): 303 generic off, 1 winter,
        0 summer, 302 generic protection. 102 is the winter (antifreeze)
        protection; 202, the summer protection, is not offered because it
        would also switch the plant to summer. 311 is the generic automatic
        command libqtdevices sends to zones; on ``#0`` it puts every zone back
        on the central unit's program.
        """
        mode_map = {
            CLIMATE_MODE_OFF: 303,
            CLIMATE_MODE_HEAT: 1,
            CLIMATE_MODE_COOL: 0,
            CLIMATE_MODE_AUTO: 311,
            "antifreeze": 102,
            "protection": 302,
        }
        mode_code = mode_map.get(mode)
        if mode_code is None:
            raise ValueError(f"Unsupported central unit mode: {mode}")
        message = cls(f"*4*{mode_code}*{where}##")
        message._human_readable_log = (
            f"Setting Central Unit {where} mode to '{mode}' (code {mode_code})."
        )
        return message

    @classmethod
    def set_central_temperature(
        cls, where: str = "#0", temperature: float = 20.0, mode: str = CLIMATE_MODE_HEAT
    ) -> OWNHeatingCommand:
        """Set master setpoint temperature on Central Unit."""
        temperature = round(temperature * 2) / 2
        temperature = max(5.0, min(40.0, temperature))
        temp_code = int(temperature * 10)
        mode_code = 1 if mode == CLIMATE_MODE_HEAT else 2
        message = cls(f"*#4*{where}*#14*{temp_code:04d}*{mode_code}##")
        message._human_readable_log = (
            f"Setting Central Unit {where} setpoint to {temperature}°C in mode '{mode}'."
        )
        return message

    @classmethod
    def central_status(cls, where: str = "#0") -> OWNHeatingCommand:
        """Query Central Unit status."""
        message = cls(f"*#4*{where}*14##")
        message._human_readable_log = f"Requesting Central Unit {where} status."
        return message


register_event_parser(4, OWNHeatingEvent)
register_command_parser(4, OWNHeatingCommand)
