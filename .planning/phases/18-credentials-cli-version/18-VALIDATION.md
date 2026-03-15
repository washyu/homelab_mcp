---
phase: 18
slug: credentials-cli-version
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-14
---

# Phase 18 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_credential_store.py tests/test_credentials_cli.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -m "not integration" -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_credential_store.py tests/test_credentials_cli.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -m "not integration" -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 18-01-01 | 01 | 0 | CRED-01..06 | unit | `uv run pytest tests/test_credentials_cli.py -x -q` | ❌ W0 | ⬜ pending |
| 18-01-02 | 01 | 0 | CRED-01..06 | unit | `uv run pytest tests/test_credential_store.py -x -q` | ✅ | ⬜ pending |
| 18-02-01 | 02 | 1 | CRED-01..06 | unit | `uv run pytest tests/test_credential_store.py -x -q` | ✅ | ⬜ pending |
| 18-03-01 | 03 | 2 | CRED-01, CRED-02, CRED-03 | unit | `uv run pytest tests/test_credentials_cli.py::test_credentials_add_ssh tests/test_credentials_cli.py::test_credentials_list_ssh tests/test_credentials_cli.py::test_credentials_remove_ssh -x -q` | ❌ W0 | ⬜ pending |
| 18-03-02 | 03 | 2 | CRED-04, CRED-05, CRED-06 | unit | `uv run pytest tests/test_credentials_cli.py::test_credentials_add_proxmox tests/test_credentials_cli.py::test_credentials_list_proxmox tests/test_credentials_cli.py::test_credentials_remove_proxmox -x -q` | ❌ W0 | ⬜ pending |
| 18-03-03 | 03 | 2 | CLI-01 | unit | `uv run pytest tests/test_credentials_cli.py::test_version_flag tests/test_credentials_cli.py::test_bare_invocation_starts_server -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_credentials_cli.py` — new file; stubs for CRED-01..06 + CLI-01 (all CLI-facing behaviors)
- [ ] Additional test cases in `tests/test_credential_store.py` — covers registry functions (`register_credential`, `unregister_credential`, `list_credentials`) + `credential_type` parameter on existing Phase 17 functions

*Existing infrastructure covers all phase requirements — pytest, pytest-mock, pyproject.toml config are already installed. `test_credential_store.py` exists from Phase 17 and will be extended.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Password is not echoed during `credentials add` | CRED-01 | Requires a real TTY; cannot verify echo suppression in pytest without a pty | Run `homelab-mcp credentials add testhost testuser` in a terminal; verify password is not visible while typing |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
