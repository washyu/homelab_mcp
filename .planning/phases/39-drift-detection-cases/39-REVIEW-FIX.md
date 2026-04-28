---
phase: 39-drift-detection-cases
fixed_at: 2026-04-28T05:20:09Z
review_path: .planning/phases/39-drift-detection-cases/39-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 39: Code Review Fix Report

**Fixed at:** 2026-04-28T05:20:09Z
**Source review:** `.planning/phases/39-drift-detection-cases/39-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 5 (5 WARNING; 0 BLOCKER — re-review pass after the
  prior 12-finding remediation)
- Fixed: 5
- Skipped: 0

All five WARNINGs from the re-review of Phase 39 are addressed. The
test suite (`uv run pytest tests/ -m "not integration"`) passes 845
tests with 15 skipped. `uv run ruff check src/` and
`uv run mypy src/homelab_mcp/drift_detection.py` are clean.

## Fixed Issues

### WR-A: BL-03 dedupe key collides across clusters with shared (vm_name, vmid)

**Files modified:** `src/homelab_mcp/drift_detection.py`
**Commit:** c3680b5
**Applied fix:** Changed the `_enumerate_unknown_vms._make_row` dedupe
key from `(name.lower(), vmid)` to `(hypervisor, name.lower(), vmid)`
and updated `seen_keys` type annotation to
`set[tuple[str, str, int]]`. The BL-03 cold-cache N-copy collapse
still works because `_enumerate_proxmox_vms` dedupes its enumeration
targets by `(cluster_name OR hostname)` upstream, so `cluster_vm_map`
carries one entry per cluster (not per node). Comment block updated
to describe both BL-03 and WR-A intent.

### WR-B: WR-04 fix preserves dead code; the new `logger.error` is itself unreachable

**Files modified:** `src/homelab_mcp/drift_detection.py`
**Commit:** e12d544
**Applied fix:** Replaced the unreachable `logger.error(...)` +
sentinel-return-`probe_one_unreachable_fallthrough` after the
`async with semaphore:` block with `raise AssertionError(
f"_probe_one reached unreachable fallthrough for hostname={hostname!r}")`.
Mypy's exhaustiveness check is already satisfied by the inner
`except Exception as exc: return ...`, so the explicit `raise` is a
defensive belt: if a future refactor splits the broad except into
narrower clauses without re-establishing exhaustiveness, this line
both satisfies mypy AND fails loudly at runtime instead of silently
emitting a sentinel into the probe map. Verified mypy still passes.

### WR-C: Telemetry-cache fallback resolver call uncaught for non-credential errors

**Files modified:** `src/homelab_mcp/drift_detection.py`
**Commit:** 412440b
**Applied fix:** Selected the "widen except + route to unreachable"
option (the more defensive of the two suggestions). Added a parallel
sentinel `transient_resolver_exc:
aiohttp.ClientError | TimeoutError | ValueError | None = None`
alongside the existing `resolver_exc`, added an
`except (aiohttp.ClientError, TimeoutError, ValueError) as exc:`
clause to the resolver fallback block, and added an
`elif transient_resolver_exc is not None:` branch that calls
`_classify_unreachable` and appends a record (with possible
`missing` promotion) to the `unreachable` bucket. The new branch
reuses the same WR-01 + WR-E `last_seen` normalization pattern
applied to the other two unreachable sites. The Phase 38.1 D-15
"no continue in scan_drift row loop" invariant is preserved — the
new branch is a sibling `elif`, not a `continue`. Verified the
existing AST guards (`tests/test_ast_regression.py`) still pass.

### WR-D: SSH probe `_error` results silently treated as "no drift"

**Files modified:** `src/homelab_mcp/drift_detection.py`
**Commit:** 6d79f00
**Applied fix:** Selected option (c) from the review (warning-level
log) because options (a) and (b) — adding a `partial: true` flag to
the probed_ok record OR a top-level `probe_warnings` field — would
break the locked envelope shape. The
`test_per_row_record_shape_preserved_for_probed_ok` AST contract
asserts `set(record.keys()) == expected_keys` (exact 7 keys); adding
fields would fail that test. Instead, when `stored_fp` is non-empty
AND the SSH probe map for the host contains `_error` (i.e., probe
failed AND a drift comparison was meaningful), log at warning level
with the sanitized `_error` string. Operators see the failure in
logs without the response envelope shape changing. Logging happens
before the diff comparison so the warning fires every scan until
SSH is repaired.

### WR-E: WR-01 last_seen normalization is partial when parse fails

**Files modified:** `src/homelab_mcp/drift_detection.py`
**Commit:** c8f324f
**Applied fix:** Replaced the
`record["last_seen"] = parsed.isoformat() if parsed else row.get("last_seen")`
one-liner with the explicit three-branch coercion the review
recommended at both unreachable sites in `scan_drift`'s row loop:
1. `parsed is not None` → `parsed.isoformat()` (success path)
2. `raw_last_seen is not None` → `str(raw_last_seen)` (defensive
   fallback so integer epochs, `date` objects, vendor-format strings
   all serialize as JSON strings)
3. else → `None`
The same coercion pattern was already applied to the new resolver-
fallback site introduced by WR-C, so all three unreachable-record
construction sites use the WR-E pattern uniformly.

## Verification

- `uv run pytest tests/ -m "not integration"`: **845 passed, 15
  skipped** (unchanged from pre-fix counts; no test regressions)
- `uv run ruff check src/`: **All checks passed!**
- `uv run mypy src/homelab_mcp/drift_detection.py`: **Success: no
  issues found in 1 source file**
- Pre-commit hooks (ruff lint, ruff format, mypy, AST/syntax checks)
  passed on every commit.

## Notes

- **Logic-bug caveat (WR-D):** The fix is intentionally minimal
  (warning-level log only, no envelope-shape change). A more visible
  surface (top-level `probe_warnings` array OR per-record `partial`
  flag) would require relaxing the existing 7-key probed_ok AST
  contract first. Tracking as a follow-up if operators report
  silent-disable surprises.
- **WR-A scope:** The dedupe is now keyed on `hypervisor` (the dict
  key in `cluster_vm_map`, which is the representative hostname per
  cluster, not per node). This addresses the cross-cluster collision
  the reviewer described. If two clusters genuinely share the same
  representative-hostname identity (a misconfiguration, not a normal
  homelab pattern), they'd still collapse — that's a separate
  enumeration-layer issue, out of scope for WR-A.
- **WR-C placement:** The new `elif transient_resolver_exc is not None`
  branch lives inside `scan_drift`'s row loop. The Phase 38.1 D-15
  AST guard forbids `continue` in that loop, so the simple "catch
  and `continue`" pattern from the review's suggestion was not
  applicable; the branch instead routes to `unreachable.append(...)`
  and lets the loop fall through to the next row naturally.

---

_Fixed: 2026-04-28T05:20:09Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
