---
phase: 41-binding-aware-resolver-hygiene
reviewed: 2026-04-29T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - src/homelab_mcp/drift_detection.py
  - src/homelab_mcp/error_handling.py
  - src/homelab_mcp/sitemap.py
  - src/homelab_mcp/ssh_tools.py
  - tests/test_ast_regression.py
  - tests/test_drift_detection.py
  - tests/test_phase41_binding_aware.py
  - tests/test_sitemap.py
  - tests/test_ssh_tools.py
findings:
  critical: 1
  warning: 5
  info: 3
  total: 9
status: issues_found
---

# Phase 41: Code Review Report

**Reviewed:** 2026-04-29
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Phase 41 introduces `resolve_ssh_for_sitemap_row` as a shared row-binding-aware
SSH credential resolver and threads `connection_ip` into the SSH/Proxmox dial
target on both the discover and drift paths. The structural changes (helper
extraction, AST guards, dead-code annotations) are well-organized and the
guard surface is solid.

The review surfaced one BLOCKER on the drift Proxmox path where a
hostname↔connection_ip key inconsistency in the resolver telemetry cache
defeats the WR-04 guard against double-resolution and may attribute the
wrong scope/cluster_name to a row when those identifiers diverge. Several
WARNINGs flag related Bug-V follow-on issues (cluster-cache key mismatch,
`_HOST_CLUSTER_CACHE` lookup keyed on hostname while dialing
connection_ip), test-coverage gaps where two new Phase 41 tests patch a
function the code under test no longer calls, and a
`resolve_ssh_for_sitemap_row` factory-call escape hatch in drift's
`_probe_one` that bypasses the caller-supplied db_adapter.

## Critical Issues

### CR-01: Telemetry cache key/dial host mismatch causes double-resolve and possible scope/cluster_name mis-attribution on drift

**File:** `src/homelab_mcp/drift_detection.py:779-868`
**Issue:** Phase 41 Bug V flips the dial-host from `hostname` to
`row.connection_ip` for `get_proxmox_client(host=dial_host, ...)`. The
client funnel forwards `host=connection_ip` to
`resolve_proxmox_credentials(host=connection_ip, ...)`, which writes the
telemetry cache as `_RESOLUTION_TELEMETRY_CACHE[(connection_ip, binding)]`
(see `proxmox_api.py:322 / 346 / 371 / 428`). But the very next block in
`scan_drift` reads the cache by **hostname**:
```python
telemetry = get_resolution_telemetry(hostname, binding)
```
When `hostname != connection_ip` (the common Phase 41 case — that is the
whole point of Bug V), this lookup always misses. The fallback then
re-runs `resolve_proxmox_credentials(hostname, ...)` — exactly the
double-resolution that WR-04 was added to prevent on flaky keyring
backends.

Worse, the second call uses `hostname`, while the first used
`connection_ip`. If the row's hostname and IP resolve via different
cluster-scope tokens (e.g., a host whose hostname is unknown to DNS but
whose IP belongs to a registered cluster scope, or a multi-homed host
straddling two clusters), the resolver returns a different
`(scope, cluster_name)` tuple than the probe actually used. The
`probed_ok` / `unreachable` row then carries scope/cluster_name attribution
that does not match the credential that successfully reached the host —
a silent integrity break in the drift envelope.

**Fix:** Pick one identifier and use it consistently for both the dial
target AND the telemetry/cache lookup. The cleanest option is to keep
`hostname` as the resolver/cache key (matches `_HOST_CLUSTER_CACHE` —
see WR-01) and pass `connection_ip` only at the underlying TCP-dial
layer of `ProxmoxAPIClient`. Concretely, restructure
`get_proxmox_client` (or add a new path) so the resolver call uses
hostname:
```python
# In drift_detection.scan_drift around line 779:
client = await get_proxmox_client(
    host=hostname,                # resolver/telemetry key
    dial_host=row.get("connection_ip") or hostname,  # actual TCP target
    session=session,
    credential_id=binding,
)
# get_resolution_telemetry(hostname, binding) then hits the cache
# populated by the same call, eliminating the second resolve.
```
Alternatively, key the telemetry lookup by `dial_host` everywhere in
drift (line 845, 864) — but then `_HOST_CLUSTER_CACHE.get(hostname)` in
`_enumerate_proxmox_vms:425` also has to flip to `connection_ip` (see
WR-01) and the `host_to_binding` map needs to be re-keyed accordingly.

## Warnings

### WR-01: `_HOST_CLUSTER_CACHE` lookup keyed on hostname while client now dials connection_ip in `_enumerate_proxmox_vms`

**File:** `src/homelab_mcp/drift_detection.py:421-431, 433-444`
**Issue:** Same root cause as CR-01 but on the unknown-VM enumeration
path. Line 425 builds the dedupe target list using
`_HOST_CLUSTER_CACHE.get(hostname)`; the cache is populated by
`resolve_proxmox_credentials` keyed on whatever `host=` value was passed.
Phase 41 now passes `host=connection_ip` from `scan_drift:780`, so for
hosts whose hostname differs from connection_ip the cluster cache is
never primed under the hostname key — every `_enumerate_proxmox_vms`
call sees a cache-miss `cluster_name=None` for those hosts and falls
through to the "standalone" path (one `/cluster/resources` call per
hostname). The cluster-dedupe loses its effect for cluster members,
multiplying API calls across a cluster of N nodes. Functionally still
correct (BL-03 dedupes on `(hypervisor, name.lower(), vmid)`), but the
intended N-fold dedupe is silently disabled.
**Fix:** After resolving CR-01's identity choice, key both
`_HOST_CLUSTER_CACHE` writes and reads on the same value (probably
hostname, with a separate dial_host parameter on the Proxmox client).

### WR-02: `resolve_ssh_for_sitemap_row` invoked inside drift `_probe_one` bypasses the caller-supplied `db_adapter`

**File:** `src/homelab_mcp/drift_detection.py:512`, `src/homelab_mcp/ssh_tools.py:865`
**Issue:** `scan_drift` accepts a `db_adapter` argument (declared the
"single funnel for sitemap reads" in the docstring) and uses it for
`db_adapter.get_all_devices()`. But the SSH pre-pass `_probe_one` calls
`resolve_ssh_for_sitemap_row(hostname)` without forwarding the adapter,
so the helper falls through to `get_database_adapter()` at
`ssh_tools.py:865`. The factory consults `os.getenv("DATABASE_TYPE")`
and constructs a brand-new SQLiteAdapter / PostgreSQLAdapter — a
different connection (potentially against a different db_path) from the
one the orchestrator handed in. The row read inside the helper may
therefore disagree with the row read in the outer loop, breaking the
sitemap-as-single-source-of-truth invariant the docstring promises.
For `MagicMock` adapters in tests, the helper's lookup would call the
production DB rather than the mock — luckily every drift test that
exercises this path mocks out `_bulk_universal_core_probes` entirely
(test_drift_detection.py:1824–2264), so the gap is invisible to the
test suite.
**Fix:** Plumb `db_adapter` from `scan_drift` through
`_bulk_universal_core_probes` and on into `_probe_one` so the helper
sees the same adapter the outer loop uses:
```python
async def _bulk_universal_core_probes(
    rows, *, db_adapter,
):
    ...
    creds, matched_row = resolve_ssh_for_sitemap_row(
        hostname, db_adapter=db_adapter,
    )
```

### WR-03: Two Phase 41 regression tests patch `ssh_discover_system_with_binding`, which `discover_and_store` no longer calls

**File:** `tests/test_phase41_binding_aware.py:207-211, 242-246`
**Issue:** Both `test_failed_discover_writes_to_requested_identifier_row`
and `test_failed_discover_does_not_collapse_to_empty_hostname` patch
`homelab_mcp.ssh_tools.ssh_discover_system_with_binding`. After Phase 41
Plan 03, `sitemap.discover_and_store` resolves credentials via
`resolve_ssh_for_sitemap_row` and then calls `ssh_discover_system`
directly (sitemap.py:489); the `_with_binding` wrapper is preserved only
as a backward-compat tombstone (see `ssh_tools.py:947` "SUPERSEDED").
The patches therefore never intercept anything.

What actually happens in each test:
- The seed row carries `ssh_credential_id="uuid-abc"`. That string is
  not a parseable UUID, so `resolve_ssh_credentials` raises
  `CredentialNotFoundError("binding stale: malformed credential_id")`
  inside `resolve_ssh_for_sitemap_row` *before* any discovery call
  fires. The `except CredentialNotFoundError` at sitemap.py:496 catches
  it and synthesizes a JSON error envelope. The test's
  `fake_discover_failed` / `fake_discover_malformed` payloads are
  unreachable.
- The downstream `find_devices_by_hostname_or_ip` merge then salvages
  the row identity, so the assertions pass — for the wrong reason.

The intended Bug-BB scenarios (real timeout / real malformed JSON from
the discovery RPC) are now uncovered.
**Fix:** Patch the layer the new flow actually calls
(`homelab_mcp.ssh_tools.ssh_discover_system` or
`homelab_mcp.sitemap.ssh_tools.ssh_discover_system`) and seed the row
with a *valid* UUID that does not exist in the registry (or seed it
with no `ssh_credential_id` so the helper falls through to Tier-1/2):
```python
with patch(
    "homelab_mcp.ssh_tools.ssh_discover_system",
    new=AsyncMock(return_value=fake_failed_payload),
):
    await discover_and_store(sitemap, hostname="pve")
```

### WR-04: `_probe_one` defensive `raise AssertionError` is unreachable and undermines the broad `except Exception` it claims to belt-and-brace

**File:** `src/homelab_mcp/drift_detection.py:543-559`
**Issue:** The trailing
`raise AssertionError(f"_probe_one reached unreachable fallthrough...")`
is genuinely unreachable — the comment in lines 543-558 explicitly
acknowledges this. The standing rationale ("if a future refactor splits
the broad except into narrower clauses without re-establishing
exhaustiveness, this line will fail loudly") is internally inconsistent:
the immediately-preceding `except Exception as exc` already catches
*every* possible exception type, so any refactor that reaches this line
would have to *delete* the broad except — at which point the
`AssertionError` would also be removed (or, if left in place, would
crash inside `asyncio.gather`'s `return_exceptions=False` and abort the
whole drift scan, defeating the very D-10 contract the rest of the
function maintains). This is dead code defending against a refactor
shape that cannot occur, and would *cause* the silent-failure mode it
claims to prevent if the broad except were ever narrowed.
**Fix:** Delete the unreachable raise and the surrounding belt-and-braces
comment. mypy's exhaustiveness check is already satisfied by the broad
`except Exception`. If a future refactor narrows that clause, it should
add a `_LOGGER.error(...) + return (hostname, {"_error": ...})` sentinel
in its own except, not rely on a structurally-unreachable raise:
```python
except Exception as exc:  # CredentialNotFoundError + defensive
    return (hostname, {"_error": sanitize_error(exc)})
# (delete the trailing raise AssertionError)
```

### WR-05: `ssh_connection_wrapper` writes the dial-target value into BOTH `hostname` and `connection_ip` envelope fields

**File:** `src/homelab_mcp/error_handling.py:261-307`
**Issue:** Every error branch sets `"hostname": hostname, "connection_ip": hostname`,
where `hostname = kwargs.get("hostname", args[0] if args else "unknown")`.
Phase 41 Bug V uses `row.connection_ip` as the dial target, so when a
sitemap row has `hostname=pve`, `connection_ip=192.168.10.20` and
`ssh_discover_system` is called with `hostname=192.168.10.20`, the
error envelope emits `{"hostname": "192.168.10.20", "connection_ip": "192.168.10.20"}` —
the original requested identifier `pve` is lost. The docstring at
lines 240-245 acknowledges the problem (`hostname` here is the
DIAL-TARGET, not the requested identifier) and defers the fix to a
post-parse merge in `discover_and_store`. That merge does work today,
but only because `find_devices_by_hostname_or_ip("pve")` finds the row.
Any caller of `ssh_discover_system` that does NOT post-process through
`discover_and_store` (e.g., direct MCP tool callers like
`ssh_execute_command`'s envelope handler at error_handling.py:1034) sees
an envelope where `hostname` is the IP and the original identifier
vanishes.
**Fix:** Either (a) split the wrapper into two args — request_identifier
and dial_target — and emit both; or (b) document the contract that
callers MUST post-merge through `find_devices_by_hostname_or_ip` and
add a unit test exercising the bare envelope (no merge layer).

## Info

### IN-01: `_resolve_ssh_credentials_with_binding` retained as DEAD CODE solely for grep-pin

**File:** `src/homelab_mcp/ssh_tools.py:306-401`
**Issue:** The 95-line function is annotated as DEAD CODE in two places
(lines 306-313 and 326-332) and is not called anywhere in production.
The justification is "kept for plan-acceptance grep" plus
deprecation-not-yet-removed. Carrying ~95 lines of unreachable code
with detailed implementation comments makes the file harder to read
and creates a maintenance trap (future readers may be unsure which
"with binding" helper is canonical).
**Fix:** Remove the function and update the Phase 38.1 plan-acceptance
grep target to look for `_scan_registry_for_binding` (the actual live
helper) instead. If the grep can't be updated, replace the body with
`raise NotImplementedError("DEAD — see ssh_discover_system_with_binding")`
and shrink the docstring to a single deprecation line.

### IN-02: `ssh_discover_system_with_binding` retained alongside the new shared helper — duplicated capability

**File:** `src/homelab_mcp/ssh_tools.py:947-983`
**Issue:** This wrapper now overlaps significantly with
`resolve_ssh_for_sitemap_row` + `ssh_discover_system`. The
"SUPERSEDED" banner at line 943 is correct in spirit — Phase 41 now has
two ways to do the same thing (auto-bind via wrapper vs. row-binding-
aware helper) — but no removal date is named. The Phase 41 AST guard
in `tests/test_ast_regression.py:1408-1411` enforces a >=2 call-site
floor on `resolve_ssh_for_sitemap_row`, so removing this helper is
safe whenever the back-compat call sites are migrated. Leaving both
helpers indefinitely creates the same maintenance trap as IN-01.
**Fix:** Schedule a follow-up phase to remove
`ssh_discover_system_with_binding` and its `_scan_registry_for_binding`
sibling; or downgrade them to internal-only with `_` prefix and a
single-line shim "use resolve_ssh_for_sitemap_row instead".

### IN-03: `_parse_last_seen` known-imprecision documented but not closed

**File:** `src/homelab_mcp/drift_detection.py:155-194`
**Issue:** WR-03 (lines 170-182) acknowledges that
`sitemap.NetworkDevice.last_seen = datetime.now().isoformat()` writes a
naive local-time string and that the `replace(tzinfo=UTC)` coercion
gives a tolerance of "threshold ± machine TZ offset". The comment
correctly identifies the proper fix (sitemap.py should write
`datetime.now(UTC).isoformat()`), but the fix lives in a different
module and was deferred. The DST boundary case in particular can flip
the missing/unreachable classification mid-scan on a single host.
**Fix:** In a follow-up phase, change `sitemap.NetworkDevice` and
`store_device` to write UTC-aware timestamps, then strengthen
`_parse_last_seen` to reject naive datetimes outright (raise / return
None) rather than silently coercing them. The current
`_DEFAULT_THRESHOLD_DAYS=7` masks the imprecision in practice but a
1-day threshold (which the env var permits) is unsafe today on any
non-UTC server.

---

_Reviewed: 2026-04-29_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
