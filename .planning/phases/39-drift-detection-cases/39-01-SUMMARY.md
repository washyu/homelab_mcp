---
phase: 39-drift-detection-cases
plan: 01
subsystem: drift-detection
tags: [drift, fingerprint, ssh-probe, helpers, phase-39, wave-0]
dependency_graph:
  requires:
    - "Phase 38 D-04 (universal-core probes in ssh_discover_system)"
    - "Phase 38 D-10 (fingerprint top-level dict on device rows)"
    - "Phase 38.1 D-15 AST guard (no continue in scan_drift row loop)"
    - "Phase 35 D-05 (_run_with_timeout per-probe wrapping)"
  provides:
    - "_probe_universal_core (ssh_tools.py async helper for universal-core fingerprint)"
    - "_diff_fingerprints (drift_detection.py per-leaf dotted-path diff)"
    - "_enumerate_unknown_vms (drift_detection.py per-VM unknown[] flattener)"
    - "_classify_unreachable (drift_detection.py missing-vs-unreachable router)"
    - "_missing_threshold_days (drift_detection.py env-var clamp)"
    - "_parse_last_seen (drift_detection.py UTC-aware naive-isoformat normalizer)"
    - "tests/conftest.py (9 shared Phase 39 fixtures)"
    - "TestPhase39Helpers (15 unit tests)"
  affects:
    - "ssh_discover_system (refactored to call _probe_universal_core; behavior unchanged)"
tech_stack:
  added: []
  patterns:
    - "Loop-free helpers (D-11b) — no `continue` inside any new helper; outer caller appends"
    - "filter(None, generator) extend pattern for per-row helpers"
    - "Inner _walk recursion for tree diff (no module-level recursion)"
    - "monkeypatch.setattr fake-datetime fixture for deterministic clock"
key_files:
  created:
    - "tests/conftest.py"
    - ".planning/phases/39-drift-detection-cases/39-01-SUMMARY.md"
  modified:
    - "src/homelab_mcp/ssh_tools.py"
    - "src/homelab_mcp/drift_detection.py"
    - "tests/test_drift_detection.py"
decisions:
  - "Extracted _probe_universal_core into ssh_tools.py (sibling of ssh_discover_system) rather than re-implementing inline in scan_drift — keeps Phase 38 D-04's canonical probe set as single source of truth."
  - "Narrowed _classify_unreachable's exc parameter to Exception (not BaseException) so sanitize_error's existing signature accepts it without an Exception narrowing dance — TimeoutError and aiohttp.ClientError (the canonical drift caller exceptions) are both Exception subclasses."
  - "All five drift helpers are sibling functions, not nested inside scan_drift — Phase 38.1 D-15 AST guard's targeted scope (n.name == 'scan_drift') stays untouched, and the new helpers are loop-free w.r.t. bucket appends per D-11(b) (verified by inline ast.Continue == 0 check)."
metrics:
  duration: "~30 minutes"
  completed_date: "2026-04-27"
  tasks_completed: 3
  files_created: 1
  files_modified: 3
  test_count: 15
  test_class: "TestPhase39Helpers"
requirements:
  - DRFT-17-helpers
  - DRFT-18-helpers
  - DRFT-19-helpers
---

# Phase 39 Plan 01: Drift Detection Helpers Summary

Extracted the universal-core SSH probe block from `ssh_discover_system` into a reusable `_probe_universal_core` helper, added five pure-function helpers (`_diff_fingerprints`, `_classify_unreachable`, `_enumerate_unknown_vms`, `_missing_threshold_days`, `_parse_last_seen`) that Plans 02 and 03 will compose into `scan_drift`, and landed `tests/conftest.py` with 9 shared Phase 39 fixtures plus `TestPhase39Helpers` covering 15 unit tests — all GREEN, all AST guards green, mypy/ruff clean.

## Helpers Added

### `src/homelab_mcp/ssh_tools.py`

| Symbol | Lines | Signature | Returns |
|--------|-------|-----------|---------|
| `_probe_universal_core` | 435–528 | `async def _probe_universal_core(conn: asyncssh.SSHClientConnection, timed_out_commands: list[str])` | `dict[str, Any]` (up to 5 keys: kernel_name, kernel_version, os_name, os_version, package_fingerprint) |

### `src/homelab_mcp/drift_detection.py`

| Symbol | Lines | Signature | Returns |
|--------|-------|-----------|---------|
| `_missing_threshold_days` | 136 | `def _missing_threshold_days()` | `int` (clamped positive; default 7) |
| `_parse_last_seen` | 149 | `def _parse_last_seen(raw: str \| None)` | `datetime \| None` (UTC-aware) |
| `_classify_unreachable` | 165 | `def _classify_unreachable(row, exc, threshold_days, now)` | `tuple[Literal["unreachable", "missing"], str]` |
| `_diff_fingerprints` | 193 | `def _diff_fingerprints(stored, current)` | `dict[str, dict[str, Any]]` (dotted-path → {stored, current}) |
| `_enumerate_unknown_vms` | 221 | `def _enumerate_unknown_vms(cluster_vm_map, sitemap_hostnames, scan_timestamp)` | `list[dict[str, Any]]` |

Module-level constant added: `_DEFAULT_THRESHOLD_DAYS: int = 7` (Phase 39 D-02).

## Extraction Summary

`ssh_discover_system` shrank from inline fingerprint probes (~78 lines, original lines 614–691) to a 3-line call site:

```python
fingerprint_info = await _probe_universal_core(conn, timed_out_commands)
if fingerprint_info:
    system_info["fingerprint"] = fingerprint_info
```

The four `await _run_with_timeout(...)` calls and the `partial: True` enrollment semantics for non-zero exits all moved into the helper verbatim. Phase 35 AST guard (`test_ssh_discover_system_wraps_every_conn_run_phase35`) stays green because its targeted scope (`n.name == "ssh_discover_system"`) does not include sibling functions per D-12.

## Test Counts

| Class | Test Count | Status |
|-------|------------|--------|
| `TestPhase39Helpers` | 15 | All GREEN |

15/15 tests pass:

- 4× `_diff_fingerprints` (per-leaf present-in-both, dotted-path, top-level kernel, equal-empty)
- 3× `_classify_unreachable` (old → missing, recent → unreachable, naive-tz normalization)
- 3× `_missing_threshold_days` (default, env override, invalid fallback)
- 2× `_parse_last_seen` (naive string, none/malformed)
- 2× `_enumerate_unknown_vms` (case-insensitive match, unmatched VM record)
- 1× `_probe_universal_core` (extraction parity vs Phase 38 schema)

Broader sweep (`tests/test_drift_detection.py tests/test_drift_wiring.py tests/test_drift_resource.py tests/test_ast_regression.py`) — 69 tests pass, 0 fail.

## AST Guard Verification

| Guard | Source | Status |
|-------|--------|--------|
| Phase 35 D-15 — `test_ssh_discover_system_wraps_every_conn_run_phase35` | `tests/test_ast_regression.py:447` | GREEN (sibling extraction does not enter scope) |
| Phase 38.1 D-15 — `test_scan_drift_no_continue_in_row_loop_phase38_1` | `tests/test_ast_regression.py:763` | GREEN (`scan_drift` body unchanged) |
| Phase 39 D-11(b) — inline `ast.Continue` count | `python -c "..."` snippet in plan verify | GREEN (0 in every new helper) |

## Commit Hashes

| # | Type | Commit | Description |
|---|------|--------|-------------|
| 1 | RED | `63298c9` | `test(39-01): wave 0 RED tests for drift helpers and conftest fixtures` |
| 2 | Refactor | `a45c496` | `refactor(39-01): extract _probe_universal_core helper from ssh_discover_system` |
| 3 | Feature | `a04ef52` | `feat(39-01): add diff/enumerate/classify/threshold helpers for drift cases` |

## Files Modified

- `src/homelab_mcp/ssh_tools.py` — added `_probe_universal_core` (lines 435–528); refactored `ssh_discover_system` fingerprint block to call it.
- `src/homelab_mcp/drift_detection.py` — added imports (`os`, `Literal`); added `_DEFAULT_THRESHOLD_DAYS` constant + 5 helpers (lines 136–267).
- `tests/test_drift_detection.py` — added imports for the 6 new helpers; appended `TestPhase39Helpers` class with 15 tests.
- `tests/conftest.py` — NEW file with 9 shared Phase 39 fixtures (`freeze_now`, probe responses, sitemap rows, SSH mocks).

## Deviations from Plan

**One small deviation:** `_classify_unreachable`'s `exc` parameter is typed `Exception` rather than `BaseException` as specified in the plan's `<behavior>`.

- **Found during:** Task 3 GREEN — mypy strict reported `Argument 1 to "sanitize_error" has incompatible type "BaseException"; expected "Exception"`.
- **Issue:** `log_filter.sanitize_error` already accepts `Exception` (not `BaseException`) — narrowing `exc` to `Exception` is a one-character fix that keeps the type chain consistent.
- **Fix:** Changed `BaseException` → `Exception` in the helper signature.
- **Why this is safe:** The two canonical caller exceptions in drift's SSH pre-pass (`TimeoutError`, `aiohttp.ClientError`) are both `Exception` subclasses, so the runtime contract is unchanged. Catching `BaseException` (which includes `KeyboardInterrupt`, `SystemExit`) was never the intent — drift should propagate those, not classify them as "unreachable".
- **Files modified:** `src/homelab_mcp/drift_detection.py` (within Task 3 commit `a04ef52`)
- **Tracked as:** `[Rule 1 — Bug]` Auto-fix to satisfy mypy without changing behavior.

No other deviations.

## Quality Gates

- `uv run pytest tests/test_drift_detection.py::TestPhase39Helpers -x` — **15 passed**
- `uv run pytest tests/test_drift_detection.py tests/test_drift_wiring.py tests/test_drift_resource.py tests/test_ast_regression.py -x` — **69 passed**
- `uv run mypy src/homelab_mcp/ssh_tools.py src/homelab_mcp/drift_detection.py` — **clean**
- `uv run ruff check src/homelab_mcp/ssh_tools.py src/homelab_mcp/drift_detection.py tests/test_drift_detection.py tests/conftest.py` — **clean**
- AST `Continue` count in 5 new helpers — **0 each**

## Self-Check: PASSED

Verified files exist on disk:
- `tests/conftest.py` — FOUND
- `.planning/phases/39-drift-detection-cases/39-01-SUMMARY.md` — FOUND (this file)
- `src/homelab_mcp/ssh_tools.py::_probe_universal_core` — FOUND (line 435)
- `src/homelab_mcp/drift_detection.py::_diff_fingerprints` — FOUND (line 193)

Verified commits exist in git log:
- `63298c9` — FOUND (test commit)
- `a45c496` — FOUND (refactor commit)
- `a04ef52` — FOUND (feature commit)
