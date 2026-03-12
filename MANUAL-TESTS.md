# Homelab MCP Server — Manual Verification Checklist (v1.1)

All tests are run by typing the quoted prompt into Claude Desktop chat with the MCP server connected.
A live Proxmox node is required for Sections 2, 3, 4, and 5. Section 1 and Section 6 work without Proxmox.

---

## Prerequisites

- [ ] Server running: `uv run python run_server.py` — no traceback on startup
- [ ] Claude Desktop connected to the server (check the hammer icon — tools should be listed)
- [ ] Proxmox credentials set in environment (`PROXMOX_HOST`, `PROXMOX_USER`, `PROXMOX_PASSWORD` or token equivalent)
- [ ] At least one VM or LXC container exists on your Proxmox node
- [ ] You know your Proxmox node name (e.g., `pve`) and at least one VMID

---

## Section 1: Server Startup and Tool Discovery

### 1.1 Tools are available

> **Prompt:** `List all the homelab tools you have available`

**Pass if:** Claude lists tools and the total count is **50**. You should see `scan_infrastructure_drift` in the list.

### 1.2 Destructive tools have dry-run support

> **Prompt:** `Do any of your tools support a dry_run parameter? List which ones do.`

**Pass if:** Claude confirms `dry_run` is available on all six of these tools:
- `decommission_device`
- `remove_vm`
- `remove_server`
- `delete_proxmox_vm`
- `destroy_terraform_service`
- `rollback_infrastructure_changes`

### 1.3 MCP Resources are advertised

> **Prompt:** `What homelab resources can you read? List the available resource URIs.`

**Pass if:** Claude lists at minimum `homelab://vms`, `homelab://devices`, and `homelab://services`.

---

## Section 2: Dry-Run Mode

Each destructive tool must preview its action without making any real changes when `dry_run` is requested.

**Expected in every dry-run response:** `mode: dry_run`, a list of what would be affected, a risk level, and whether it's reversible.

### 2.1 decommission_device

> **Prompt:** `Run decommission_device in dry-run mode on the device with hostname [YOUR_DEVICE_HOSTNAME]`

**Pass if:** Response describes what would be removed, says `dry_run` mode, and the device still shows up when you ask Claude to list registered devices afterward.

### 2.2 remove_vm

> **Prompt:** `Do a dry run of remove_vm for the VM named [YOUR_VM_NAME]`

**Pass if:** Response shows a preview of what would happen. The VM is still present when you check.

### 2.3 remove_server

> **Prompt:** `Dry run remove_server for [YOUR_SERVER_HOSTNAME]`

**Pass if:** Response shows a preview. Server record still exists — confirm by asking `list all registered servers`.

### 2.4 delete_proxmox_vm

> **Prompt:** `Dry run delete_proxmox_vm for vmid [YOUR_VMID] on node pve`

**Pass if:** Response shows what would be deleted. VM still exists — ask `get_proxmox_vm_status` for the same VMID to confirm.

### 2.5 destroy_terraform_service

> **Prompt:** `Dry run destroy_terraform_service for service named [YOUR_SERVICE_NAME]`

**Pass if:** Response shows a destroy preview. No actual Terraform process runs.

### 2.6 rollback_infrastructure_changes

> **Prompt:** `Do a dry run of rollback_infrastructure_changes`

**Pass if:** Response describes what a rollback would do. No actual changes are made.

### 2.7 Live execution still works (regression check)

> **Prompt:** `Run remove_server (NOT dry run) for a test/expendable server hostname [YOUR_TEST_HOSTNAME]`

**Pass if:** The response does NOT say `dry_run` mode — it actually removes the record. This confirms dry-run logic doesn't intercept live calls.

---

## Section 3: MCP Resources (Live Data)

### 3.1 VM resource

> **Prompt:** `Read the homelab://vms resource and show me the raw data`

**Pass if:** Response contains a `vms` array with your Proxmox VMs, a `total` count, and a `scanned_at` timestamp.

### 3.2 Devices resource

> **Prompt:** `Read the homelab://devices resource`

**Pass if:** Response contains a `devices` array (may be empty if no discovery has run yet) and a `scanned_at` timestamp. Each device should have `last_seen` and `last_discovery_data` fields.

### 3.3 Service resource

> **Prompt:** `Read the homelab://services/nginx resource`

**Pass if:** Response returns service status for nginx (running/stopped/unknown) with a `scanned_at` timestamp. If no `MCP_DEFAULT_SERVICE_HOST` is set, a `status: unconfigured` response is also a pass.

### 3.4 Unknown resource returns an error

> **Prompt:** `Read the resource homelab://nonexistent`

**Pass if:** Claude reports an error (not empty data). The error should indicate the resource was not found.

---

## Section 4: Resource Notifications

These verify the server notifies the client when discovery changes the device list.

### 4.1 Notification after discover_and_map

> **Prompt:** `Run discover_and_map on subnet [YOUR_SUBNET e.g. 192.168.1.0/24]`

**Pass if:** Discovery completes and Claude's response mentions devices found or updated. In Claude Desktop's developer tools (Help → Developer Tools → MCP tab) you can confirm a `notifications/resources/list_changed` event was received.

### 4.2 No notification after dry-run

> **Prompt:** `Dry run delete_proxmox_vm for vmid [YOUR_VMID] on node pve`

**Pass if:** No resource update notification appears in the MCP developer tools tab. Dry runs must not trigger notifications.

### 4.3 Notification after bulk_discover_and_map

> **Prompt:** `Run bulk_discover_and_map on subnets ["192.168.1.0/24"]`

**Pass if:** Discovery completes. A `notifications/resources/list_changed` notification is visible in the MCP dev tools if any devices were found or updated.

---

## Section 5: Drift Detection

Requires baselines from a previous scan. Run 5.1 first, then 5.2–5.5.

### 5.1 Initial scan (no baselines yet)

> **Prompt:** `Scan infrastructure drift on node pve`

**Pass if:** Response is a structured report with `scan_timestamp`, `config_drift` list, and `state_drift` list. Lists may be empty on the first run — that's expected. Baselines are now stored.

### 5.2 State drift detection

First, stop a VM via the Proxmox web UI (outside of MCP). Then:

> **Prompt:** `Scan infrastructure drift on node pve again`

**Pass if:** The stopped VM appears in the `state_drift` section with `expected: running` and `actual: stopped`.

### 5.3 Config drift detection

First, change a VM's CPU count or memory in Proxmox (outside of MCP). Then:

> **Prompt:** `Scan infrastructure drift on node pve`

**Pass if:** The modified VM appears in `config_drift` with the old values under `expected` and new values under `actual`.

### 5.4 Baseline auto-update after MCP mutation

> **Prompt:** `Create a new VM on node pve with [your parameters], then immediately scan infrastructure drift`

**Pass if:** The newly created VM does NOT appear as drift — its baseline was written automatically at creation time.

### 5.5 Baselines persist across restarts

1. Stop the server (`Ctrl-C`)
2. Restart: `uv run python run_server.py`
3. Reconnect Claude Desktop

> **Prompt:** `Scan infrastructure drift on node pve`

**Pass if:** VMs with unchanged config do NOT appear as fresh drift — baselines survived the restart.

---

## Section 6: Automated Test Suite (Regression Gate)

Run locally — no Proxmox required.

- [ ] `uv run pytest tests/ -m "not integration" -v` — all unit tests pass (zero failures)
- [ ] `uv run ruff check src/ tests/` — no linting errors
- [ ] `uv run mypy src/` — no new type errors

---

## Section 7: HTTP Transport Auth (optional — skip if using stdio only)

Requires restarting the server with `MCP_API_KEY=test-key` and HTTP transport enabled.

- [ ] Request without `Authorization` header → expect `401` or `403`
- [ ] Request with `Authorization: Bearer test-key` → expect success
- [ ] `GET /health` without auth → expect `200 OK`

---

## Sign-off

| Section | Result | Notes |
|---------|--------|-------|
| Section 1: Tool Discovery | | |
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

## v1.1 Requirement Traceability

| Requirement ID | Description | Verified In |
|---|---|---|
| DRY-01 | dry_run on decommission_device | Section 2.1 |
| DRY-02 | dry_run on remove_vm | Section 2.2 |
| DRY-03 | dry_run on remove_server | Section 2.3 |
| DRY-04 | dry_run on delete_proxmox_vm | Section 2.4 |
| DRY-05 | dry_run on destroy_terraform_service | Section 2.5 |
| DRY-06 | dry_run on rollback_infrastructure_changes | Section 2.6 |
| DRY-07 | Live execution not blocked by dry_run logic | Section 2.7 |
| RES-01 | resources/list exposes homelab:// URIs | Section 1.3 |
| RES-02 | homelab://vms returns live Proxmox data | Section 3.1 |
| RES-03 | homelab://devices returns DB device records | Section 3.2 |
| RES-04 | homelab://services/{name} returns service status | Section 3.3 |
| RES-05 | Unknown URI returns error | Section 3.4 |
| RES-06 | All resource responses include scanned_at timestamp | Sections 3.1–3.3 |
| RES-07 | Notifications emitted after discovery mutations | Sections 4.1, 4.3 |
| DRFT-01 | scan_infrastructure_drift returns structured report | Section 5.1 |
| DRFT-02 | State drift detected | Section 5.2 |
| DRFT-03 | Config drift detected | Section 5.3 |
| DRFT-04 | Baseline auto-updated after MCP mutation | Section 5.4 |
| DRFT-05 | Baselines persist across restarts | Section 5.5 |
| DEBT-01 | Tool annotations exposed | Section 1.2 |
| DEBT-02 | HTTP transport API key auth | Section 7 |
| DEBT-03 | Dry-run calls do not emit notifications | Section 4.2 |
