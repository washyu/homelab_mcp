---
phase: 39-drift-detection-cases
reviewed: 2026-04-27T12:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - src/homelab_mcp/ssh_tools.py
  - src/homelab_mcp/drift_detection.py
  - tests/conftest.py
  - tests/test_drift_detection.py
  - tests/test_ast_regression.py
findings:
  blocker: 4
  warning: 8
  total: 12
status: issues_found
---

# Phase 39: Code Review Report

**Reviewed:** 2026-04-27T12:00:00Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Phase 39 wires three new drift sub-states (DRFT-17 unknown VMs, DRFT-18
missing, DRFT-19 changed) onto the Phase 38.1 5-bucket envelope. The
helpers are reasonably factored and the AST-guard surface is updated. The
test surface is broad. However the integration into `scan_drift` has
several real correctness bugs around duplicate-hostname collisions in two
separate `dict(...)` reductions, a coercion that can crash the entire
scan on malformed Proxmox payloads, a flow path where `scope` /
`cluster_name` can be referenced unbound on a single rare error
combination, and an enumeration cache assumption that doesn't hold on a
cold-start scan. Several lower-severity findings cover dead code,
silently-swallowed enumeration errors, and a documentation/behaviour
drift in the per-row record shape contract.

Counts: 4 BLOCKER, 8 WARNING.

## Blocker Findings

### BL-01: Duplicate-hostname rows collapse SSH probe results, mis-attributing fingerprints

**File:** `src/homelab_mcp/drift_detection.py:391-395`
**Issue:**
`_bulk_universal_core_probes` returns `dict(pairs)` where `pairs` is a
list of `(hostname, probe_result)` tuples gathered across rows. When the
sitemap contains two rows with the same `hostname` (legitimately possible
during migration, after a stale-row purge race, or when the same host is
discovered under two different connection_ips), only the *last-seen*
probe result survives in the dict. The row loop in `scan_drift` then
calls `ssh_probe_results.get(hostname or "", {})` for *each* row — so row
A's stored fingerprint is diffed against row B's probe result, producing
a phantom `changed[]` entry attributed to row A.

Worse, when `_probe_one` is called for a row whose hostname is `""`
(degenerate but with `ssh_credential_id` set — note the SSH pre-pass
runs *before* `scan_drift`'s degenerate filter), every such row writes
to the same `""` key.

**Fix:** Either (a) key the probe map by sitemap row id (DB rowid /
connection_ip composite) instead of hostname, threading the key back to
the row loop; or (b) detect the collision and emit per-row probe
records via a list-of-dicts rather than a dict reduction. Simplest
defensive fix:

```python
# At minimum, dedupe input rows so degenerate / colliding rows don't
# silently overwrite real probe results:
seen: set[str] = set()
unique_rows = []
for r in rows:
    h = r.get("hostname") or ""
    binding = r.get("ssh_credential_id")
    if not h or not binding or h in seen:
        continue
    seen.add(h)
    unique_rows.append(r)
pairs = await asyncio.gather(*[_probe_one(r) for r in unique_rows], return_exceptions=False)
```

Or carry the row identity through the result tuple and key the map on
the row's stable identity.

---

### BL-02: `int(vm.get("vmid", 0))` can crash the whole scan on a malformed Proxmox payload

**File:** `src/homelab_mcp/drift_detection.py:255`
**Issue:**
`_enumerate_unknown_vms._make_row` does `"vmid": int(vm.get("vmid", 0))`.
The cluster-resources payload comes from `client.get("/cluster/resources")`
and is treated as `list[dict]` after the type guard. Proxmox normally
returns `vmid` as int, but a malformed/non-numeric value (e.g., `None`,
`"abc"`, `[]`) raises `TypeError` / `ValueError` from inside the
generator, which `unknown.extend(filter(None, ...))` evaluates eagerly.
The exception unwinds out of `_enumerate_unknown_vms` → out of the
`await _enumerate_proxmox_vms`-fed call → out of `scan_drift`, aborting
the entire drift scan with an unhandled exception. Every other row's
classification is lost.

The Phase 39 design contract is "enumeration failure on the host does
not move it out of its host bucket" — a single garbage VM record
violates that.

**Fix:** Wrap the coercion defensively and skip the bad row:

```python
def _make_row(vm: dict[str, Any], hypervisor: str) -> dict[str, Any] | None:
    name = (vm.get("name") or "").strip()
    if not name or name.lower() in sitemap_hostnames:
        return None
    try:
        vmid = int(vm.get("vmid", 0))
    except (ValueError, TypeError):
        logger.debug("skipping malformed vmid in /cluster/resources: %r", vm.get("vmid"))
        return None
    return {
        "hypervisor_hostname": hypervisor,
        "node": vm.get("node", ""),
        "vmid": vmid,
        ...
    }
```

---

### BL-03: `_enumerate_proxmox_vms` cluster dedupe is wrong on a cold `_HOST_CLUSTER_CACHE`

**File:** `src/homelab_mcp/drift_detection.py:296-307`
**Issue:**
The dedupe key is `c or h` — when `_HOST_CLUSTER_CACHE` has no entry for
a hostname (i.e., the cache is cold), `cluster_name` is `None`, and the
dedupe degenerates to per-hostname. On a server restart followed
immediately by `scan_drift` against a 5-node cluster, all five hosts hit
`/cluster/resources` (5 calls instead of the documented 1), which not
only contradicts D-05's locked dedupe contract but also produces five
copies of every unknown VM in the response — `_enumerate_unknown_vms`
flattens `cluster_vm_map.items()` and emits one record per
(hypervisor, vm) pair.

The test `test_cluster_dedup_single_enumeration` pre-seeds the cache via
`patch.dict`, masking this. Cache warming inside `scan_drift` (via
`get_proxmox_client` → `resolve_proxmox_credentials`) only happens for
cluster-scoped resolutions; in the cluster-served-via-cluster-walk path
the cache is populated as a side effect, but the contract is fragile
and not guaranteed by the helper itself.

Additionally, even when warm, the dict comprehension `{(c or h): (h, c)
for h, c in pairs}` keeps the *last-seen* `(hostname, cluster_name)` for
the cluster, so the chosen representative hostname is order-dependent —
fine functionally but worth noting that two consecutive scans can hit
different hosts in the same cluster, complicating per-host failure
signals.

**Fix:** Either (a) explicitly pre-warm the cache for every record
before dedupe (call `resolve_proxmox_credentials` synchronously to
ensure cluster_name is populated); (b) deduplicate by an authoritative
cluster-membership lookup; or (c) accept that cold-cache scans
duplicate-emit unknown VMs and dedupe at the consumer
(`_enumerate_unknown_vms`) by `(vmid, vm_name)` to suppress duplicates.

The simplest fix is to deduplicate unknown VMs after enumeration:

```python
# In _enumerate_unknown_vms, dedupe by (hypervisor, vmid) or (vm_name, vmid):
seen_keys: set[tuple[str, int]] = set()
for hypervisor, vms in cluster_vm_map.items():
    for vm in vms:
        row = _make_row(vm, hypervisor)
        if row is None:
            continue
        key = (row["vm_name"].lower(), row["vmid"])
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unknown.append(row)
```

Note this would require relaxing the Phase 39 D-11(b) "no continue"
guard for `_enumerate_unknown_vms`, or refactoring to a comprehension
with a `seen` closure.

---

### BL-04: Enumeration failure swallowed at debug level, masking auth/config issues

**File:** `src/homelab_mcp/drift_detection.py:317-319`
**Issue:**
`_enum_one` catches `aiohttp.ClientError`, `TimeoutError`, `ValueError`,
`CredentialNotFoundError` and logs at `logger.debug(...)`. In
production the default log level is INFO or WARNING — debug is
discarded. Every enumeration failure is invisible to the operator: the
host stays in `probed_ok` (D-10 by design), `unknown[]` is empty for
that host, and there is no observable signal that VM-level drift
detection is broken for that host.

A `CredentialNotFoundError` here in particular is an architectural
contradiction — the host already passed `/cluster/status` in the row
loop, so credentials clearly resolve there. If they don't resolve here,
the resolver is non-deterministic (flaky keyring) and the operator
deserves to know.

**Fix:** Bump enumeration failures to `logger.warning`. The
sanitize_error pass already redacts secrets:

```python
except (aiohttp.ClientError, TimeoutError, ValueError, CredentialNotFoundError) as exc:
    logger.warning("VM enumeration failed for %s; unknown[] will not include VMs from this host: %s",
                   h, sanitize_error(exc))
    return (h, [])
```

## Warning Findings

### WR-01: `record["last_seen"]` may pass through non-string types unchanged

**File:** `src/homelab_mcp/drift_detection.py:583, 689`
**Issue:**
On `missing` records, `record["last_seen"] = row.get("last_seen")`
copies whatever the DB adapter put there. SQLite stores ISO strings,
but Postgres may return `datetime` objects (depends on adapter
type-mapping). The drift response is downstream JSON-serialized; mixed
types break clients that assume the field is a string. `_parse_last_seen`
only inspects `raw` for parsing — it never normalizes the value
re-emitted in the response.
**Fix:** Normalize before storing on the record:

```python
parsed = _parse_last_seen(row.get("last_seen"))
record["last_seen"] = parsed.isoformat() if parsed else row.get("last_seen")
```

---

### WR-02: Per-row record shape contract drifted; old shape test still claims 7 keys

**File:** `src/homelab_mcp/drift_detection.py:476-485`, `tests/test_drift_detection.py:741-779`
**Issue:**
The Phase 36 D-02 contract documents an `unreachable` record as having
exactly 7 canonical keys. Phase 39 conditionally adds `last_seen` and
`message` when `substatus == "missing"`, producing 9 keys for those
records. The test `test_per_row_record_shape_preserved_for_unreachable`
asserts `set(record.keys()) == expected_keys` (the 7-key set) and
passes only because that test's mock has no `last_seen` field, so
`_classify_unreachable` returns `unreachable`. The contract docstring
in `scan_drift` (lines 476-485) still says `unreachable` records have 7
keys without acknowledging the conditional missing-extension. Clients
relying on a stable record shape break.
**Fix:** Either (a) update the docstring + add a separate test for the
9-key `missing` shape, OR (b) always emit `last_seen` and `message` as
optional fields (set to None when not missing) so the shape stays
constant.

---

### WR-03: `_parse_last_seen` silently treats naive timestamps as UTC

**File:** `src/homelab_mcp/drift_detection.py:154-167`
**Issue:**
The helper applies `.replace(tzinfo=UTC)` to any naive datetime. The
sitemap writes `datetime.now().isoformat()` — *local* wall-clock time.
On a non-UTC server (or one that crosses a DST boundary), a 6-hour-old
record can be classified as 6 hours in the *future* or 30 hours in the
past depending on offset, and the missing-threshold gate misfires
either direction.
The helper is documented to do this normalization, but the underlying
sitemap-writes-local-time bug is not surfaced — Phase 39 inherits and
papers over it. Acceptable for now if the documentation makes the
limitation explicit; otherwise a 7-day threshold has a true tolerance
of "7 days ± machine TZ offset".
**Fix:** Either (a) fix `sitemap.py` to write `datetime.now(UTC).isoformat()`
in a follow-up phase and treat naive timestamps as malformed here; or
(b) add a prominent comment in `_parse_last_seen` warning of the
offset risk and document the threshold's true precision.

---

### WR-04: Dead "defensive fallthrough" return masquerades as type-safety

**File:** `src/homelab_mcp/drift_detection.py:387-389`
**Issue:**
```python
# Defensive fallthrough — should never execute (try-block returns or
# an except branch returns). Present so mypy can prove all paths return.
return (hostname, {"_error": "unreachable_fallthrough"})
```
Every branch of the try / except already returns. The comment claims
mypy needs the line, but mypy flow-analyzes try/except + bare `Exception`
catches and proves exhaustiveness without it. This is dead code, and
the literal `"unreachable_fallthrough"` will never reach a logging
backend if it does fire — meaning a future regression that *does* hit
this line vanishes silently.
**Fix:** Remove the line. If it actually trips mypy, add `# type: ignore`
or restructure with an explicit `else: raise` to make the impossibility
audible.

---

### WR-05: `_diff_fingerprints` silently ignores keys present only in `current`

**File:** `src/homelab_mcp/drift_detection.py:213-223`
**Issue:**
The walker iterates `s.keys() & c.keys()` for dict-vs-dict pairs. The
docstring documents this as "leaves present in BOTH sides"
(intentional, prevents capability sub-keys absent from `current` from
firing every scan). However, the same rule means a *new* leaf appearing
in current (e.g., a freshly-added `package_fingerprint` after the host
got dpkg installed) is also silently skipped on the first scan. The
intent (per D-09a) was to suppress one-sided *stored→current* drops,
not one-sided *current* additions. This produces missed-drift signals
when a host gains a probe field rather than losing one.
**Fix:** Walk `s.keys() | c.keys()` instead, but only emit a diff when
both sides actually had a value (so genuinely-missing-in-current keys
stay suppressed). Or document explicitly that current-only keys are
intentionally invisible to drift.

---

### WR-06: `cluster_name` / `scope` reused across loop iterations on shared try/else flow

**File:** `src/homelab_mcp/drift_detection.py:586-691`
**Issue:**
In the `else:` clause of the resolver `try`, `scope` and `cluster_name`
are bound either via `telemetry` cache or via `resolve_proxmox_credentials`.
A subsequent inner `try / except (aiohttp.ClientError, TimeoutError, ValueError)`
on `client.get("/cluster/status")` (lines 622-691) creates `record_inner`
using `scope` and `cluster_name` from the OUTER `else`. This works for
the current row.

But on the next row iteration, if get_proxmox_client raises a network
error (line 567 `except (aiohttp.ClientError, ...)`), `_classify_unreachable`
is called and `record["scope"] = "unknown"` is hardcoded — fine. The
issue: `scope` and `cluster_name` retain values from the *previous*
iteration in the function-level scope (Python doesn't scope variables
to `for` blocks). If a future refactor forgets to re-bind them in the
`else:` branch, an unreachable row could attach a stale prior-row
`cluster_name` to its record. Currently safe but fragile.
**Fix:** Reset `scope = "unknown"` and `cluster_name: str | None = None`
at the top of the row loop body so any reuse is explicit.

---

### WR-07: `_classify_unreachable` `.days` floors to integer days, threshold semantics off-by-23h59m

**File:** `src/homelab_mcp/drift_detection.py:187`
**Issue:**
`(now - parsed).days > threshold_days` uses `timedelta.days`, which is
the floor of the day count. A host last seen exactly 7 days + 23h ago
yields `.days == 7`, and `7 > 7` is False — the host stays
`unreachable`, not `missing`. The doc says "older than threshold"
which is ambiguous; tests use 12-day-old to dodge the boundary.
Operators setting `HOMELAB_DRIFT_MISSING_THRESHOLD_DAYS=1` will see
records take up to 47 hours to promote.
**Fix:** Use `total_seconds()` or compare `timedelta(days=threshold_days)`
directly:

```python
if parsed is not None and (now - parsed) > timedelta(days=threshold_days):
    ...
```

---

### WR-08: SSH pre-pass runs against rows with degenerate hostnames before scan_drift can route them

**File:** `src/homelab_mcp/drift_detection.py:517-526`, ordering vs degenerate filter at 536
**Issue:**
`_bulk_universal_core_probes(rows)` runs *before* the row loop applies
the degenerate-row routing (`hostname is None or hostname in ("",
"unknown") or row.get("status") == "error"`). A degenerate row with a
non-null `ssh_credential_id` (legacy data, or a row that errored mid-
discovery) will trigger an SSH connection attempt to whatever
`creds.hostname` resolves to via the credential's stored hostname (the
sitemap row hostname is empty so the resolver may fail or fall back
ambiguously).

Worst case: a degenerate row with a stale credential_id triggers an
`asyncssh` connect attempt to an unintended host. Best case: extra
latency on every scan equal to the SSH connection timeout.
**Fix:** Filter out degenerate rows before passing to
`_bulk_universal_core_probes`:

```python
ssh_eligible = [
    r for r in rows
    if r.get("hostname") and r.get("hostname") not in ("", "unknown")
    and r.get("status") != "error"
    and r.get("ssh_credential_id")
]
ssh_probe_results = await asyncio.wait_for(
    _bulk_universal_core_probes(ssh_eligible),
    timeout=120.0,
)
```

---

## Summary of Actions

The four BLOCKERs all involve `scan_drift` correctness during real
production scenarios (duplicate hostnames, malformed Proxmox payloads,
cold cache, silent enumeration failures). They should be addressed
before this code is shipped.

The eight WARNINGs are quality / robustness issues that should be
addressed but don't constitute incorrect behaviour on the happy path
exercised by the current test surface.

---

_Reviewed: 2026-04-27T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
