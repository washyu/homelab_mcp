---
phase: 11-drift-detection
verified: 2026-03-12T19:30:00Z
status: passed
score: 17/17 must-haves verified
re_verification: false
---

# Phase 11: Drift Detection Verification Report

**Phase Goal:** Detect when VM/container configurations have drifted from their provisioned baseline — providing automated drift scanning, config diffing, and baseline management for homelab infrastructure.
**Verified:** 2026-03-12T19:30:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | scan_drift returns structured report with status, config_drift, state_drift, summary, scan_timestamp | VERIFIED | drift_detection.py lines 214-225 return all 5 keys; TestScanDriftReport passes |
| 2  | _diff_vm_config compares only CONFIG_DRIFT_FIELDS (cores, memory, sockets, net0, net1, net2) | VERIFIED | drift_detection.py line 16 + loop at line 41; TestConfigDrift (3 tests) pass |
| 3  | State drift uses "observation": "vm_offline" (never "confirmed_drift") | VERIFIED | drift_detection.py lines 171 and 197 use "observation": "vm_offline" exclusively |
| 4  | SSH probe fires for running VMs with known IPs; records "actual": "ssh_unreachable" on failure | VERIFIED | drift_detection.py lines 184-205; test_ssh_probe_unreachable passes |
| 5  | VMs without baselines are skipped for config drift (not false-reported) | VERIFIED | scan_drift iterates get_all_drift_baselines() — only baseline VMs are checked |
| 6  | drift_baselines SQLite table is created by init_schema() and run_sqlite_migrations() | VERIFIED | database.py init_schema and migration.py lines 68-91 confirmed |
| 7  | SQLiteAdapter.upsert_drift_baseline uses INSERT OR REPLACE with JSON serialization | VERIFIED | database.py line 654 INSERT OR REPLACE; lines 662/693/712 json.dumps/loads |
| 8  | get_proxmox_vm_config calls /nodes/{node}/{vm_type}/{vmid}/config endpoint | VERIFIED | proxmox_api.py line 355+; separate from /status/current |
| 9  | scan_infrastructure_drift tool appears in get_all_tool_schemas() | VERIFIED | tool_schemas/__init__.py imports and spreads DRIFT_TOOLS; test_tools.py asserts 50 tools pass |
| 10 | scan_infrastructure_drift is in TOOL_HANDLERS and dispatched to handle_scan_infrastructure_drift | VERIFIED | tool_handlers/__init__.py line 122 |
| 11 | scan_infrastructure_drift has readOnlyHint=True in TOOL_ANNOTATIONS | VERIFIED | tool_annotations.py line 37; test_tools.py passes |
| 12 | handle_create_proxmox_vm calls update_baseline_after_mutation on success | VERIFIED | proxmox_handlers.py line 155-175 |
| 13 | handle_create_proxmox_lxc calls update_baseline_after_mutation on success | VERIFIED | proxmox_handlers.py line 118-145 |
| 14 | handle_clone_proxmox_vm calls update_baseline_after_mutation using new_vmid on success | VERIFIED | proxmox_handlers.py line 190-212 |
| 15 | DatabaseAdapter ABC declares all three drift baseline methods as @abstractmethod | VERIFIED | database.py lines 112-137: @abstractmethod on all three |
| 16 | All 15 unit tests for drift detection pass (10 in test_drift_detection.py, 5 in TestDriftBaselines) | VERIFIED | uv run pytest: 15 passed in 0.68s |
| 17 | Full test suite has no regressions (578 passed, 7 skipped) | VERIFIED | uv run pytest tests/ -m "not integration": 578 passed, 7 skipped |

**Score:** 17/17 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/homelab_mcp/drift_detection.py` | scan_drift, update_baseline_after_mutation, _diff_vm_config, CONFIG_DRIFT_FIELDS | VERIFIED | 280 lines; all 4 exports present and substantive |
| `src/homelab_mcp/database.py` | upsert_drift_baseline, get_drift_baseline, get_all_drift_baselines on SQLiteAdapter + ABC | VERIFIED | All 3 methods on ABC (abstractmethod), SQLiteAdapter (concrete), PostgreSQLAdapter (NotImplementedError stubs) |
| `src/homelab_mcp/migration.py` | drift_baselines table migration in run_sqlite_migrations() | VERIFIED | Lines 68-91: SELECT check, CREATE TABLE, CREATE INDEX, append migration name |
| `src/homelab_mcp/proxmox_api.py` | get_proxmox_vm_config() function | VERIFIED | Line 355+; calls /config endpoint; mirrors get_proxmox_vm_status signature exactly |
| `src/homelab_mcp/tool_schemas/drift_tools_schema.py` | DRIFT_TOOLS dict with scan_infrastructure_drift schema | VERIFIED | 27 lines; node + vm_type parameters; correct inputSchema |
| `src/homelab_mcp/tool_handlers/drift_handlers.py` | handle_scan_infrastructure_drift | VERIFIED | 20 lines; calls scan_drift via get_resource_manager(); returns content-wrapped JSON |
| `src/homelab_mcp/tool_schemas/__init__.py` | DRIFT_TOOLS merged into get_all_tool_schemas() | VERIFIED | Line 6 import + line 25 **DRIFT_TOOLS spread |
| `src/homelab_mcp/tool_handlers/__init__.py` | scan_infrastructure_drift registered in TOOL_HANDLERS | VERIFIED | Line 12 import + line 122 dict entry + line 144 __all__ |
| `src/homelab_mcp/tool_annotations.py` | scan_infrastructure_drift in _READ_ONLY_TOOLS | VERIFIED | Line 37; readOnlyHint=True inherited from block definition at line 18 |
| `src/homelab_mcp/tool_handlers/proxmox_handlers.py` | update_baseline_after_mutation hook in 3 handlers | VERIFIED | Lines 118, 155, 190: all three handlers have inline import + success guard + await call |
| `tests/test_drift_detection.py` | 4 test classes: TestScanDriftReport, TestConfigDrift, TestStateDrift, TestBaselineUpdate | VERIFIED | 10 tests; all pass GREEN |
| `tests/test_database.py::TestDriftBaselines` | 5 CRUD tests for DRFT-04 | VERIFIED | 5 tests at lines 338-430; all pass GREEN |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| drift_detection.py::scan_drift | proxmox_api.py::get_proxmox_vm_config | await get_proxmox_vm_config(node, vmid, vm_type, session) | WIRED | Line 107-112; imported at line 11 |
| drift_detection.py::scan_drift | db_adapter.get_all_drift_baselines | synchronous call | WIRED | Line 83 |
| drift_detection.py::scan_drift | proxmox_api.py::get_proxmox_vm_status | await get_proxmox_vm_status(node, vmid, vm_type, session) | WIRED | Line 149-154; imported at line 11 |
| drift_detection.py::scan_drift | db_adapter.get_all_devices | synchronous call for IP lookup | WIRED | Line 94 |
| drift_detection.py::scan_drift | asyncssh.connect (SSH probe) | await asyncssh.connect(ip, ...) | WIRED | Lines 186-192; import at line 8 |
| drift_detection.py::update_baseline_after_mutation | db_adapter.upsert_drift_baseline | synchronous call after config fetch | WIRED | Line 272-278 |
| migration.py::run_sqlite_migrations | sqlite_master | SELECT name check before CREATE TABLE | WIRED | Lines 68-74 |
| database.py::SQLiteAdapter.upsert_drift_baseline | drift_baselines table | INSERT OR REPLACE INTO drift_baselines | WIRED | Line 654 |
| tool_schemas/__init__.py::get_all_tool_schemas | drift_tools_schema.py::DRIFT_TOOLS | **DRIFT_TOOLS spread | WIRED | Line 25 |
| tool_handlers/__init__.py::TOOL_HANDLERS | drift_handlers.py::handle_scan_infrastructure_drift | dict key "scan_infrastructure_drift" | WIRED | Line 122 |
| proxmox_handlers.py::handle_create_proxmox_vm | drift_detection.py::update_baseline_after_mutation | inline import + await on success | WIRED | Lines 155-175 |
| proxmox_handlers.py::handle_create_proxmox_lxc | drift_detection.py::update_baseline_after_mutation | inline import + await on success | WIRED | Lines 118-145 |
| proxmox_handlers.py::handle_clone_proxmox_vm | drift_detection.py::update_baseline_after_mutation | inline import + await on success (new_vmid) | WIRED | Lines 190-212 |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| DRFT-01 | 11-01, 11-04, 11-05 | User can run scan_infrastructure_drift to get a report of all detected drift | SATISFIED | scan_infrastructure_drift tool in TOOL_HANDLERS; scan_drift returns structured report; TestScanDriftReport passes |
| DRFT-02 | 11-01, 11-04 | State drift detects when VMs/services are offline (SSH + Proxmox status) | SATISFIED | scan_drift checks Proxmox status AND SSH probe; state_drift uses "observation": "vm_offline"; test_ssh_probe_unreachable passes |
| DRFT-03 | 11-01, 11-03, 11-04 | Config drift detects when VM/device config changed outside MCP (CPU, memory, network) | SATISFIED | get_proxmox_vm_config calls /config endpoint; _diff_vm_config compares CONFIG_DRIFT_FIELDS; TestConfigDrift passes |
| DRFT-04 | 11-01, 11-02 | Drift baselines stored in SQLite as full config dicts for field-level diffing | SATISFIED | drift_baselines table in init_schema() + migration; INSERT OR REPLACE; json.dumps/loads; TestDriftBaselines (5 tests) pass |
| DRFT-05 | 11-01, 11-04, 11-05 | Drift baselines update after successful MCP mutations to avoid false positives | SATISFIED | update_baseline_after_mutation called in 3 proxmox handlers on success; TestBaselineUpdate passes; test_proxmox_baseline_hooks.py (15 tests) pass |

All 5 DRFT requirements satisfied. No orphaned requirements.

---

## Anti-Patterns Found

No anti-patterns detected in new files. Scan results:

- drift_detection.py: No TODOs, FIXMEs, placeholders, or empty implementations
- drift_tools_schema.py: Substantive schema definition (27 lines)
- drift_handlers.py: Real implementation calling scan_drift (not stub)
- database.py new methods: Real SQL with json.dumps/loads (PostgreSQLAdapter uses explicit NotImplementedError — intentional, per design decision)

One minor documentation staleness noted (not a blocker):

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/homelab_mcp/tool_annotations.py` | 3 | Module docstring says "Maps all 49 tool names" but there are now 50 tools | Info | No functional impact; test_tools.py asserts 50 and passes |

---

## Human Verification Required

### 1. End-to-end drift scan against live Proxmox

**Test:** With a running Proxmox environment and at least one VM with a stored baseline, call `scan_infrastructure_drift` via the MCP client.
**Expected:** Report returns with config_drift empty (if no changes) or populated with field-level diffs. State drift reflects current VM running/stopped status. SSH probe result appears in state_drift if VM is unreachable.
**Why human:** Requires live Proxmox instance and real baseline records. Cannot mock at this level.

### 2. Baseline auto-update after VM creation

**Test:** Create a VM via `create_proxmox_vm`. Then call `scan_infrastructure_drift`. The new VM should appear in baselines_available and should produce no config drift.
**Expected:** `scan_infrastructure_drift` shows baselines_available incremented; no false config drift for the new VM.
**Why human:** Requires live Proxmox + full server session with get_resource_manager().

---

## Summary

Phase 11 goal is fully achieved. All five drift detection requirements (DRFT-01 through DRFT-05) are implemented, wired, and tested:

- The `drift_detection.py` module is substantive (280 lines) with real logic for config diffing, Proxmox API integration, SSH probing, and baseline mutation tracking
- All 17 observable truths were verified against the actual codebase — no stubs, no orphaned artifacts, no broken wiring
- 578 unit tests pass with no regressions
- The scan_infrastructure_drift tool is correctly registered as read-only and dispatched through the MCP tool pipeline
- Baseline auto-update hooks are in place in all three Proxmox mutation handlers with error-swallowing guards so handler results are never blocked by baseline failures

The only item flagged is a stale comment in tool_annotations.py docstring (says 49 tools, should say 50) — this is informational, does not affect runtime behavior, and the test suite asserts the correct count of 50.

---

_Verified: 2026-03-12T19:30:00Z_
_Verifier: Claude (gsd-verifier)_
