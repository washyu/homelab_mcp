---
phase: 35-sitemap-discovery-reliability-fix-discover-and-map-field-los
plan: 02
subsystem: sitemap
tags: [bug-fix, sitemap, json-columns, parallelism, null-defensiveness]
dependency-graph:
  requires:
    - "`ssh_discover_system` producer emits `usb_devices`/`pci_devices`/`block_devices` keys (Plan 01 does not change these)"
    - "Existing `parse_discovery_output` network_interfaces template at sitemap.py:97-98"
    - "Existing correct null-guard exemplar at sitemap.py:200-201"
  provides:
    - "`NetworkDevice` dataclass with three new JSON-string fields — `asdict()` produces `usb_devices`/`pci_devices`/`block_devices` keys for Plan 03's adapter column threading"
    - "`parse_discovery_output` reader extension — three new JSON-stringify writes on producer-side discovery data"
    - "`bulk_discover_and_store` parallelized with `asyncio.Semaphore(10)` + `asyncio.gather(return_exceptions=True)`"
    - "Module-level `_has_threshold_data(device, *fields)` helper for null/empty defensiveness"
  affects:
    - "src/homelab_mcp/sitemap.py — only file modified (scope-enforced)"
tech-stack:
  added:
    - "`asyncio` stdlib import in sitemap.py (was not previously imported)"
  patterns:
    - "`asyncio.gather(..., return_exceptions=True)` + dict-or-error coercion (I7)"
    - "`asyncio.Semaphore(N)` + `async with semaphore:` concurrency cap"
    - "`asyncio.Lock` for counter read-modify-write inside coroutine fan-out"
    - "Helper-function-based null defensiveness (`_has_threshold_data(device, *fields)`) with truthy-empty-string-as-missing semantics"
key-files:
  created: []
  modified:
    - src/homelab_mcp/sitemap.py
decisions:
  - "Adopted CONTEXT D-07 verbatim: `asyncio.gather(..., return_exceptions=True)` with post-gather dict-or-error coercion — guarantees `list[dict[str, Any]]` for json.dumps(results) regardless of stray raises outside `_discover_one`'s try/except (I7 fix)"
  - "Per-completion progress emit under `asyncio.Lock` (not per-position) — interleaved output but correct counter, matches CONTEXT D-07a"
  - "`_has_threshold_data` is module-level (not method on `NetworkSiteMap`) — placed above `NetworkDevice` dataclass for locality with `logger`; pure predicate, no self-state needed"
  - "Treat `None` and `\"\"` as missing, `0` as present — a device with `cpu_cores=0` is unusual but valid and should enter the comparison"
  - "Preserved existing correct exemplar at line 200 (analyze_network_topology `cpu_cores is not None and cpu_cores <= 2`) untouched — style-unify refactor explicitly out of scope to avoid drift without functional benefit (PATTERNS guidance)"
  - "Preserved `disk_use_percent` truthy guards at lines 208/305 — `N%` string value, truthy-empty-string handling is correct there; switching to `is not None` would regress"
metrics:
  duration_minutes: 8
  completed: "2026-04-24"
  tasks_completed: 3
  files_modified: 1
  lines_added: ~128
  lines_removed: ~49
---

# Phase 35 Plan 02: Sitemap Field-Loss + Parallelism + Null-Defensiveness Summary

**One-liner:** Fixed D-09b (usb/pci/block device field-loss at reader end), D-07/D-07a (serial bulk-discovery hung-host pileup), and D-10/D-11/D-12/D-13 (null-to-0 coercion false positives) — single-file surgery on `sitemap.py`.

## Objective

Three concerns, one file (`src/homelab_mcp/sitemap.py`), no overlap with Plan 01's `ssh_tools.py` scope:

1. **D-09b (reader extension):** `parse_discovery_output` ignored `usb_devices`/`pci_devices`/`block_devices` producer keys — reader had no branches for them.
2. **D-07/D-07a (bulk parallelism):** Serial `for` loop stacked N hung hosts × 120s serially — catastrophic wall time on large inventories.
3. **D-10/D-11/D-12/D-13 (null-threshold defensiveness):** `cpu_cores or 0` coerced `None` to `0`, producing a false-positive "every null-cpu device is low-resource → upgrade recommendation" bug at `:297` and a false-negative load-balancer-candidate miss at `:256`.

## What Changed

### Task 1 — `NetworkDevice` + `parse_discovery_output` (D-09b)

- Added 3 new JSON-string fields to `NetworkDevice` dataclass with `None` defaults, grouped directly after `network_interfaces`:
  - `usb_devices: str | None = None`
  - `pci_devices: str | None = None`
  - `block_devices: str | None = None`
- Added 3 parallel JSON-stringify writes in `parse_discovery_output`, mirroring the existing `network_interfaces` pattern — gated on `"<key>" in discovery_data`.
- `asdict(device)` now produces all three keys for downstream adapter consumption (Plan 03 threading).

**Commit:** `d5e686c`

### Task 2 — `bulk_discover_and_store` parallelization (D-07, D-07a)

- Added `import asyncio` at module top (was not previously imported).
- Replaced the entire body of `bulk_discover_and_store` (previously a serial `for i, target in enumerate(targets):` loop):
  - `asyncio.Semaphore(10)` caps concurrent SSH sessions to 10 (prevents FD exhaustion and SSH-server-side rate-limit triggers on large inventories).
  - Inner async closure `_discover_one(target)` holds the semaphore, increments a locked counter, emits start+completion progress, and converts caught exceptions to error-dicts using `sanitize_error` (preserves existing redaction).
  - `asyncio.gather(*[_discover_one(t) for t in targets], return_exceptions=True)` — **matches CONTEXT D-07 verbatim**. This is the I7 fix: a surprise raise outside `_discover_one`'s try/except lands as an exception object in `raw_results` rather than aborting the whole gather.
  - Post-gather coercion: `[r if isinstance(r, dict) else {"status": "error", "message": str(r)} for r in raw_results]` normalizes to homogeneous `list[dict[str, Any]]` for clean `json.dumps(results)`.
  - `asyncio.Lock` guards `completed += 1; local_i = completed` read-modify-write — progress emit happens outside the lock (inside semaphore scope) to avoid holding the lock across network IO.

**Commit:** `b4be799`

### Task 3 — `_has_threshold_data` helper + null-defensive analyzer bodies (D-10, D-11, D-12, D-13)

- Added module-level `_has_threshold_data(device: dict[str, Any], *fields: str) -> bool` helper above `@dataclass NetworkDevice` (directly below the `logger = logging.getLogger(__name__)` line).
  - Treats `None` and `""` as missing (truthy-empty-string semantics consistent with existing `if device.get("disk_use_percent"):` guards).
  - Treats `0` as present — a device with `cpu_cores=0` is valid.
- Fixed **broken site #1** (`suggest_deployments` load-balancer candidates at former `:254-266`):
  - Removed `cpu_cores = device.get("cpu_cores") or 0`.
  - Wrapped in `if not _has_threshold_data(...): logger.debug(...); else: ...` with direct dict reads `device["cpu_cores"]` / `device["memory_total"]` inside the else branch.
- Fixed **broken site #2** (`suggest_deployments` upgrade recommendations at former `:294-307`):
  - Same transformation — removes the false-positive bug where `None or 0 = 0 <= 2 = True` flagged every null-cpu device as a low-resource upgrade candidate.
- **Preserved untouched:**
  - Correct exemplar at line 200 (`analyze_network_topology`): `cpu_cores is not None and cpu_cores <= 2` — no functional benefit to refactoring; style-unify explicitly out of scope per PATTERNS guidance.
  - `disk_use_percent` truthy guards at lines 208 and 305 — `N%` string means truthy-empty-string handling is correct there; `is not None` would regress on empty strings.

**Commit:** `dc15928`

## Files Modified

- `src/homelab_mcp/sitemap.py` — +128/-49 lines (3 tasks combined)

## Verification Output

### Unit tests

```
uv run pytest tests/test_sitemap.py -v --no-header
============================= 23 passed in 1.91s ==============================
```

### Lint + type gate

```
uv run ruff check src/homelab_mcp/sitemap.py  →  All checks passed!
uv run mypy src/homelab_mcp/sitemap.py         →  Success: no issues found in 1 source file
```

### Structural proofs (expected vs actual)

| Check | Expected | Actual |
|-------|----------|--------|
| `usb_devices: str \| None = None` | 1 | 1 |
| `pci_devices: str \| None = None` | 1 | 1 |
| `block_devices: str \| None = None` | 1 | 1 |
| `device.(usb\|pci\|block)_devices = json.dumps` | 3 | 3 |
| `asyncio.Semaphore(10)` | ≥1 | 2 (1 docstring ref + 1 code) |
| `return_exceptions=True` | ≥1 | 2 (1 comment + 1 code) |
| `device.get("cpu_cores") or 0` | 0 | 0 |
| `_has_threshold_data` | ≥3 (1 def + 2 calls) | 3 |
| `for i, target in enumerate(targets):` inside bulk function | 0 | 0 |

### Functional check

```
uv run python -c "from homelab_mcp.sitemap import NetworkDevice, _has_threshold_data; \
  d = NetworkDevice(hostname='x', connection_ip='y', last_seen='z', status='success'); \
  assert hasattr(d, 'usb_devices') and hasattr(d, 'pci_devices') and hasattr(d, 'block_devices')"
→  OK

uv run python -c "from homelab_mcp.sitemap import _has_threshold_data; \
  assert _has_threshold_data({'cpu_cores': 2, 'memory_total': '4Gi'}, 'cpu_cores', 'memory_total') is True; \
  assert _has_threshold_data({'cpu_cores': None, 'memory_total': '4Gi'}, 'cpu_cores', 'memory_total') is False; \
  assert _has_threshold_data({'cpu_cores': 2, 'memory_total': ''}, 'cpu_cores', 'memory_total') is False; \
  assert _has_threshold_data({'cpu_cores': 0, 'memory_total': '4Gi'}, 'cpu_cores', 'memory_total') is True"
→  OK
```

## Decisions Implemented

| ID | Decision | Implementation |
|----|----------|----------------|
| D-07 | Parallelize `bulk_discover_and_store` with `asyncio.gather` | `asyncio.gather(..., return_exceptions=True)` + error-dict coercion |
| D-07a | Concurrency cap 10 + per-completion progress | `asyncio.Semaphore(10)` + `asyncio.Lock` counter + start/completion emits |
| D-09b | Reader extension for USB/PCI/block device JSON columns | 3 new dataclass fields + 3 new `parse_discovery_output` writes |
| D-10 | Remove `or 0` / `or ""` coercion | Both broken sites replaced with helper-guarded branches |
| D-11 | `_has_threshold_data` helper with None/empty semantics | Module-level def; `for field in fields: if value is None or value == "": return False` |
| D-12 | Fix false-positive upgrade recommendation | Broken site #2 (`:296`) now skips null-cpu devices with `logger.debug` audit trail |
| D-13 | Explicit skip + `logger.debug` (not silent default) | Matches existing disk-usage skip template at lines 194/283 |
| I7 | CONTEXT D-07 alignment — `return_exceptions=True` + coerce | `raw_results` normalized to `list[dict[str, Any]]` before json.dumps |

## Deviations from Plan

None — plan executed exactly as written.

## Deferred Issues

None.

## Handoff to Plan 03

**New contract available:** `NetworkDevice` now carries `usb_devices`, `pci_devices`, `block_devices` as JSON-string fields with `None` defaults. `asdict(device)` produces all three keys for downstream adapter consumption.

**Plan 03 responsibilities:**
1. Thread `usb_devices`, `pci_devices`, `block_devices` through `SQLiteAdapter.store_device` column list (INSERT and UPDATE paths).
2. Thread the same three keys through `PostgreSQLAdapter.store_device` JSONB/column writes.
3. Add schema migration step to ALTER TABLE ADD COLUMN for the three new TEXT columns in both adapters.
4. Teach `SQLiteAdapter.get_all_devices` to JSON-decode the three new columns back to dicts (parallel to existing `network_interfaces` decode at `database.py` ~:320).

**Current reader contract:** `parse_discovery_output` JSON-stringifies on the presence gate `"<key>" in discovery_data` — producer (ssh_tools.py Plan 01) emits these keys under `system_info["usb_devices"]` / `["pci_devices"]` / `["block_devices"]`, already confirmed in PATTERNS.

## Handoff to Plan 04 (AST meta-test)

**Forbidden coercion patterns scanner (D-16) should find zero matches after this plan:**

- `grep -cE 'device\.get\("cpu_cores"\) or 0' src/homelab_mcp/sitemap.py` → 0 ✓
- `grep -cE 'device\.get\("memory_total"\) or ""' src/homelab_mcp/sitemap.py` → 0 ✓

**Correct patterns preserved (must NOT be flagged as violations):**

- `cpu_cores is not None and cpu_cores <= 2` at `analyze_network_topology` (line ~200) — pre-existing exemplar
- `if device.get("disk_use_percent"):` at lines 208, 305 — `N%` string, truthy-empty-string is correct

## Threat Flags

None. All `<threat_model>` entries in the plan were either mitigated as specified (T-35-02-01 semaphore cap, T-35-02-03 helper-guard skips, T-35-02-05 counter_lock, T-35-02-06 return_exceptions+coerce) or explicitly accepted (T-35-02-02 bounded JSON size, T-35-02-04 debug-level hostname in log). No new security-relevant surface introduced.

## Self-Check: PASSED

- [x] `src/homelab_mcp/sitemap.py` modified — FOUND
- [x] Commit `d5e686c` (Task 1 — NetworkDevice fields) — FOUND in git log
- [x] Commit `b4be799` (Task 2 — parallelization) — FOUND in git log
- [x] Commit `dc15928` (Task 3 — null defensiveness) — FOUND in git log
- [x] All 23 test_sitemap.py tests passing — VERIFIED
- [x] `ruff check src/homelab_mcp/sitemap.py` exits 0 — VERIFIED
- [x] `mypy src/homelab_mcp/sitemap.py` exits 0 — VERIFIED
- [x] `_has_threshold_data` functional behavior matches spec (None/""/0 cases) — VERIFIED
- [x] `NetworkDevice` import round-trip exposes all 3 new fields — VERIFIED
