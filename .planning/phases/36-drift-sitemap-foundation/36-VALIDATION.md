---
phase: 36
slug: drift-sitemap-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-25
---

# Phase 36 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio (existing) |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/ -m "not integration" -x --tb=short` |
| **Full suite command** | `uv run pytest tests/ -x --tb=short` |
| **Estimated runtime** | ~30 seconds (unit) / ~3 minutes (full incl. Postgres integration) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -m "not integration" -x --tb=short` (filtered to touched test files where possible)
- **After every plan wave:** Run `uv run pytest tests/ -m "not integration" -x --tb=short`
- **Before `/gsd-verify-work`:** Full suite (incl. integration) must be green plus `uv run ruff check src/ tests/` and `uv run mypy src/`
- **Max feedback latency:** 60 seconds (unit subset)

---

## Per-Task Verification Map

> Task IDs to be filled in during plan generation. Below is the requirement → test-type mapping the planner uses to wire `<automated>` blocks.

| Plan Area | Wave | Requirement | Test Type | Automated Command |
|-----------|------|-------------|-----------|-------------------|
| AST regression guards (D-12/D-13) | 1 | DRFT-21 / SC-4 | meta | `uv run pytest tests/test_ast_regression.py::test_drift_detection_no_baseline_references_phase36 -v` |
| Migration drop step SQLite (D-05) | 1 | DRFT-21 / SC-1 | unit | `uv run pytest tests/test_database.py -k migration -v` |
| Migration drop step Postgres (D-05) | 1 | DRFT-21 / SC-1 | integration | `uv run pytest tests/integration/ -m integration -k drift_baselines -v` |
| Adapter method removal (D-06/D-07) | 1 | DRFT-21 / SC-1 | unit | `uv run pytest tests/test_database.py -v` (TestDriftBaselines class deleted; rest stays green) |
| `scan_drift` 2-bucket shape (D-01/D-02/D-09/D-09a/D-10) | 2 | DRFT-11 / DRFT-12 / SC-2 / SC-3 | unit | `uv run pytest tests/test_drift_detection.py -v` |
| Precondition removal — empty sitemap success (D-03) | 2 | DRFT-12 / SC-2 | unit | `uv run pytest tests/test_drift_detection.py::test_scan_drift_empty_sitemap_returns_success -v` |
| Inert-passthrough schema description (D-04) | 2 | DRFT-12 | unit | `uv run pytest tests/test_tool_schemas.py -k drift -v` (or new test asserting description) |
| `update_baseline_after_mutation` removal (D-11) | 2 | DRFT-21 / SC-3 | unit | `uv run pytest tests/test_proxmox_baseline_hooks.py` should fail-to-collect (file deleted); `tests/test_proxmox_api.py` patches removed and tests pass |
| Drift resource cache pass-through (D-18) | 2 | DRFT-11 | unit | `uv run pytest tests/test_drift_resource.py -v` |
| Docs sweep (D-19) | 2 | DRFT-11 | manual | `grep -rn "register_drift_baseline\|list_drift_baselines\|delete_drift_baseline" docs/` returns empty |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_ast_regression.py` — already exists (Phase 32/33/35); extend `FORBIDDEN_SOURCE_STRINGS` and add `test_drift_detection_no_baseline_references_phase36()`
- [x] `tests/test_drift_detection.py` — exists; full rewrite per CONTEXT.md D-16
- [x] `tests/test_database.py` — exists; delete `TestDriftBaselines` class only
- [x] `tests/test_drift_resource.py` — exists; verify cache shape compatibility
- [x] `tests/integration/` — Postgres harness already in place (Phase 33/35); reuse for D-15 idempotency test
- [ ] Confirm `tests/test_proxmox_baseline_hooks.py` deletion (research finding — orphaned by D-11; not in CONTEXT.md D-16)
- [ ] Confirm 4 patch lines in `tests/test_proxmox_api.py` (lines ~1784/1825/1854/1893) removed (research finding)

*Existing infrastructure covers all phase requirements; only test-content changes are needed (no new framework installs).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Migration banner on real upgrade path | DRFT-21 / SC-1 | Banner is stderr emission only on first-run-with-table; reproduces only on a DB that pre-contains rows | Start server with a SQLite DB containing a `drift_baselines` table; observe stderr matches D-08 banner; restart server, observe banner is absent (idempotent) |
| Production-log resolver telemetry | DRFT-12 / SC-2 | `get_proxmox_client` logs `DEBUG: proxmox resolve host=X tier=node HIT/MISS` — verifying live wiring requires a running server with at least one Proxmox host registered | With `LOG_LEVEL=DEBUG` and a registered Proxmox host: call `scan_infrastructure_drift`; confirm log shows resolver tier (per-node or cluster) for each probed row |
| `grep -rn "drift_baselines" src/` returns only `migration.py` | DRFT-21 / SC-3 | Architectural assertion — AST meta-test enforces this in CI but a one-time human check on the merged result is the SC-3 verification language | After merge to feature branch: `grep -rn "drift_baselines\|get_all_drift_baselines\|upsert_drift_baseline\|get_drift_baseline" src/homelab_mcp/ \| grep -v migration.py` returns no matches |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (test files exist; only content changes)
- [ ] No watch-mode flags (pytest one-shot only)
- [ ] Feedback latency < 60s for unit subset
- [ ] `nyquist_compliant: true` set in frontmatter once planner wires per-task `<automated>` blocks

**Approval:** pending
