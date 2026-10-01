"""Gateway configuration and endpoint discovery container."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any
from urllib.parse import urlparse

from ..discovery import find_gateways, get_gateway, get_port
from ..profiles import GatewayProfile, get_gateway_profile


def _first_scalar(value: Any, default: Any = None) -> Any:
    """Return a scalar from legacy tuple/list discovery values."""
    while isinstance(value, (list, tuple)):
        if not value:
            return default
        value = value[0]
    return default if value is None else value

class OWNGateway:
    def __init__(self, discovery_info: Mapping[str, Any] | dict[str, Any]) -> None:
        # Attributes potentially provided by user
        self.address = discovery_info.get("address")
        pw = discovery_info.get("password")
        self._password = str(pw) if pw not in (None, "") else None
        # Attributes retrieved from SSDP discovery
        self.ssdp_location = discovery_info.get("ssdp_location")
        self.ssdp_st = discovery_info.get("ssdp_st")
        # Attributes retrieved from UPnP device description
        self.device_type = discovery_info.get("deviceType")
        self.friendly_name = discovery_info.get("friendlyName")
        self.manufacturer = _first_scalar(
            discovery_info.get("manufacturer"), "BTicino S.p.A."
        )
        self.manufacturer_url = discovery_info.get("manufacturerURL")
        self.model_name = discovery_info.get("modelName", "Unknown model")
        self.model = self.model_name
        self.profile: GatewayProfile = get_gateway_profile(self.model_name)
        model_number = discovery_info.get("modelNumber")
        if isinstance(model_number, (list, tuple)):
            self.model_number = (
                ".".join(str(part) for part in model_number) if model_number else None
            )
        elif model_number is None:
            self.model_number = None
        else:
            self.model_number = str(model_number)
        # self.presentationURL = discovery_info.get("presentationURL")
        self.serial_number = discovery_info.get("serialNumber")
        self.udn = discovery_info.get("UDN")
        # Attributes retrieved from SOAP service control
        self.port = discovery_info.get("port") or self.profile.default_port

        self._log_id = f"[{self.model_name} gateway - {self.host}]"

    @property
    def unique_id(self) -> str | None:
        return self.serial_number

    @unique_id.setter
    def unique_id(self, unique_id: str) -> None:
        self.serial_number = unique_id

    @property
    def host(self) -> str | None:
        return self.address

    @host.setter
    def host(self, host: str) -> None:
        self.address = host

    @property
    def firmware(self) -> str | None:
        return self.model_number

    @firmware.setter
    def firmware(self, firmware: object) -> None:
        if isinstance(firmware, (list, tuple)):
            self.model_number = (
                ".".join(str(part) for part in firmware) if firmware else None
            )
        elif firmware is None:
            self.model_number = None
        else:
            self.model_number = str(firmware)

    @property
    def serial(self) -> str | None:
        return self.serial_number

    @serial.setter
    def serial(self, serial: str) -> None:
        self.serial_number = serial

    @property
    def password(self) -> str | None:
        return self._password

    @password.setter
    def password(self, password: str | None) -> None:
        self._password = str(password) if password not in (None, "") else None

    @property
    def log_id(self) -> str:
        return self._log_id

    @log_id.setter
    def log_id(self, value: str) -> None:
        self._log_id = value

    @classmethod
    async def get_first_available_gateway(
        cls, password: str | None = None
    ) -> OWNGateway | None:
        local_gateways = await find_gateways()
        if not local_gateways:
            return None
        local_gateways[0]["password"] = password
        return cls(local_gateways[0])

    @classmethod
    async def find_from_address(cls, address: str | None) -> OWNGateway | None:
        if address is not None:
            gateway = await get_gateway(address)
            return cls(gateway) if gateway is not None else None
        return await cls.get_first_available_gateway()

    @classmethod
    async def build_from_discovery_info(
        cls, discovery_info: Mapping[str, Any] | dict[str, Any]
    ) -> OWNGateway | None:
        # Work on our own copy: never mutate the caller's dict.
        discovery_info = dict(discovery_info)
        if (
            ("address" not in discovery_info or discovery_info["address"] is None)
            and "ssdp_location" in discovery_info
            and discovery_info["ssdp_location"] is not None
        ):
            discovery_info["address"] = urlparse(
                discovery_info["ssdp_location"]
            ).hostname

        if "port" in discovery_info and discovery_info["port"] is None:
            if (
                "ssdp_location" in discovery_info
                and discovery_info["ssdp_location"] is not None
            ):
                discovery_info["port"] = await get_port(discovery_info["ssdp_location"])
            elif "address" in discovery_info and discovery_info["address"] is not None:
                return await cls.find_from_address(discovery_info["address"])
            else:
                return await cls.get_first_available_gateway(
                    password=discovery_info.get("password")
                )

        return cls(discovery_info)

