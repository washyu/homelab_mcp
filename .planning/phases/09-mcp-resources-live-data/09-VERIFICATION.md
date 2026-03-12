---
phase: 09-mcp-resources-live-data
verified: 2026-03-11T00:00:00Z
status: passed
score: 14/14 must-haves verified
re_verification: false
---

# Phase 9: MCP Resources Live Data — Verification Report

**Phase Goal:** MCP Resources return live data from the homelab infrastructure (VMs, devices, services) instead of stubs.
**Verified:** 2026-03-11
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | `read_vms_resource()` returns a dict with `vms` list and `scanned_at` ISO timestamp | VERIFIED | Lines 46-51 of resource_readers.py; test `test_read_vms_resource_returns_scanned_at` asserts both |
| 2  | `read_vms_resource()` returns graceful error payload when Proxmox is not configured, not an exception | VERIFIED | Lines 59-65 of resource_readers.py catch `ValueError`, return `{"vms": [], "config_error": ..., "scanned_at": ...}`; test `test_read_vms_resource_no_proxmox_config` covers this |
| 3  | `read_devices_resource()` returns a dict with `devices` list where each device has `last_discovery_data` field | VERIFIED | Lines 100-101 of resource_readers.py enrich each device; tests `test_read_devices_resource_includes_last_discovery_data` and `test_read_devices_resource_no_history` verify both cases |
| 4  | `read_devices_resource()` returns `scanned_at` ISO timestamp in response | VERIFIED | Line 109 of resource_readers.py; test `test_read_devices_resource_returns_scanned_at` asserts `scanned_at` in result |
| 5  | `read_service_resource('nginx')` returns a dict with `service`, `scanned_at` fields | VERIFIED | Lines 175-177 inject `scanned_at` into status dict; test `test_read_service_resource_returns_status` asserts both fields |
| 6  | `read_service_resource` returns `unconfigured` status when no hostname is resolvable | VERIFIED | Lines 165-171 of resource_readers.py; test `test_read_service_resource_unconfigured` asserts `result["status"] == "unconfigured"` |
| 7  | All three readers catch `RuntimeError` from `get_resource_manager()` and return graceful error payload | VERIFIED | Lines 52-58, 111-117, 156-163 of resource_readers.py; tests `test_read_vms_resource_no_resource_manager`, pattern replicated for all three functions |
| 8  | `handle_read_resource('homelab://vms')` calls `read_vms_resource()` and returns its JSON payload | VERIFIED | Line 166 of server.py: `payload = await read_vms_resource()`; test `test_read_vms_resource_has_scanned_at` patches and asserts dispatch |
| 9  | `handle_read_resource('homelab://devices')` calls `read_devices_resource()` and returns its JSON payload | VERIFIED | Line 168 of server.py: `payload = await read_devices_resource()`; test `test_read_devices_resource_has_scanned_at` confirms |
| 10 | `handle_read_resource('homelab://services/nginx')` calls `read_service_resource('nginx')` and returns its JSON payload | VERIFIED | Lines 169-179 of server.py; test `test_read_services_template_uri` patches and asserts `service` field present |
| 11 | `handle_read_resource('homelab://services/')` with empty name raises McpError -32002 | VERIFIED | Lines 171-178 of server.py raise `McpError(RESOURCE_NOT_FOUND, "Service name required")`; test `test_read_services_empty_name_error` asserts code == -32002 |
| 12 | `handle_read_resource('homelab://unknown')` raises McpError -32002 | VERIFIED | Lines 186-193 of server.py; pre-existing test `test_read_unknown_resource_raises_mcp_error` passes |
| 13 | Every resource read returns `application/json` MIME type | VERIFIED | Line 203 of server.py: `mime_type="application/json"` on all paths; test `test_list_resources_has_json_mimetype` and `test_read_vms_resource_has_scanned_at` assert `mime_type == "application/json"` |
| 14 | Responses include `scanned_at` field (proven by reader functions) | VERIFIED | All three reader functions emit `scanned_at = datetime.now(UTC).isoformat()` on every code path |

**Score:** 14/14 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/homelab_mcp/resource_readers.py` | Three async reader functions for VMs, devices, and services | VERIFIED | 187 lines; exports `read_vms_resource`, `read_devices_resource`, `read_service_resource`; substantive implementations with full error handling |
| `tests/test_resource_readers.py` | Unit tests for all three reader functions with mocked dependencies | VERIFIED | 268 lines; 9 test functions covering success, config error, runtime error, no-history, unconfigured, SSH error paths |
| `src/homelab_mcp/server.py` | Live dispatch in `handle_read_resource` replacing stub lookup | VERIFIED | Lines 164-203 contain the full live dispatch block; `stub` key removed from `HOMELAB_RESOURCES`; imports `read_vms_resource`, `read_devices_resource`, `read_service_resource` at line 31 |
| `tests/test_mcp_resources.py` | Tests covering live dispatch, services template URI, and scanned_at presence | VERIFIED | 239 lines; 4 new Phase 9 tests in the "Live dispatch tests" section (lines 181-238); all existing Phase 7 tests retained |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `resource_readers.read_vms_resource` | `proxmox_api.list_proxmox_resources` | `get_resource_manager().proxmox_session` passed as `session` kwarg | VERIFIED | Line 44 of resource_readers.py: `await list_proxmox_resources(session=rm.proxmox_session)`; test mocks both `get_resource_manager` and `list_proxmox_resources` |
| `resource_readers.read_devices_resource` | `db_adapter.get_all_devices + get_device_changes` | `get_resource_manager().db_adapter` | VERIFIED | Lines 93 and 100 of resource_readers.py call `db.get_all_devices()` and `db.get_device_changes(device_id, limit=1)` |
| `resource_readers.read_service_resource` | `ServiceInstaller.get_service_status` | hostname resolved from env or first DB device | VERIFIED | Lines 174-176 of resource_readers.py: `installer = ServiceInstaller(); status = await installer.get_service_status(service_name, hostname)` |
| `server.handle_read_resource` | `resource_readers.read_vms_resource` | `uri_str == 'homelab://vms'` branch | VERIFIED | Line 166 of server.py: `payload = await read_vms_resource()` |
| `server.handle_read_resource` | `resource_readers.read_service_resource` | `uri_str.startswith('homelab://services/')` branch | VERIFIED | Lines 169-179 of server.py; `startswith` check precedes `HOMELAB_RESOURCES` membership check |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| RES-02 | 09-01, 09-02 | `homelab://vms` resource returns live VM list from Proxmox/Docker/LXD | SATISFIED | `read_vms_resource()` calls `list_proxmox_resources` with live Proxmox session; dispatched by `handle_read_resource` for `homelab://vms` |
| RES-03 | 09-01, 09-02 | `homelab://devices` resource returns device inventory with last discovery data | SATISFIED | `read_devices_resource()` fetches all DB devices and enriches each with `last_discovery_data` from `get_device_changes`; dispatched for `homelab://devices` |
| RES-04 | 09-01, 09-02 | `homelab://services/{name}` resource returns individual service status | SATISFIED | `read_service_resource(service_name)` calls `ServiceInstaller.get_service_status` via SSH; dispatched for `homelab://services/{name}` template URIs |

All three Phase 9 requirement IDs are satisfied. No orphaned requirements found — REQUIREMENTS.md traceability table marks RES-02, RES-03, RES-04 as Phase 9 / Complete.

**Adjacent requirements check:** RES-05 (application/json) and RES-06 (-32002 for unknown URIs) were Phase 7 responsibilities. Both remain satisfied — `mime_type="application/json"` on line 203 of server.py and the unknown-URI McpError path on lines 186-193 still pass in the full test suite.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | None found | — | — |

Scanned `resource_readers.py`, `server.py`, `test_resource_readers.py`, `test_mcp_resources.py`. No TODO/FIXME/placeholder comments, no empty implementations, no stub returns in dispatch paths, no stubs remaining in `HOMELAB_RESOURCES` (the `stub` key was removed from all entries).

---

### Human Verification Required

None. All truths were verifiable programmatically via code inspection and test execution.

---

### Test Suite Results

```
tests/test_resource_readers.py  — 9/9 pass
tests/test_mcp_resources.py     — 25/25 pass (21 existing + 4 new Phase 9 tests)
Full unit suite                 — 537 passed, 7 skipped, 0 failures
```

---

### Summary

Phase 9 achieved its goal. All three MCP Resources — `homelab://vms`, `homelab://devices`, and `homelab://services/{name}` — now return live data from the homelab infrastructure instead of stubs. The stub lookup was replaced with a URI-based dispatch in `handle_read_resource` that calls isolated, independently testable reader functions. The circular import introduced when server.py began importing resource_readers was resolved by deferring `get_resource_manager` imports to function-body scope. All 14 observable truths pass, all 5 key links are wired, and all three phase requirements (RES-02, RES-03, RES-04) are satisfied with passing tests as evidence.

---

_Verified: 2026-03-11_
_Verifier: Claude (gsd-verifier)_
