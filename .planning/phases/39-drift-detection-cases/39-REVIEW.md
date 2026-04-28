---
phase: 39-drift-detection-cases
reviewed: 2026-04-27T13:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - src/homelab_mcp/drift_detection.py
  - src/homelab_mcp/ssh_tools.py
  - tests/conftest.py
  - tests/test_ast_regression.py
  - tests/test_drift_detection.py
findings:
  blocker: 0
  warning: 5
  total: 5
status: issues_found
---

# Phase 39: Code Review Report (Re-review after fixes)

**Reviewed:** 2026-04-27T13:00:00Z
**Depth:** standard
**Status:** issues_found

## Summary

Re-review of Phase 39 after the 12-finding remediation pass (4 BLOCKER, 8
WARNING). The four BLOCKERs from the prior review are addressed:

- **BL-01** (duplicate-hostname SSH probe collisions) — fixed by deduping
  `seen_hostnames` before `asyncio.gather` in `_bulk_universal_core_probes`
  (drift_detection.py:530-541). Empty/colliding hostnames are dropped.
- **BL-02** (`int(vm.get("vmid", 0))` crashing the scan on malformed
  payloads) — fixed via try/except around the coercion in
  `_enumerate_unknown_vms._make_row` (drift_detection.py:336-344).
- **BL-03** (cold `_HOST_CLUSTER_CACHE` duplicate VM emission) — addressed
  at the consumer via a `(vm_name_lower, vmid)` dedupe set inside
  `_enumerate_unknown_vms` (drift_detection.py:325, 349-352). The N-call
  enumeration cost on cold cache is accepted (out-of-scope: performance);
  correctness is preserved.
- **BL-04** (silent enumeration failures at debug level) — fixed by
  bumping to `logger.warning` (drift_detection.py:424).

All eight prior WARNINGs are also addressed in code or in docstring text
(WR-01 last_seen normalization, WR-02 docstring 9-key shape doc + new
test, WR-03 documented offset risk + follow-up plan, WR-04 logger.error
on fallthrough, WR-05 asymmetric one-sided diff with current-only emit,
WR-06 explicit per-iteration scope/cluster_name reset, WR-07 timedelta
comparison, WR-08 degenerate-row pre-filter for SSH pre-pass).

This re-review surfaces five remaining or newly-visible issues, all
WARNING severity. None block ship; all are robustness / correctness
edge cases that should be tracked.

Counts: 0 BLOCKER, 5 WARNING.

## Warning Findings

### WR-A: BL-03 dedupe key collides across clusters with shared (vm_name, vmid)

**File:** `src/homelab_mcp/drift_detection.py:349-352`
**Issue:**
The new BL-03 fix dedupes unknown VMs on `(name.lower(), vmid)`. Proxmox
vmids are only unique *within* a cluster, not across clusters. A
multi-cluster homelab with two unrelated VMs that happen to share both
name and vmid (e.g., a "web" VM at vmid 100 in `cluster-a` and a "web" VM
at vmid 100 in `cluster-b`) will see exactly ONE entry in `unknown[]`
even though two distinct VMs need adoption. The "first seen wins"
behavior depends on `cluster_vm_map.items()` ordering, which is dict
insertion order — not stable across runs (depends on which cluster's
`/cluster/resources` call resolves first under `asyncio.gather`).

This is the same class of "silent collapse on collision" that BL-01
addressed for SSH probe results. The fix replaced one collision point
with another; the cold-cache duplicate is suppressed, but legitimate
distinct VMs across clusters are also collapsed.

**Fix:** Include the hypervisor or cluster identity in the dedupe key:

```python
key = (hypervisor, name.lower(), vmid)
```

This still suppresses the BL-03 cold-cache N-copy case (because all N
hits enumerate the same cluster, hypervisor differs but VM list is
identical — the duplicates collapse on `(name.lower(), vmid)` portion
when the same VM is reported from two cluster members; pick a
representative). A safer key is `(cluster_name_or_hypervisor, vmid)`,
threaded through from `_enumerate_proxmox_vms` if cluster_name is
known. The current dedupe is too aggressive.

---

### WR-B: WR-04 fix preserves dead code; the new `logger.error` is itself unreachable

**File:** `src/homelab_mcp/drift_detection.py:507-522`
**Issue:**
The original WR-04 finding was "remove the dead fallthrough return."
The fix instead reframed the line: it added a `logger.error(...)` with
diagnostic text and kept the sentinel return. But the lines remain
unreachable: every branch of the inner try/except (`return` in `try`,
`return` in `except (asyncssh.Error, OSError, TimeoutError, ValueError)`,
`return` in bare `except Exception`) returns inside the `async with
semaphore:` block. Control never reaches lines 517-522.

The new comment claims "mypy requires a terminal statement after the
async with," which is true mechanically — but the right answer is
either (a) move the diagnostic INSIDE one of the except branches, or
(b) replace it with `raise AssertionError("unreachable")` so any
regression that does fire crashes loudly instead of silently emitting
`probe_one_unreachable_fallthrough` into the result dict (where the
row loop would then treat it like a real `_error` and route the host
to probed_ok with no fingerprint diff — the *exact* silent-failure
mode the comment claims to prevent).

The `logger.error` is also dead, so a future refactor that DID make
this reachable would still not see the log line until they exercised
the reachable path.

**Fix:** Replace with `raise AssertionError(...)` or restructure the
try/except so mypy is satisfied without the unreachable line:

```python
async with semaphore:
    try:
        ...
        return (hostname, {"fingerprint": fp, ...})
    except (asyncssh.Error, OSError, TimeoutError, ValueError) as exc:
        return (hostname, {"_error": sanitize_error(exc)})
    except Exception as exc:
        return (hostname, {"_error": sanitize_error(exc)})
```

Move outside-of-async-with code: nothing. Mypy correctly proves
exhaustiveness because the bare `except Exception` matches everything.

---

### WR-C: Telemetry-cache fallback resolver call uncaught for non-credential errors

**File:** `src/homelab_mcp/drift_detection.py:795-803`
**Issue:**
When the resolution telemetry cache misses (rare; documented as
defensive), the code falls back to a fresh
`await resolve_proxmox_credentials(...)` call. The surrounding
try/except catches ONLY `CredentialNotFoundError`. The resolver also
raises `aiohttp.ClientError`, `TimeoutError`, and `ValueError` from its
cluster-walk path (Tier-1 failure during fresh resolution). Any of
these on the fallback path would propagate uncaught all the way out of
`scan_drift`, aborting the entire scan and losing every other row's
classification — the exact contract violation that BL-02 was fixed to
avoid.

The fallback should "almost never" execute (telemetry should be warm
right after `get_proxmox_client` succeeded), but "almost never" is
exactly the kind of latent failure mode that crashes a long-running
scan during a midnight cron run.

**Fix:** Widen the except clause:

```python
try:
    _token, scope, cluster_name = await resolve_proxmox_credentials(...)
except CredentialNotFoundError as exc:
    resolver_exc = exc
except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
    # Treat transient resolver-fallback failures as if /cluster/status
    # had failed — route to unreachable, not a hard crash.
    substatus, classify_msg = _classify_unreachable(
        row, exc, _missing_threshold_days(), datetime.now(UTC)
    )
    record_inner = {...}
    unreachable.append(record_inner)
    continue  # IF refactored out of D-15-guarded loop
```

Or simpler: make the fallback synchronous in a way that cannot raise
network errors (use only the cache hit; if it misses, route to
not_eligible/binding_stale rather than re-resolve).

---

### WR-D: SSH probe `_error` results silently treated as "no drift"

**File:** `src/homelab_mcp/drift_detection.py:827-830`
**Issue:**
When `_bulk_universal_core_probes` records an `_error` for a host (auth
failure, transient SSH outage, command timeouts, asyncssh/OSError), the
returned dict has shape `{"_error": "..."}` with NO `"fingerprint"` key.
The drift loop checks `if "fingerprint" in probe else {}` — a missing
key yields `current_fp = {}`. Then:

```python
diff = _diff_fingerprints(stored_fp, current_fp) if (stored_fp and current_fp) else {}
```

`current_fp = {}` makes the conditional False, so `diff = {}` and the
host lands in probed_ok with `status: "probed-ok"`. There is no signal
to the operator that drift detection silently could not run for that
host — the response looks identical to a host whose stored and current
fingerprints genuinely match.

This is structurally similar to BL-04 (silent enumeration failures) but
on the SSH path: an SSH probe failure on a host with a stored
fingerprint produces a clean-looking probed_ok record and quietly
disables drift detection for that host on every subsequent scan until
SSH is fixed.

**Fix:** Either (a) surface a `partial: true` flag on the probed_ok
record when the SSH probe failed, OR (b) add a top-level
`probe_warnings` field listing hosts whose drift comparison was
skipped, OR (c) at minimum, log at warning level when the SSH
probe map for a probed_ok host with a non-empty stored_fp contains
`_error`. The current behavior makes broken SSH on a Proxmox host
indistinguishable from "no drift" in the response.

---

### WR-E: WR-01 last_seen normalization is partial when parse fails

**File:** `src/homelab_mcp/drift_detection.py:779, 883`
**Issue:**
The WR-01 fix introduces:

```python
parsed = _parse_last_seen(row.get("last_seen"))
record["last_seen"] = parsed.isoformat() if parsed else row.get("last_seen")
```

This normalizes the *successful* parse case to ISO-8601 strings. But
the fallback branch (`else row.get("last_seen")`) preserves whatever
the DB adapter returned — which is exactly the unnormalized type WR-01
was meant to scrub. Practical scenarios:

1. Adapter returns a malformed string (e.g., truncated, vendor format) →
   `_parse_last_seen` returns None → fallback emits the malformed string.
   Acceptable.
2. Adapter returns an integer epoch timestamp (possible if a custom
   adapter type-mapped `last_seen` to BIGINT) → `_parse_last_seen`
   returns None (`fromisoformat` raises ValueError, datetime check
   doesn't match) → fallback emits the integer. Downstream JSON encoder
   serializes as a number; clients expecting a string break.
3. Adapter returns a `date` (not `datetime`) object → not handled
   anywhere; `isinstance(raw, datetime)` is False (`date` is the parent
   but `datetime` is the subclass; `date` instances fail the
   `isinstance(raw, datetime)` check), `fromisoformat` may or may not
   accept it depending on Python version, fallback emits the `date`
   object — JSON encoder fails entirely.

**Fix:** Coerce the fallback to a string explicitly:

```python
parsed = _parse_last_seen(row.get("last_seen"))
raw_last_seen = row.get("last_seen")
if parsed is not None:
    record["last_seen"] = parsed.isoformat()
elif raw_last_seen is not None:
    # Defensive: stringify whatever the adapter returned so JSON
    # serialization cannot fail downstream.
    record["last_seen"] = str(raw_last_seen)
else:
    record["last_seen"] = None
```

---

## Notes on Prior Findings (Verification)

The four BLOCKERs and most WARNINGs from the prior review were
addressed correctly. Specific verifications:

- **BL-01**: dedupe is correctly placed BEFORE `asyncio.gather` (not
  after), so colliding hostnames never enter the probe call. The
  filter also drops empty hostnames, addressing the degenerate-row
  collision case.
- **BL-02**: try/except around `int(vm.get("vmid", 0))` correctly
  catches both `ValueError` (e.g., `int("abc")`) and `TypeError`
  (e.g., `int(None)`, `int([])`). Returns `None` from `_make_row`,
  which `filter(None, ...)` strips.
- **BL-04**: `logger.warning` with `sanitize_error(exc)` properly
  redacts secrets while making failures visible.
- **WR-02**: docstring extended with "Per-row record shape extension
  (unreachable.status == "missing", Phase 39 DRFT-18 — adds two keys
  to the 7-key base for a total of 9 keys)" + new test
  `test_per_row_record_shape_for_missing_substatus_phase39` locks the
  9-key shape contract.
- **WR-05**: walker correctly emits asymmetric current-only keys; tests
  `test_diff_fingerprints_current_only_top_level_emits_phase39_wr05`
  and `_nested_emits_` lock the new behavior; stored-only suppression
  preserved by `test_diff_fingerprints_stored_only_still_suppressed`.
- **WR-07**: `(now - parsed) > timedelta(days=threshold_days)` correctly
  uses second-level precision instead of `.days` floor.
- **WR-08**: `ssh_eligible_rows` correctly filters degenerate rows
  before bulk probe call. The filter mirrors the row loop's degenerate
  routing (D-17), so SSH attempts to bad rows are prevented.

The remaining WARNINGs (WR-A through WR-E above) cover edge cases that
the original review either missed (WR-A WR-C WR-D) or that the chosen
fix addressed only partially (WR-B WR-E).

---

_Reviewed: 2026-04-27T13:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
