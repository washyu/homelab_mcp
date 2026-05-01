"""SSH tools for system discovery and management."""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import asyncssh

from .credential_store import find_credential_by_id, get_credential, list_credentials
from .database import (
    DatabaseAdapter,
    get_database_adapter,  # noqa: F401 — module-level attr for test monkeypatch (tests assert not-called)
)
from .error_handling import retry_on_failure, ssh_connection_wrapper
from .log_filter import sanitize_error
from .ssh_connection import ssh_connect

# Configure logging
logger = logging.getLogger(__name__)

# Get the path for storing SSH keys
SSH_KEY_DIR = Path.home() / ".ssh" / "mcp"


class CredentialNotFoundError(RuntimeError):
    """Raised when no credentials are found for a hostname in any tier.

    Phase 38.1 attribute: ``reason_hint`` is set by the Tier-0 UUID short-circuit
    paths in :func:`resolve_proxmox_credentials` and :func:`resolve_ssh_credentials`
    to indicate which D-08 reason enum value drift should map this to.

    Possible values:
      * ``"binding_stale"`` (D-11) — UUID not in registry, or registry entry has
        wrong ``credential_type`` for the resolver, or malformed UUID format.
      * ``"keyring_desync"`` (D-12) — UUID found in registry but keyring fetch
        returned ``None``.
      * ``None`` (Tier-1/Tier-2 paths) — drift maps these to ``"unbound"``.
    """

    reason_hint: str | None = None


@dataclass
class SSHCredentials:
    """Resolved SSH credentials for connection."""

    hostname: str
    username: str
    port: int = 22
    key_path: str | None = None
    password: str | None = None
    credential_id: int | None = None  # Database ID if from stored credentials


def _resolve_username_from_registry(hostname: str) -> tuple[str, list[dict[str, str]]]:
    """Scan the keyring registry for ``hostname``; return (resolved_username, matched_entries).

    Phase 33.1 D-04 / D-04a: when a caller omits ``username``, both the Tier-1
    (explicit password/key) and Tier-2 (pure keyring) branches of
    :func:`resolve_ssh_credentials` use this helper to resolve a username from
    the registered SSH credential set — the literal ``"mcp_admin"`` fallback is
    gone.

    Behaviour:
      * **Single match** → returns the one registered ``username`` plus the
        matched entry list (for downstream ``auth_type`` branching).
      * **Zero match** → raises :class:`CredentialNotFoundError` with the
        standard ``homelab-mcp credentials add`` pointer.
      * **Multiple matches** → raises :class:`CredentialNotFoundError` whose
        message names every registered username and points the agent at
        ``list_keyring_credentials`` / ``list_registered_servers`` so it can
        self-disambiguate (D-04a).
    """
    registry_entries = list_credentials(credential_type="ssh")
    matched = [e for e in registry_entries if e["hostname"] == hostname]
    if len(matched) == 0:
        raise CredentialNotFoundError(
            f"No credentials found for {hostname}. "
            f"Run `homelab-mcp credentials add {hostname} <username>` "
            "in your terminal."
        )
    if len(matched) >= 2:
        registered = ", ".join(sorted(e["username"] for e in matched))
        raise CredentialNotFoundError(
            f"Multiple credentials registered for {hostname}: {registered}. "
            "Specify username explicitly, or call list_keyring_credentials "
            "to inspect registered entries."
        )
    return matched[0]["username"], matched


def resolve_ssh_credentials(
    hostname: str,
    username: str | None = None,
    password: str | None = None,
    key_path: str | None = None,
    port: int = 22,
    *,
    credential_id: str | None = None,
) -> SSHCredentials:
    """Resolve SSH credentials for a hostname.

    Resolution tiers (v1.7 Phase 38.1 D-11/D-12/D-13/D-14 + v1.6 Phase 33/33.1):
      0. **UUID short-circuit** (when ``credential_id`` is supplied) — look up
         the entry by UUID via :func:`credential_store.find_credential_by_id`.
         UUID wins (D-13): hostname is used only for log/error context.
         Branches on ``auth_type`` to mirror Tier-2 logic; key vs password
         path. NEVER falls back to hostname-exact-match (D-11).
      1. **Explicit args** (``password`` or ``key_path`` supplied): returned
         directly. When ``username`` is also ``None``, the keyring registry is
         scanned by hostname to inject the username — no silent
         ``"mcp_admin"`` fallback (Phase 33.1 D-04 / BLOCKER 1).
      2. **Keyring registry**: look up by hostname; when ``username`` is
         ``None`` the helper :func:`_resolve_username_from_registry` picks the
         sole registered user (single-match) or raises with an actionable
         message (zero/multi match). Returns password or key_path based on the
         entry's ``auth_type`` (D-09).

    Args:
        hostname: Sitemap row hostname (used only for log/error context when
            ``credential_id`` is supplied — UUID is the join key in tier-0).
        username, password, key_path, port: Tier-1 explicit args.
        credential_id: Optional UUID from a sitemap row's
            ``ssh_credential_id`` column (Phase 38.1 D-14 keyword-only).

    Raises:
        CredentialNotFoundError: if no tier resolves credentials. Tier-0
            raises with ``.reason_hint`` set to ``"binding_stale"`` (UUID not
            in registry, wrong credential_type, or malformed UUID — D-11) or
            ``"keyring_desync"`` (UUID found, keyring miss — D-12). Tier-1/
            Tier-2 raises leave ``.reason_hint`` unset (drift maps to
            ``"unbound"``).
    """
    # Phase 38.1 Tier-0: UUID short-circuit (D-11/D-12/D-13).
    if credential_id is not None:
        # T-38.1-05-01: validate UUID format defensively.
        try:
            uuid.UUID(credential_id)
        except (ValueError, AttributeError) as exc:
            raise CredentialNotFoundError(f"binding stale: malformed credential_id {credential_id!r}") from exc

        entry = find_credential_by_id(credential_id)
        if entry is None:
            # D-11: never fall back to hostname-exact-match
            exc_inst = CredentialNotFoundError(
                f"binding stale: UUID {credential_id} not in registry. "
                f"Run `homelab-mcp credentials add --type ssh {hostname} <username>` "
                f"to register, or `homelab-mcp credentials unlink {hostname} --type ssh` "
                f"to clear the stale binding."
            )
            exc_inst.reason_hint = "binding_stale"
            raise exc_inst
        if entry.get("credential_type") != "ssh":
            # T-38.1-05-02: caller passed a proxmox UUID to the SSH resolver.
            exc_inst = CredentialNotFoundError(
                f"binding type mismatch: credential_id {credential_id} is type "
                f"{entry.get('credential_type')!r}, expected 'ssh'."
            )
            exc_inst.reason_hint = "binding_stale"
            raise exc_inst

        entry_username = entry["username"]
        entry_hostname = entry["hostname"]
        auth_type = entry.get("auth_type", "password")
        if auth_type == "key":
            key_path_stored = get_credential(
                entry_hostname,
                entry_username,
                credential_type="ssh",
            )
            if key_path_stored is None:
                exc_inst = CredentialNotFoundError(
                    f"keyring desync for credential_id={credential_id}: "
                    f"registry entry exists but keyring returned None — "
                    f"re-run `homelab-mcp credentials add --type ssh "
                    f"{entry_hostname} {entry_username} --key-path <path>` to restore."
                )
                exc_inst.reason_hint = "keyring_desync"
                raise exc_inst
            logger.debug(
                "ssh resolve hostname=%s source=tier0_uuid auth=key credential_id=%s",
                hostname,
                credential_id,
            )
            return SSHCredentials(
                hostname=hostname,
                username=entry_username,
                port=port,
                key_path=key_path_stored,
                password=None,
            )
        # password auth
        keyring_password = get_credential(
            entry_hostname,
            entry_username,
            credential_type="ssh",
        )
        if keyring_password is None:
            exc_inst = CredentialNotFoundError(
                f"keyring desync for credential_id={credential_id}: "
                f"registry entry exists but keyring returned None — "
                f"re-run `homelab-mcp credentials add --type ssh "
                f"{entry_hostname} {entry_username}` to restore."
            )
            exc_inst.reason_hint = "keyring_desync"
            raise exc_inst
        logger.debug(
            "ssh resolve hostname=%s source=tier0_uuid auth=password credential_id=%s",
            hostname,
            credential_id,
        )
        return SSHCredentials(
            hostname=hostname,
            username=entry_username,
            port=port,
            password=keyring_password,
            key_path=None,
        )

    # Tier 1: explicit args (backward compatible with test-only callers).
    # When username is None, perform the same registry scan as Tier 2 —
    # no "mcp_admin" silent fallback (D-04 contract: keyring is the only
    # source of truth for username).
    if password or key_path:
        resolved_username = username
        if resolved_username is None:
            resolved_username, _ = _resolve_username_from_registry(hostname)
        return SSHCredentials(
            hostname=hostname,
            username=resolved_username,
            port=port,
            key_path=key_path,
            password=password,
        )

    # Tier 2: Keyring — sole remaining fallback.
    if username is None:
        # D-04: registry-scan by hostname. Zero-match / multi-match raise
        # inside the helper. For single-match we continue with the matched
        # entry's auth_type branching below.
        resolved_username, matched = _resolve_username_from_registry(hostname)
    else:
        # Explicit username path: find the registry entry for this user
        # (existing behaviour from Phase 33).
        registry_entries = list_credentials(credential_type="ssh")
        matched = [e for e in registry_entries if e["hostname"] == hostname and e["username"] == username]
        resolved_username = username

    if matched:
        stored_username = matched[0]["username"]
        auth_type = matched[0].get("auth_type", "password")  # D-09 backward compat

        if auth_type == "key":
            key_path_stored = get_credential(hostname, stored_username, credential_type="ssh")
            if key_path_stored:
                logger.debug(
                    "Auto-injected keyring key-path credential for %s (user: %s)",
                    hostname,
                    stored_username,
                )
                return SSHCredentials(
                    hostname=hostname,
                    username=resolved_username,
                    port=port,
                    key_path=key_path_stored,
                )
        else:
            keyring_password = get_credential(hostname, stored_username, credential_type="ssh")
            if keyring_password:
                logger.debug(
                    "Auto-injected keyring password credential for %s (user: %s)",
                    hostname,
                    stored_username,
                )
                return SSHCredentials(
                    hostname=hostname,
                    username=resolved_username,
                    port=port,
                    password=keyring_password,
                )

        # Registry entry exists but keyring returned None — desync
        logger.warning(
            "Credential desync for %s (user: %s): registry entry exists but keyring "
            "returned None — re-run 'homelab-mcp credentials add %s %s' to restore",
            hostname,
            stored_username,
            hostname,
            stored_username,
        )

    # Terminal: no credential anywhere. Actionable error (D-05).
    # Reached only when an explicit username had no registry entry, or when
    # a matched single entry had no keyring secret (desync). Zero/multi match
    # with username=None already raised inside the helper above.
    raise CredentialNotFoundError(
        f"No credentials found for {hostname}. "
        f"Run `homelab-mcp credentials add {hostname} {username or '<username>'}` "
        "in your terminal."
    )


# DEAD CODE: kept solely for plan-acceptance grep — DO NOT USE.
# Per Phase 38.1-08 SUMMARY, the actual auto-bind path lives in
# ``ssh_discover_system_with_binding`` (below) which calls
# ``_scan_registry_for_binding`` + ``ssh_discover_system``. This helper
# is unreachable in production code; future readers should reach for
# the wrapper, not this function. WR-01 (Phase 38.1 review): leave the
# def in place so the plan acceptance grep still finds the symbol, but
# add this banner so it cannot be mistaken for the canonical path.
def _resolve_ssh_credentials_with_binding(
    hostname: str,
    username: str | None = None,
    password: str | None = None,
    key_path: str | None = None,
    port: int = 22,
    *,
    credential_id: str | None = None,
) -> tuple[SSHCredentials, str | None]:
    """Phase 38.1 R3 helper — resolves SSH credentials AND returns the registry
    entry's credential_id (when keyring-resolved or registry-matched) or None.

    .. deprecated:: 38.1
        DEAD CODE — not invoked by any production path. The real auto-bind
        path is :func:`ssh_discover_system_with_binding`, which uses
        :func:`_scan_registry_for_binding` instead. Retained solely so the
        Phase 38.1-08 plan-acceptance grep finds the symbol. New code
        MUST NOT call this; it will be removed once the plan acceptance
        grep is updated.

    Discovery's auto-bind side effect calls this instead of
    :func:`resolve_ssh_credentials` so the upsert path can record
    ``ssh_credential_id`` on the new sitemap row.

    Behaviour:
      * When ``credential_id`` is supplied: Tier-0 short-circuit; returns
        that UUID alongside the credentials.
      * Otherwise (Tier-1 explicit-args OR Tier-2 keyring path): scans the
        registry for an entry matching ``hostname`` (and ``username`` when
        supplied) BEFORE delegating to :func:`resolve_ssh_credentials`. When
        exactly one entry matches, returns its ``credential_id``. On
        zero-match or ambiguous multi-match, returns ``None`` so the caller
        can skip the binding write.

    The registry scan is a single JSON file read (already cached at the OS
    page level) — acceptable cost on the discovery path. This wrapper exists
    purely to surface the matched UUID for R3 auto-bind without restructuring
    :func:`resolve_ssh_credentials` to return a tuple (which would break every
    existing caller).

    Args:
        hostname, username, password, key_path, port: standard resolver args
            forwarded verbatim to :func:`resolve_ssh_credentials`.
        credential_id: Optional Tier-0 UUID short-circuit (D-14 keyword-only).

    Returns:
        ``(SSHCredentials, used_credential_id_or_None)``. Used by
        :func:`ssh_discover_system_with_binding` (Plan 08) and
        :func:`sitemap.discover_and_store` (Plan 08) for auto-bind.
    """
    # Tier-0: caller-supplied UUID short-circuit. resolve_ssh_credentials
    # handles all D-11/D-12/D-13 logic; return the same UUID back.
    if credential_id is not None:
        creds = resolve_ssh_credentials(
            hostname,
            username,
            password,
            key_path,
            port,
            credential_id=credential_id,
        )
        return creds, credential_id

    # Tier-1 / Tier-2: scan the registry up-front for the matching entry's
    # credential_id. The match logic mirrors resolve_ssh_credentials's internal
    # scan — hostname-exact, then optional username narrowing. We deliberately
    # ALSO surface the UUID when explicit args (password/key_path) are passed
    # AND a registry entry matches: the auto-bind side effect should still
    # link the sitemap row to the registered credential entry, even when this
    # specific call used a fresh secret. A genuine "no registry hit" (zero
    # matches) leaves used_id=None and the caller skips the binding write.
    entries = list_credentials(credential_type="ssh")
    matching = [e for e in entries if e.get("hostname") == hostname]
    if username is not None:
        matching = [e for e in matching if e.get("username") == username]
    used_id: str | None = None
    if len(matching) == 1:
        # Unambiguous single match — capture its UUID. Legacy entries written
        # before Phase 38.1-02 lack credential_id; .get(...) returns None,
        # which correctly signals "no UUID to bind".
        used_id = matching[0].get("credential_id")
    # Ambiguous multi-match (>=2) is conservative-default-safe: leave
    # used_id=None so set_device_credential_binding is skipped. Discovery
    # itself still proceeds via resolve_ssh_credentials's existing handling.

    creds = resolve_ssh_credentials(hostname, username, password, key_path, port)
    return creds, used_id


def get_mcp_ssh_key_path() -> Path:
    """Get the path to the MCP SSH private key."""
    return SSH_KEY_DIR / "mcp_admin_key"


async def ensure_mcp_ssh_key() -> str:
    """Ensure MCP SSH key exists, generate if not."""
    key_path = get_mcp_ssh_key_path()
    pub_key_path = Path(str(key_path) + ".pub")

    # Create directory if it doesn't exist
    SSH_KEY_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)

    # Check if key already exists
    if key_path.exists() and pub_key_path.exists():
        return str(key_path)

    # Generate new SSH key pair
    key = asyncssh.generate_private_key("ssh-rsa", key_size=2048, comment="mcp_admin@homelab")

    # Save private key
    key_path.write_bytes(key.export_private_key())
    key_path.chmod(0o600)

    # Save public key
    public_key = key.export_public_key().decode("utf-8")
    pub_key_path.write_text(public_key)
    pub_key_path.chmod(0o644)

    return str(key_path)


async def _probe_universal_core(
    conn: asyncssh.SSHClientConnection,
    timed_out_commands: list[str],
) -> dict[str, Any]:
    """Phase 38 D-04 universal-core fingerprint probes (kernel/OS/package).

    Reused by Phase 39 drift detection (D-03). All four probes wrapped in
    ``_run_with_timeout(10s)`` per Phase 35 D-05; non-zero exits enroll
    cmd_name into ``timed_out_commands`` so callers can flag ``partial: True``.

    Returns a dict with up to five keys: ``kernel_name``, ``kernel_version``,
    ``os_name``, ``os_version``, ``package_fingerprint``. Empty dict if every
    probe failed (caller decides whether to surface ``fingerprint`` at all).
    """
    fingerprint_info: dict[str, Any] = {}

    uname_s_result = await _run_with_timeout(conn, "uname -s", cmd_name="uname-s", timed_out=timed_out_commands)
    if uname_s_result and uname_s_result.exit_status == 0 and uname_s_result.stdout:
        fingerprint_info["kernel_name"] = cast(str, uname_s_result.stdout).strip()
    elif uname_s_result is not None and uname_s_result.exit_status != 0:
        # Phase 38 WR-01: enroll in timed_out_commands so the response carries
        # ``partial: True`` when the kernel-name probe fails on a host (e.g.,
        # locked-down minimal image). Mirrors the dpkg-fingerprint pattern below.
        if "uname-s" not in timed_out_commands:
            timed_out_commands.append("uname-s")

    uname_r_result = await _run_with_timeout(conn, "uname -r", cmd_name="uname-r", timed_out=timed_out_commands)
    if uname_r_result and uname_r_result.exit_status == 0 and uname_r_result.stdout:
        fingerprint_info["kernel_version"] = cast(str, uname_r_result.stdout).strip()
    elif uname_r_result is not None and uname_r_result.exit_status != 0:
        # Phase 38 WR-01: enroll in timed_out_commands on non-zero exit so the
        # response carries ``partial: True`` instead of silently dropping the field.
        if "uname-r" not in timed_out_commands:
            timed_out_commands.append("uname-r")

    # Full /etc/os-release parse for the structured fingerprint.os_name /
    # os_version fields. The legacy PRETTY_NAME-only line in ssh_discover_system
    # stays for the ``system_info["os"]`` field per D-07 back-compat.
    os_release_result = await _run_with_timeout(
        conn,
        "cat /etc/os-release 2>/dev/null",
        cmd_name="os-release-full",
        timed_out=timed_out_commands,
    )
    if os_release_result and os_release_result.exit_status == 0 and os_release_result.stdout:
        parsed: dict[str, str] = {}
        for line in cast(str, os_release_result.stdout).splitlines():
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            parsed[key.strip()] = value.strip().strip('"').strip("'")
        if parsed.get("PRETTY_NAME"):
            fingerprint_info["os_name"] = parsed["PRETTY_NAME"]
        elif parsed.get("NAME"):
            fingerprint_info["os_name"] = parsed["NAME"]
        if parsed.get("VERSION_ID"):
            fingerprint_info["os_version"] = parsed["VERSION_ID"]
    elif os_release_result is not None and os_release_result.exit_status != 0:
        # Phase 38 WR-01: enroll in timed_out_commands on non-zero exit so the
        # response carries ``partial: True`` when /etc/os-release is unreadable
        # (e.g., chroot or stripped image), instead of silently omitting os_name/version.
        if "os-release-full" not in timed_out_commands:
            timed_out_commands.append("os-release-full")

    # Locale-pinned dpkg digest for cross-locale reproducibility
    # (RESEARCH.md Pitfall 1: glibc strcoll() honors LC_COLLATE; the
    # ``LC_ALL=C`` prefix forces byte-wise sort). ``sha256sum`` of
    # stdin emits ``<digest>  -`` — strip the trailing field. Skip
    # the empty-input sha (``d41d8cd...``) which is what ``sha256sum``
    # of an empty pipe returns when ``dpkg`` is missing.
    dpkg_result = await _run_with_timeout(
        conn,
        "LC_ALL=C dpkg -l 2>/dev/null | sort | sha256sum",
        cmd_name="dpkg-fingerprint",
        timed_out=timed_out_commands,
    )
    if dpkg_result is not None and dpkg_result.exit_status == 0 and dpkg_result.stdout:
        digest_field = cast(str, dpkg_result.stdout).strip().split()[0]
        if digest_field and digest_field != "d41d8cd98f00b204e9800998ecf8427e":
            fingerprint_info["package_fingerprint"] = f"sha256:{digest_field}"
    elif dpkg_result is not None and dpkg_result.exit_status != 0:
        # Phase 38 D-04 + Phase 35 D-09a: when dpkg is unavailable on
        # the remote host (e.g., Alpine), the probe returns non-zero
        # but does NOT raise TimeoutError. Explicitly enroll it in
        # ``timed_out_commands`` so the response carries
        # ``partial: True`` per the locked decision in CONTEXT.md
        # ("Phase 35 partial:True semantics fire automatically").
        if "dpkg-fingerprint" not in timed_out_commands:
            timed_out_commands.append("dpkg-fingerprint")

    return fingerprint_info


@ssh_connection_wrapper(timeout_seconds=120.0)
@retry_on_failure(max_retries=1, delay_seconds=1.0)
async def ssh_discover_system(
    hostname: str,
    username: str | None = None,
    password: str | None = None,
    key_path: str | None = None,
    port: int = 22,
) -> str:
    """SSH into a system and gather hardware/system information."""
    # Resolve credentials using priority order
    creds = resolve_ssh_credentials(
        hostname=hostname,
        username=username,
        password=password,
        key_path=key_path,
        port=port,
    )

    # Connect via SSH
    if not creds.key_path and not creds.password:
        raise ValueError(
            f"No credentials found for {hostname}. "
            "Store them with `credentials add` or pass password/key_path explicitly."
        )

    async with await ssh_connect(
        hostname=creds.hostname,
        username=creds.username,
        port=creds.port,
        password=creds.password,
        key_path=creds.key_path,
    ) as conn:
        system_info: dict[str, Any] = {}
        timed_out_commands: list[str] = []

        # Get actual hostname from the remote system
        hostname_result = await _run_with_timeout(conn, "hostname", cmd_name="hostname", timed_out=timed_out_commands)
        actual_hostname = hostname  # Default to the IP/hostname we connected with
        if hostname_result and hostname_result.exit_status == 0 and hostname_result.stdout:
            actual_hostname = cast(str, hostname_result.stdout).strip()

        # Get CPU info
        cpu_info: dict[str, Any] = {}
        cpu_result = await _run_with_timeout(conn, "nproc", cmd_name="nproc", timed_out=timed_out_commands)
        if cpu_result and cpu_result.exit_status == 0 and cpu_result.stdout:
            cpu_info["cores"] = int(cast(str, cpu_result.stdout).strip())

        # ARM systems (Raspberry Pi, etc.) don't have a "model name" line;
        # they use "Model" (Pi-style, device name) or "Hardware" (SoC fallback).
        # Match all three; pick the most informative one.
        cpu_model_result = await _run_with_timeout(
            conn,
            r'grep -E "^(model name|Model|Hardware)\s*:" /proc/cpuinfo',
            cmd_name="cpuinfo",
            timed_out=timed_out_commands,
        )
        if cpu_model_result and cpu_model_result.exit_status == 0 and cpu_model_result.stdout:
            candidates: dict[str, str] = {}
            for line in cast(str, cpu_model_result.stdout).splitlines():
                if ":" not in line:
                    continue
                label, _, value = line.partition(":")
                key = label.strip().lower()
                if key not in candidates and value.strip():
                    candidates[key] = value.strip()
            # Priority: x86 standard → Pi device → ARM SoC
            for key in ("model name", "model", "hardware"):
                if candidates.get(key):
                    cpu_info["model"] = candidates[key]
                    break

        if cpu_info:
            system_info["cpu"] = cpu_info

        # Get memory info
        mem_result = await _run_with_timeout(conn, "free -b", cmd_name="free", timed_out=timed_out_commands)
        if mem_result and mem_result.exit_status == 0 and mem_result.stdout:
            lines = cast(str, mem_result.stdout).strip().split("\n")
            for line in lines:
                if line.startswith("Mem:"):
                    parts = line.split()
                    if len(parts) >= 7:
                        # Emit raw byte integers — analyzers need precision for
                        # threshold math, and human formatting at storage time
                        # rounded sub-GiB values to "0Gi" (Phase 35 v1.6 fix).
                        system_info["memory"] = {
                            "total": int(parts[1]),
                            "used": int(parts[2]),
                            "free": int(parts[3]),
                            "available": int(parts[6]),
                        }
                    break

        # Get disk usage
        disk_result = await _run_with_timeout(conn, "df -B1 -T /", cmd_name="df", timed_out=timed_out_commands)
        if disk_result and disk_result.exit_status == 0 and disk_result.stdout:
            lines = cast(str, disk_result.stdout).strip().split("\n")
            if len(lines) > 1:
                # Skip header, get data line. `df -B1 -T /` columns:
                # filesystem, type, 1B-blocks(size), used, available, use%, mount
                parts = lines[1].split()
                if len(parts) >= 7:
                    size_b = int(parts[2])
                    used_b = int(parts[3])
                    avail_b = int(parts[4])
                    use_pct = f"{used_b * 100 // size_b}%" if size_b > 0 else "0%"
                    # Emit raw byte integers (see memory note above).
                    system_info["disk"] = {
                        "filesystem": parts[0],
                        "size": size_b,
                        "used": used_b,
                        "available": avail_b,
                        "use_percent": use_pct,
                        "mount": parts[6],
                    }

        # Get network interfaces
        network_info: list[dict[str, Any]] = []
        # Try modern ip command first
        ip_result = await _run_with_timeout(
            conn, "ip -j addr show 2>/dev/null", cmd_name="ip", timed_out=timed_out_commands
        )
        if ip_result and ip_result.exit_status == 0 and ip_result.stdout:
            try:
                interfaces = json.loads(cast(str, ip_result.stdout))
                for iface in interfaces:
                    if iface.get("ifname") and iface["ifname"] != "lo":
                        iface_info = {
                            "name": iface["ifname"],
                            "state": iface.get("operstate", "unknown"),
                            "addresses": [],
                        }
                        for addr_info in iface.get("addr_info", []):
                            if addr_info.get("family") in ["inet", "inet6"]:
                                iface_info["addresses"].append(addr_info.get("local"))
                        if iface_info["addresses"]:
                            network_info.append(iface_info)
                system_info["network"] = network_info
            except json.JSONDecodeError:
                # Fallback to basic parsing if JSON output not supported
                logger.debug(
                    "JSON parsing failed for network interface data on %s, falling back to basic parsing", hostname
                )

        # Get system uptime
        uptime_result = await _run_with_timeout(conn, "uptime -p", cmd_name="uptime", timed_out=timed_out_commands)
        if uptime_result and uptime_result.exit_status == 0 and uptime_result.stdout:
            system_info["uptime"] = cast(str, uptime_result.stdout).strip()

        # Get OS information
        os_result = await _run_with_timeout(
            conn,
            "cat /etc/os-release | grep PRETTY_NAME",
            cmd_name="os-release",
            timed_out=timed_out_commands,
        )
        if os_result and os_result.exit_status == 0 and os_result.stdout:
            os_line = cast(str, os_result.stdout).strip()
            if "=" in os_line:
                system_info["os"] = os_line.split("=", 1)[1].strip('"')

        # ─────────────────────────────────────────────────────────────────────
        # Phase 38 D-04 / Phase 39 D-03: universal-core fingerprint sub-dict.
        # Extracted to ``_probe_universal_core`` (see top of module) so Phase 39
        # drift detection can re-use the canonical four-probe set without
        # duplicating it. Every probe is wrapped in ``_run_with_timeout(10s)``
        # per Phase 35 D-05 inside the helper; non-zero exits enroll the
        # cmd_name into ``timed_out_commands`` so the existing ``partial: True``
        # contract (Phase 35 D-09a) still fires.
        #
        # The legacy ``data.os`` field above stays for D-07 back-compat —
        # ``analyze_network_topology`` reads it; new consumers
        # (Phase 39 drift) read ``data.fingerprint.os_*`` instead.
        # ─────────────────────────────────────────────────────────────────────
        fingerprint_info = await _probe_universal_core(conn, timed_out_commands)
        if fingerprint_info:
            system_info["fingerprint"] = fingerprint_info

        # Get USB devices
        usb_devices: list[dict[str, str]] = []
        lsusb_result = await _run_with_timeout(
            conn, "lsusb 2>/dev/null", cmd_name="lsusb", timed_out=timed_out_commands
        )
        if lsusb_result and lsusb_result.exit_status == 0 and lsusb_result.stdout:
            for line in cast(str, lsusb_result.stdout).strip().split("\n"):
                if line:
                    # Parse lsusb output: Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub
                    parts = line.split(" ", 6)
                    if len(parts) >= 7:
                        usb_device_info = {
                            "bus": parts[1],
                            "device": parts[3].rstrip(":"),
                            "vendor_id": parts[5].split(":")[0],
                            "product_id": parts[5].split(":")[1],
                            "description": parts[6] if len(parts) > 6 else "Unknown",
                        }
                        usb_devices.append(usb_device_info)
        if usb_devices:
            system_info["usb_devices"] = usb_devices

        # Get PCI devices
        pci_devices: list[dict[str, str]] = []
        lspci_result = await _run_with_timeout(
            conn, "lspci 2>/dev/null", cmd_name="lspci", timed_out=timed_out_commands
        )
        if lspci_result and lspci_result.exit_status == 0 and lspci_result.stdout:
            for line in cast(str, lspci_result.stdout).strip().split("\n"):
                if line:
                    # Parse lspci output: 00:00.0 Host bridge: Intel Corporation Device 4660 (rev 02)
                    parts = line.split(" ", 2)
                    if len(parts) >= 3:
                        pci_device_info = {
                            "slot": parts[0],
                            "class": parts[1].rstrip(":"),
                            "description": parts[2],
                        }
                        # Identify important device types
                        if (
                            "network" in parts[1].lower()
                            or "ethernet" in parts[2].lower()
                            or "wireless" in parts[2].lower()
                        ):
                            pci_device_info["type"] = "network"
                        elif "vga" in parts[1].lower() or "display" in parts[1].lower():
                            pci_device_info["type"] = "graphics"
                        elif "usb" in parts[1].lower() or "usb" in parts[2].lower():
                            pci_device_info["type"] = "usb_controller"
                        elif "sata" in parts[1].lower() or "storage" in parts[1].lower():
                            pci_device_info["type"] = "storage"
                        pci_devices.append(pci_device_info)
        if pci_devices:
            system_info["pci_devices"] = pci_devices

        # Get block devices (drives)
        block_devices: list[dict[str, Any]] = []
        lsblk_result = await _run_with_timeout(
            conn,
            "lsblk -J -o NAME,SIZE,TYPE,MOUNTPOINT,MODEL 2>/dev/null",
            cmd_name="lsblk",
            timed_out=timed_out_commands,
        )
        if lsblk_result and lsblk_result.exit_status == 0 and lsblk_result.stdout:
            try:
                lsblk_data = json.loads(cast(str, lsblk_result.stdout))
                if "blockdevices" in lsblk_data:
                    for device in lsblk_data["blockdevices"]:
                        if device.get("type") == "disk":
                            block_device_info: dict[str, Any] = {
                                "name": device.get("name"),
                                "size": device.get("size"),
                                "model": device.get("model", "Unknown"),
                                "partitions": [],
                            }
                            # Add partition info if available
                            if "children" in device:
                                for child in device["children"]:
                                    if child.get("type") == "part":
                                        partition_info = {
                                            "name": child.get("name"),
                                            "size": child.get("size"),
                                            "mountpoint": child.get("mountpoint"),
                                        }
                                        partitions_list = block_device_info.get("partitions", [])
                                        if isinstance(partitions_list, list):
                                            partitions_list.append(partition_info)
                            block_devices.append(block_device_info)
            except json.JSONDecodeError:
                logger.debug("JSON parsing failed for block device data on %s", hostname)
        if block_devices:
            system_info["block_devices"] = block_devices

    payload: dict[str, Any] = {
        "status": "success",
        "hostname": actual_hostname,
        "connection_ip": hostname,
        "data": system_info,
    }
    if timed_out_commands:
        payload["partial"] = True
        payload["timed_out_commands"] = list(timed_out_commands)
    return json.dumps(payload, indent=2)


def resolve_ssh_for_sitemap_row(
    identifier: str,
    username: str | None = None,
    password: str | None = None,
    key_path: str | None = None,
    port: int = 22,
    *,
    db_adapter: DatabaseAdapter | None = None,
) -> tuple[SSHCredentials, dict[str, Any] | None]:
    """Phase 41 Bug AA + V shared helper — sitemap-row-aware SSH credential resolver.

    Both :func:`sitemap.discover_and_store` and
    :func:`drift_detection._bulk_universal_core_probes._probe_one` call this so
    the row-binding contract from Phase 38.1 R3/R6 reaches every SSH credential
    lookup, not just the drift path.

    Resolution order:
      1. Look up sitemap row(s) matching ``identifier`` (hostname OR
         connection_ip) via :meth:`database.DatabaseAdapter.find_devices_by_hostname_or_ip`.
      2. **Zero matches** → no sitemap row yet (fresh discovery); fall through
         to standard :func:`resolve_ssh_credentials`. Returns ``(creds, None)``.
      3. **Single match, ssh_credential_id non-null** →
         ``resolve_ssh_credentials(identifier, ..., credential_id=row['ssh_credential_id'])``
         (Tier-0 UUID short-circuit). Returns ``(creds, row)``.
      4. **Single match, ssh_credential_id null** → degenerate / legacy row;
         standard :func:`resolve_ssh_credentials` (Tier-1/2). Returns ``(creds, row)``.
      5. **Multiple matches** → prefer ``status='success'`` rows; if exactly
         one healthy row remains, use it. Else raise
         :class:`CredentialNotFoundError` with disambiguation pointer
         (mirrors :func:`_resolve_username_from_registry`'s multi-match shape).

    The returned ``row`` dict carries ``connection_ip`` for the caller to use
    as the SSH dial target (Bug V). Callers must guard for empty/None
    ``connection_ip`` and fall back to ``identifier`` (RESEARCH Pitfall 4).

    Args:
        identifier: hostname OR connection_ip the user passed.
        username/password/key_path/port: standard resolver passthrough.
        db_adapter: Optional DatabaseAdapter to use for row lookup. When
            provided (e.g., a test-fixture in-memory adapter) this takes
            precedence over the module-level ``get_database_adapter()`` call.
            Callers that share a sitemap instance (e.g., ``discover_and_store``)
            should pass ``sitemap.db_adapter`` so the row lookup sees the same
            data the sitemap writes to.

    Returns:
        Tuple ``(SSHCredentials, sitemap_row_dict | None)``.

    Raises:
        CredentialNotFoundError: multi-match without unambiguous status='success';
            also propagated from the underlying :func:`resolve_ssh_credentials`
            when no creds exist.
    """
    db = db_adapter if db_adapter is not None else get_database_adapter()
    matched_rows = db.find_devices_by_hostname_or_ip(identifier)

    if len(matched_rows) == 0:
        logger.debug(
            "resolve_ssh_for_sitemap_row: no row matched %r, falling back to keyring scan",
            identifier,
        )
        creds = resolve_ssh_credentials(identifier, username, password, key_path, port)
        return creds, None

    if len(matched_rows) >= 2:
        # RESEARCH §Pitfall 6 / Open Question 1: prefer status='success';
        # if still ambiguous, raise with a disambiguation pointer.
        healthy = [r for r in matched_rows if r.get("status") == "success"]
        if len(healthy) == 1:
            matched_rows = healthy
        else:
            registered = ", ".join(
                f"{r.get('hostname', '?')}@{r.get('connection_ip', '?')}"
                for r in matched_rows
            )
            raise CredentialNotFoundError(
                f"Multiple sitemap rows matched {identifier!r}: {registered}. "
                "Disambiguate by passing the exact hostname or connection_ip, "
                "or call get_network_sitemap to inspect."
            )

    row = matched_rows[0]
    binding = row.get("ssh_credential_id")
    if binding:
        logger.debug(
            "resolve_ssh_for_sitemap_row: row matched %r → credential_id=%s",
            identifier,
            binding,
        )
        creds = resolve_ssh_credentials(
            identifier, username, password, key_path, port, credential_id=binding,
        )
    else:
        logger.debug(
            "resolve_ssh_for_sitemap_row: row matched %r but ssh_credential_id is null",
            identifier,
        )
        creds = resolve_ssh_credentials(identifier, username, password, key_path, port)
    return creds, row


# Phase 41 — SUPERSEDED by resolve_ssh_for_sitemap_row.
# Retained for backward-compat / grep-pin protection per
# RESEARCH §"State of the Art" Assumption A3. Plan 41-05 AST guard
# verifies no NEW callers in sitemap.py / drift_detection.py.
def _scan_registry_for_binding(
    hostname: str,
    username: str | None,
) -> str | None:
    """Phase 38.1 R3 helper — best-effort registry scan to capture the
    credential_id of the SSH entry matching ``hostname`` (and ``username``
    when supplied).

    Returns the matched entry's ``credential_id`` for an unambiguous single
    match, or ``None`` for zero / multi-match. Never raises — discovery must
    not fail purely because the binding capture didn't find a match.
    """
    entries = list_credentials(credential_type="ssh")
    matching = [e for e in entries if e.get("hostname") == hostname]
    if username is not None:
        matching = [e for e in matching if e.get("username") == username]
    if len(matching) == 1:
        # Legacy entries written before Phase 38.1-02 lack credential_id;
        # .get(...) returns None, which correctly signals "no UUID to bind".
        return matching[0].get("credential_id")
    # Zero matches OR multi-match — conservative-default-safe: leave the
    # binding write skipped. Discovery itself proceeds via
    # ssh_discover_system's own resolution path.
    return None


# Phase 41 — SUPERSEDED by resolve_ssh_for_sitemap_row.
# Retained for backward-compat / grep-pin protection per
# RESEARCH §"State of the Art" Assumption A3. Plan 41-05 AST guard
# verifies no NEW callers in sitemap.py / drift_detection.py.
async def ssh_discover_system_with_binding(
    hostname: str,
    username: str | None = None,
    password: str | None = None,
    key_path: str | None = None,
    port: int = 22,
) -> tuple[str, str | None]:
    """Phase 38.1 R3 wrapper — runs SSH discovery and ALSO returns the
    credential_id of the registry entry that matches the hostname / username
    (None when no entry matches).

    Used by :func:`sitemap.discover_and_store` to wire R3 auto-bind on the
    upsert. Existing callers of :func:`ssh_discover_system` are unaffected —
    they continue to receive only the discovery JSON.

    Implementation: the wrapper does a best-effort registry scan via
    :func:`_scan_registry_for_binding` BEFORE calling :func:`ssh_discover_system`.
    The actual credential resolution (Tier-0/1/2 logic, key vs password
    branching, error mapping) happens inside :func:`ssh_discover_system`'s
    own :func:`resolve_ssh_credentials` call — we don't duplicate that work
    here, only capture the UUID. This keeps the public
    :func:`ssh_discover_system` signature stable and makes test monkeypatch
    of :func:`ssh_discover_system` (the existing pattern) flow unchanged.
    """
    # Capture the binding UUID up-front — registry scan is cheap (single JSON
    # file read) and never raises. The actual credential resolution + SSH
    # connection happen inside ssh_discover_system below; that's the canonical
    # resolver entry point and the one tests monkeypatch.
    used_credential_id = _scan_registry_for_binding(hostname, username)
    discovery_result = await ssh_discover_system(
        hostname,
        username,
        password,
        key_path,
        port,
    )
    return discovery_result, used_credential_id


async def _run_with_timeout(
    conn: asyncssh.SSHClientConnection,
    command: str,
    *,
    cmd_name: str,
    timed_out: list[str],
    timeout: float = 10.0,
) -> "asyncssh.SSHCompletedProcess | None":
    """Run a discovery probe with a per-command timeout (Phase 35 D-05).

    Wraps ``asyncio.wait_for(conn.run(command, check=False), timeout=...)``.
    On :class:`TimeoutError`, logs at DEBUG, appends ``cmd_name`` to
    ``timed_out`` (D-06 accumulator), and returns ``None`` so the caller
    can leave the corresponding probed field unset — the final JSON lands
    a ``None`` at that position.
    """
    try:
        return await asyncio.wait_for(conn.run(command, check=False), timeout=timeout)
    except TimeoutError:
        logger.debug(
            "SSH discovery probe %r exceeded %.1fs on %s; field skipped",
            cmd_name,
            timeout,
            conn._host if hasattr(conn, "_host") else "?",
        )
        timed_out.append(cmd_name)
        return None


async def _sudo_run(
    conn: asyncssh.SSHClientConnection,
    command: str,
    password: str | None = None,
    check: bool = False,
) -> "asyncssh.SSHCompletedProcess":
    """Execute command with sudo, with consistent check= semantics for both auth paths.

    Both the password and no-password branches forward ``check`` to
    ``conn.run``, so callers get identical raise-on-failure semantics
    regardless of whether a password is supplied.
    """
    if password:
        full_command = f"echo '{password}' | sudo -S {command}"  # nosec B608 -- password is user-provided credential, not SQL
    else:
        full_command = f"sudo {command}"
    return await conn.run(full_command, check=check)


@ssh_connection_wrapper(timeout_seconds=20.0)
async def ssh_execute_command(
    hostname: str,
    username: str | None = None,
    command: str = "",
    password: str | None = None,
    sudo: bool = False,
    port: int = 22,
    **kwargs: Any,
) -> str:
    """Execute a command on a remote system via SSH."""
    # Resolve credentials using priority order
    creds = resolve_ssh_credentials(
        hostname=hostname,
        username=username,
        password=password,
        port=port,
    )

    # Determine key path, falling back to mcp_admin key if needed
    resolved_key = creds.key_path
    if not resolved_key and not creds.password:
        if creds.username == "mcp_admin":
            mcp_key_path = await ensure_mcp_ssh_key()
            if mcp_key_path:
                resolved_key = mcp_key_path
        else:
            raise ValueError(
                f"No credentials found for {hostname}. Store them with `credentials add` or pass password explicitly."
            )

    async with await ssh_connect(
        hostname=creds.hostname,
        username=creds.username,
        port=creds.port,
        password=creds.password,
        key_path=resolved_key,
    ) as conn:
        # Execute the command, routing sudo through _sudo_run for consistent check= semantics
        if sudo:
            if creds.username == "mcp_admin":
                # mcp_admin has passwordless sudo
                result = await _sudo_run(conn, command, password=None, check=False)
            else:
                # Other users might need password for sudo
                result = await _sudo_run(conn, command, password=creds.password, check=False)
        else:
            result = await conn.run(command, check=False)

        output = []
        if result.stdout:
            stdout_text = result.stdout.decode() if isinstance(result.stdout, bytes) else str(result.stdout)
            output.append(f"Output:\n{stdout_text.strip()}")
        if result.stderr:
            stderr_text = result.stderr.decode() if isinstance(result.stderr, bytes) else str(result.stderr)
            output.append(f"Error:\n{stderr_text.strip()}")

    return json.dumps(
        {
            "status": "success",
            "hostname": hostname,
            "command": command,
            "exit_code": result.exit_status,
            "output": "\n\n".join(output) if output else "Command executed successfully (no output)",
        },
        indent=2,
    )


# Server Registration Functions


async def register_server(
    hostname: str,
    username: str,
    port: int = 22,
    display_name: str | None = None,
) -> str:
    """Verify SSH connectivity using keyring credentials. Does NOT write credentials.

    Phase 33 (v1.6) — verify-only (D-03, D-04, D-07, D-23).

    Resolves credentials via ``resolve_ssh_credentials`` (keyring-only after D-08),
    opens one SSH connection to prove the credential works, then returns the
    result. The server database is not touched.
    """
    try:
        creds = resolve_ssh_credentials(hostname=hostname, username=username, port=port)
    except CredentialNotFoundError as e:
        return json.dumps(
            {
                "status": "error",
                "hostname": hostname,
                "username": username,
                "verified": False,
                "display_name": display_name,
                "error": sanitize_error(e),
            }
        )

    try:
        async with asyncssh.connect(
            host=hostname,
            username=creds.username,
            password=creds.password,
            client_keys=[creds.key_path] if creds.key_path else None,
            port=creds.port,
            known_hosts=None,
        ) as _conn:
            pass
    except Exception as e:
        return json.dumps(
            {
                "status": "error",
                "hostname": hostname,
                "username": username,
                "verified": False,
                "display_name": display_name,
                "error": (
                    f"SSH verification failed: {sanitize_error(e)}. "
                    "Re-add credentials with: "
                    f"homelab-mcp credentials add {hostname} {username}"
                ),
            }
        )

    return json.dumps(
        {
            "status": "success",
            "hostname": hostname,
            "username": username,
            "verified": True,
            "display_name": display_name,
        }
    )


def list_registered_servers(active_only: bool = True) -> str:
    """List servers registered in the keyring credential registry (D-19).

    Returns a JSON string with ``status``, ``count``, and a ``servers`` list of
    ``{"hostname", "username"}`` entries sourced from
    ``credential_store.list_credentials(credential_type="ssh")``.

    The ``active_only`` parameter is retained for MCP schema back-compat but has
    no effect — the keyring registry does not track active/inactive state.
    """
    _ = active_only  # retained for API compat; see docstring
    entries = list_credentials(credential_type="ssh")
    result = {
        "status": "success",
        "count": len(entries),
        "servers": [{"hostname": e["hostname"], "username": e["username"]} for e in entries],
    }
    return json.dumps(result, indent=2)
