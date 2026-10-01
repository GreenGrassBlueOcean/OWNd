"""Pure authentication and cryptographic functions for OpenWebNet gateways."""

from __future__ import annotations

import hashlib


def int_string_to_hex_string(int_string: str) -> str:
    """Convert numeric ASCII pairs to hex string."""
    return "".join(f"{int(int_string[i:i+2]):x}" for i in range(0, len(int_string), 2))


def hex_string_to_int_string(hex_string: str) -> str:
    """Convert hex string to numeric ASCII pairs."""
    return "".join(f"{int(c, 16):0>2d}" for c in hex_string)


def calculate_open_password(
    password: str | int, nonce: str, test: bool = False
) -> int:
    """Calculate legacy numeric OPEN password response."""
    del test
    start = True
    num1 = 0
    num2 = 0
    password = int(password)
    for character in nonce:
        if character != "0":
            if start:
                num2 = password
            start = False
        if character == "1":
            num1 = (num2 & 0xFFFFFF80) >> 7
            num2 = num2 << 25
        elif character == "2":
            num1 = (num2 & 0xFFFFFFF0) >> 4
            num2 = num2 << 28
        elif character == "3":
            num1 = (num2 & 0xFFFFFFF8) >> 3
            num2 = num2 << 29
        elif character == "4":
            num1 = num2 << 1
            num2 = num2 >> 31
        elif character == "5":
            num1 = num2 << 5
            num2 = num2 >> 27
        elif character == "6":
            num1 = num2 << 12
            num2 = num2 >> 20
        elif character == "7":
            num1 = (
                num2 & 0x0000FF00
                | ((num2 & 0x000000FF) << 24)
                | ((num2 & 0x00FF0000) >> 16)
            )
            num2 = (num2 & 0xFF000000) >> 8
        elif character == "8":
            num1 = (num2 & 0x0000FFFF) << 16 | (num2 >> 24)
            num2 = (num2 & 0x00FF0000) >> 8
        elif character == "9":
            num1 = ~num2
        else:
            num1 = num2

        num1 &= 0xFFFFFFFF
        num2 &= 0xFFFFFFFF
        if character not in "09":
            num1 |= num2
        num2 = num1
    return num1


def encode_hmac_password(
    method: str, password: str, nonce_a: str, nonce_b: str
) -> str | None:
    """Encode client HMAC challenge response for SHA-1 or SHA-256."""
    # SHA-1 here is mandated by the OpenWebNet protocol: the gateway
    # selects the digest, the client cannot opt out. See nosec below.
    if method == "sha1":
        message = (
            int_string_to_hex_string(nonce_a)
            + int_string_to_hex_string(nonce_b)
            + "736F70653E"
            + "636F70653E"
            + hashlib.sha1(password.encode()).hexdigest()  # nosec B324
        )
        return hex_string_to_int_string(
            hashlib.sha1(message.encode()).hexdigest()  # nosec B324
        )
    if method == "sha256":
        message = (
            int_string_to_hex_string(nonce_a)
            + int_string_to_hex_string(nonce_b)
            + "736F70653E"
            + "636F70653E"
            + hashlib.sha256(password.encode()).hexdigest()
        )
        return hex_string_to_int_string(
            hashlib.sha256(message.encode()).hexdigest()
        )
    return None


def decode_hmac_response(
    method: str, password: str, nonce_a: str, nonce_b: str
) -> str | None:
    """Decode expected gateway HMAC response for mutual authentication."""
    # SHA-1 here is mandated by the OpenWebNet protocol: the gateway
    # selects the digest, the client cannot opt out. See nosec below.
    if method == "sha1":
        message = (
            int_string_to_hex_string(nonce_a)
            + int_string_to_hex_string(nonce_b)
            + hashlib.sha1(password.encode()).hexdigest()  # nosec B324
        )
        return hex_string_to_int_string(
            hashlib.sha1(message.encode()).hexdigest()  # nosec B324
        )
    if method == "sha256":
        message = (
            int_string_to_hex_string(nonce_a)
            + int_string_to_hex_string(nonce_b)
            + hashlib.sha256(password.encode()).hexdigest()
        )
        return hex_string_to_int_string(
            hashlib.sha256(message.encode()).hexdigest()
        )
    return None
