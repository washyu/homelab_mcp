"""Headless-safe OS keyring wrapper for homelab-mcp credential storage.

Exposes store_credential, get_credential, and delete_credential. Every function
returns a safe fallback value (None or False) rather than propagating any
exception when the OS keyring is unavailable (headless Linux, no D-Bus session).

No keyring imports at module level — all imports are lazy (inside each function
body) to avoid D-Bus probing during server startup.
"""

import json
import logging
import pathlib

logger = logging.getLogger(__name__)

_SERVICE_NAME = "homelab-mcp"  # keep for backward compat
_SERVICE_NAMES: dict[str, str] = {
    "ssh": "homelab-mcp",
    "proxmox": "homelab-mcp-proxmox",
}
_REGISTRY_PATH = pathlib.Path.home() / ".homelab_mcp" / "credential_registry.json"


def store_credential(hostname: str, username: str, password: str, credential_type: str = "ssh") -> bool:
    """Store a credential in the OS keyring.

    Returns True on success, False on headless fallback (never raises).
    """
    service_name = _SERVICE_NAMES.get(credential_type, _SERVICE_NAME)
    try:
        import keyring  # noqa: PLC0415
        import keyring.errors  # noqa: PLC0415

        keyring.set_password(service_name, f"{username}@{hostname}", password)
        return True
    except keyring.errors.NoKeyringError:
        logger.warning("OS keyring unavailable (headless host) — credential not stored for %s", hostname)
        return False
    except RuntimeError as exc:
        logger.warning("OS keyring runtime error — credential not stored for %s: %s", hostname, exc)
        return False
    except Exception as exc:  # noqa: BLE001
        logger.warning("Unexpected keyring error — credential not stored for %s: %s", hostname, exc)
        return False


def get_credential(hostname: str, username: str, credential_type: str = "ssh") -> str | None:
    """Retrieve a credential from the OS keyring.

    Returns the password string on success, None on headless fallback or missing
    entry (never raises).
    """
    service_name = _SERVICE_NAMES.get(credential_type, _SERVICE_NAME)
    try:
        import keyring  # noqa: PLC0415
        import keyring.errors  # noqa: PLC0415

        result: str | None = keyring.get_password(service_name, f"{username}@{hostname}")
        return result
    except keyring.errors.NoKeyringError:
        logger.warning("OS keyring unavailable (headless host) — no credential for %s", hostname)
        return None
    except RuntimeError as exc:
        logger.warning("OS keyring runtime error — returning None for %s: %s", hostname, exc)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Unexpected keyring error — returning None for %s: %s", hostname, exc)
        return None


def delete_credential(hostname: str, username: str, credential_type: str = "ssh") -> bool:
    """Delete a credential from the OS keyring.

    Returns True on success, False when entry does not exist (PasswordDeleteError)
    or when the keyring is unavailable (never raises).
    """
    service_name = _SERVICE_NAMES.get(credential_type, _SERVICE_NAME)
    try:
        import keyring  # noqa: PLC0415
        import keyring.errors  # noqa: PLC0415
        from keyring.errors import PasswordDeleteError  # noqa: PLC0415

        keyring.delete_password(service_name, f"{username}@{hostname}")
        return True
    except PasswordDeleteError:
        return False  # credential didn't exist — not an error for callers
    except keyring.errors.NoKeyringError:
        logger.warning("OS keyring unavailable (headless host) — delete skipped for %s", hostname)
        return False
    except RuntimeError as exc:
        logger.warning("OS keyring runtime error — delete skipped for %s: %s", hostname, exc)
        return False
    except Exception as exc:  # noqa: BLE001
        logger.warning("Unexpected keyring error — delete skipped for %s: %s", hostname, exc)
        return False


def _load_registry() -> list[dict[str, str]]:
    """Load credential registry from JSON file. Returns empty list if missing or unreadable."""
    if not _REGISTRY_PATH.exists():
        return []
    try:
        return json.loads(_REGISTRY_PATH.read_text())  # type: ignore[no-any-return]
    except Exception:  # noqa: BLE001
        logger.warning("Credential registry unreadable — returning empty list")
        return []


def _save_registry(entries: list[dict[str, str]]) -> None:
    """Persist credential registry to JSON file."""
    _REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    _REGISTRY_PATH.write_text(json.dumps(entries, indent=2))


def register_credential(
    hostname: str,
    username: str,
    credential_type: str = "ssh",
    auth_type: str = "password",
) -> None:
    """Record credential metadata in the registry (no password stored here).

    Upserts: replaces existing entry for same (hostname, username, credential_type).

    Args:
        hostname: Target host identifier.
        username: Account used on the target host.
        credential_type: "ssh" or "proxmox".
        auth_type: "password" (keyring stores password string) or "key"
            (keyring stores an SSH private-key filesystem path — D-09). Legacy
            entries without this field are treated as "password" by readers.
    """
    if auth_type not in ("password", "key"):
        raise ValueError(f"auth_type must be 'password' or 'key', got {auth_type!r}")
    entries = _load_registry()
    entries = [
        e
        for e in entries
        if not (e["hostname"] == hostname and e["username"] == username and e["credential_type"] == credential_type)
    ]
    entries.append(
        {
            "hostname": hostname,
            "username": username,
            "credential_type": credential_type,
            "auth_type": auth_type,
        }
    )
    _save_registry(entries)


def unregister_credential(hostname: str, credential_type: str = "ssh") -> None:
    """Remove all registry entries matching hostname + credential_type."""
    entries = _load_registry()
    entries = [e for e in entries if not (e["hostname"] == hostname and e["credential_type"] == credential_type)]
    _save_registry(entries)


def list_credentials(credential_type: str = "ssh") -> list[dict[str, str]]:
    """Return all registry entries for the given credential type.

    Returns:
        List of dicts with keys: ``hostname``, ``username``, ``credential_type``,
        and optionally ``auth_type`` (``"password"`` | ``"key"``) — entries
        written before v1.6 lack this field and should be treated as
        ``"password"`` (use ``.get("auth_type", "password")``).

        Returns empty list if registry file does not exist (fresh install).
    """
    return [e for e in _load_registry() if e["credential_type"] == credential_type]
