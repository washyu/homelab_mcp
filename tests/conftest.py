"""Phase 39 shared test fixtures for drift detection.

Provides the deterministic substrate (frozen clock, mocked SSH probes, sitemap
row factories, Proxmox cluster-resources mocks) that Plans 01/02/03 of Phase 39
compose into RED tests for ``scan_drift``'s unknown / missing / changed buckets.

All datetimes use UTC. ``freeze_now`` monkeypatches
``homelab_mcp.drift_detection.datetime`` so any helper that calls
``datetime.now(UTC)`` inside ``drift_detection`` sees a fixed wall-clock.
"""

import hashlib
import pathlib
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def freeze_now(monkeypatch: pytest.MonkeyPatch) -> datetime:
    """Freeze ``datetime.now`` inside ``homelab_mcp.drift_detection`` to
    2026-04-27T12:00:00Z. Returns the frozen aware datetime.

    Tests that call helpers requiring a ``now`` parameter pass the returned
    value explicitly. Helpers that read ``datetime.now(UTC)`` internally see
    the frozen clock automatically.
    """
    frozen = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)

    class _FakeDatetime(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> datetime:  # type: ignore[override]
            if tz is not None:
                return frozen
            return frozen.replace(tzinfo=None)

    monkeypatch.setattr("homelab_mcp.drift_detection.datetime", _FakeDatetime)
    return frozen


@pytest.fixture
def mock_universal_core_probe_response() -> dict[str, Any]:
    """Canonical universal-core probe result for a clean Proxmox host."""
    return {
        "kernel_name": "Linux",
        "kernel_version": "6.5.13-1-pve",
        "os_name": "Proxmox VE",
        "os_version": "8.2.4",
        "package_fingerprint": "sha256:abc123",
    }


@pytest.fixture
def mock_universal_core_probe_drifted() -> dict[str, Any]:
    """Same shape as ``mock_universal_core_probe_response`` but with a kernel
    bump and package-fingerprint shift — used to drive DRFT-19 changed-bucket
    fixtures in Plan 03.
    """
    return {
        "kernel_name": "Linux",
        "kernel_version": "6.8.4-2-pve",
        "os_name": "Proxmox VE",
        "os_version": "8.2.4",
        "package_fingerprint": "sha256:def456",
    }


@pytest.fixture
def mock_cluster_resources_response() -> list[dict[str, Any]]:
    """``GET /cluster/resources`` shape — three VM/LXC entries plus one
    node-type record (filtered out by ``_enumerate_unknown_vms``).

    Used by DRFT-17 unknown-bucket tests to mock per-cluster enumeration.
    """
    return [
        {"type": "qemu", "vmid": 100, "name": "ubuntu-prod", "node": "pve1", "status": "running"},
        {"type": "qemu", "vmid": 110, "name": "ubuntu-test", "node": "pve1", "status": "stopped"},
        {"type": "lxc", "vmid": 200, "name": "pi-hole", "node": "pve1", "status": "running"},
        {"type": "node", "node": "pve1", "status": "online"},
    ]


@pytest.fixture
def sitemap_row_old_last_seen(freeze_now: datetime) -> dict[str, Any]:
    """Sitemap row with ``last_seen`` 12 days before frozen now — promotes
    to ``status: "missing"`` under the default 7-day threshold.

    ``last_seen`` is naive isoformat (no tzinfo) per Phase 35 sitemap.py:84;
    helpers must normalize via ``_parse_last_seen``.
    """
    naive_now = freeze_now.replace(tzinfo=None)
    return {
        "hostname": "pi-lab",
        "connection_ip": "10.0.0.12",
        "status": "success",
        "ssh_credential_id": "11111111-1111-1111-1111-111111111111",
        "proxmox_credential_id": None,
        "last_seen": (naive_now - timedelta(days=12)).isoformat(),
        "fingerprint": {},
    }


@pytest.fixture
def sitemap_row_recent_last_seen(freeze_now: datetime) -> dict[str, Any]:
    """Sitemap row with ``last_seen`` 1 day before frozen now — stays in
    ``unreachable`` (not promoted to missing)."""
    naive_now = freeze_now.replace(tzinfo=None)
    return {
        "hostname": "pi-lab",
        "connection_ip": "10.0.0.12",
        "status": "success",
        "ssh_credential_id": "11111111-1111-1111-1111-111111111111",
        "proxmox_credential_id": None,
        "last_seen": (naive_now - timedelta(days=1)).isoformat(),
        "fingerprint": {},
    }


@pytest.fixture
def sitemap_row_with_stored_fingerprint(
    mock_universal_core_probe_response: dict[str, Any],
) -> dict[str, Any]:
    """Sitemap row with full Phase 38 fingerprint blob INCLUDING agent-curated
    capabilities sub-tree — exercises the D-09a leaf-level "present in both"
    diff rule.
    """
    fingerprint = dict(mock_universal_core_probe_response)
    fingerprint["capabilities"] = {"vulkan": {"available": True}}
    return {
        "hostname": "pve1",
        "connection_ip": "10.0.0.10",
        "status": "success",
        "ssh_credential_id": "22222222-2222-2222-2222-222222222222",
        "proxmox_credential_id": "33333333-3333-3333-3333-333333333333",
        "last_seen": "2026-04-27T11:00:00",
        "fingerprint": fingerprint,
    }


@pytest.fixture
def mock_resolve_ssh_credentials() -> MagicMock:
    """Mock for ``resolve_ssh_credentials`` — returns a credential record
    matching what the Phase 38.1 R6 resolver produces.
    """
    creds = MagicMock()
    creds.hostname = "10.0.0.12"
    creds.username = "mcp_admin"
    creds.port = 22
    creds.password = None
    creds.key_path = "/tmp/fake-key"  # noqa: S108 (test fixture path, not a secret)
    return creds


@pytest.fixture
def mock_ssh_connect() -> MagicMock:
    """Async-context-manager mock for ``asyncssh.connect``.

    ``__aenter__`` returns a conn whose ``.run`` is an ``AsyncMock`` that
    returns ``MagicMock(exit_status=0, stdout="Linux")`` by default. Tests
    that need per-command stdouts override ``conn.run.side_effect``.
    """
    cm = MagicMock()
    conn = MagicMock()
    conn.run = AsyncMock(return_value=MagicMock(exit_status=0, stdout="Linux"))
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


# ---------------------------------------------------------------------------
# Phase 41.1: session-autouse keyring + registry isolation
# ---------------------------------------------------------------------------
# Closes the leak surfaced in 2026-04-28 UAT: integration tests writing
# fake-secret-token into the developer's Windows Credential Manager
# (or macOS keychain / Linux secret-service). Three-layer defence — see
# .planning/phases/41.1-test-isolation-keyring-hygiene/41.1-RESEARCH.md
# §Pattern 1 for full rationale.
#
#  Layer 1: keyring.set_keyring(_InMemoryKeyring()) — swaps the active
#           backend so any code path using keyring.get_keyring().X(...)
#           hits the in-memory store.
#  Layer 2: pytest.MonkeyPatch().setattr on keyring.set_password /
#           get_password / delete_password — defeats lazy `import keyring`
#           inside production function bodies (credential_store.py:58).
#  Layer 3: Dual-alias _REGISTRY_PATH redirect to a session-scoped
#           tmp_path_factory directory — both `homelab_mcp.*` and
#           `src.homelab_mcp.*` aliases, since they are distinct module
#           objects in sys.modules.
#
# Snapshot pre/post: sha256 of ~/.homelab_mcp/credential_registry.json file
# content + keyring.get_keyring() type identity. Teardown asserts pre==post.
# ---------------------------------------------------------------------------

import keyring  # noqa: E402
import keyring.backend  # noqa: E402


class _InMemoryKeyring(keyring.backend.KeyringBackend):
    """Test-only keyring backend. Stores everything in a per-instance dict.

    Phase 41.1 SC-1 Layer 1. The ``priority`` class attribute is required
    since keyring 24.x — keyring's ``jaraco.classes`` machinery raises
    ``NotImplementedError`` at instantiation if it is unset.
    """

    priority = 1  # type: ignore[misc]

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], str] = {}

    def set_password(self, service: str, username: str, password: str) -> None:
        self._store[(service, username)] = password

    def get_password(self, service: str, username: str) -> str | None:
        return self._store.get((service, username))

    def delete_password(self, service: str, username: str) -> None:
        self._store.pop((service, username), None)


_REAL_REGISTRY_PATH = pathlib.Path.home() / ".homelab_mcp" / "credential_registry.json"


def _capture_real_state() -> tuple[str | None, str]:
    """Return ``(registry_sha256_or_None, active_backend_class_name)``.

    Phase 41.1 SC-4 snapshot helper. Used inside the ``_isolate_keyring``
    fixture's setup/teardown. Public-ish (single-leading-underscore) so the
    SC-4 unit test in ``tests/test_keyring_isolation_phase41_1.py`` can
    import and exercise it directly.

    Snapshot reduces to two invariants (RESEARCH §Pitfall 5 + §Open
    Question 2):
      * registry file content sha256 — captures any byte-level write
        to ``~/.homelab_mcp/credential_registry.json`` (mtime is not
        used because timezone / clock-skew flakiness)
      * active backend class NAME (not identity — Plan 03 inserts a fresh
        InMemoryKeyring per session so identity differs between fixture
        setup/teardown but class name is stable)
    """
    if _REAL_REGISTRY_PATH.exists():
        registry_hash: str | None = hashlib.sha256(_REAL_REGISTRY_PATH.read_bytes()).hexdigest()
    else:
        registry_hash = None
    backend_cls_name = type(keyring.get_keyring()).__name__
    return registry_hash, backend_cls_name


@pytest.fixture(scope="session", autouse=True)
def _isolate_keyring(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[None]:
    """Phase 41.1 SC-1 + SC-3 + SC-4 session-autouse fixture.

    Activates with no opt-in for the entire test session (unit + integration).
    See module-level comment block above for the three-layer defence
    rationale.
    """
    # ── Pre-snapshot of the developer's real state ──────────────────────
    pre = _capture_real_state()

    # ── Layer 1: backend swap ───────────────────────────────────────────
    original_backend = keyring.get_keyring()
    in_memory_backend = _InMemoryKeyring()
    keyring.set_keyring(in_memory_backend)

    # ── Layer 2: function-level monkeypatch (in-memory shim dict) ───────
    # We use a SECOND dict here (not the backend's) because lazy imports
    # in production code resolve `keyring.set_password` to the module
    # attribute, NOT to keyring.get_keyring().set_password. Both layers
    # must point at writable test storage.
    keyring_shim: dict[tuple[str, str], str] = {}

    def _shim_set(svc: str, user: str, pw: str) -> None:
        keyring_shim[(svc, user)] = pw

    def _shim_get(svc: str, user: str) -> str | None:
        return keyring_shim.get((svc, user))

    def _shim_del(svc: str, user: str) -> None:
        keyring_shim.pop((svc, user), None)

    mp = pytest.MonkeyPatch()
    mp.setattr("keyring.set_password", _shim_set)
    mp.setattr("keyring.get_password", _shim_get)
    mp.setattr("keyring.delete_password", _shim_del)

    # ── Layer 3: dual-alias _REGISTRY_PATH redirect ─────────────────────
    # Both module aliases — production code uses `src.homelab_mcp.X` for
    # some imports and `homelab_mcp.X` for others; they are distinct
    # module objects in sys.modules. Single-alias patches silently leak.
    session_tmp = tmp_path_factory.mktemp("homelab_mcp_session_isolation")
    session_registry = session_tmp / "credential_registry.json"
    mp.setattr("homelab_mcp.credential_store._REGISTRY_PATH", session_registry)
    mp.setattr("src.homelab_mcp.credential_store._REGISTRY_PATH", session_registry)

    try:
        yield
    finally:
        # Teardown order matters: undo monkeypatches FIRST so the snapshot
        # reads the developer's real backend, not the in-memory one.
        mp.undo()
        keyring.set_keyring(original_backend)
        post = _capture_real_state()
        assert pre == post, (
            "Phase 41.1 SC-4: test session leaked state to the developer's "
            "real OS keyring or ~/.homelab_mcp/credential_registry.json.\n"
            f"  pre  = {pre!r}\n  post = {post!r}\n"
            f"  registry path = {_REAL_REGISTRY_PATH}"
        )
