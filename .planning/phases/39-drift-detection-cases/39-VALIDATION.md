---
phase: 39
slug: drift-detection-cases
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-27
---

# Phase 39 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (with pytest-asyncio plugin) |
| **Config file** | `pyproject.toml` (pytest-asyncio mode + markers); pytest discovers `tests/` |
| **Quick run command** | `uv run pytest tests/test_drift_detection.py tests/test_ast_regression.py -x -v` |
| **Full suite command** | `uv run pytest -m "not integration" -x` |
| **Estimated runtime** | ~10–15 seconds (drift + AST regression files); ~60 seconds full unit suite |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_drift_detection.py::TestPhase39Helpers tests/test_ast_regression.py -x` (~3–5 s, all unit + AST guards)
- **After every plan wave:** Run `uv run pytest tests/test_drift_detection.py tests/test_ast_regression.py -x -v` (~10–15 s)
- **Before `/gsd-verify-work`:** Full unit suite green — `uv run pytest -m "not integration" -x` + `uv run ruff check src/ tests/` + `uv run mypy src/`
- **Max feedback latency:** 15 seconds (per-wave); 5 seconds (per-task)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 39-01-01 | 01 | 1 | DRFT-19 | — | N/A | unit | `pytest tests/test_drift_detection.py::TestPhase39Helpers::test_diff_fingerprints_per_leaf_present_in_both -x` | ❌ W0 | ⬜ pending |
| 39-01-02 | 01 | 1 | DRFT-19 | — | N/A | unit | `pytest tests/test_drift_detection.py::TestPhase39Helpers::test_diff_fingerprints_dotted_path -x` | ❌ W0 | ⬜ pending |
| 39-01-03 | 01 | 1 | DRFT-19 | T-V5 | env-var clamp; positive int | unit | `pytest tests/test_drift_detection.py::TestPhase39Helpers::test_classify_unreachable_timezone_normalization -x` | ❌ W0 | ⬜ pending |
| 39-01-04 | 01 | 1 | DRFT-19 | — | N/A | unit | `pytest tests/test_drift_detection.py::TestPhase39Helpers::test_probe_universal_core_extraction_parity -x` | ❌ W0 | ⬜ pending |
| 39-01-05 | 01 | 1 | DRFT-17 | — | N/A | unit | `pytest tests/test_drift_detection.py::TestPhase39Helpers::test_enumerate_unknown_case_insensitive -x` | ❌ W0 | ⬜ pending |
| 39-02-01 | 02 | 2 | DRFT-17 | — | N/A | functional | `pytest tests/test_drift_detection.py::TestPhase39Unknown::test_unmatched_vm_in_unknown_bucket -x` | ❌ W0 | ⬜ pending |
| 39-02-02 | 02 | 2 | DRFT-17 | — | N/A | functional | `pytest tests/test_drift_detection.py::TestPhase39Unknown::test_cluster_dedup_single_enumeration -x` | ❌ W0 | ⬜ pending |
| 39-03-01 | 03 | 2 | DRFT-18 | — | N/A | functional | `pytest tests/test_drift_detection.py::TestPhase39Missing::test_old_last_seen_promotes_to_missing -x` | ❌ W0 | ⬜ pending |
| 39-03-02 | 03 | 2 | DRFT-18 | T-V5 | env-var override | unit | `pytest tests/test_drift_detection.py::TestPhase39Missing::test_threshold_env_var_override -x` | ❌ W0 | ⬜ pending |
| 39-03-03 | 03 | 2 | DRFT-18 | — | N/A | functional | `pytest tests/test_drift_detection.py::TestPhase39Missing::test_recent_unreachable_not_promoted -x` | ❌ W0 | ⬜ pending |
| 39-03-04 | 03 | 2 | DRFT-19 | — | N/A | functional | `pytest tests/test_drift_detection.py::TestPhase39Changed::test_kernel_change_in_changed_bucket -x` | ❌ W0 | ⬜ pending |
| 39-03-05 | 03 | 2 | DRFT-19 | — | N/A | functional | `pytest tests/test_drift_detection.py::TestPhase39Changed::test_no_diff_stays_probed_ok -x` | ❌ W0 | ⬜ pending |
| 39-03-06 | 03 | 2 | DRFT-19 | T-V7 | sanitize_error on error fields | functional | `pytest tests/test_drift_detection.py::TestPhase39Changed::test_drift_does_not_update_fingerprint -x` | ❌ W0 | ⬜ pending |
| 39-03-07 | 03 | 2 | D-10 | — | N/A | functional | `pytest tests/test_drift_detection.py::TestPhase39Bucket::test_scanned_equals_counts_sum -x` | ❌ W0 | ⬜ pending |
| 39-03-08 | 03 | 2 | D-10 | — | N/A | functional | `pytest tests/test_drift_detection.py::TestPhase39Bucket::test_changed_host_with_unknown_vms -x` | ❌ W0 | ⬜ pending |
| 39-03-09 | 03 | 2 | D-11 | — | AST guard preserved | regression | `pytest tests/test_ast_regression.py::TestPhase39DriftCases -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_drift_detection.py::TestPhase39Helpers` — unit tests for `_diff_fingerprints`, `_classify_unreachable`, `_enumerate_unknown_vms`, `_probe_universal_core` extraction parity
- [ ] `tests/test_drift_detection.py::TestPhase39Unknown` — DRFT-17 functional tests (≥ 2)
- [ ] `tests/test_drift_detection.py::TestPhase39Missing` — DRFT-18 functional tests (≥ 3)
- [ ] `tests/test_drift_detection.py::TestPhase39Changed` — DRFT-19 functional tests (≥ 4)
- [ ] `tests/test_drift_detection.py::TestPhase39Bucket` — D-10 invariants (≥ 2 tests including `scanned == sum(counts)`)
- [ ] `tests/test_ast_regression.py::TestPhase39DriftCases` — D-11(b) extension for new helpers
- [ ] `tests/conftest.py` fixture additions: `freeze_now`, `mock_universal_core_probe_response`, `mock_universal_core_probe_drifted`, `mock_cluster_resources_response`, `sitemap_row_old_last_seen`, `sitemap_row_recent_last_seen`, `sitemap_row_with_stored_fingerprint`, `mock_resolve_ssh_credentials`, `mock_ssh_connect`
- [ ] No new pytest plugins required.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| End-to-end live drift scan against real Proxmox cluster + SSH hosts | DRFT-17/18/19 | Requires real lab — not reproducible in CI | After phase merge, run `uv run python -c "from homelab_mcp.drift_detection import scan_drift; import asyncio; print(asyncio.run(scan_drift()))"` against live homelab; confirm at least one host appears with expected bucket. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15 s (per-wave) / < 5 s (per-task)
- [ ] `nyquist_compliant: true` set in frontmatter (after wave 0 stubs land)

**Approval:** pending
