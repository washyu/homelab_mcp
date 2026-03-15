---
phase: 17
slug: credential-store-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-14
---

# Phase 17 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_credential_store.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -m "not integration" -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_credential_store.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -m "not integration" -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 17-01-01 | 01 | 0 | CRED-07 | unit | `uv run pytest tests/test_credential_store.py -x -q` | ❌ W0 | ⬜ pending |
| 17-01-02 | 01 | 1 | CRED-07 | unit | `uv run pytest tests/test_credential_store.py::test_get_credential_headless_no_keyring_error -x` | ❌ W0 | ⬜ pending |
| 17-01-03 | 01 | 1 | CRED-07 | unit | `uv run pytest tests/test_credential_store.py::test_store_credential_headless_no_keyring_error -x` | ❌ W0 | ⬜ pending |
| 17-01-04 | 01 | 1 | CRED-07 | unit | `uv run pytest tests/test_credential_store.py::test_delete_credential_headless_no_keyring_error -x` | ❌ W0 | ⬜ pending |
| 17-01-05 | 01 | 1 | CRED-07 | unit | `uv run pytest tests/test_credential_store.py::test_get_credential_headless_runtime_error -x` | ❌ W0 | ⬜ pending |
| 17-01-06 | 01 | 1 | CRED-07 | unit | `uv run pytest tests/test_credential_store.py::test_store_credential_success -x` | ❌ W0 | ⬜ pending |
| 17-01-07 | 01 | 1 | CRED-07 | unit | `uv run pytest tests/test_credential_store.py::test_get_credential_success -x` | ❌ W0 | ⬜ pending |
| 17-01-08 | 01 | 1 | CRED-07 | unit | `uv run pytest tests/test_credential_store.py::test_delete_credential_not_found -x` | ❌ W0 | ⬜ pending |
| 17-01-09 | 01 | 1 | CRED-07 | unit | `uv run pytest tests/test_credential_store.py::test_no_module_level_keyring_import -x` | ❌ W0 | ⬜ pending |
| 17-01-10 | 01 | 1 | CRED-07 | unit | `uv run pytest tests/test_credential_store.py::test_keyring_in_core_dependencies -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_credential_store.py` — stubs for all CRED-07 test cases (new file, does not exist)

*All other test infrastructure already exists — pytest, pytest-mock, pyproject.toml config.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Server starts on headless host with no keyring warning at startup | CRED-07 | Requires actual headless Linux environment with no D-Bus session | Start server, check logs for keyring warnings before first credential call |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
