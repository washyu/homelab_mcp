# Roadmap: Homelab MCP Server

## Milestones

- ✅ **v1.0 MVP** — Phases 1-5 (shipped 2026-03-11)
- 🚧 **v1.1 Safety & Observability** — Phases 6-11 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-5) — SHIPPED 2026-03-11</summary>

- [x] Phase 1: Architecture Foundation (3/3 plans) — completed 2026-03-08
- [x] Phase 2: Security Hardening (5/5 plans) — completed 2026-03-09
- [x] Phase 3: Functional Completeness (3/3 plans) — completed 2026-03-09
- [x] Phase 4: MCP Protocol Compliance (2/2 plans) — completed 2026-03-11
- [x] Phase 5: Documentation (2/2 plans) — completed 2026-03-11

</details>

### 🚧 v1.1 Safety & Observability (In Progress)

**Milestone Goal:** Make the server trustworthy for real use — preview before breaking things, detect when reality drifts from expectations, expose live infra state via MCP Resources, and clean up v1.0 tech debt.

- [ ] **Phase 6: Tech Debt Cleanup** - Fix three known bugs that block every subsequent feature
- [x] **Phase 7: MCP Resources Plumbing** - Wire the Resources protocol skeleton (list, read, subscribe, error handling) with stub data (completed 2026-03-11)
- [ ] **Phase 8: Dry-Run Mode** - Add `dry_run: true` to all six destructive tools with structured preview output
- [ ] **Phase 9: MCP Resources Live Data** - Connect ResourceFetcher to real Proxmox, Docker, SQLite data sources
- [ ] **Phase 10: Resource Notifications** - Emit `listChanged` and `resourceUpdated` notifications after mutations and discoveries
- [ ] **Phase 11: Drift Detection** - Build on-demand infrastructure drift scanner with config and state drift reporting

## Phase Details

### Phase 6: Tech Debt Cleanup
**Goal**: Three v1.0 bugs are fixed so Proxmox session management is correct, HTTP authentication is enforced, and VM provider errors are structured — unblocking all downstream phases.
**Depends on**: Phase 5 (v1.0 complete)
**Requirements**: DEBT-01, DEBT-02, DEBT-03
**Success Criteria** (what must be TRUE):
  1. Proxmox tool calls route through the shared `ResourceManager.proxmox_session` aiohttp ClientSession — zero additional sessions opened per request
  2. HTTP transport endpoints reject requests without a valid API key (return 401/403), not silently accept them
  3. All VM provider error paths return structured dicts with `error`, `error_type`, and `detail` fields instead of raw `str(e)` strings
**Plans**: 3 plans
Plans:
- [x] 06-01-PLAN.md — Thread shared Proxmox session through handler chain
- [x] 06-02-PLAN.md — Wire APIKeyAuth into HTTP app
- [x] 06-03-PLAN.md — Structured error dicts in VM providers

### Phase 7: MCP Resources Plumbing
**Goal**: The MCP Resources protocol is fully wired — clients can list resources, read stubs, subscribe, and receive correct error codes — validating SDK integration before real data is connected.
**Depends on**: Phase 6
**Requirements**: RES-01, RES-05, RES-06
**Success Criteria** (what must be TRUE):
  1. Server declares the `resources` capability and `resources/list` returns all defined `homelab://` URIs with correct metadata
  2. `resources/read` on any declared URI returns `application/json` content (stub data acceptable at this phase)
  3. `resources/read` on an unknown URI returns MCP error code `-32002`
  4. `resources/subscribe` and `resources/unsubscribe` complete without error and update the server-side subscription tracker
**Plans**: 1 plan
Plans:
- [ ] 07-01-PLAN.md — Resource handlers (list, read, subscribe) with TDD tests

### Phase 8: Dry-Run Mode
**Goal**: All six destructive tools accept `dry_run: true` and return structured previews describing what would be affected — users can inspect before committing to irreversible operations.
**Depends on**: Phase 6
**Requirements**: DRY-01, DRY-02, DRY-03, DRY-04, DRY-05, DRY-06, DRY-07
**Success Criteria** (what must be TRUE):
  1. Passing `dry_run: true` to `decommission_device`, `remove_vm`, `remove_server`, `delete_proxmox_vm`, `destroy_terraform_service`, and `rollback_infrastructure_changes` returns a preview without executing any mutation
  2. Every dry-run response includes `mode: "dry_run"`, `would_affect` (list of affected resources), `risk_level` (`high`/`medium`/`low`), and `reversible` (`true`/`false`) fields
  3. Calling the same tool without `dry_run: true` (or with `dry_run: false`) still executes the real operation unchanged
  4. Tool schemas in `tools.py` expose `dry_run` as an optional boolean parameter for all six tools
**Plans**: 4 plans
Plans:
- [ ] 08-01-PLAN.md — dry_run.py contract builder + TDD test scaffold (RED state)
- [ ] 08-02-PLAN.md — Dry-run for decommission_device + rollback_infrastructure_changes
- [ ] 08-03-PLAN.md — Dry-run for remove_vm + remove_server
- [ ] 08-04-PLAN.md — Dry-run for delete_proxmox_vm + destroy_terraform_service

### Phase 9: MCP Resources Live Data
**Goal**: `resources/read` on every declared URI returns live data — VMs from Proxmox/Docker/LXD, devices from SQLite, services from SSH status — with a `scanned_at` timestamp in every response.
**Depends on**: Phase 7
**Requirements**: RES-02, RES-03, RES-04
**Success Criteria** (what must be TRUE):
  1. `homelab://vms` returns a live VM list queried from Proxmox API, Docker, and LXD providers — not placeholder data
  2. `homelab://devices` returns the current device inventory from SQLite with `last_seen` and `last_discovery_data` fields
  3. `homelab://services/{name}` returns the current status of the named service, including whether it is running
  4. Every resource JSON response includes a `scanned_at` ISO timestamp indicating when the data was fetched
**Plans**: 2 plans
Plans:
- [ ] 09-01-PLAN.md — resource_readers.py module with live data fetchers (TDD)
- [ ] 09-02-PLAN.md — Wire live readers into handle_read_resource in server.py

### Phase 10: Resource Notifications
**Goal**: Subscribed clients receive `notifications/resources/list_changed` when new devices are discovered and `notifications/resources/updated` after any successful mutating tool call — keeping client caches coherent.
**Depends on**: Phase 9
**Requirements**: RES-07
**Success Criteria** (what must be TRUE):
  1. After `ssh_discover` completes and adds new devices to the database, the server emits `notifications/resources/list_changed` to the connected client
  2. Subscribed clients do not receive notifications for dry-run executions (only real mutations trigger notifications)
**Plans**: 1 plan
Plans:
- [ ] 10-01-PLAN.md — MUTATING_TOOLS constant + notification dispatch in handle_call_tool (TDD)

### Phase 11: Drift Detection
**Goal**: Users can run `scan_infrastructure_drift` to get a structured report of config drift (CPU/memory/network changed outside MCP) and state drift (VMs/services offline that should be running), with baselines that stay current after every MCP mutation.
**Depends on**: Phase 10
**Requirements**: DRFT-01, DRFT-02, DRFT-03, DRFT-04, DRFT-05
**Success Criteria** (what must be TRUE):
  1. `scan_infrastructure_drift` returns a structured report listing each drifted resource with `drift_type` (`config` or `state`), `expected`, `actual`, and `scan_timestamp` fields
  2. State drift correctly identifies VMs and services that are offline but should be running, using both Proxmox API status and SSH probe
  3. Config drift correctly identifies VM resources (CPU, memory, network) that changed outside MCP by comparing live Proxmox VM config against stored baselines
  4. Drift baselines stored in SQLite update automatically after every successful MCP mutation — intentional changes do not appear as drift on the next scan
  5. State drift findings are labeled as point-in-time observations (not "confirmed drift") to prevent false positives from transient VM reboot states
**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Architecture Foundation | v1.0 | 3/3 | Complete | 2026-03-08 |
| 2. Security Hardening | v1.0 | 5/5 | Complete | 2026-03-09 |
| 3. Functional Completeness | v1.0 | 3/3 | Complete | 2026-03-09 |
| 4. MCP Protocol Compliance | v1.0 | 2/2 | Complete | 2026-03-11 |
| 5. Documentation | v1.0 | 2/2 | Complete | 2026-03-11 |
| 6. Tech Debt Cleanup | 2/3 | In Progress|  | - |
| 7. MCP Resources Plumbing | 1/1 | Complete   | 2026-03-11 | - |
| 8. Dry-Run Mode | 2/4 | In Progress|  | - |
| 9. MCP Resources Live Data | v1.1 | 0/2 | Not started | - |
| 10. Resource Notifications | v1.1 | 0/1 | Not started | - |
| 11. Drift Detection | v1.1 | 0/TBD | Not started | - |
