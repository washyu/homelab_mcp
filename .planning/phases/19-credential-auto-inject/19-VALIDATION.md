---
phase: 19
slug: credential-auto-inject
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-14
---

# Phase 19 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-asyncio |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/test_ssh_tools.py tests/test_credential_store.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -m "not integration" -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_ssh_tools.py tests/test_credential_store.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -m "not integration" -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 19-01-01 | 01 | 0 | INJECT-01 | unit | `uv run pytest tests/test_ssh_tools.py -x -q` | ❌ W0 | ⬜ pending |
| 19-01-02 | 01 | 0 | INJECT-02 | unit | `uv run pytest tests/test_ssh_tools.py -x -q` | ❌ W0 | ⬜ pending |
| 19-02-01 | 02 | 1 | INJECT-01 | unit | `uv run pytest tests/test_ssh_tools.py -x -q` | ✅ | ⬜ pending |
| 19-02-02 | 02 | 1 | INJECT-02 | unit | `uv run pytest tests/test_ssh_tools.py -x -q` | ✅ | ⬜ pending |
| 19-03-01 | 03 | 1 | INJECT-03 | unit | `uv run pytest tests/test_vm_operations.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_ssh_tools.py` — failing tests for keyring injection into `resolve_ssh_credentials()` (INJECT-01, INJECT-02)
- [ ] `tests/test_vm_operations.py` (or `tests/test_proxmox_api.py`) — failing tests for Proxmox keyring fallback (INJECT-03)

*Wave 0 establishes RED tests before implementation. Existing test files may need extension.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Log output never contains injected password | SC-4 | Requires log inspection during live run | Run `uv run python run_server.py` with DEBUG logging, trigger SSH tool call with keyring credential, grep logs for password value |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
