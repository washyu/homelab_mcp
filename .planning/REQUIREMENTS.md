# Requirements: Homelab MCP Server

**Defined:** 2026-03-11
**Core Value:** Every tool in the server actually works — a Proxmox homelabber can install this, connect it to any MCP client, and reliably manage their infrastructure through AI.

## v1.1 Requirements

Requirements for v1.1 Safety & Observability milestone. Each maps to roadmap phases.

### Tech Debt

- [x] **DEBT-01**: ResourceManager.proxmox_session is consumed by handler chain when Proxmox operations are invoked
- [x] **DEBT-02**: API key authentication is enforced on HTTP transport endpoints
- [x] **DEBT-03**: vm_providers error paths return structured error dicts instead of raw str(e)

### Dry-Run

- [x] **DRY-01**: User can pass `dry_run: true` to `decommission_device` and see what would be affected
- [x] **DRY-02**: User can pass `dry_run: true` to `remove_vm` and see what would be affected
- [x] **DRY-03**: User can pass `dry_run: true` to `remove_server` and see what would be affected
- [x] **DRY-04**: User can pass `dry_run: true` to `delete_proxmox_vm` and see what would be affected
- [x] **DRY-05**: User can pass `dry_run: true` to `destroy_terraform_service` and see what would be affected
- [x] **DRY-06**: User can pass `dry_run: true` to `rollback_infrastructure_changes` and see what would be affected
- [x] **DRY-07**: All dry-run responses return structured JSON with `mode`, `would_affect`, `risk_level`, and `reversible` fields

### Drift Detection

- [ ] **DRFT-01**: User can run `scan_infrastructure_drift` to get a report of all detected drift
- [ ] **DRFT-02**: State drift detects when VMs/services are offline that should be running (SSH + Proxmox status)
- [ ] **DRFT-03**: Config drift detects when VM/device config changed outside MCP (CPU, memory, network)
- [ ] **DRFT-04**: Drift baselines are stored in SQLite as full config dicts for field-level diffing
- [ ] **DRFT-05**: Drift baselines update after successful MCP mutations to avoid false positives

### MCP Resources

- [x] **RES-01**: Server declares `resources` capability and responds to `resources/list`
- [ ] **RES-02**: `homelab://vms` resource returns live VM list from Proxmox/Docker/LXD
- [ ] **RES-03**: `homelab://devices` resource returns device inventory with last discovery data
- [ ] **RES-04**: `homelab://services/{name}` resource returns individual service status
- [x] **RES-05**: All resources return `application/json` content via `resources/read`
- [x] **RES-06**: Server returns error code `-32002` for unknown resource URIs
- [ ] **RES-07**: Server emits `notifications/resources/list_changed` after `ssh_discover` adds new devices

## Future Requirements

Deferred to future release. Tracked but not in current roadmap.

### Dry-Run Enhancements

- **DRY-08**: Risk classification derives risk_level and reversible from existing tool annotations
- **DRY-09**: Dry-run preview stored as `homelab://dry-run/{device_id}` MCP Resource

### Drift Detection Enhancements

- **DRFT-06**: Drift report includes root-cause hints (e.g., "possible cause: Proxmox live resize")
- **DRFT-07**: Last drift scan report exposed as `homelab://drift/latest` MCP Resource
- **DRFT-08**: Background auto-polling drift detection with false-positive suppression

### MCP Resources Enhancements

- **RES-08**: Resource subscriptions via `resources/subscribe` with notification dispatch
- **RES-09**: `notifications/resources/updated` pushed after drift scans and mutations

### Distribution

- **DIST-01**: PyPI package distribution with `pip install homelab-mcp`

### MCP Prompts

- **PRMT-01**: Pre-built MCP Prompts for common workflows (device onboarding, service deploy, etc.)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Full workflow simulation (dry-run beyond destructive ops) | Requires mock state and counterfactual execution — massive complexity for marginal gain |
| Auto-polling drift detection (background loop) | Creates noisy notifications for transient states; explicitly deferred |
| Automated remediation after drift | Unattended changes to production infra defeats the safety milestone purpose |
| Resource versioning and history | Unbounded resource list growth; use existing `get_device_changes` tool |
| `dry_run` on read-only tools | Read-only tools don't change state; adds no value |
| Resource templates for every tool parameter | Large surface area; clients don't navigate templates well |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DEBT-01 | Phase 6 | Complete |
| DEBT-02 | Phase 6 | Complete |
| DEBT-03 | Phase 6 | Complete |
| DRY-01 | Phase 8 | Complete |
| DRY-02 | Phase 8 | Complete |
| DRY-03 | Phase 8 | Complete |
| DRY-04 | Phase 8 | Complete |
| DRY-05 | Phase 8 | Complete |
| DRY-06 | Phase 8 | Complete |
| DRY-07 | Phase 8 | Complete |
| DRFT-01 | Phase 11 | Pending |
| DRFT-02 | Phase 11 | Pending |
| DRFT-03 | Phase 11 | Pending |
| DRFT-04 | Phase 11 | Pending |
| DRFT-05 | Phase 11 | Pending |
| RES-01 | Phase 7 | Complete |
| RES-02 | Phase 9 | Pending |
| RES-03 | Phase 9 | Pending |
| RES-04 | Phase 9 | Pending |
| RES-05 | Phase 7 | Complete |
| RES-06 | Phase 7 | Complete |
| RES-07 | Phase 10 | Pending |

**Coverage:**
- v1.1 requirements: 22 total
- Mapped to phases: 22
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-11*
*Last updated: 2026-03-12 after phase 08 execution — DRY-01 through DRY-07 complete*
