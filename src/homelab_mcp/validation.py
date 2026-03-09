"""Input validation for hostnames, IP addresses, and ports (SEC-03).

Provides strict validation for network identifiers before they reach SSH/HTTP
operations. Uses Python stdlib only (ipaddress, re).
"""

from __future__ import annotations

import ipaddress
import logging
import re

logger = logging.getLogger(__name__)

# RFC 1123 hostname label: 1-63 chars, alphanumeric + hyphens, no leading/trailing hyphen.
_LABEL_RE = re.compile(r"^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$")

# Characters that should never appear in a hostname (shell metacharacters, whitespace).
_DANGEROUS_CHARS = re.compile(r"[;\s|&$`\"'\\<>(){}!\[\]#~*?]")


def validate_hostname(value: str) -> str:
    """Validate and return a hostname or IP address.

    Accepts:
        - IPv4 addresses (192.168.1.1)
        - IPv6 addresses (::1, fe80::1)
        - RFC 1123 hostnames with any TLD (.local, .internal, etc.)

    Raises:
        ValueError: If the hostname/IP is invalid with a clear message.
    """
    if not value:
        raise ValueError("Hostname must not be empty")

    if len(value) > 253:
        raise ValueError(f"Hostname exceeds 253 characters (got {len(value)})")

    # Check for dangerous characters first (catches shell injection attempts).
    if _DANGEROUS_CHARS.search(value):
        raise ValueError(
            f"Hostname contains invalid characters: {value!r}"
        )

    # Try parsing as an IP address (IPv4 or IPv6).
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError:
        logger.debug("Value %r is not a valid IP address, trying hostname validation", value)

    # Validate as hostname: split into labels, check each.
    labels = value.split(".")
    for label in labels:
        if not label:
            raise ValueError(f"Hostname has empty label: {value!r}")
        if not _LABEL_RE.match(label):
            raise ValueError(
                f"Invalid hostname label {label!r} in {value!r}: "
                "labels must be 1-63 alphanumeric characters with internal hyphens only"
            )

    return value


def validate_port(value: int) -> int:
    """Validate and return a TCP/UDP port number.

    Accepts ports in range 1-65535.

    Raises:
        ValueError: If the port is out of range.
    """
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"Port must be an integer, got {type(value).__name__}")
    if value < 1 or value > 65535:
        raise ValueError(f"Port must be between 1 and 65535, got {value}")
    return value


def validate_ip_network(value: str, strict: bool = False) -> str:
    """Validate and return a CIDR network string.

    Args:
        value: Network in CIDR notation (e.g. "192.168.1.0/24").
        strict: If True, reject addresses with host bits set.

    Raises:
        ValueError: If the network is invalid.
    """
    try:
        network = ipaddress.ip_network(value, strict=strict)
        return str(network)
    except ValueError as e:
        raise ValueError(f"Invalid IP network {value!r}: {e}") from e
