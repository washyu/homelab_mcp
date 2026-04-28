---
phase: 39-drift-detection-cases
fixed_at: 2026-04-27T22:00:00Z
review_path: .planning/phases/39-drift-detection-cases/39-REVIEW.md
iteration: 1
findings_in_scope: 12
fixed: 12
skipped: 0
status: all_fixed
---

# Phase 39: Code Review Fix Report

**Fixed at:** 2026-04-27T22:00:00Z
**Source review:** .planning/phases/39-drift-detection-cases/39-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 12 (4 BLOCKER + 8 WARNING)
- Fixed: 12
- Skipped: 0

All 4 BLOCKER and 8 WARNING findings from the Phase 39 code review were
addressed. Each fix is committed atomically with a `fix(39): <ID>
<description>` message. Three fixes (WR-02, WR-04, WR-05) shipped with
new tests locking the changed contract; WR-04 deviates from the
reviewer's literal recommendation because the dead-code claim was wrong
(mypy DOES require the trailing return) — the spirit of the finding
("audible failure mode") is preserved by replacing the silent sentinel
with `logger.error` plus a clearly diagnostic return value.

Full unit-test suite: 845 passed, 15 skipped, 25 deselected (Phase 39
suite grew from 73 -> 77 tests).

## Fixed Issues

### BL-01: Duplicate-hostname rows collapse SSH probe results, mis-attributing fingerprints

**Files modified:** `src/homelab_mcp/drift_detection.py`
**Commit:** c0c0705
**Applied fix:** Dedupe by hostname inside `_bulk_universal_core_probes`
before invoking `_probe_one`. Empty/None hostnames and rows without
`ssh_credential_id` are filtered out at the same stage so duplicate
rows do not collide on the same `""` key. Runs outside scan_drift's
row loop, so the Phase 38.1 D-15 / Phase 39 D-12 AST guards do not
apply — a defensive `continue` is permitted here.

### BL-02: `int(vm.get("vmid", 0))` can crash the whole scan on a malformed Proxmox payload

**Files modified:** `src/homelab_mcp/drift_detection.py`
**Commit:** fb3bd94
**Applied fix:** Wrapped `int(vm.get("vmid", 0))` in try/except
`(ValueError, TypeError)` inside `_make_row`. Malformed records skip
via `return None` (consumed by `filter(None, ...)`) rather than
raising out of the generator and aborting the entire `scan_drift`
call. Preserves the D-10 contract that enumeration failures don't
move hosts out of their bucket.

### BL-03: `_enumerate_proxmox_vms` cluster dedupe is wrong on a cold `_HOST_CLUSTER_CACHE`

**Files modified:** `src/homelab_mcp/drift_detection.py`
**Commit:** b1cb017
**Applied fix:** Dedupe at the consumer (`_enumerate_unknown_vms`) by
`(vm_name_lower, vmid)`. A closure-captured `seen_keys` set inside
`_make_row` causes duplicate rows to return None, which `filter(None,
...)` drops — keeps the helper loop-free with respect to `continue`
per the Phase 39 D-11(b) AST guard. This is the safest of the three
options the reviewer offered (the other two would have required
relaxing the AST guard scope or pre-warming the cluster cache from
inside `scan_drift`).

### BL-04: Enumeration failure swallowed at debug level, masking auth/config issues

**Files modified:** `src/homelab_mcp/drift_detection.py`
**Commit:** 912e546
**Applied fix:** Bumped the `_enum_one` exception log from
`logger.debug` to `logger.warning` with an explicit message that
explains why the host's VMs are absent from `unknown[]`.
sanitize_error already redacts secrets so warning-level is safe.

### WR-01: `record["last_seen"]` may pass through non-string types unchanged

**Files modified:** `src/homelab_mcp/drift_detection.py`
**Commit:** 5b1c7f3
**Applied fix:** Extended `_parse_last_seen` to accept `datetime`
objects directly (so Postgres adapters that type-map `last_seen` to
datetime are normalized through the same UTC-coercion path), then
routed both `record["last_seen"]` assignments in the row loop through
`parsed.isoformat() if parsed else row.get("last_seen")`. The
downstream JSON-serialized response now sees a string in the common
case regardless of which DB adapter is in use.

### WR-02: Per-row record shape contract drifted; old shape test still claims 7 keys

**Files modified:** `src/homelab_mcp/drift_detection.py`,
`tests/test_drift_detection.py`
**Commit:** c473e00
**Applied fix:** Updated the `scan_drift` docstring to document BOTH
shapes — the 7-key `unreachable` base and the 9-key `missing`
extension (additive `last_seen` + `message`). Added a new test
`test_per_row_record_shape_for_missing_substatus_phase39` that locks
the 9-key shape so future refactors can't drop or rename the new
fields without the suite catching it.

### WR-03: `_parse_last_seen` silently treats naive timestamps as UTC

**Files modified:** `src/homelab_mcp/drift_detection.py`
**Commit:** 1bb7b20
**Applied fix:** Added a prominent docstring section in
`_parse_last_seen` calling out the imprecision (sitemap.py writes
local-wall-clock time without an offset suffix), the practical
operator impact ("threshold +/- machine TZ offset"), the proper fix
(sitemap.py UTC writer in a follow-up phase), and the workaround (run
the server in UTC). The reviewer accepted documentation-only as a
valid resolution since the underlying bug lives in `sitemap.py`, not
`drift_detection.py`.

### WR-04: Dead "defensive fallthrough" return masquerades as type-safety

**Files modified:** `src/homelab_mcp/drift_detection.py`
**Commit:** 15f948b
**Applied fix:** Deviation from the reviewer's literal advice. The
reviewer's claim that mypy didn't need the trailing return turned out
to be wrong — running `uv run mypy` confirmed mypy requires a
terminal statement after the `async with semaphore` block (it can't
prove exhaustiveness across try/except inside an async-with).
Replacing the line with `raise RuntimeError` would have crashed the
surrounding `asyncio.gather(return_exceptions=False)` and broken the
SSH pre-pass for every other row. Compromise: keep the return but
prefix it with `logger.error(...)` and use a distinctive diagnostic
sentinel string. mypy stays green, the line stays present so a
regression contains to a single row's probe (not a scan-wide crash),
and the operator sees a loud signal in logs instead of a silent miss
— the spirit of the original finding.

### WR-05: `_diff_fingerprints` silently ignores keys present only in `current`

**Files modified:** `src/homelab_mcp/drift_detection.py`,
`tests/test_drift_detection.py`
**Commit:** ecaee6e
**Applied fix:** Walk the union of stored.keys() | current.keys()
instead of the intersection, but skip stored-only paths via a list
comprehension (no `continue`, per the Phase 39 D-11(b) AST guard).
Current-only leaves emit with `stored=None` so clients can detect
the asymmetric add. Added three tests locking the new behaviour:
top-level current-only emits, nested current-only emits, and
stored-only remains suppressed. **Status flagged for human
verification:** this is a logic change to fingerprint diffing
semantics — recommend the developer manually confirm the asymmetric
emit policy matches the intended Phase 39 D-09a contract before the
phase proceeds to verification.

### WR-06: `cluster_name` / `scope` reused across loop iterations on shared try/else flow

**Files modified:** `src/homelab_mcp/drift_detection.py`
**Commit:** d7371a1
**Applied fix:** Bind `scope: str = "unknown"` and `cluster_name:
str | None = None` explicitly at the top of each iteration of the
row loop. Previously safe but fragile (Python doesn't scope variables
to `for` blocks) — this makes the per-iteration default audible so a
future refactor that forgets to re-bind in the resolver-success
`else:` branch can't attach the previous row's cluster_name to the
current row's record.

### WR-07: `_classify_unreachable` `.days` floors to integer days, threshold semantics off-by-23h59m

**Files modified:** `src/homelab_mcp/drift_detection.py`
**Commit:** 733c4fe
**Applied fix:** Replaced `(now - parsed).days > threshold_days`
with `(now - parsed) > timedelta(days=threshold_days)`. Imported
`timedelta` from datetime. Comparison now has second-level precision
instead of day-floor, so a host last seen exactly 7 days + 23 hours
ago promotes to `missing` correctly (previously it stayed
`unreachable` for nearly an extra day). With
`HOMELAB_DRIFT_MISSING_THRESHOLD_DAYS=1` this fixes a 47-hour
worst-case promotion delay.

### WR-08: SSH pre-pass runs against rows with degenerate hostnames before scan_drift can route them

**Files modified:** `src/homelab_mcp/drift_detection.py`
**Commit:** 3086dd5
**Applied fix:** Filter out degenerate rows (hostname None / "" /
"unknown" or `status == "error"` or no `ssh_credential_id`) BEFORE
passing the list to `_bulk_universal_core_probes`. Stops unintended
SSH connect attempts to whatever the credential's stored hostname
resolves to (worst case) and saves the SSH connection timeout per
degenerate row (best case). The row loop still routes these rows to
`not_eligible` per D-17.

---

_Fixed: 2026-04-27T22:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
