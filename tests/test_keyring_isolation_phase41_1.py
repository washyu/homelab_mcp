"""Phase 41.1 SC-1 / SC-3 / SC-4 unit tests.

Tests in this file rely on the session-autouse ``_isolate_keyring`` fixture
that lands in ``tests/conftest.py`` in Plan 02 (Wave 1). Wave 0 commits this
file RED with ``@pytest.mark.xfail(strict=True)`` markers; Plan 02 removes
the markers once the fixture is in place.

Coverage map:
* ``test_in_memory_backend_active_session_scope`` — SC-1 Layer 1 verification
* ``test_set_password_routes_to_in_memory`` — SC-1 Layer 2 verification
* ``test_no_test_host_test_user_leak`` — SC-3 regression pin
* ``test_pre_post_snapshot_helper`` — SC-4 snapshot helper unit test
"""

from __future__ import annotations

import hashlib
import pathlib

import pytest

_WAVE1_REASON = (
    "Phase 41.1 Wave 1 (Plan 02) installs the session-autouse "
    "_isolate_keyring fixture in tests/conftest.py. This test FAILS in "
    "Wave 0 and FLIPS to passing in Wave 1. Plan 02 acceptance includes "
    "removing the xfail marker."
)


@pytest.mark.xfail(strict=True, reason=_WAVE1_REASON)
def test_in_memory_backend_active_session_scope() -> None:
    """SC-1 Layer 1: keyring.get_keyring() returns an in-memory backend.

    Confirms the session-autouse fixture installed an _InMemoryKeyring (or
    equivalent) via keyring.set_keyring(...). The class name check is loose
    on purpose — Plan 02 chooses the exact class name; this test only pins
    "not the OS backend".
    """
    import keyring  # noqa: PLC0415

    backend = keyring.get_keyring()
    backend_cls = type(backend).__name__
    assert "InMemory" in backend_cls or "Memory" in backend_cls, (
        f"SC-1 Layer 1: expected an in-memory backend, got {backend_cls!r}. "
        f"The session-autouse _isolate_keyring fixture in tests/conftest.py "
        f"must call keyring.set_keyring(_InMemoryKeyring())."
    )


@pytest.mark.xfail(strict=True, reason=_WAVE1_REASON)
def test_set_password_routes_to_in_memory() -> None:
    """SC-1 Layer 2: keyring.set_password / get_password round-trip through
    the in-memory store, confirming the function-level monkeypatch is active.

    The round-trip is gated behind a backend-identity check so a Wave-0 run
    on Windows / macOS (where the OS keyring is fully functional) does NOT
    write a real credential to Credential Manager / keychain — exactly the
    SC-1 leak this phase is meant to prevent. The gate fails in Wave 0
    (no in-memory backend installed yet) and unblocks in Wave 1 once the
    session-autouse fixture lands.
    """
    import keyring  # noqa: PLC0415

    backend_cls = type(keyring.get_keyring()).__name__
    assert "InMemory" in backend_cls or "Memory" in backend_cls, (
        f"SC-1 Layer 2 gate: in-memory backend not active (got "
        f"{backend_cls!r}). Round-trip skipped to avoid writing a real "
        f"credential to the OS keyring. The session-autouse "
        f"_isolate_keyring fixture in tests/conftest.py is required."
    )

    keyring.set_password("homelab-mcp-test-svc", "test-user-isolation", "secret-A")
    got = keyring.get_password("homelab-mcp-test-svc", "test-user-isolation")
    assert got == "secret-A", (
        "SC-1 Layer 2: keyring.set/get_password did not round-trip through "
        "the in-memory dict. Plan 02 must monkeypatch keyring.{set,get,"
        "delete}_password at session scope."
    )
    keyring.delete_password("homelab-mcp-test-svc", "test-user-isolation")
    assert keyring.get_password("homelab-mcp-test-svc", "test-user-isolation") is None


@pytest.mark.xfail(strict=True, reason=_WAVE1_REASON)
def test_no_test_host_test_user_leak(tmp_path: pathlib.Path) -> None:
    """SC-3 regression pin: driving register_credential("test-host",
    "test-user", credential_type="ssh") through the dual-alias-fixed call
    site MUST NOT leave any entry in the real ~/.homelab_mcp/credential_
    registry.json. Plan 02 fixes the test_sitemap.py:947 single-alias bug;
    this test pins the closure."""
    real_registry = pathlib.Path.home() / ".homelab_mcp" / "credential_registry.json"
    pre_hash = hashlib.sha256(real_registry.read_bytes()).hexdigest() if real_registry.exists() else None

    # Drive the suspect path. Plan 02's fixture redirects _REGISTRY_PATH to
    # a tmp dir, so this call writes to tmp, not to the developer's home.
    from homelab_mcp.credential_store import register_credential  # noqa: PLC0415

    cred_id = register_credential("test-host", "test-user", credential_type="ssh")
    assert isinstance(cred_id, str)

    post_hash = hashlib.sha256(real_registry.read_bytes()).hexdigest() if real_registry.exists() else None
    assert pre_hash == post_hash, (
        "SC-3 regression: register_credential('test-host', 'test-user') "
        "leaked into the real credential registry at "
        f"{real_registry}. Plan 02 must redirect _REGISTRY_PATH on BOTH "
        "module aliases (homelab_mcp.* AND src.homelab_mcp.*) and fix the "
        "tests/test_sitemap.py:947 single-alias bug."
    )


@pytest.mark.xfail(strict=True, reason=_WAVE1_REASON)
def test_pre_post_snapshot_helper() -> None:
    """SC-4 snapshot helper: the conftest exposes a ``_capture_real_state()``
    helper that returns a stable, hashable representation of the developer's
    real-side state (registry sha256 + active backend identity). Two
    successive calls without intervening writes return equal results.

    Plan 02 implements ``_capture_real_state`` as a module-level helper in
    conftest.py and exposes it via the ``capture_real_state`` pytest
    fixture (function-scope, returns the helper itself).
    """
    from tests.conftest import _capture_real_state  # type: ignore[attr-defined] # noqa: PLC0415

    snap_a = _capture_real_state()
    snap_b = _capture_real_state()
    assert snap_a == snap_b, (
        "SC-4: _capture_real_state must be deterministic between successive "
        "calls when no real-side mutation occurs. Plan 02 must hash the "
        "registry file content (not mtime — see RESEARCH §Open Questions) "
        "and capture keyring.get_keyring() identity."
    )
