---
phase: 41
slug: binding-aware-resolver-hygiene
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-29
---

# Phase 41 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: 41-RESEARCH.md §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-asyncio |
| **Config file** | pyproject.toml (pytest section) |
| **Quick run command** | `uv run pytest tests/ -m "not integration" -x --ff` |
| **Full suite command** | `uv run pytest tests/ -m "not integration"` |
| **Estimated runtime** | ~30 seconds (unit subset) |

---

## Sampling Rate

- **After every task commit:** Run quick command (focused on the touched module's tests)
- **After every plan wave:** Run full unit suite
- **Before `/gsd-verify-work`:** Full unit suite must be green; AST regression suite green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

> Filled by planner during PLAN.md generation. Each task references this row by ID.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 41-01-01 | 01 | 0 | Bug AA | — | RED test fails before helper exists | functional | `uv run pytest tests/test_phase41_binding_aware.py::test_discover_uses_row_binding -x` | ❌ W0 | ⬜ pending |
| 41-01-02 | 01 | 0 | Bug BB | — | RED test fails before error-row identifier fix | functional | `uv run pytest tests/test_phase41_binding_aware.py::test_failed_discover_does_not_collapse -x` | ❌ W0 | ⬜ pending |
| 41-01-03 | 01 | 0 | Bug V | — | RED test fails before connection_ip dial | functional | `uv run pytest tests/test_phase41_binding_aware.py::test_dials_connection_ip_not_hostname -x` | ❌ W0 | ⬜ pending |
| 41-02-01 | 02 | 1 | Bug AA | — | New helper resolves creds via row binding | unit | `uv run pytest tests/test_ssh_tools.py::test_resolve_ssh_for_sitemap_row -x` | ❌ W0 | ⬜ pending |
| 41-03-01 | 03 | 2 | Bug AA + BB | — | discover_and_store wires through helper | functional | `uv run pytest tests/test_phase41_binding_aware.py::test_discover_uses_row_binding -x` | ❌ W0 | ⬜ pending |
| 41-04-01 | 04 | 3 | Bug V | — | drift + Proxmox dial connection_ip | functional | `uv run pytest tests/test_phase41_binding_aware.py::test_dials_connection_ip_not_hostname -x` | ❌ W0 | ⬜ pending |
| 41-05-01 | 05 | 4 | AST guard | — | Both call sites use shared helper (AST-locked) | meta | `uv run pytest tests/test_ast_regression.py::TestPhase41BindingAwareResolver -x` | ❌ W0 | ⬜ pending |

*Plan/task IDs above are a researcher-suggested decomposition; the planner can renumber to match its actual plan layout. The verification map will be updated after planning.*

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_phase41_binding_aware.py` — RED regression tests for Bugs AA, BB, V
- [ ] `tests/test_ast_regression.py::TestPhase41BindingAwareResolver` — AST guard scaffold (initial RED state)
- [ ] No new fixtures required — existing `tests/conftest.py` covers SQLite setup, asyncssh mocks, keyring fakes

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| End-to-end UAT against live Proxmox host | Bug AA | Requires real `pve` host, real keyring entry, real sitemap row | Per project memory, manual UAT batched at milestone close. Add scenario to `HUMAN-UAT.md`: `discover_and_map hostname=pve` succeeds without `hostname=<ip>` workaround. |
| External-DNS-not-required scan | Bug V | Requires environment without /etc/hosts entry for sitemap row | UAT: remove `pve` from /etc/hosts, run discover_and_map; expect success via `connection_ip`. |
| Failed-discovery row tagging | Bug BB | Requires intentionally bad target | UAT: `discover_and_map hostname=nonexistent-host`; assert error row matches input identifier, no degenerate-hostname zombie row appears. |

*All three Bug-AA/BB/V failure-mode scenarios are covered by automated functional tests in Wave 0 RED. Manual UAT is the production-environment validation, deferred per project policy.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify command or Wave 0 dependency
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (RED tests + AST scaffold)
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter once planner backfills task IDs

**Approval:** pending
