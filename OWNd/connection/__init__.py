"""This module handles TCP connections to the OpenWebNet gateway."""

from __future__ import annotations

# Standard library and utility imports retained exclusively for backwards compatibility
# with consumer test suites and legacy mock/patch targets (e.g., patch("OWNd.connection.time"),
# patch("OWNd.connection.socket"), patch("OWNd.connection.asyncio")).
# While not directly referenced in this module's runtime logic, _ConnectionModule forwards
# patched attributes to underlying submodules. DO NOT REMOVE or "clean up" these imports.
import asyncio
import contextlib
import hashlib
import hmac
import logging
import secrets
import socket
import string
import sys
import time
from collections.abc import Callable, Mapping
from types import ModuleType
from typing import Any
from urllib.parse import urlparse

from . import auth, command_session, event_session, gateway, session
from .auth import (
    calculate_open_password,
    decode_hmac_response,
    encode_hmac_password,
    hex_string_to_int_string,
    int_string_to_hex_string,
)
from .command_session import OWNCommandSession
from .event_session import OWNEventSession
from .gateway import OWNGateway, _first_scalar
from .session import (
    COMMAND_RESPONSE_MAX_FRAMES,
    COMMAND_TIMEOUT,
    CONNECT_TIMEOUT,
    DROP_BURST_COUNT,
    DROP_BURST_WINDOW,
    DROP_WARNING_INTERVAL,
    EVENT_INACTIVITY_TIMEOUT,
    EVENT_KEEPALIVE_FRAME,
    KEEPALIVE_FRAME,
    KEEPALIVE_INTERVAL,
    MAX_CONNECT_ATTEMPTS,
    NEGOTIATION_MAX_FRAMES,
    NEGOTIATION_TIMEOUT,
    NEGOTIATION_TOTAL_TIMEOUT,
    OWNSession,
    RECONNECT_PAUSE,
    RECONNECT_PAUSE_FATAL,
    TCP_KEEPALIVE_CNT,
    TCP_KEEPALIVE_IDLE,
    TCP_KEEPALIVE_INTVL,
    _FATAL_NEGOTIATION_ERRORS,
)
from ..discovery import find_gateways, get_gateway, get_port
from ..message import OWNMessage, OWNSignaling
from ..profiles import GatewayProfile, get_gateway_profile

__all__ = [
    # Gateway container
    "OWNGateway",
    # Sessions
    "OWNSession",
    "OWNEventSession",
    "OWNCommandSession",
    # Constants
    "NEGOTIATION_TIMEOUT",
    "NEGOTIATION_TOTAL_TIMEOUT",
    "NEGOTIATION_MAX_FRAMES",
    "COMMAND_TIMEOUT",
    "COMMAND_RESPONSE_MAX_FRAMES",
    "CONNECT_TIMEOUT",
    "MAX_CONNECT_ATTEMPTS",
    "KEEPALIVE_FRAME",
    "KEEPALIVE_INTERVAL",
    "EVENT_KEEPALIVE_FRAME",
    "EVENT_INACTIVITY_TIMEOUT",
    "TCP_KEEPALIVE_IDLE",
    "TCP_KEEPALIVE_INTVL",
    "TCP_KEEPALIVE_CNT",
    "_FATAL_NEGOTIATION_ERRORS",
    "RECONNECT_PAUSE",
    "RECONNECT_PAUSE_FATAL",
    "DROP_BURST_COUNT",
    "DROP_BURST_WINDOW",
    "DROP_WARNING_INTERVAL",
    "_first_scalar",
    # Profiles & Discovery re-exports
    "GatewayProfile",
    "get_gateway_profile",
    "find_gateways",
    "get_gateway",
    "get_port",
    # Message re-exports
    "OWNMessage",
    "OWNSignaling",
    # Auth helpers
    "calculate_open_password",
    "decode_hmac_response",
    "encode_hmac_password",
    "hex_string_to_int_string",
    "int_string_to_hex_string",
]


_FORWARD_TARGETS: dict[str, tuple[str, ...]] = {
    "time": ("session",),
    "socket": ("session",),
    "asyncio": ("session",),
    "secrets": ("session",),
    "hashlib": ("auth",),
    "hmac": ("session",),
    "string": ("session",),
    "logging": ("session", "gateway"),
    "urlparse": ("gateway", "session"),
    "find_gateways": ("gateway",),
    "get_gateway": ("gateway",),
    "get_port": ("gateway",),
    "GatewayProfile": ("gateway", "session"),
    "get_gateway_profile": ("gateway", "session"),
}


class _ConnectionModule(ModuleType):
    """Proxy module synchronizing mocked attributes with submodules.

    Ensures 100% backward compatibility when test suites or consumers patch
    attributes directly on ``OWNd.connection`` (e.g. ``time``, ``find_gateways``,
    ``NEGOTIATION_MAX_FRAMES``).
    """

    def _get_submodules(self) -> list[ModuleType]:
        """Dynamically resolve all loaded connection submodules."""
        pkg = self.__name__
        return [
            mod
            for name, mod in list(sys.modules.items())
            if name.startswith(f"{pkg}.")
            and isinstance(mod, ModuleType)
            and mod.__name__ != pkg
        ]

    def __getattr__(self, name: str) -> Any:
        for mod in self._get_submodules():
            if hasattr(mod, name):
                return getattr(mod, name)
        raise AttributeError(f"module '{self.__name__}' has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("__") and name.endswith("__"):
            super().__setattr__(name, value)
            return

        if name in _FORWARD_TARGETS:
            pkg = self.__name__
            for sub_name in _FORWARD_TARGETS[name]:
                target_mod = sys.modules.get(f"{pkg}.{sub_name}")
                if target_mod is None or not hasattr(target_mod, name):
                    raise AttributeError(
                        f"Patched attribute '{name}' missing from expected target submodule '{sub_name}'"
                    )

        all_attrs = getattr(self, "__all__", ())
        submodules = self._get_submodules()
        if name in all_attrs and submodules:
            if not any(hasattr(mod, name) for mod in submodules):
                raise AttributeError(
                    f"Patched attribute '{name}' in __all__ is missing from all connection submodules"
                )

        super().__setattr__(name, value)
        for mod in submodules:
            if hasattr(mod, name):
                setattr(mod, name, value)

    def __delattr__(self, name: str) -> None:
        if name.startswith("__") and name.endswith("__"):
            super().__delattr__(name)
            return

        deleted = False
        with contextlib.suppress(AttributeError):
            super().__delattr__(name)
            deleted = True

        for mod in self._get_submodules():
            if hasattr(mod, name):
                with contextlib.suppress(AttributeError):
                    delattr(mod, name)
                    deleted = True

        if not deleted:
            raise AttributeError(f"module '{self.__name__}' has no attribute '{name}'")

    def __dir__(self) -> list[str]:
        attrs = set(super().__dir__())
        for mod in self._get_submodules():
            attrs.update(dir(mod))
        return sorted(attrs)


sys.modules[__name__].__class__ = _ConnectionModule

