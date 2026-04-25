# v1.7 Requirements: Drift Architectural Fix

**Milestone goal:** Make the sitemap the single source of truth for drift detection. Drop the parallel `drift_baselines` table; wire `scan_infrastructure_drift` to iterate sitemap rows; detect three drift cases (unknown / missing / changed); capture richer fingerprints in sitemap so OS-level changes (kernel updates, capability regressions) surface as meaningful drift. Polish two adjacent Proxmox VM-lifecycle bugs caught during the same retest session.

**Surfaced from:** 2026-04-25 retest session of v1.6 codebase. 10 distinct bugs (A-J) in the drift detection family; 9 trace to one architectural gap (Bug J).

**Architectural decision:** Sitemap is the baseline. Drift = `current_probe(host) != sitemap_row(host)`. No separate baseline storage. This dissolves Bug J at the root rather than integrating two data layers.

---

## Active Requirements

### Drift Module ↔ Sitemap Unification (DRFT-*)

Continues v1.1 numbering (DRFT-01..10 shipped in v1.1 Phase 11 / v1.2 Phase 13).

- [ ] **DRFT-11**: `scan_infrastructure_drift` iterates sitemap rows as the source of truth — no parallel baseline table read on the scan path
- [ ] **DRFT-12**: `scan_infrastructure_drift` resolves Proxmox credentials via `resolve_proxmox_credentials` — no `PROXMOX_HOST` env-var coupling on the success path
- [ ] **DRFT-13**: `scan_infrastructure_drift` returns consistent shape across all filter scopes (no filter, `node=*`, `vm_type=qemu`, `vm_type=lxc`) — empty result on no-match, never a scope error (closes Bugs A, E)
- [ ] **DRFT-14**: `scan_infrastructure_drift` output distinguishes four buckets — probed-OK, unreachable, unknown (drift case 1), changed (drift case 3) — so coverage is transparent (closes Bug D)
- [ ] **DRFT-15**: Drift family error messages point to existing sitemap tools (`discover_and_map`, `get_network_sitemap`, `purge_failed_discoveries`, `decommission_device`), never `PROXMOX_HOST` env var (closes Bug B)
- [ ] **DRFT-16**: Bug C resolved by architectural unification — no new `register_drift_baseline` / `list_drift_baselines` / `delete_drift_baseline` MCP tools created. Drift docs and error messages reference existing sitemap CRUD tools as the baseline lifecycle.
- [ ] **DRFT-17**: `scan_infrastructure_drift` detects **unknown infrastructure** — VMs/LXC present on a Proxmox hypervisor but absent from sitemap (drift case 1: manually-created VM)
- [ ] **DRFT-18**: `scan_infrastructure_drift` detects **missing infrastructure** — sitemap rows that no longer respond to live probe (drift case 2: offline / removed host or VM)
- [ ] **DRFT-19**: `scan_infrastructure_drift` detects **changed infrastructure** — sitemap fields differ from current probe values (drift case 3: kernel update, package change, hardware capability change)
- [ ] **DRFT-20**: Sitemap schema captures the fields necessary for meaningful drift detection — kernel version, package fingerprint, and capability probes (e.g., GPU passthrough state, ML library availability such as Vulkan support for llama.cpp). Specific fields finalized during phase planning; principle is that background OS updates that change behavior must surface as drift.
- [ ] **DRFT-21**: Drop the parallel `drift_baselines` SQLite table on both adapters (SQLite + Postgres). No auto-migration — homelab single-user scope, mirrors v1.6 CRED-04 keyring migration. Migration step removes the table cleanly; pre-existing baseline rows are not reconciled.

### Polish (POL-*)

- [ ] **POL-01**: `get_proxmox_vm_status` returns a clean structured "VM not found" error on nonexistent VMID — not raw HTTP 500 with internal API URL leaked in the message (closes Bug I)
- [ ] **POL-02**: `create_proxmox_vm` `host` parameter schema accurately reflects whether it is optional or required given cluster-scope keyring resolution. Schema and runtime behavior must agree. (closes Bug G — schema accuracy half)
- [ ] **POL-03**: `create_proxmox_vm` error messages on missing credentials point to `credentials add --type proxmox` / cluster scope option, never `PROXMOX_HOST` env var (closes Bug G — error guidance half)

---

## Coverage Map

| Bug from retest | Resolved by |
|---|---|
| Bug A (scope inconsistency on missing baseline) | DRFT-13 |
| Bug B (env-var-leak error message in drift) | DRFT-15 |
| Bug C (no register/list/delete drift baseline tools) | DRFT-16 (architectural dissolve — no new tools needed) |
| Bug D (no coverage transparency) | DRFT-14 |
| Bug E (vm_type=lxc errors on missing baseline) | DRFT-13 |
| Bug G (host param schema lie + env-var error) | POL-02 + POL-03 |
| Bug I (HTTP 500 leak on nonexistent VMID) | POL-01 |
| Bug J (parallel data layer not integrated with sitemap) | DRFT-11 + DRFT-21 (root cause: parallel layer dropped) |

| User-described drift case | Resolved by |
|---|---|
| Manually-created VM not in sitemap | DRFT-17 |
| Server offline / unresponsive | DRFT-18 |
| Kernel update breaks Vulkan / llama.cpp | DRFT-19 + DRFT-20 |

| Bug from retest | Deferred to |
|---|---|
| Bug F (delete_proxmox_vm doesn't clean up baseline) | v1.7.1 LIFE-02 |
| Bug H (create_proxmox_vm doesn't populate baseline) | v1.7.1 LIFE-01 |

Note: Under the v1.7 architectural decision (sitemap = single source of truth), F and H reframe as "delete_proxmox_vm doesn't update sitemap" and "create_proxmox_vm doesn't update sitemap." That work belongs in v1.7.1's lifecycle-hooks scope.

---

## Future Requirements (deferred to upcoming milestones)

### v1.7.1 Infrastructure Lifecycle Hooks (~12 reqs)

Every infrastructure-mutating tool family updates sitemap on create/destroy. Defined fully when v1.7.1 cycle begins; sketched here to lock scope:

- LIFE-01: `create_proxmox_vm` populates sitemap row on success (Bug H)
- LIFE-02: `delete_proxmox_vm` removes sitemap row on success (Bug F)
- LIFE-03: Proxmox LXC create populates sitemap row on success
- LIFE-04: Proxmox LXC delete removes sitemap row on success
- LIFE-05: Terraform service install populates sitemap row on apply
- LIFE-06: Terraform service uninstall removes sitemap row on destroy
- LIFE-07: Ansible service install populates sitemap row on success
- LIFE-08: Ansible service uninstall removes sitemap row on success
- LIFE-09: Proxmox community-script execution emits a completion signal (callback wrap or poll-able status) — interactive browser flow gives no completion signal today
- LIFE-10: Community-script onboarding workflow prompt — guides user through `credentials add` + `discover_and_map` after script completion (delegate-via-discovery pattern, not direct registration)
- LIFE-11: Docker-adjacent tools register/clean up sitemap on container create/destroy (audit during phase planning to identify which tools)
- LIFE-12: AST meta-test guard — every infrastructure-mutating tool path either updates sitemap directly or delegates via `discover_and_map`-style discovery (lint-style regression guard, follows v1.6 33.1/35 pattern)

### v1.7.2 Role-Aware Drift (~6 reqs)

Promotes backlog 999.4 (sitemap tags/categories). Drift checks role-scoped via tags:

- TAGS-01: Sitemap rows have a multi-value `tags` field for role/category labels (e.g., `proxmox-host`, `truenas`, `gateway`, `compute`, `lxc`, `vm`)
- TAGS-02: `get_network_sitemap` accepts a `tags` filter for role-scoped queries
- TAGS-03: `discover_and_map` infers initial tags from probe data where possible (Proxmox via `/etc/pve`, TrueNAS via `/etc/version`, gateway via routing-table presence); tags editable explicitly
- ROLE-01: Drift checks are role-scoped via sitemap tags — each check declares which tag(s) it applies to; checks only run against matching hosts
- ROLE-02: Gateway role drift profile — tracks routing table + NAT/firewall rules; flags rule additions/removals/changes
- ROLE-03: NAS / service-host drift profile — sitemap stores per-host expected-running services list; drift flags any expected service that isn't running, and any unexpected service that is (TrueNAS smb-stops-killing-Plex case)

---

## Out of Scope (this milestone)

- **Lifecycle hooks across infrastructure-mutating tools** — deferred to v1.7.1
- **Sitemap tags/categories + role-aware drift** — deferred to v1.7.2 (promotes 999.4)
- **`probe_pending_updates` advisory family** — sibling concept to drift, not divergence-from-sitemap. Captured as 999.9 backlog. Pending OS / Nextcloud / app-update advisories normalize across distros and self-hosted apps; they describe a property OF the live system, not a state mismatch with sitemap.
- **Auto-update sitemap when drift detected** — drift reports differences; user accepts changes by re-running `discover_and_map`. Preserves the "kernel update breaks Vulkan" use case where you want an alert, not silent acceptance.
- **Reconciling pre-existing rows in `drift_baselines` table on upgrade** — DRFT-21 drops the table without auto-migration; users with active baseline rows lose them and re-establish via discovery.
- **Cross-cutting `mcp_admin` cleanup** in non-resolver code paths — v1.8 candidate
- **SSH-04 per-call timeout to handshake** — v1.8 candidate
- **QUAL-01 Proxmox iso/cdrom mutual exclusivity** — v1.8 candidate
- **HTTP-01 truthy variants for HTTP-mode flag** — v1.8 candidate
- **ERR-02 `resolve_ssh_credentials` error wrapping** — v1.8 candidate
- **Renaming docker-adjacent tools to `docker_*`** — captured as 999.8 backlog (naming-only refactor)
- **Auto-detect drift via background polling** — already declared out of scope at project level
- **Per-device drift resources** (`homelab://drift/device/{id}`) — already declared out of scope at project level
- **Retroactive VERIFICATION/VALIDATION.md gap closure** from v1.5/v1.6 close — non-blocking tech_debt per CLAUDE.md regression-test scope policy

---

## Traceability

(filled by gsd-roadmapper when phases are mapped to requirements)

| REQ-ID | Phase | Status |
|--------|-------|--------|
| DRFT-11 | TBD | pending |
| DRFT-12 | TBD | pending |
| DRFT-13 | TBD | pending |
| DRFT-14 | TBD | pending |
| DRFT-15 | TBD | pending |
| DRFT-16 | TBD | pending |
| DRFT-17 | TBD | pending |
| DRFT-18 | TBD | pending |
| DRFT-19 | TBD | pending |
| DRFT-20 | TBD | pending |
| DRFT-21 | TBD | pending |
| POL-01 | TBD | pending |
| POL-02 | TBD | pending |
| POL-03 | TBD | pending |

---

*Last updated: 2026-04-25 — v1.7 milestone scope locked (14 reqs). v1.7.1 + v1.7.2 sketched as upcoming.*
