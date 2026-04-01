---
phase: 30
slug: security-fixes
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-01
---

# Phase 30 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (installed) |
| **Config file** | `pytest.ini` (project root) |
| **Quick run command** | `uv run pytest tests/test_ssh_connection.py tests/test_ssh_tools.py -v --tb=short` |
| **Full suite command** | `uv run pytest tests/ -m "not integration" -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_ssh_connection.py tests/test_ssh_tools.py -v --tb=short`
- **After every plan wave:** Run `uv run pytest tests/ -m "not integration" -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 30-01-01 | 01 | 0 | SEC-01 | unit | `uv run pytest tests/test_ssh_tools.py -k "injection" -v` | ❌ W0 | ⬜ pending |
| 30-01-02 | 01 | 0 | SEC-01 | unit | `uv run pytest tests/test_ssh_tools.py -k "cleanup" -v` | ❌ W0 | ⬜ pending |
| 30-01-03 | 01 | 0 | SEC-02 | unit | `uv run pytest tests/test_ssh_connection.py -k "concurrent or race" -v` | ❌ W0 | ⬜ pending |
| 30-01-04 | 01 | 0 | SEC-02 | unit | `uv run pytest tests/test_ssh_connection.py -k "single_entry" -v` | ❌ W0 | ⬜ pending |
| 30-01-05 | 01 | 0 | SEC-02 | unit | `uv run pytest tests/test_ssh_connection.py::TestTOFULock -v` | ✅ needs update | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_ssh_tools.py` — new test: `test_setup_mcp_admin_key_injection_safe` — covers SEC-01 (metacharacters in key content; asserts no f-string interpolation path reached)
- [ ] `tests/test_ssh_tools.py` — new test: `test_setup_mcp_admin_tmpfile_cleanup_on_error` — covers SEC-01 D-04 (finally block removes tmpfile even when append fails)
- [ ] `tests/test_ssh_connection.py` — new test: `test_tofu_concurrent_first_connection_single_entry` — covers SEC-02 (two threads racing; known_hosts ends with one entry)
- [ ] `tests/test_ssh_connection.py` — update test: `TestTOFULock::test_store_host_key_uses_lock` → assert lock acquired in `validate_host_public_key` instead of `_store_host_key`

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
