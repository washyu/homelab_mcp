"""Centralized SSH connection helper with TOFU host key verification.

Implements Trust-On-First-Use (TOFU) for SSH host keys:
- First connection to a new host accepts and stores the host key
- Subsequent connections to known hosts verify against stored keys
- Changed keys are rejected (possible MITM attack)

All SSH connections in the codebase should use ssh_connect() from this module.
"""

import logging
import threading
from pathlib import Path
from typing import Any

import asyncssh

from .validation import validate_hostname, validate_port

logger = logging.getLogger(__name__)

# Default known_hosts file location (alongside the homelab database)
KNOWN_HOSTS_PATH = Path.home() / ".homelab_mcp" / "known_hosts"

# Module-level lock to prevent race conditions on concurrent TOFU
_tofu_lock = threading.Lock()


class TOFUSSHClient(asyncssh.SSHClient):
    """SSH client implementing Trust-On-First-Use host key verification.

    When asyncssh encounters a host key NOT in the known_hosts file, it calls
    validate_host_public_key(). This class checks if any key is already stored
    for the host (key mismatch = reject) or stores the new key (TOFU accept).
    """

    def __init__(self, known_hosts_path: Path) -> None:
        """Initialize with path to known_hosts file.

        Args:
            known_hosts_path: Path to the known_hosts file for key storage.
        """
        super().__init__()
        self._known_hosts_path = known_hosts_path

    def validate_host_public_key(
        self,
        host: str,
        addr: Any,
        port: int,
        key: asyncssh.SSHKey,
    ) -> bool:
        """Validate a host public key not found in known_hosts file.

        Called by asyncssh when the host key is NOT in the known_hosts file.
        If a different key was previously stored for this host, reject (MITM).
        If no key exists, store it (TOFU) and accept.

        The entire check-then-store sequence is protected by ``_tofu_lock`` to
        prevent concurrent first-connections from writing conflicting host keys.

        Args:
            host: The hostname being connected to.
            addr: The address being connected to (may be None).
            port: The port being connected to.
            key: The host's public key.

        Returns:
            True if the key should be accepted, False to reject.
        """
        with _tofu_lock:
            host_label = self._format_host_label(host, port)

            # Check if any key already exists for this host (key mismatch case)
            if self._host_has_stored_key(host, port):
                logger.warning(
                    "Host key mismatch for %s -- possible MITM attack. Connection rejected.",
                    host_label,
                )
                return False

            # No key stored -- TOFU: accept and store
            self._store_host_key(host, port, key)
            logger.info("TOFU: Accepted and stored host key for %s", host_label)
            return True

    def _host_has_stored_key(self, host: str, port: int) -> bool:
        """Check if any key is already stored for this host.

        Args:
            host: The hostname to check.
            port: The port to check.

        Returns:
            True if a key entry exists for this host/port.
        """
        host_label = self._format_host_label(host, port)

        if not self._known_hosts_path.exists():
            return False

        try:
            content = self._known_hosts_path.read_text()
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) >= 2 and parts[0] == host_label:
                    return True
        except OSError:
            logger.error("Failed to read known_hosts file: %s", self._known_hosts_path)

        return False

    def _store_host_key(self, host: str, port: int, key: asyncssh.SSHKey) -> None:
        """Store a host key in the known_hosts file.

        Caller must hold ``_tofu_lock`` before calling this method.

        Args:
            host: The hostname.
            port: The port.
            key: The host's public key to store.
        """
        host_label = self._format_host_label(host, port)

        # Extract key data from the public key export
        key_export = key.export_public_key().decode("utf-8").strip()
        # Strip trailing comment field -- known_hosts requires exactly "algorithm base64"
        parts = key_export.split()
        key_data = " ".join(parts[:2])
        entry = f"{host_label} {key_data}\n"

        try:
            with open(self._known_hosts_path, "a") as f:
                f.write(entry)
        except OSError:
            logger.error("Failed to write to known_hosts file: %s", self._known_hosts_path)

    @staticmethod
    def _format_host_label(host: str, port: int) -> str:
        """Format hostname for known_hosts file.

        Standard port 22 uses plain hostname. Non-standard ports use
        [hostname]:port format per OpenSSH convention.

        Args:
            host: The hostname.
            port: The port number.

        Returns:
            Formatted host label string.
        """
        if port == 22:
            return host
        return f"[{host}]:{port}"


async def ssh_connect(
    hostname: str,
    username: str = "mcp_admin",
    port: int = 22,
    password: str | None = None,
    key_path: str | None = None,
    known_hosts_path: Path | None = None,
    connect_timeout: int = 10,
) -> asyncssh.SSHClientConnection:
    """Create an SSH connection with TOFU host key verification.

    Centralized SSH connection helper that ensures all connections use
    proper host key verification via Trust-On-First-Use.

    Args:
        hostname: Target hostname or IP address.
        username: SSH username (default: mcp_admin).
        port: SSH port (default: 22).
        password: SSH password (optional).
        key_path: Path to SSH private key (optional).
        known_hosts_path: Path to known_hosts file (default: ~/.homelab_mcp/known_hosts).
        connect_timeout: Connection timeout in seconds (default: 10).

    Returns:
        An asyncssh.SSHClientConnection instance.
    """
    validate_hostname(hostname)
    validate_port(port)

    kh_path = known_hosts_path or KNOWN_HOSTS_PATH

    # Ensure known_hosts file and parent directory exist
    kh_path.parent.mkdir(parents=True, exist_ok=True)
    if not kh_path.exists():
        kh_path.touch()

    # Build connection kwargs
    connect_kwargs: dict[str, Any] = {
        "host": hostname,
        "username": username,
        "port": port,
        "known_hosts": str(kh_path),
        "client_factory": lambda: TOFUSSHClient(kh_path),
        "connect_timeout": connect_timeout,
    }

    if password:
        connect_kwargs["password"] = password

    if key_path:
        connect_kwargs["client_keys"] = [key_path]

    return await asyncssh.connect(**connect_kwargs)
