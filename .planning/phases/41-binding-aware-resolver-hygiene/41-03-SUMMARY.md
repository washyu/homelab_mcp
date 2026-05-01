---
phase: 41-binding-aware-resolver-hygiene
plan: "03"
subsystem: sitemap, ssh, error_handling
tags: [ssh, credential-resolution, sitemap, error-handling, phase41, bug-aa, bug-bb, bug-v]

# Dependency graph
requires:
  - phase: 41-02
    provides: "resolve_ssh_for_sitemap_row helper in ssh_tools.py"
  - phase: 41-01
    provides: "6 RED xfail functional tests + AST guard scaffold"
  - phase: 38.1
    provides: "set_device_credential_binding, _scan_registry_for_binding, Phase 38.1 R3 auto-bind contract"

provides:
  - "discover_and_store wired through resolve_ssh_for_sitemap_row (Bug AA + V)"
  - "parse_discovery_output accepts requested_identifier; error paths preserve row identity (Bug BB)"
  - "ssh_connection_wrapper error envelopes carry hostname field on all 5 branches (Bug BB envelope layer)"
  - "5 Wave-0 functional tests flipped from XFAIL to PASS"
  - "test_resolve_ssh_for_sitemap_row_helper_exists AST guard flipped PASS"

affects:
  - "41-04 (drift_detection._probe_one side of Bug AA + V waits on Plan 04)"
  - "41-05 (AST guard verifies both call sites post-Plan 04)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "pre-resolve-then-discover: discover_and_store resolves credentials via resolve_ssh_for_sitemap_row BEFORE calling ssh_discover_system — credentials are passed explicitly, not resolved inside ssh_discover_system"
    - "db_adapter threading: resolve_ssh_for_sitemap_row accepts optional db_adapter kwarg to share the sitemap's in-memory adapter; prevents test isolation issues with module-level get_database_adapter()"
    - "R3 fallback: _scan_registry_for_binding used as fallback for first-discovery (row=None) to preserve Phase 38.1 R3 auto-bind without regression"
    - "error-row identity preservation: on CredentialNotFoundError or parse error, existing row looked up by requested identifier; zombie rows prevented"

key-files:
  created: []
  modified:
    - src/homelab_mcp/sitemap.py
    - src/homelab_mcp/ssh_tools.py
    - src/homelab_mcp/error_handling.py
    - tests/test_phase41_binding_aware.py
    - tests/test_sitemap.py
    - tests/test_ast_regression.py

key-decisions:
  - "Added db_adapter kwarg to resolve_ssh_for_sitemap_row so discover_and_store can share the sitemap's in-memory adapter (otherwise test in-memory rows invisible to module-level get_database_adapter())"
  - "Kept _scan_registry_for_binding for Phase 38.1 R3 fallback on first-discovery (row=None case); plan spec said 'replaces' but first-discovery has no row yet — regression in test_discover_writes_credential_id_phase381 confirmed the need"
  - "Removed xfail from 4 functional tests + 1 AST guard and updated mock targets to Phase 41 paths (call_args_list[0] for first resolver call; fake_creds with non-None password to reach ssh_connect)"
  - "Updated D-06/D-07 tests in test_sitemap.py to reflect Phase 41 architecture: credential resolution now happens before ssh_discover_system, so tests mock resolve_ssh_credentials instead of just ssh_discover_system"

patterns-established:
  - "Phase 41 error envelope: hostname field carries dial-target identity; requested-identifier preservation is discover_and_store's post-parse merge responsibility, not the envelope"

requirements-completed:
  - Bug-AA
  - Bug-BB

# Metrics
duration: 30min
completed: 2026-04-30
---

# Phase 41 Plan 03: discover_and_store Wire + Error Envelope Hostname Summary

**Bug AA + V + BB unified fix on the discover side — discover_and_store resolves creds via row-binding-aware helper, dials row.connection_ip, preserves error-row identity; error envelopes now carry hostname on all 5 branches**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-04-30T22:00:00Z
- **Completed:** 2026-04-30T22:30:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

### Task 1: Wire discover_and_store through resolve_ssh_for_sitemap_row (Bugs AA + BB + V)

- **sitemap.py — discover_and_store rewrite:**
  - Calls `resolve_ssh_for_sitemap_row(hostname, ..., db_adapter=sitemap.db_adapter)` to resolve creds + matched row
  - Bug V: `dial_target = row.get("connection_ip") or hostname` — dials the stored IP, not the logical hostname
  - Bug BB: on error, `find_devices_by_hostname_or_ip(hostname)` lookup reuses existing row identity
  - Phase 38.1 R3 preserved: `_scan_registry_for_binding` fallback for first-discovery case
  - `CredentialNotFoundError` caught and surfaced as error row keyed on requested identifier

- **sitemap.py — parse_discovery_output signature update:**
  - Added `requested_identifier: str | None = None` parameter
  - On `status="error"`: if `device.hostname` empty, set to `requested_identifier`
  - On `JSONDecodeError`: fallback = `requested_identifier or "unknown"` (not literal "unknown")

- **ssh_tools.py — resolve_ssh_for_sitemap_row db_adapter param:**
  - Added `db_adapter: DatabaseAdapter | None = None` keyword-only param
  - When provided, uses that adapter; otherwise falls through to `get_database_adapter()`
  - Fixes test isolation: in-memory sitemap rows now visible to the helper

- **ssh_tools.py — superseded banners:**
  - Added Phase 41 banner above `_scan_registry_for_binding` and `ssh_discover_system_with_binding`

- **Test updates:**
  - `test_phase41_binding_aware.py`: removed xfail from 4 tests; updated fake_creds to have `password="fake-password"` so ssh_connect is reachable; updated assertion to check `call_args_list[0]` for first resolver call
  - `test_ast_regression.py`: removed xfail from `test_resolve_ssh_for_sitemap_row_helper_exists` (Plan 02 landed it)
  - `test_sitemap.py`: updated D-06/D-07 tests to mock `resolve_ssh_credentials` (not just `ssh_discover_system`) since Phase 41 resolves credentials before calling ssh_discover_system

### Task 2: Add hostname field to ssh_connection_wrapper error envelopes (Bug BB)

- Added `"hostname": hostname,` to all 5 error envelope branches in `ssh_connection_wrapper`
- Normalized line-292 hostname extraction to `kwargs.get("hostname", args[0] if args else "unknown")`
- Added docstring explaining hostname field carries DIAL-TARGET identity (not requested identifier)
- `test_error_envelope_carries_hostname` flipped from XFAIL to PASS

## Task Commits

1. **Task 1: Wire discover_and_store + parse_discovery_output** - `d31f364` (feat)
2. **Task 2: Error envelope hostname field** - `b362b4c` (feat)

## Files Created/Modified

- `src/homelab_mcp/sitemap.py` — discover_and_store rewrite (89 lines) + parse_discovery_output update (12 lines)
- `src/homelab_mcp/ssh_tools.py` — db_adapter param on resolve_ssh_for_sitemap_row + DatabaseAdapter import + 2 banner comments
- `src/homelab_mcp/error_handling.py` — 5 hostname fields + line-292 normalization + docstring update
- `tests/test_phase41_binding_aware.py` — xfail removed from 4 tests + mock targets updated
- `tests/test_sitemap.py` — D-06/D-07 tests updated for Phase 41 architecture
- `tests/test_ast_regression.py` — xfail removed from test_resolve_ssh_for_sitemap_row_helper_exists

## Decisions Made

- **db_adapter threading via kwarg:** The plan called `resolve_ssh_for_sitemap_row(hostname, ...)` without passing a DB adapter, but the function uses `get_database_adapter()` (module-level, returns different adapter than test sitemap's in-memory SQLite). Added `db_adapter` kwarg to thread the sitemap's adapter through — this is what makes tests 1 and 4 work.

- **Kept _scan_registry_for_binding for first-discovery R3:** The plan said "capture `used_credential_id = row.get('ssh_credential_id') if row else None`". For first discovery, `row=None`, so `used_credential_id=None`, breaking Phase 38.1 R3. Fixed by adding a `_scan_registry_for_binding(hostname, username)` call in the `row=None` branch — consistent with the "superseded but retained" contract in RESEARCH Assumption A3.

- **xfail removal is part of Task 1 scope:** The tests were RED (xfail) because the bugs existed. Part of the GREEN phase is removing the xfail markers. The plan listed specific tests to flip GREEN — those tests also needed mock-target updates to work with the Phase 41 code path.

- **D-06/D-07 tests updated:** Phase 41 changes the boundary where credential resolution happens (before ssh_discover_system, not inside it). D-06 contract is preserved at the resolve_ssh_credentials level; tests now mock at the correct boundary.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] resolve_ssh_for_sitemap_row needed db_adapter param for test isolation**
- **Found during:** Task 1 test run — tests 1 and 4 were still XFAIL after implementation
- **Issue:** `resolve_ssh_for_sitemap_row` uses `get_database_adapter()` which creates a NEW adapter pointing to the production DB path (or default SQLite), not the test's in-memory sitemap. Test-seeded rows in the in-memory sitemap were invisible to the helper.
- **Fix:** Added `db_adapter: DatabaseAdapter | None = None` kwarg to `resolve_ssh_for_sitemap_row`; `discover_and_store` passes `sitemap.db_adapter`
- **Files modified:** `src/homelab_mcp/ssh_tools.py`, `src/homelab_mcp/sitemap.py`
- **Committed in:** `d31f364` (Task 1)

**2. [Rule 1 - Bug] Phase 38.1 R3 regression on first-discovery**
- **Found during:** Task 1 test run — `test_discover_writes_credential_id_phase381` failed
- **Issue:** When `row=None` (first discovery), `used_credential_id=None` means `set_device_credential_binding` is never called. Old code used `_scan_registry_for_binding` separately. Plan said to replace registry scan with row-based capture, but this only works for second-and-later discoveries.
- **Fix:** Added `_scan_registry_for_binding(hostname, username)` call in the `row is None` branch as R3 fallback
- **Files modified:** `src/homelab_mcp/sitemap.py`
- **Committed in:** `d31f364` (Task 1)

**3. [Rule 1 - Bug] xfail mock targets needed updating for Phase 41 paths**
- **Found during:** Task 1 test run — tests 2 and 3 were XPASS but test 1 and 4 were still XFAIL
- **Issue:** Tests 1/4 had `fake_creds.password=None` causing ValueError in ssh_discover_system (skipping ssh_connect); test 1 was checking `call_args` (last call) instead of `call_args_list[0]` (first call)
- **Fix:** Updated fake_creds to include `password="fake-password"` in tests 1 and 4; updated test 1 assertion to check `call_args_list[0].kwargs`
- **Files modified:** `tests/test_phase41_binding_aware.py`
- **Committed in:** `d31f364` (Task 1)

**4. [Rule 1 - Bug] D-06/D-07 tests in test_sitemap.py broke under Phase 41 architecture**
- **Found during:** Task 1 test run — 3 sitemap tests failed
- **Issue:** D-06/D-07 tests only mocked `ssh_discover_system` but with Phase 41, credential resolution happens before `ssh_discover_system` via `resolve_ssh_for_sitemap_row` → `resolve_ssh_credentials`. Without mocking `resolve_ssh_credentials`, the call fails with `CredentialNotFoundError` (empty test keyring), never reaching `ssh_discover_system`.
- **Fix:** Updated tests to also mock `resolve_ssh_credentials`; updated assertions to check the new D-06 contract (resolver called with `username=None`, not "mcp_admin")
- **Files modified:** `tests/test_sitemap.py`
- **Committed in:** `d31f364` (Task 1)

---

Total deviations: 4 auto-fixed (Rules 1 and 2)

## Issues Encountered

None beyond the auto-fixed deviations above.

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes introduced.

The `db_adapter` kwarg addition is trust-boundary-neutral: it accepts an existing adapter object from the caller. No new trust surface created.

The `_scan_registry_for_binding` fallback was already in production code (via `ssh_discover_system_with_binding`); retaining it for the `row=None` case preserves existing surface, not expanding it.

## Known Stubs

None. All 3 bugs (AA, BB, V) are fully implemented on the discover side. The drift side (Bug V for `scan_drift`) waits on Plan 04.

## Self-Check

Files exist:
- `src/homelab_mcp/sitemap.py` — confirmed (modified)
- `src/homelab_mcp/ssh_tools.py` — confirmed (modified)
- `src/homelab_mcp/error_handling.py` — confirmed (modified)
- `tests/test_phase41_binding_aware.py` — confirmed (modified)
- `tests/test_sitemap.py` — confirmed (modified)
- `tests/test_ast_regression.py` — confirmed (modified)

Commits exist:
- `d31f364` feat(41-03): wire discover_and_store through resolve_ssh_for_sitemap_row — confirmed
- `b362b4c` feat(41-03): add hostname field to ssh_connection_wrapper error envelopes — confirmed

## Self-Check: PASSED

---
*Phase: 41-binding-aware-resolver-hygiene*
*Completed: 2026-04-30*
