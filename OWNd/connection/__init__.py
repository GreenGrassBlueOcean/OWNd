"""This module handles TCP connections to the OpenWebNet gateway."""

from __future__ import annotations

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


class _ConnectionModule(ModuleType):
    """Proxy module synchronizing mocked attributes with submodules.

    Ensures 100% backward compatibility when test suites or consumers patch
    attributes directly on ``OWNd.connection`` (e.g. ``time``, ``find_gateways``,
    ``NEGOTIATION_MAX_FRAMES``).
    """

    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)
        for mod in (auth, command_session, event_session, gateway, session):
            if hasattr(mod, name):
                setattr(mod, name, value)

    def __delattr__(self, name: str) -> None:
        super().__delattr__(name)
        for mod in (auth, command_session, event_session, gateway, session):
            if hasattr(mod, name):
                with contextlib.suppress(AttributeError):
                    delattr(mod, name)


sys.modules[__name__].__class__ = _ConnectionModule

