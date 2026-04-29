"""Phase 41.1 Wave 0 — forensic instrumentation for keyring leak triage.

This module exists ONLY to pinpoint the exact source of the test-host/test-user
keyring/registry leak surfaced in the 2026-04-28 UAT session. RESEARCH.md
§Pitfall 2 explicitly states static grep cannot identify the leak path —
runtime instrumentation must capture the traceback at the moment of write.

USAGE:
    uv run pytest tests/test_keyring_isolation_forensic.py -v -s

Read the printed log paths after the run completes. Each log file contains
one entry per captured call:
    <service>:<username>
    <traceback>
    ---

This file is DELETED in Plan 02 once the leak source is fixed and the
permanent regression test (test_no_test_host_test_user_leak) is wired in
tests/test_keyring_isolation_phase41_1.py.
"""

from __future__ import annotations

import traceback
from pathlib import Path
from typing import Any


def _writer(log_path: Path) -> Any:
    """Return a side_effect that appends (svc, user, traceback) to log_path."""

    def _capture(svc: str, user: str, *args: Any, **kwargs: Any) -> None:
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"{svc}:{user}\n")
            fh.write("".join(traceback.format_stack()))
            fh.write("\n---\n")

    return _capture


def test_keyring_set_password_traceback_log(mocker: Any, tmp_path: Path) -> None:
    """Forensic: log every keyring.set_password call site to a file.

    Drives a representative leak-suspect path and prints the log location so
    the human reader can correlate stack frames with the offending test
    file/line.
    """
    log_path = tmp_path / "keyring_set_password_calls.log"
    mocker.patch("keyring.set_password", side_effect=_writer(log_path))

    # Drive ONE write through the production seam to confirm instrumentation
    # is active. (The Wave-0 goal is the broader full-suite run; this test
    # just proves the harness works.)
    import keyring  # noqa: PLC0415

    keyring.set_password("homelab-mcp", "test-user@test-host", "fake-secret")

    print(f"\n[FORENSIC] keyring.set_password log: {log_path}\n")
    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    assert "homelab-mcp:test-user@test-host" in content, (
        "forensic harness did not capture the seeded call — instrumentation broken"
    )


def test_register_credential_traceback_log(mocker: Any, tmp_path: Path, monkeypatch: Any) -> None:
    """Forensic: log every register_credential call site by patching it
    in BOTH module aliases (per RESEARCH §Pitfall 2 / PATTERNS dual-alias).

    Drives the test_sitemap.py:952 suspect path
    (register_credential("test-host", "test-user", credential_type="ssh"))
    after redirecting _REGISTRY_PATH to tmp_path so the real registry is not
    touched.
    """
    log_path = tmp_path / "register_credential_calls.log"
    registry_path = tmp_path / "registry.json"

    # Dual-alias _REGISTRY_PATH redirect so the call we drive does not hit
    # ~/.homelab_mcp/credential_registry.json. (PATTERNS §Dual-Alias.)
    monkeypatch.setattr("homelab_mcp.credential_store._REGISTRY_PATH", registry_path)
    monkeypatch.setattr("src.homelab_mcp.credential_store._REGISTRY_PATH", registry_path)

    # Stub keyring.set_password to a no-op so we do not also leak via Layer 2.
    mocker.patch("keyring.set_password", return_value=None)

    # Wrap register_credential to log the call site. Patch BOTH aliases.
    import homelab_mcp.credential_store as cs_pkg  # noqa: PLC0415
    import src.homelab_mcp.credential_store as cs_src  # noqa: PLC0415

    real_register = cs_pkg.register_credential

    def _logged_register(hostname: str, username: str, **kw: Any) -> str:
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"{hostname}:{username}\n")
            fh.write("".join(traceback.format_stack()))
            fh.write("\n---\n")
        return real_register(hostname, username, **kw)

    monkeypatch.setattr(cs_pkg, "register_credential", _logged_register)
    monkeypatch.setattr(cs_src, "register_credential", _logged_register)

    cred_id = cs_src.register_credential("test-host", "test-user", credential_type="ssh")

    print(f"\n[FORENSIC] register_credential log: {log_path}\n")
    assert log_path.exists()
    assert isinstance(cred_id, str)
    content = log_path.read_text(encoding="utf-8")
    assert "test-host:test-user" in content, "forensic harness did not capture the seeded call — instrumentation broken"
