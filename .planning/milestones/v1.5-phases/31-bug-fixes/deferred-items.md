# Phase 31 Deferred Items

Items discovered during plan execution that are **out of scope** for the current plan's
task boundaries. Logged per GSD workflow scope-boundary rules — do NOT fix from the
current plan; surface to the phase owner for triage into a follow-up plan or the next
applicable plan in the phase.

---

## 2026-04-19 — Discovered during 31-01 execution

### `ssh_tools.py:656` — `asyncssh.SSHCompletedProcess[str]` not subscriptable

**File:** `src/homelab_mcp/ssh_tools.py:656`
**Symptom:** `TypeError: type 'SSHCompletedProcess' is not subscriptable` at
import/collection time. Causes pytest collection errors in 12 test files when
running the broader non-integration suite.

**Introduced by:** A sibling SSH-01 plan's `_sudo_run` helper (present before
31-01 execution began — not caused by 31-01's edits).

**Impact on 31-01:** None. The three verification test files targeted by 31-01
(`test_error_handling.py`, `test_ssh_tools.py`, `test_tools.py`) all import
via module paths that do not trigger the faulty annotation during their own
collection, and all 84 tests across those three files pass.

**Why deferred:** Scope boundary — 31-01's charter is ERR-01, SSH-02, SCH-01.
Rewriting the `_sudo_run` return annotation belongs to the SSH-01 plan or a
follow-up repair plan. Proposed fix (for the owning plan): change the annotation
to `asyncssh.SSHCompletedProcess` without the `[str]` parameter, or use
`asyncssh.SSHCompletedProcess[Any]` with `from typing import Any` and a type
ignore if strict-mypy demands it. The asyncssh `SSHCompletedProcess` class is
not generic at runtime even though newer stubs declare it as such.

**Verification that this is pre-existing:** `git log --oneline -- src/homelab_mcp/ssh_tools.py`
shows the most recent ssh_tools.py commit is `34bf920 fix(v1.4): restore
CredentialNotFoundError + repair SEC-01 test mocks` — predates 31-01 work.

### Pre-existing dev-only failures (noted in execution prompt, ignored by design)

- `tests/test_packaging.py::test_version_unified` — stale install artifact
- `tests/test_proxmox_api.py::TestGetProxmoxClient::test_client_missing_host` — keyring isolation

Do not attempt to fix from Phase 31.
