---
phase: 2
slug: security-hardening
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-09
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio |
| **Config file** | pyproject.toml (pytest section) |
| **Quick run command** | `uv run pytest tests/ -m "not integration" -x -q` |
| **Full suite command** | `uv run pytest tests/ -m "not integration" -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -m "not integration" -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -m "not integration" -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 0 | SEC-01 | unit | `uv run pytest tests/test_ssh_connection.py -x` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 0 | SEC-03 | unit | `uv run pytest tests/test_validation.py -x` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 0 | SEC-04 | unit | `uv run pytest tests/test_log_filter.py -x` | ❌ W0 | ⬜ pending |
| 02-01-04 | 01 | 0 | SEC-02 | unit | `uv run pytest tests/test_proxmox_api.py -x` | ✅ | ⬜ pending |
| 02-02-01 | 01 | 1 | SEC-01 | unit | `uv run pytest tests/test_ssh_connection.py::test_tofu_first_connection -x` | ❌ W0 | ⬜ pending |
| 02-02-02 | 01 | 1 | SEC-01 | unit | `uv run pytest tests/test_ssh_connection.py::test_tofu_rejects_mismatch -x` | ❌ W0 | ⬜ pending |
| 02-02-03 | 01 | 1 | SEC-01 | unit | `uv run pytest tests/test_ssh_connection.py::test_tofu_accepts_known_key -x` | ❌ W0 | ⬜ pending |
| 02-03-01 | 02 | 1 | SEC-02 | unit | `uv run pytest tests/test_proxmox_api.py::test_ssl_verify_default_true -x` | ❌ W0 | ⬜ pending |
| 02-03-02 | 02 | 1 | SEC-02 | unit | `uv run pytest tests/test_proxmox_api.py::test_ssl_custom_ca_cert -x` | ❌ W0 | ⬜ pending |
| 02-04-01 | 03 | 1 | SEC-03 | unit | `uv run pytest tests/test_validation.py::test_valid_hostnames -x` | ❌ W0 | ⬜ pending |
| 02-04-02 | 03 | 1 | SEC-03 | unit | `uv run pytest tests/test_validation.py::test_invalid_hostnames -x` | ❌ W0 | ⬜ pending |
| 02-04-03 | 03 | 1 | SEC-03 | unit | `uv run pytest tests/test_validation.py::test_port_validation -x` | ❌ W0 | ⬜ pending |
| 02-05-01 | 04 | 2 | SEC-04 | unit | `uv run pytest tests/test_log_filter.py::test_redacts_password -x` | ❌ W0 | ⬜ pending |
| 02-05-02 | 04 | 2 | SEC-04 | unit | `uv run pytest tests/test_log_filter.py::test_sanitize_error -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_ssh_connection.py` — stubs for SEC-01 (TOFU behavior with mocked asyncssh)
- [ ] `tests/test_validation.py` — stubs for SEC-03 (hostname, IP, port validation)
- [ ] `tests/test_log_filter.py` — stubs for SEC-04 (credential redaction)
- [ ] Update `tests/test_proxmox_api.py` — add SEC-02 test stubs (SSL default, CA cert)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SSH TOFU prompt on real host | SEC-01 | Requires actual SSH server | Connect to a test VM, verify key stored in `~/.homelab_mcp/known_hosts` |
| Proxmox SSL with self-signed cert | SEC-02 | Requires Proxmox instance | Set `PROXMOX_CA_CERT`, verify connection succeeds |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
