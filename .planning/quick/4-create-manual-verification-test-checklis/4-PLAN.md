---
quick: 4
type: execute
wave: 1
depends_on: []
files_modified:
  - MANUAL-TESTS.md
autonomous: true
requirements: []

must_haves:
  truths:
    - "MANUAL-TESTS.md exists at the repo root"
    - "Checklist covers all v1.1 feature areas: dry-run, MCP resources, resource notifications, and drift detection"
    - "Each check is a concrete, actionable step with expected output described"
    - "Checks are organized by feature and marked with checkboxes"
  artifacts:
    - path: "MANUAL-TESTS.md"
      provides: "Human-executable QA checklist for v1.1 build verification"
  key_links: []
---

<objective>
Explore the codebase to understand all 50 tools and v1.1 features, then produce MANUAL-TESTS.md — a markdown checklist a human tester can follow against a live Proxmox homelab to verify the v1.1 build is working end-to-end.

Purpose: The v1.1 milestone shipped all 22 requirements but 2 items (live drift scan, live baseline update) were deferred to ops/QA. This checklist closes that gap and gives any user a repeatable verification recipe.
Output: MANUAL-TESTS.md at repo root
</objective>

<execution_context>
@/home/shaun/.claude/get-shit-done/workflows/execute-plan.md
@/home/shaun/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/milestones/v1.1-ROADMAP.md
@.planning/milestones/v1.1-MILESTONE-AUDIT.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Explore codebase and produce MANUAL-TESTS.md</name>
  <files>MANUAL-TESTS.md</files>
  <action>
Read the following files to understand all tools, parameters, and v1.1 feature contracts:

- src/homelab_mcp/tool_schemas/drift_tools_schema.py — scan_infrastructure_drift parameters
- src/homelab_mcp/tool_schemas/infrastructure_tools_schema.py — dry_run tools (decommission_device, rollback_infrastructure_changes)
- src/homelab_mcp/tool_schemas/vm_tools_schema.py — dry_run tools (remove_vm, remove_server)
- src/homelab_mcp/tool_schemas/proxmox_tools_schema.py — dry_run tools (delete_proxmox_vm, create_proxmox_vm)
- src/homelab_mcp/tool_schemas/service_tools_schema.py — dry_run tools (destroy_terraform_service)
- src/homelab_mcp/resource_readers.py — homelab://vms, homelab://devices, homelab://services/{name} URIs
- src/homelab_mcp/drift_detection.py — drift scan internals, config fields compared, state drift logic
- src/homelab_mcp/server.py — MCP resources protocol handlers, notification dispatch
- src/homelab_mcp/tool_annotations.py — MUTATING_TOOLS set (which tools trigger notifications)

Then create MANUAL-TESTS.md at the repo root with the following structure:

---

# Homelab MCP Server — Manual Verification Checklist (v1.1)

Brief intro: explain this is a post-install QA checklist for v1.1 Safety & Observability milestone. Note that a live Proxmox node is required for the Proxmox-specific sections; the MCP protocol sections can be tested with any MCP client connected via stdio or HTTP transport.

## Prerequisites

Checklist items before starting:
- [ ] Server running: `uv run python run_server.py`
- [ ] MCP client connected (Claude Desktop or any MCP-capable client)
- [ ] Proxmox API credentials configured in environment (PROXMOX_HOST, PROXMOX_USER, PROXMOX_PASSWORD or PROXMOX_TOKEN_NAME/PROXMOX_TOKEN_VALUE)
- [ ] At least one VM exists on the Proxmox node

---

## Section 1: Server Startup and Tool Discovery

Verify the server starts and exposes all expected tools.

- [ ] Server starts without errors: `uv run python run_server.py` produces no traceback
- [ ] `initialize` response includes `resources` in `capabilities` object
- [ ] `tools/list` returns 50 tools (verify count)
- [ ] `scan_infrastructure_drift` is present in the tools list
- [ ] `dry_run` parameter visible in schema for: `decommission_device`, `remove_vm`, `remove_server`, `delete_proxmox_vm`, `destroy_terraform_service`, `rollback_infrastructure_changes`

---

## Section 2: Dry-Run Mode (Phase 08 — DRY-01 through DRY-07)

For each destructive tool, verify dry_run=true returns a preview without executing any real action.

### 2.1 decommission_device dry-run
- [ ] Call `decommission_device` with `dry_run: true` and a known device hostname
- [ ] Response contains `mode: "dry_run"`
- [ ] Response contains `would_affect` (list of resources that would be removed)
- [ ] Response contains `risk_level` (one of `high`, `medium`, `low`)
- [ ] Response contains `reversible` (boolean)
- [ ] No device is removed from the database after the call

### 2.2 remove_vm dry-run
- [ ] Call `remove_vm` with `dry_run: true` and a known VM name
- [ ] Response contains all four dry-run fields: `mode`, `would_affect`, `risk_level`, `reversible`
- [ ] No SSH command is executed against the target host

### 2.3 remove_server dry-run
- [ ] Call `remove_server` with `dry_run: true` and a registered server hostname
- [ ] Response contains all four dry-run fields
- [ ] Server record still present in database after the call (verify with `list_registered_servers`)

### 2.4 delete_proxmox_vm dry-run
- [ ] Call `delete_proxmox_vm` with `dry_run: true`, providing `node` and `vmid`
- [ ] Response contains all four dry-run fields
- [ ] VM still exists on Proxmox after the call (verify with `get_proxmox_vm_status`)

### 2.5 destroy_terraform_service dry-run
- [ ] Call `destroy_terraform_service` with `dry_run: true` and a service name
- [ ] Response contains all four dry-run fields
- [ ] No `terraform destroy` process is spawned

### 2.6 rollback_infrastructure_changes dry-run
- [ ] Call `rollback_infrastructure_changes` with `dry_run: true`
- [ ] Response contains all four dry-run fields
- [ ] No rollback action is executed

### 2.7 Live execution still works (regression check)
- [ ] Call any dry-run tool WITHOUT `dry_run: true` (or with `dry_run: false`)
- [ ] Response does NOT contain `mode: "dry_run"`
- [ ] Actual operation proceeds normally (use a non-critical target)

---

## Section 3: MCP Resources Protocol (Phase 07 + Phase 09 — RES-01 through RES-06)

Verify `resources/list` and `resources/read` work correctly.

### 3.1 resources/list
- [ ] `resources/list` returns at minimum three URIs: `homelab://vms`, `homelab://devices`, `homelab://services`
- [ ] Each resource entry has `uri`, `name`, and `mimeType: "application/json"` fields

### 3.2 homelab://vms (live data)
- [ ] `resources/read` with `uri: "homelab://vms"` returns a JSON payload
- [ ] JSON payload contains a list of VMs from Proxmox (not placeholder data — compare against `list_proxmox_resources` output)
- [ ] Response includes a `scanned_at` ISO timestamp field

### 3.3 homelab://devices (live data)
- [ ] `resources/read` with `uri: "homelab://devices"` returns JSON
- [ ] JSON contains device records from the SQLite database
- [ ] Each device record includes `last_seen` and `last_discovery_data` fields (or null if never scanned)
- [ ] Response includes a `scanned_at` ISO timestamp

### 3.4 homelab://services/{name} (live data)
- [ ] `resources/read` with `uri: "homelab://services/nginx"` (or any installed service name) returns JSON
- [ ] JSON indicates whether the service is running
- [ ] Response includes a `scanned_at` ISO timestamp

### 3.5 Unknown URI returns MCP error -32002
- [ ] `resources/read` with `uri: "homelab://nonexistent"` returns an MCP error
- [ ] Error code is `-32002`

---

## Section 4: Resource Notifications (Phase 10 — RES-07)

Verify the server emits resource notifications after mutations and discoveries.

### 4.1 Notification after ssh_discover
- [ ] Subscribe to `homelab://devices` via `resources/subscribe`
- [ ] Call `discover_and_map` or `bulk_discover_and_map` with a valid subnet
- [ ] After discovery completes, client receives a `notifications/resources/list_changed` notification
- [ ] Notification is NOT sent if no new devices were discovered (optional check — inspect server logs)

### 4.2 No notification after dry-run
- [ ] Call any mutating tool (e.g., `delete_proxmox_vm`) with `dry_run: true`
- [ ] Confirm no `notifications/resources/updated` or `notifications/resources/list_changed` is emitted
- [ ] Check server logs: no "Sending resource notification" line for dry-run calls

### 4.3 Notification after real mutation (optional — requires safe test target)
- [ ] Call a mutating tool (e.g., `create_proxmox_vm` with a test VM) without `dry_run`
- [ ] Client receives `notifications/resources/updated` notification after successful completion

---

## Section 5: Drift Detection (Phase 11 — DRFT-01 through DRFT-05)

Verify drift scanning and baseline management work correctly.

### 5.1 scan_infrastructure_drift — initial run (no baselines)
- [ ] Call `scan_infrastructure_drift` with a valid `node` (Proxmox node name)
- [ ] Response is a structured dict (not an error)
- [ ] Response contains `scan_timestamp` (ISO format)
- [ ] Response contains `config_drift` list and `state_drift` list (both may be empty on first run)

### 5.2 scan_infrastructure_drift — state drift detection
- [ ] Manually stop a VM on Proxmox (outside of MCP) that has a stored baseline marking it as running
- [ ] Call `scan_infrastructure_drift` for that node
- [ ] Stopped VM appears in `state_drift` findings
- [ ] Each state drift finding includes `drift_type: "state_drift"` (or `"vm_offline"`), `expected`, `actual`, and `scan_timestamp`
- [ ] Finding is labeled as a point-in-time observation (not confirmed permanent drift)

### 5.3 scan_infrastructure_drift — config drift detection
- [ ] Manually change a VM's CPU or memory on Proxmox (outside of MCP) for a VM with a stored baseline
- [ ] Call `scan_infrastructure_drift` for that node
- [ ] Changed VM appears in `config_drift` findings
- [ ] Each config drift finding includes `drift_type: "config_drift"`, `expected`, `actual` (showing old vs new values), and `scan_timestamp`

### 5.4 Baseline auto-update after MCP mutation
- [ ] Record the current baseline for a VM (note its CPU/memory)
- [ ] Call `create_proxmox_vm` or `clone_proxmox_vm` via MCP to create/modify a VM
- [ ] Call `scan_infrastructure_drift` immediately after
- [ ] The newly created/modified VM does NOT appear as config drift (baseline was updated)

### 5.5 Drift baselines persist in SQLite
- [ ] Restart the MCP server
- [ ] Call `scan_infrastructure_drift` again
- [ ] Baselines are preserved (previously-known VMs do not reappear as fresh drift)

---

## Section 6: Automated Test Suite (Regression Gate)

Run the test suite to confirm no regressions.

- [ ] `uv run pytest tests/ -m "not integration" -v` — all unit tests pass
- [ ] `uv run ruff check src/ tests/` — no linting errors
- [ ] `uv run mypy src/` — no type errors (pre-existing deferred errors are acceptable; see MILESTONE-AUDIT.md)

---

## Section 7: HTTP Transport Auth (DEBT-02 regression)

Only applicable if running the HTTP transport with `MCP_API_KEY` set.

- [ ] Set `MCP_API_KEY=test-key` in environment and start HTTP transport
- [ ] Request without `Authorization` header returns 401 or 403
- [ ] Request with `Authorization: Bearer test-key` header succeeds
- [ ] `/health` endpoint is accessible WITHOUT authentication header

---

## Sign-off

| Check | Result | Notes |
|-------|--------|-------|
| Section 1: Server + Tools | | |
| Section 2: Dry-Run Mode | | |
| Section 3: MCP Resources | | |
| Section 4: Notifications | | |
| Section 5: Drift Detection | | |
| Section 6: Automated Tests | | |
| Section 7: HTTP Auth (optional) | | |

**Verified by:** _______________
**Date:** _______________
**Server version / commit:** _______________

---

After producing the document, verify it looks correct: it should have 7 sections, checkbox items throughout, and cover all 22 v1.1 requirements mapped to their verification steps.
  </action>
  <verify>ls -la /home/shaun/projects/mcp_python_server/MANUAL-TESTS.md && wc -l /home/shaun/projects/mcp_python_server/MANUAL-TESTS.md</verify>
  <done>MANUAL-TESTS.md exists at repo root, is at least 100 lines, contains checkbox items for all 6 v1.1 feature areas (dry-run, MCP resources list, MCP resources read, resource notifications, drift detection, automated tests), and every checkbox step has a clear expected outcome described.</done>
</task>

</tasks>

<verification>
- MANUAL-TESTS.md exists at `/home/shaun/projects/mcp_python_server/MANUAL-TESTS.md`
- File contains sections for all v1.1 phases: dry-run (Phase 08), MCP resources (Phases 07+09), notifications (Phase 10), drift detection (Phase 11)
- Each section has concrete, actionable checkbox items with expected outputs
- Sign-off table present at the end
</verification>

<success_criteria>
A human tester with a live Proxmox homelab can open MANUAL-TESTS.md, work through each section top-to-bottom, and confirm whether the v1.1 build is working correctly — with no ambiguity about what to call, what parameters to pass, or what the expected result should be.
</success_criteria>

<output>
After completion, create `.planning/quick/4-create-manual-verification-test-checklis/4-SUMMARY.md`
</output>
