# Homelab MCP Server — Manual Verification Checklist (v1.1)

This is a post-install QA checklist for the v1.1 Safety & Observability milestone. Work through each section top-to-bottom against a live deployment. A live Proxmox node is required for sections 2, 3, 5, and the Proxmox-specific parts of section 4. Sections 1, 3.5, 4.2, and 6 can be verified with any MCP client connected via stdio transport.

---

## Prerequisites

Complete all items before starting:

- [ ] Server is running: `uv run python run_server.py` — no traceback on startup
- [ ] MCP client is connected (Claude Desktop or any MCP-capable client via stdio)
- [ ] Proxmox credentials configured in environment:
  - Option A (password auth): `PROXMOX_HOST`, `PROXMOX_USER`, `PROXMOX_PASSWORD`
  - Option B (token auth): `PROXMOX_HOST`, `PROXMOX_USER`, `PROXMOX_TOKEN_NAME`, `PROXMOX_TOKEN_VALUE`
- [ ] At least one VM or LXC container exists on the Proxmox node
- [ ] You know the Proxmox node name (e.g., `pve`) and at least one VMID

---

## Section 1: Server Startup and Tool Discovery

Verify the server starts and exposes all expected tools.

- [ ] Server starts without errors: `uv run python run_server.py` produces no traceback on stdout/stderr
- [ ] The `initialize` response (sent by server on first connection) includes `resources` in the `capabilities` object — confirms MCP Resources protocol support is advertised
- [ ] `tools/list` returns exactly **50 tools** — count the entries in the response
- [ ] `scan_infrastructure_drift` is present in the tools list
- [ ] The following destructive tools each expose a `dry_run` boolean parameter in their input schema (check `tools/list` output):
  - `decommission_device`
  - `remove_vm`
  - `remove_server`
  - `delete_proxmox_vm`
  - `destroy_terraform_service`
  - `rollback_infrastructure_changes`

---

## Section 2: Dry-Run Mode (Phase 08 — DRY-01 through DRY-07)

Each destructive tool supports a `dry_run: true` parameter. When set, the tool must return a preview response without executing any real action. Verify each one.

**Expected dry-run response fields (all four must be present):**

| Field | Type | Description |
|---|---|---|
| `mode` | string | Must equal `"dry_run"` |
| `would_affect` | array | Resources that would be removed or modified |
| `risk_level` | string | One of `"high"`, `"medium"`, or `"low"` |
| `reversible` | boolean | Whether the operation could be undone |

### 2.1 decommission_device dry-run

- [ ] Call `decommission_device` with `dry_run: true` and a known device hostname or device ID
- [ ] Response contains `mode: "dry_run"`
- [ ] Response contains `would_affect` (list of resources that would be removed)
- [ ] Response contains `risk_level` (one of `"high"`, `"medium"`, `"low"`)
- [ ] Response contains `reversible` (boolean)
- [ ] Confirm the device is still present in the database after the call: call `list_registered_servers` or run `discover_and_map` and verify device still appears

### 2.2 remove_vm dry-run

- [ ] Call `remove_vm` with `dry_run: true` and a known VM name (as registered with the server)
- [ ] Response contains all four dry-run fields: `mode`, `would_affect`, `risk_level`, `reversible`
- [ ] No SSH command was executed against the target host — verify the VM process is still running on the host

### 2.3 remove_server dry-run

- [ ] Call `remove_server` with `dry_run: true` and a registered server hostname
- [ ] Response contains all four dry-run fields
- [ ] Server record still present in database after the call — verify by calling `list_registered_servers` and confirming the hostname still appears

### 2.4 delete_proxmox_vm dry-run

- [ ] Call `delete_proxmox_vm` with `dry_run: true`, providing `node` (e.g., `"pve"`) and `vmid` (integer)
- [ ] Response contains all four dry-run fields
- [ ] VM still exists on Proxmox after the call — verify by calling `get_proxmox_vm_status` with the same `node` and `vmid`

### 2.5 destroy_terraform_service dry-run

- [ ] Call `destroy_terraform_service` with `dry_run: true` and a service `name`
- [ ] Response contains all four dry-run fields
- [ ] No `terraform destroy` process was spawned — verify service state is unchanged

### 2.6 rollback_infrastructure_changes dry-run

- [ ] Call `rollback_infrastructure_changes` with `dry_run: true`
- [ ] Response contains all four dry-run fields
- [ ] No rollback action was executed — infrastructure state is unchanged

### 2.7 Live execution regression check

- [ ] Call any one of the dry-run tools WITHOUT `dry_run: true` (or explicitly with `dry_run: false`) using a non-critical or expendable target
- [ ] Response does NOT contain `mode: "dry_run"` — confirms live path is not intercepted
- [ ] Actual operation proceeds normally (e.g., device is actually removed, or server record is actually deleted)

---

## Section 3: MCP Resources Protocol (Phases 07 + 09 — RES-01 through RES-06)

Verify `resources/list` and `resources/read` work correctly.

### 3.1 resources/list

- [ ] Call `resources/list`
- [ ] Response returns at minimum three resource entries with URIs: `homelab://vms`, `homelab://devices`, `homelab://services`
- [ ] Each resource entry has:
  - `uri` field
  - `name` field (human-readable label)
  - `mimeType: "application/json"`

### 3.2 homelab://vms (live data)

- [ ] Call `resources/read` with `uri: "homelab://vms"`
- [ ] Response is a valid JSON payload (not an error)
- [ ] JSON payload contains a `vms` array — compare the list against `list_proxmox_resources` output to confirm it reflects live Proxmox state (not placeholder data)
- [ ] JSON payload contains a `scanned_at` field in ISO 8601 format (e.g., `"2026-03-12T10:00:00+00:00"`)
- [ ] JSON payload contains a `total` integer equal to the length of the `vms` array

### 3.3 homelab://devices (live data)

- [ ] Call `resources/read` with `uri: "homelab://devices"`
- [ ] Response returns a JSON payload with a `devices` array containing records from the SQLite database
- [ ] Each device record includes:
  - `last_seen` field (timestamp or null if never seen)
  - `last_discovery_data` field (discovery blob or null if no history)
- [ ] JSON payload includes a `scanned_at` ISO 8601 timestamp

### 3.4 homelab://services/{name} (live data)

- [ ] Call `resources/read` with `uri: "homelab://services/nginx"` (substitute any installed service name, or set `MCP_DEFAULT_SERVICE_HOST` to a reachable host)
- [ ] Response is a JSON payload indicating whether the service is running on the target host
- [ ] JSON payload includes a `scanned_at` ISO 8601 timestamp
- [ ] Note: if no `MCP_DEFAULT_SERVICE_HOST` is set and no devices are in the DB, response will contain `status: "unconfigured"` — this is expected behavior, not a failure

### 3.5 Unknown URI returns MCP error -32002

- [ ] Call `resources/read` with `uri: "homelab://nonexistent"`
- [ ] Response is an MCP error (not a 200 with empty data)
- [ ] Error code is `-32002` (resource not found)

---

## Section 4: Resource Notifications (Phase 10 — RES-07)

Verify the server emits `notifications/resources/list_changed` after discovery mutations. Only `discover_and_map` and `bulk_discover_and_map` are in the `MUTATING_TOOLS` set and trigger notifications.

### 4.1 Notification after ssh_discover (discover_and_map)

- [ ] Subscribe to `homelab://devices` via `resources/subscribe` with `uri: "homelab://devices"`
- [ ] Call `discover_and_map` with a valid `subnet` (e.g., `"192.168.1.0/24"`)
- [ ] After discovery completes successfully, the client receives a `notifications/resources/list_changed` notification
- [ ] Optional — check server logs: a "Sending resource notification" log line should appear when new devices were discovered
- [ ] Optional — if no new devices were discovered (subnet already fully known), no notification is sent; this is expected behavior

### 4.2 No notification after dry-run

- [ ] Call any dry-run-capable tool (e.g., `delete_proxmox_vm`) with `dry_run: true`
- [ ] Confirm no `notifications/resources/updated` or `notifications/resources/list_changed` notification is emitted to the client
- [ ] Optional — check server logs: there should be NO "Sending resource notification" line associated with the dry-run call

### 4.3 Notification after bulk_discover_and_map

- [ ] Call `bulk_discover_and_map` with a `subnets` list containing at least one reachable subnet
- [ ] Client receives `notifications/resources/list_changed` notification after completion
- [ ] Notification is sent once per successful discovery run that finds or updates devices

---

## Section 5: Drift Detection (Phase 11 — DRFT-01 through DRFT-05)

Verify drift scanning and baseline management work correctly against a live Proxmox node.

### 5.1 scan_infrastructure_drift — initial run (no baselines)

- [ ] Call `scan_infrastructure_drift` with a valid `node` parameter (e.g., `"pve"`)
  - Optional parameters: `vm_type` — one of `"qemu"`, `"lxc"`, `"all"` (default: `"all"`)
- [ ] Response is a structured dict (not an error string)
- [ ] Response contains `scan_timestamp` in ISO 8601 format
- [ ] Response contains `config_drift` list (may be empty on first run — no baselines yet)
- [ ] Response contains `state_drift` list (may be empty on first run)
- [ ] After first run, baselines are now stored in SQLite (`drift_baselines` table)

### 5.2 scan_infrastructure_drift — state drift detection

To test this, a VM must have a stored baseline from a previous scan (run 5.1 first):

- [ ] On Proxmox, manually stop a VM that was scanned in 5.1 and whose baseline shows it as `running` — do this outside of MCP (e.g., via Proxmox web UI or CLI)
- [ ] Call `scan_infrastructure_drift` for the same node
- [ ] The stopped VM appears in the `state_drift` list in the response
- [ ] Each state drift finding includes:
  - `drift_type` field (e.g., `"state_drift"` or `"vm_offline"`)
  - `expected` field (showing the previously known running state)
  - `actual` field (showing the current stopped state)
  - `scan_timestamp` field
- [ ] The finding is labeled as a point-in-time observation, not a confirmed permanent failure

### 5.3 scan_infrastructure_drift — config drift detection

To test this, a VM must have a stored baseline from a previous scan (run 5.1 first):

- [ ] On Proxmox, manually change a VM's CPU count or memory allocation outside of MCP (e.g., via Proxmox web UI or `qm set`)
- [ ] Call `scan_infrastructure_drift` for the same node
- [ ] The modified VM appears in the `config_drift` list in the response
- [ ] Each config drift finding includes:
  - `drift_type: "config_drift"`
  - `expected` field (showing the old CPU/memory values from the baseline)
  - `actual` field (showing the new values from live Proxmox)
  - `scan_timestamp` field

### 5.4 Baseline auto-update after MCP mutation

Verify that VMs created or cloned through MCP do not generate false drift findings:

- [ ] Note the current state: call `scan_infrastructure_drift` and confirm no existing drift for a known VM
- [ ] Create a new VM through MCP: call `create_proxmox_vm` or `clone_proxmox_vm` with valid parameters
- [ ] Wait for the MCP tool call to complete successfully
- [ ] Call `scan_infrastructure_drift` immediately after
- [ ] The newly created or cloned VM does NOT appear as config drift — baseline was written automatically after the MCP mutation
- [ ] If the new VM has the expected CPU/memory from the `create_proxmox_vm` call, confirm those values match in the scan result (no drift)

### 5.5 Drift baselines persist across restarts

- [ ] While the server is running and has accumulated baselines (from 5.1–5.4), note a VM's baseline values
- [ ] Stop the MCP server (Ctrl-C or kill the process)
- [ ] Restart: `uv run python run_server.py`
- [ ] Call `scan_infrastructure_drift` again for the same node
- [ ] Baselines are preserved — previously-known VMs with unchanged config do NOT reappear as fresh drift

---

## Section 6: Automated Test Suite (Regression Gate)

Run the automated suite to confirm no regressions were introduced.

- [ ] `uv run pytest tests/ -m "not integration" -v` — all unit tests pass (zero failures, zero errors)
- [ ] `uv run ruff check src/ tests/` — no linting errors reported
- [ ] `uv run mypy src/` — no new type errors (pre-existing deferred errors documented in MILESTONE-AUDIT.md are acceptable; any NEW errors require investigation)

---

## Section 7: HTTP Transport Auth (DEBT-02 Regression)

Only applicable when running the HTTP transport with `MCP_API_KEY` configured. Skip if running stdio transport only.

- [ ] Set `MCP_API_KEY=test-key` in environment, then start the HTTP transport
- [ ] Send a request to any MCP endpoint WITHOUT an `Authorization` header — expect `401` or `403`
- [ ] Send the same request WITH `Authorization: Bearer test-key` — expect a successful response
- [ ] Access the `/health` endpoint WITHOUT any auth header — expect `200 OK` (health endpoint is public)

---

## Sign-off

| Section | Result | Notes |
|---------|--------|-------|
| Section 1: Server Startup + Tool Discovery | | |
| Section 2: Dry-Run Mode (6 tools) | | |
| Section 3: MCP Resources Protocol | | |
| Section 4: Resource Notifications | | |
| Section 5: Drift Detection | | |
| Section 6: Automated Test Suite | | |
| Section 7: HTTP Auth (optional) | | |

**Verified by:** _______________
**Date:** _______________
**Server version / commit:** _______________

---

## v1.1 Requirement Traceability

| Requirement ID | Description | Verified In |
|---|---|---|
| DRY-01 | dry_run parameter on decommission_device | Section 2.1 |
| DRY-02 | dry_run parameter on remove_vm | Section 2.2 |
| DRY-03 | dry_run parameter on remove_server | Section 2.3 |
| DRY-04 | dry_run parameter on delete_proxmox_vm | Section 2.4 |
| DRY-05 | dry_run parameter on destroy_terraform_service | Section 2.5 |
| DRY-06 | dry_run parameter on rollback_infrastructure_changes | Section 2.6 |
| DRY-07 | Live execution not blocked by dry_run logic | Section 2.7 |
| RES-01 | resources/list exposes homelab:// URIs | Section 3.1 |
| RES-02 | homelab://vms returns live Proxmox data | Section 3.2 |
| RES-03 | homelab://devices returns DB device records | Section 3.3 |
| RES-04 | homelab://services/{name} returns service status | Section 3.4 |
| RES-05 | Unknown URI returns -32002 error | Section 3.5 |
| RES-06 | All resource responses include scanned_at timestamp | Sections 3.2–3.4 |
| RES-07 | Notifications emitted after discovery mutations | Section 4.1, 4.3 |
| DRFT-01 | scan_infrastructure_drift tool exists and returns structured report | Section 5.1 |
| DRFT-02 | State drift detected (VM stopped outside MCP) | Section 5.2 |
| DRFT-03 | Config drift detected (CPU/memory changed outside MCP) | Section 5.3 |
| DRFT-04 | Baseline auto-updated after MCP mutation | Section 5.4 |
| DRFT-05 | Baselines persist in SQLite across restarts | Section 5.5 |
| DEBT-01 | Tool annotations (readOnlyHint, destructiveHint) exposed | Section 1 |
| DEBT-02 | HTTP transport API key auth | Section 7 |
| DEBT-03 | Dry-run calls do not emit resource notifications | Section 4.2 |
