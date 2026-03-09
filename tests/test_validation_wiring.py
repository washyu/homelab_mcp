"""Tests verifying validation.py is wired into production code paths.

These tests prove that invalid hostnames, ports, and network addresses are
rejected before reaching SSH/HTTP operations (SEC-03).
"""

import pytest

from homelab_mcp.ssh_connection import ssh_connect


@pytest.mark.asyncio
async def test_ssh_connect_rejects_invalid_hostname() -> None:
    """ssh_connect rejects shell-injectable hostnames."""
    with pytest.raises(ValueError, match="invalid"):
        await ssh_connect("host; rm -rf /")


@pytest.mark.asyncio
async def test_ssh_connect_rejects_empty_hostname() -> None:
    """ssh_connect rejects empty hostnames."""
    with pytest.raises(ValueError, match="empty"):
        await ssh_connect("")


@pytest.mark.asyncio
async def test_ssh_connect_rejects_invalid_port() -> None:
    """ssh_connect rejects out-of-range ports."""
    with pytest.raises(ValueError, match="65535"):
        await ssh_connect("valid-host", port=99999)


@pytest.mark.asyncio
async def test_ssh_connect_rejects_zero_port() -> None:
    """ssh_connect rejects port 0."""
    with pytest.raises(ValueError, match="between 1 and 65535"):
        await ssh_connect("valid-host", port=0)
