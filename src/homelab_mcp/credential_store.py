"""Headless-safe OS keyring wrapper for homelab-mcp credential storage.

Exposes store_credential, get_credential, and delete_credential. Every function
returns a safe fallback value (None or False) rather than propagating any
exception when the OS keyring is unavailable (headless Linux, no D-Bus session).

No keyring imports at module level — all imports are lazy (inside each function
body) to avoid D-Bus probing during server startup.
"""

import logging

logger = logging.getLogger(__name__)

_SERVICE_NAME = "homelab-mcp"


def store_credential(hostname: str, username: str, password: str) -> bool:
    """Store a credential in the OS keyring.

    Returns True on success, False on headless fallback (never raises).
    """
    try:
        import keyring  # noqa: PLC0415
        import keyring.errors  # noqa: PLC0415

        keyring.set_password(_SERVICE_NAME, f"{username}@{hostname}", password)
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


def get_credential(hostname: str, username: str) -> str | None:
    """Retrieve a credential from the OS keyring.

    Returns the password string on success, None on headless fallback or missing
    entry (never raises).
    """
    try:
        import keyring  # noqa: PLC0415
        import keyring.errors  # noqa: PLC0415

        result: str | None = keyring.get_password(_SERVICE_NAME, f"{username}@{hostname}")
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


def delete_credential(hostname: str, username: str) -> bool:
    """Delete a credential from the OS keyring.

    Returns True on success, False when entry does not exist (PasswordDeleteError)
    or when the keyring is unavailable (never raises).
    """
    try:
        import keyring  # noqa: PLC0415
        import keyring.errors  # noqa: PLC0415
        from keyring.errors import PasswordDeleteError  # noqa: PLC0415

        keyring.delete_password(_SERVICE_NAME, f"{username}@{hostname}")
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
