---
phase: 6
slug: tech-debt-cleanup
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-11
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8+ with pytest-asyncio |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_proxmox_api.py tests/test_http_app.py tests/test_vm_providers.py -x` |
| **Full suite command** | `uv run pytest tests/ -m "not integration"` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_proxmox_api.py tests/test_http_app.py tests/test_vm_providers.py -x`
- **After every plan wave:** Run `uv run pytest tests/ -m "not integration"`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 6-01-01 | 01 | 0 | DEBT-01 | unit | `uv run pytest tests/test_proxmox_api.py -x -k "session"` | ❌ W0 | ⬜ pending |
| 6-01-02 | 01 | 0 | DEBT-02 | unit | `uv run pytest tests/test_http_app.py -x -k "api_key"` | ❌ W0 | ⬜ pending |
| 6-01-03 | 01 | 0 | DEBT-03 | unit | `uv run pytest tests/test_vm_providers.py -x -k "error_type"` | ❌ W0 | ⬜ pending |
| 6-02-01 | 02 | 1 | DEBT-01 | unit | `uv run pytest tests/test_proxmox_api.py -x -k "shared_session"` | ❌ W0 | ⬜ pending |
| 6-02-02 | 02 | 1 | DEBT-02 | unit | `uv run pytest tests/test_http_app.py -x -k "health"` | ❌ W0 | ⬜ pending |
| 6-02-03 | 02 | 1 | DEBT-03 | unit | `uv run pytest tests/test_vm_providers.py -x -k "list_vms_error"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_proxmox_api.py` — add session-threading tests: verify shared session is passed through handler chain
- [ ] `tests/test_http_app.py` — add DEBT-02 auth tests: 401 without key, 200 with valid key, /health excluded
- [ ] `tests/test_vm_providers.py` — add DEBT-03 structural tests: error dicts from exception paths contain `error_type` and `detail`

*Existing test files cover happy paths — Wave 0 only needs new test functions in existing files.*

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
