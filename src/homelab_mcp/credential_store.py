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


def _keyring_key(username: str, hostname: str, scope: str, cluster_name: str) -> str:
    """Return the keyring key for a credential. Cluster scope uses the `@cluster:` form (D-03)."""
    if scope == "cluster":
        return f"{username}@cluster:{cluster_name}"
    return f"{username}@{hostname}"


def store_credential(
    hostname: str,
    username: str,
    password: str,
    credential_type: str = "ssh",
    *,
    scope: str = "node",
    cluster_name: str = "",
) -> bool:
    """Store a credential in the OS keyring.

    Returns True on success, False on headless fallback (never raises).

    Args:
        scope: "node" (default) or "cluster". When "cluster", the keyring key uses
            the ``f"{username}@cluster:{cluster_name}"`` form (D-03).
        cluster_name: Required when scope="cluster".
    """
    if scope not in ("node", "cluster"):
        raise ValueError(f"scope must be 'node' or 'cluster', got {scope!r}")
    if scope == "cluster" and not cluster_name:
        raise ValueError("scope='cluster' requires a non-empty cluster_name")
    service_name = _SERVICE_NAMES.get(credential_type, _SERVICE_NAME)
    identity = f"cluster:{cluster_name}" if scope == "cluster" else hostname
    try:
        import keyring  # noqa: PLC0415
        import keyring.errors  # noqa: PLC0415

        keyring.set_password(service_name, _keyring_key(username, hostname, scope, cluster_name), password)
        return True
    except keyring.errors.NoKeyringError:
        logger.warning("OS keyring unavailable (headless host) — credential not stored for %s", identity)
        return False
    except RuntimeError as exc:
        logger.warning("OS keyring runtime error — credential not stored for %s: %s", identity, exc)
        return False
    except Exception as exc:  # noqa: BLE001
        logger.warning("Unexpected keyring error — credential not stored for %s: %s", identity, exc)
        return False


def get_credential(
    hostname: str,
    username: str,
    credential_type: str = "ssh",
    *,
    scope: str = "node",
    cluster_name: str = "",
) -> str | None:
    """Retrieve a credential from the OS keyring.

    Returns the password string on success, None on headless fallback or missing
    entry (never raises).

    Args:
        scope: "node" (default) or "cluster". When "cluster", the keyring key uses
            the ``f"{username}@cluster:{cluster_name}"`` form (D-03).
        cluster_name: Required when scope="cluster".
    """
    if scope not in ("node", "cluster"):
        raise ValueError(f"scope must be 'node' or 'cluster', got {scope!r}")
    if scope == "cluster" and not cluster_name:
        raise ValueError("scope='cluster' requires a non-empty cluster_name")
    service_name = _SERVICE_NAMES.get(credential_type, _SERVICE_NAME)
    identity = f"cluster:{cluster_name}" if scope == "cluster" else hostname
    try:
        import keyring  # noqa: PLC0415
        import keyring.errors  # noqa: PLC0415

        result: str | None = keyring.get_password(service_name, _keyring_key(username, hostname, scope, cluster_name))
        return result
    except keyring.errors.NoKeyringError:
        logger.warning("OS keyring unavailable (headless host) — no credential for %s", identity)
        return None
    except RuntimeError as exc:
        logger.warning("OS keyring runtime error — returning None for %s: %s", identity, exc)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Unexpected keyring error — returning None for %s: %s", identity, exc)
        return None


def delete_credential(
    hostname: str,
    username: str,
    credential_type: str = "ssh",
    *,
    scope: str = "node",
    cluster_name: str = "",
) -> bool:
    """Delete a credential from the OS keyring.

    Returns True on success, False when entry does not exist (PasswordDeleteError)
    or when the keyring is unavailable (never raises).

    Args:
        scope: "node" (default) or "cluster". When "cluster", the keyring key uses
            the ``f"{username}@cluster:{cluster_name}"`` form (D-03).
        cluster_name: Required when scope="cluster".
    """
    if scope not in ("node", "cluster"):
        raise ValueError(f"scope must be 'node' or 'cluster', got {scope!r}")
    if scope == "cluster" and not cluster_name:
        raise ValueError("scope='cluster' requires a non-empty cluster_name")
    service_name = _SERVICE_NAMES.get(credential_type, _SERVICE_NAME)
    identity = f"cluster:{cluster_name}" if scope == "cluster" else hostname
    try:
        import keyring  # noqa: PLC0415
        import keyring.errors  # noqa: PLC0415
        from keyring.errors import PasswordDeleteError  # noqa: PLC0415

        keyring.delete_password(service_name, _keyring_key(username, hostname, scope, cluster_name))
        return True
    except PasswordDeleteError:
        return False  # credential didn't exist — not an error for callers
    except keyring.errors.NoKeyringError:
        logger.warning("OS keyring unavailable (headless host) — delete skipped for %s", identity)
        return False
    except RuntimeError as exc:
        logger.warning("OS keyring runtime error — delete skipped for %s: %s", identity, exc)
        return False
    except Exception as exc:  # noqa: BLE001
        logger.warning("Unexpected keyring error — delete skipped for %s: %s", identity, exc)
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
    *,
    scope: str = "node",
    cluster_name: str = "",
) -> None:
    """Record credential metadata in the registry (no password stored here).

    Upserts: replaces existing entry for same (hostname, username, credential_type)
    for per-node entries, or (cluster_name, username, credential_type) for cluster
    entries (D-08a).

    Args:
        hostname: Target host identifier. Set to "" for cluster-scoped entries (D-02).
        username: Account used on the target host.
        credential_type: "ssh" or "proxmox".
        auth_type: "password" (keyring stores password string) or "key"
            (keyring stores an SSH private-key filesystem path — D-09). Legacy
            entries without this field are treated as "password" by readers.
        scope: "node" (default, per-node credential) or "cluster" (cluster-scoped
            credential that serves all nodes in the named cluster). Legacy entries
            without this field are treated as "node" by readers
            (use ``.get("scope", "node")``).
        cluster_name: Required when scope="cluster". Identifies the Proxmox cluster
            this credential serves. Empty string for per-node entries. Legacy entries
            without this field default to "" (use ``.get("cluster_name", "")``) — D-01.
    """
    if auth_type not in ("password", "key"):
        raise ValueError(f"auth_type must be 'password' or 'key', got {auth_type!r}")
    if scope not in ("node", "cluster"):
        raise ValueError(f"scope must be 'node' or 'cluster', got {scope!r}")
    if scope == "cluster" and not cluster_name:
        raise ValueError("scope='cluster' requires a non-empty cluster_name")
    entries = _load_registry()
    if scope == "cluster":
        # Cluster entries dedup by (cluster_name, username, credential_type) — D-08a.
        # Do NOT compare hostname: a user may re-run with a different host arg (or none).
        entries = [
            e
            for e in entries
            if not (
                e.get("scope", "node") == "cluster"
                and e.get("cluster_name", "") == cluster_name
                and e["username"] == username
                and e["credential_type"] == credential_type
            )
        ]
    else:
        # Per-node entries dedup by (hostname, username, credential_type) — legacy behavior.
        # Exclude cluster entries from the match so a per-node and cluster entry with the
        # same username can coexist.
        entries = [
            e
            for e in entries
            if not (
                e.get("scope", "node") == "node"
                and e["hostname"] == hostname
                and e["username"] == username
                and e["credential_type"] == credential_type
            )
        ]
    entries.append(
        {
            "hostname": hostname,
            "username": username,
            "credential_type": credential_type,
            "auth_type": auth_type,
            "scope": scope,
            "cluster_name": cluster_name,
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

        Two additional optional fields follow the same back-compat pattern (D-01):
        ``scope`` (``"node"`` | ``"cluster"``) — use ``.get("scope", "node")``
        for legacy entries written before Phase 34 which lack this field.
        ``cluster_name`` (``str``) — use ``.get("cluster_name", "")``; empty
        string for per-node entries and for legacy rows.

        Returns empty list if registry file does not exist (fresh install).
    """
    return [e for e in _load_registry() if e["credential_type"] == credential_type]
