# Roadmap: Homelab MCP Server

## Milestones

- ✅ **v1.0 MVP** — Phases 1-5 (shipped 2026-03-11)
- ✅ **v1.1 Safety & Observability** — Phases 6-11 (shipped 2026-03-12)
- ✅ **v1.2 Protocol Completeness** — Phases 12-16 (shipped 2026-03-13)
- ✅ **v1.3 Credentials & Release Automation** — Phases 17-20 (shipped 2026-03-15)
- ✅ **v1.4.1 Security Patch** — Phase 30 (shipped 2026-04-01)
- ✅ **v1.5 Critical Bug Fixes** — Phases 31-32 (shipped 2026-04-20)
- ✅ **v1.6 Credential Architecture Cleanup** — Phases 33, 33.1, 34, 35 (shipped 2026-04-24)
- 🚧 **v1.7 Drift Architectural Fix** — Phases 36-40 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-5) — SHIPPED 2026-03-11</summary>

- [x] Phase 1: Architecture Foundation (3/3 plans) — completed 2026-03-08
- [x] Phase 2: Security Hardening (5/5 plans) — completed 2026-03-09
- [x] Phase 3: Functional Completeness (3/3 plans) — completed 2026-03-09
- [x] Phase 4: MCP Protocol Compliance (2/2 plans) — completed 2026-03-11
- [x] Phase 5: Documentation (2/2 plans) — completed 2026-03-11

Full details: `.planning/milestones/v1.0-ROADMAP.md`

</details>

<details>
<summary>✅ v1.1 Safety & Observability (Phases 6-11) — SHIPPED 2026-03-12</summary>

- [x] Phase 6: Tech Debt Cleanup (3/3 plans) — completed 2026-03-11
- [x] Phase 7: MCP Resources Plumbing (1/1 plan) — completed 2026-03-11
- [x] Phase 8: Dry-Run Mode (4/4 plans) — completed 2026-03-12
- [x] Phase 9: MCP Resources Live Data (2/2 plans) — completed 2026-03-12
- [x] Phase 10: Resource Notifications (1/1 plan) — completed 2026-03-12
- [x] Phase 11: Drift Detection (5/5 plans) — completed 2026-03-12

Full details: `.planning/milestones/v1.1-ROADMAP.md`

</details>

<details>
<summary>✅ v1.2 Protocol Completeness (Phases 12-16) — SHIPPED 2026-03-13</summary>

- [x] Phase 12: PyPI Distribution (3/3 plans) — completed 2026-03-13
- [x] Phase 13: Drift Resource (2/2 plans) — completed 2026-03-13
- [x] Phase 14: MCP Prompts (2/2 plans) — completed 2026-03-13
- [x] Phase 15: Preview Tool Split (2/2 plans) — completed 2026-03-13
- [x] Phase 16: Quality Gate (1/1 plan) — completed 2026-03-13

Full details: `.planning/milestones/v1.2-ROADMAP.md`

</details>

<details>
<summary>✅ v1.3 Credentials & Release Automation (Phases 17-20) — SHIPPED 2026-03-15</summary>

- [x] Phase 17: Credential Store Foundation (1/1 plan) — completed 2026-03-15
- [x] Phase 18: Credentials CLI + --version (3/3 plans) — completed 2026-03-15
- [x] Phase 19: Credential Auto-Inject (2/2 plans) — completed 2026-03-15
- [x] Phase 20: Release Automation + PRMT-02 (3/3 plans) — completed 2026-03-15

Full details: `.planning/milestones/v1.3-ROADMAP.md`

</details>

<details>
<summary>✅ v1.4.1 Security Patch (Phase 30) — SHIPPED 2026-04-01</summary>

- [x] Phase 30: Security Fixes (2/2 plans) — completed 2026-04-01

Full details: `.planning/milestones/v1.4.1-ROADMAP.md`

</details>

<details>
<summary>✅ v1.5 Critical Bug Fixes (Phases 31-32) — SHIPPED 2026-04-20</summary>

- [x] Phase 31: Bug Fixes (2/2 plans) — completed 2026-04-19
- [x] Phase 32: Regression Tests (5/5 plans) — completed 2026-04-20

Full details: `.planning/milestones/v1.5-ROADMAP.md`

</details>

<details>
<summary>✅ v1.6 Credential Architecture Cleanup (Phases 33, 33.1, 34, 35) — SHIPPED 2026-04-24</summary>

- [x] Phase 33: Keyring Single Source of Truth (5/5 plans) — completed 2026-04-21
- [x] Phase 33.1: SSH Tool Family Keyring Uniformity (INSERTED, 5/5 plans) — completed 2026-04-23
- [x] Phase 34: Cluster-Scoped Proxmox Credentials (4/4 plans) — completed 2026-04-23
- [x] Phase 35: Sitemap + Discovery Reliability (INSERTED, 4/4 plans) — completed 2026-04-24

Full details: `.planning/milestones/v1.6-ROADMAP.md`

</details>

<details>
<summary>🚧 v1.7 Drift Architectural Fix (Phases 36-40) — IN PROGRESS</summary>

- [ ] **Phase 36: Drift ↔ Sitemap Foundation** — Drop parallel `drift_baselines` table; wire `scan_infrastructure_drift` to iterate sitemap rows; resolve Proxmox creds via `resolve_proxmox_credentials`
- [ ] **Phase 37: Drift Output Shape & Error Hygiene** — Consistent shape across all filter scopes; four-bucket coverage transparency; error messages reference sitemap CRUD tools, never `PROXMOX_HOST`
- [x] **Phase 38: Sitemap Fingerprint Schema** — Sitemap rows capture kernel version, package fingerprint, and capability probes (GPU passthrough, Vulkan/ML library availability) so OS-level changes surface as drift (completed 2026-04-26)
- [ ] **Phase 39: Drift Detection Cases** — Detect unknown (manually-created VMs not in sitemap), missing (sitemap rows that no longer probe-respond), and changed (fingerprint differs from stored) infrastructure
- [ ] **Phase 40: Proxmox VM Lifecycle Polish** — `get_proxmox_vm_status` clean "VM not found" error; `create_proxmox_vm` schema accuracy + cred-error guidance pointing to `credentials add`, never `PROXMOX_HOST`

</details>

## Phase Details

### Phase 36: Drift ↔ Sitemap Foundation
**Goal**: Sitemap becomes the single source of truth for drift — the parallel `drift_baselines` table is gone and `scan_infrastructure_drift` reads sitemap rows directly with proper credential resolution.
**Depends on**: Nothing (foundation phase for v1.7)
**Requirements**: DRFT-11, DRFT-12, DRFT-21
**Success Criteria** (what must be TRUE):
  1. After upgrading, the `drift_baselines` table no longer exists in either the SQLite or Postgres adapter — fresh installs never create it, and migration on existing installs drops it cleanly
  2. A user calling `scan_infrastructure_drift` with no Proxmox env vars set sees a successful scan that resolves credentials through `resolve_proxmox_credentials` (per-node → cluster → actionable error), identical to how every other Proxmox tool resolves
  3. A user can grep the production code path for `drift_baselines` reads/writes and find none — the only references that remain are the migration step that drops the table
  4. An AST meta-test fails CI if any future code path on the drift-scan call chain reads from a parallel baseline table instead of sitemap rows
**Plans**: 6 plans
  - [x] 36-01-PLAN.md — Database adapter cleanup (remove drift_baseline ABC + SQLite/Postgres methods + CREATE block)
  - [x] 36-02-PLAN.md — Migration drop step (idempotent DROP TABLE on both adapters; delete auto-create block)
  - [x] 36-03-PLAN.md — AST regression guards (extend test_ast_regression.py for Phase 36 D-12/D-13)
  - [x] 36-04-PLAN.md — Drift detection refactor (rewrite scan_drift for 2-bucket sitemap iteration; remove update_baseline_after_mutation)
  - [x] 36-05-PLAN.md — Test suite realignment (rewrite drift tests; delete TestDriftBaselines + test_proxmox_baseline_hooks.py; surgical patch-line removal)
  - [x] 36-06-PLAN.md — Documentation sweep (update scan_infrastructure_drift entry in docs/tool-reference.md)

### Phase 37: Drift Output Shape & Error Hygiene
**Goal**: A user calling `scan_infrastructure_drift` gets the same response shape regardless of filter scope, can see at a glance which hosts were probed and which weren't, and never sees an error message pointing to a deprecated env var or a non-existent baseline tool.
**Depends on**: Phase 36
**Requirements**: DRFT-13, DRFT-14, DRFT-15, DRFT-16
**Success Criteria** (what must be TRUE):
  1. A user calling `scan_infrastructure_drift` with `node=*`, `vm_type=qemu`, `vm_type=lxc`, or no filter at all gets the same response shape — empty match returns an empty result, never a scope error (closes Bugs A and E)
  2. The drift report distinguishes four buckets — probed-OK, unreachable, unknown, and changed — so a user reading the output can tell exactly which hosts were covered and which weren't (closes Bug D)
  3. Every drift family error message that suggests a recovery action points to an existing sitemap CRUD tool (`discover_and_map`, `get_network_sitemap`, `purge_failed_discoveries`, `decommission_device`) — no message mentions `PROXMOX_HOST` (closes Bug B)
  4. The MCP tool list contains no `register_drift_baseline`, `list_drift_baselines`, or `delete_drift_baseline` tool — drift docs and any baseline-lifecycle error message reference the existing sitemap CRUD tools (closes Bug C architecturally)
**Plans**:
  - [x] 37-01-PLAN.md — `scan_drift` shape rewrite (hostname filter, 4-bucket envelope, counts sub-dict, conditional guidance, Phase 36 per-row preservation)
  - [x] 37-02-PLAN.md — Drift surface text scrub (schema description, MCP resource description, OpenAPI Drift block, handler docstring, tool-reference.md)
  - [x] 37-03-PLAN.md — AST regression guards (`TestPhase37DriftHygiene`: PROXMOX_HOST per-file scan + forbidden baseline-tool-name whole-tree scan)
  - [x] 37-04-PLAN.md — Functional regression tests (`TestScanDrift4Bucket`: envelope, counts, guidance, node filter, vm_type inertness)

### Phase 38: Sitemap Fingerprint Schema
**Goal**: Sitemap rows capture enough fingerprint detail (kernel version, installed-package digest, hardware capability probes) that an OS-level change like a kernel update breaking GPU passthrough or Vulkan support shows up as drift instead of vanishing silently.
**Depends on**: Phase 36
**Requirements**: DRFT-20
**Success Criteria** (what must be TRUE):
  1. After running `discover_and_map` on a host, the user can read the sitemap row and see kernel version, package fingerprint, and capability probe results (GPU passthrough state, Vulkan/ML library availability) populated
  2. A user inspecting two sitemap rows for the same host taken before and after a kernel update can see the kernel version field change, with package fingerprint and capability fields available for comparison
  3. The schema migration runs cleanly on existing sitemap databases — old rows get NULL for the new fields and re-discovery populates them; no data loss for existing fields
  4. The discovery probe code that populates the new fields wraps every `conn.run` call with `_run_with_timeout(10s)` and emits the `partial: True` payload tag when probes time out (carries forward Phase 35 reliability pattern)
**Plans**: 6 plans
  - [x] 38-01-PLAN.md — Universal core probes + payload assembly inside ssh_discover_system; refactor brittle test mock
  - [x] 38-02-PLAN.md — Schema substrate: NetworkDevice field, parse branch, SQLite column, idempotent ALTER + schema-rebuild update
  - [x] 38-03-PLAN.md — Adapter round-trip: SQLite store/get + Postgres system_info JSONB write + flatten-on-read
  - [x] 38-04-PLAN.md — update_device_fingerprint adapter method + MCP tool wired through 5 sites (schema/handler/routing/annotations/MUTATING_TOOLS)
  - [x] 38-05-PLAN.md — configure_host_fingerprint prompt + preview tool + description follow-ups + docs sweep
  - [x] 38-06-PLAN.md — End-to-end integration test against Debian Docker container

### Phase 38.1: Sitemap-keystore credential binding (INSERTED)

**Goal**: A user who runs the documented happy path — `credentials add --type proxmox <id> <user> <secret>`, then `discover_and_map <id>`, then `scan_infrastructure_drift` — sees their host in `probed_ok` (count >= 1), regardless of whether the credential was registered by IP, short hostname, or FQDN. Drift detection becomes verifiable end-to-end in Claude Desktop instead of silently returning `scanned: 0`.
**Requirements**: R1, R2, R3, R4, R5, R6, R7, R8, R9, R10 (locked in 38.1-SPEC.md; closes Bug O architectural + Bug N invisible eligibility from 2026-04-26 Claude Desktop UAT)
**Depends on:** Phase 38
**Plans:** 5/9 plans executed
  - [x] 38.1-01-PLAN.md — Wave 0 RED test scaffolds (AST guards + functional fixtures + migration test scaffold + integration round-trip scaffold)
  - [x] 38.1-02-PLAN.md — Wave 1 credential_store.py UUID generation + find_credential_by_id helper (R1)
  - [x] 38.1-03-PLAN.md — Wave 1 database.py credential_id columns on both adapters + set_device_credential_binding method + eligibility flatten (R2 + R7-eligibility)
  - [x] 38.1-04-PLAN.md — Wave 2 migration.py destructive drop-and-recreate with version-stamp + 3-block banner (R10 + idempotent ALTER for R2)
  - [x] 38.1-05-PLAN.md — Wave 2 resolver credential_id keyword-only param (Tier-0 UUID short-circuit) on both proxmox_api.py + ssh_tools.py (R5)
  - [ ] 38.1-06-PLAN.md — Wave 3 drift_detection.py 5-bucket envelope + reason-enum routing; AST guard D-15 GREEN (R6 + R7-bucket)
  - [ ] 38.1-07-PLAN.md — Wave 3 server.py CLI auto-bind on add + rotation cleanup on remove + link/unlink subcommands + --json on list (R1-caller + R4 + R8 + R9)
  - [ ] 38.1-08-PLAN.md — Wave 4 sitemap.py discover_and_map writes ssh_credential_id post-upsert (R3)
  - [ ] 38.1-09-PLAN.md — Wave 5 integration round-trip acceptance test wired and GREEN (SPEC headline + 12 acceptance criteria + 4 invariants)

### Phase 39: Drift Detection Cases
**Goal**: A user running `scan_infrastructure_drift` after a real-world change — a manually-created VM, an offline NAS, a kernel update that regressed Vulkan support — sees that change reported as drift, classified into the right bucket.
**Depends on**: Phase 36, Phase 38
**Requirements**: DRFT-17, DRFT-18, DRFT-19
**Success Criteria** (what must be TRUE):
  1. When a user creates a VM directly in the Proxmox UI without going through the MCP server, the next `scan_infrastructure_drift` reports that VM in the **unknown infrastructure** bucket with the host node, VMID, and a pointer to `discover_and_map` for adoption
  2. When a sitemap-known host stops responding (powered off, network outage, decommissioned but not purged), `scan_infrastructure_drift` reports it in the **missing infrastructure** bucket with last-seen timestamp and a pointer to `decommission_device` or `purge_failed_discoveries`
  3. When a host's kernel version, package fingerprint, or capability probe (e.g., Vulkan availability) differs from the stored sitemap row, `scan_infrastructure_drift` reports it in the **changed infrastructure** bucket with a per-field diff showing stored-vs-current values
  4. The unknown-detection path enumerates Proxmox VMs/LXC via the API; the missing- and changed-detection paths use SSH probes that respect the per-subprocess `_run_with_timeout(10s)` pattern from Phase 35 — no scan hangs longer than the documented bulk timeout when a host is unresponsive
**Plans**: TBD

### Phase 40: Proxmox VM Lifecycle Polish
**Goal**: A user hitting Bug I (querying a nonexistent VMID) or Bug G (calling `create_proxmox_vm` without configured credentials) gets a clean structured error that tells them what to do next, never a raw HTTP 500 leak or a pointer to a deprecated env var.
**Depends on**: Nothing (independent of drift work; can run in parallel with Phase 37/38/39)
**Requirements**: POL-01, POL-02, POL-03
**Success Criteria** (what must be TRUE):
  1. A user calling `get_proxmox_vm_status` with a VMID that doesn't exist on the target node sees a structured `VM not found` error with hostname and VMID echoed back — no raw HTTP 500, no internal Proxmox API URL leaked into the message (closes Bug I)
  2. The `create_proxmox_vm` tool schema declares its `host` parameter as optional or required in a way that matches runtime behavior under cluster-scope keyring resolution — schema and runtime agree, no schema lie (closes Bug G schema half)
  3. When `create_proxmox_vm` cannot resolve credentials, the error message points the user to `homelab-mcp credentials add --type proxmox` (with a note about `--scope cluster:<name>` for cluster tokens) — no message mentions `PROXMOX_HOST` (closes Bug G error half)
**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Architecture Foundation | v1.0 | 3/3 | Complete | 2026-03-08 |
| 2. Security Hardening | v1.0 | 5/5 | Complete | 2026-03-09 |
| 3. Functional Completeness | v1.0 | 3/3 | Complete | 2026-03-09 |
| 4. MCP Protocol Compliance | v1.0 | 2/2 | Complete | 2026-03-11 |
| 5. Documentation | v1.0 | 2/2 | Complete | 2026-03-11 |
| 6. Tech Debt Cleanup | v1.1 | 3/3 | Complete | 2026-03-11 |
| 7. MCP Resources Plumbing | v1.1 | 1/1 | Complete | 2026-03-11 |
| 8. Dry-Run Mode | v1.1 | 4/4 | Complete | 2026-03-12 |
| 9. MCP Resources Live Data | v1.1 | 2/2 | Complete | 2026-03-12 |
| 10. Resource Notifications | v1.1 | 1/1 | Complete | 2026-03-12 |
| 11. Drift Detection | v1.1 | 5/5 | Complete | 2026-03-12 |
| 12. PyPI Distribution | v1.2 | 3/3 | Complete | 2026-03-13 |
| 13. Drift Resource | v1.2 | 2/2 | Complete | 2026-03-13 |
| 14. MCP Prompts | v1.2 | 2/2 | Complete | 2026-03-13 |
| 15. Preview Tool Split | v1.2 | 2/2 | Complete | 2026-03-13 |
| 16. Quality Gate | v1.2 | 1/1 | Complete | 2026-03-13 |
| 17. Credential Store Foundation | v1.3 | 1/1 | Complete | 2026-03-15 |
| 18. Credentials CLI + --version | v1.3 | 3/3 | Complete | 2026-03-15 |
| 19. Credential Auto-Inject | v1.3 | 2/2 | Complete | 2026-03-15 |
| 20. Release Automation + PRMT-02 | v1.3 | 3/3 | Complete | 2026-03-15 |
| 30. Security Fixes | v1.4.1 | 2/2 | Complete | 2026-04-01 |
| 31. Bug Fixes | v1.5 | 2/2 | Complete | 2026-04-19 |
| 32. Regression Tests | v1.5 | 5/5 | Complete | 2026-04-20 |
| 33. Keyring Single Source of Truth | v1.6 | 5/5 | Complete | 2026-04-21 |
| 33.1 SSH Tool Family Keyring Uniformity | v1.6 | 5/5 | Complete | 2026-04-23 |
| 34. Cluster-Scoped Proxmox Credentials | v1.6 | 4/4 | Complete | 2026-04-23 |
| 35. Sitemap + Discovery Reliability | v1.6 | 4/4 | Complete | 2026-04-24 |
| 36. Drift ↔ Sitemap Foundation | v1.7 | 6/6 | Complete   | 2026-04-25 |
| 37. Drift Output Shape & Error Hygiene | v1.7 | 0/0 | Not started | - |
| 38. Sitemap Fingerprint Schema | v1.7 | 6/6 | Complete    | 2026-04-26 |
| 38.1 Sitemap-keystore Credential Binding | v1.7 | 5/9 | In Progress|  |
| 39. Drift Detection Cases | v1.7 | 0/0 | Not started | - |
| 40. Proxmox VM Lifecycle Polish | v1.7 | 0/0 | Not started | - |

## Backlog

### Phase 999.1: MCP tool CRUD for registered servers (BACKLOG)

**Goal:** [Captured for future planning] Add MCP-side tools (or confirm CLI parity) for server-registration CRUD beyond `register_server` verify: renaming `display_name`, changing the registered username, unregistering from sitemap while preserving history. Phase 33 removed `update_server_credentials` + `remove_server` MCP tools (D-20/D-21). The replacements are CLI-only (`credentials remove`) and CLI doesn't touch sitemap rows. Live testing flagged the gap.
**Requirements:** TBD
**Plans:** 6/6 plans complete

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

### Phase 999.2: Credential-mismatch warning on register_server (BACKLOG)

**Goal:** [Captured for future planning] When `register_server(host, username=X)` is called but the keyring entry for `host` has username Y, emit a UX warning ("keyring says host's user is Y; you're registering as X — are you sure?"). Currently silent — the verify step either succeeds-incidentally or fails with a less helpful error. Minor UX nicety.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

### Phase 999.3: discover_and_map accepts display_name (BACKLOG)

**Goal:** [Captured for future planning] Add an optional `display_name` param to `discover_and_map` so fresh hosts get a sitemap row with a friendly label in one call. Today it's a two-step flow (`register_server` first, then `discover_and_map`) — works but clunky.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

### Phase 999.4: Sitemap device tags / categories (LOCKED FOR v1.7.2)

**Goal:** [Captured for future planning, **locked for v1.7.2 Role-Aware Drift** as of 2026-04-25] Add a `tags` or `category` field to sitemap rows so `get_network_sitemap` is filterable (PVE hosts, NAS, routers, Pi endpoints, etc.). Parity with Proxmox's existing tag model (`community-script;docker` on LXC). Flat table is fine for a few hosts; pain grows with the homelab. Promoted into v1.7.2 milestone scope as the prerequisite for role-aware drift checks (gateway routing/NAT profile, NAS service-health profile).
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

### Phase 999.5: Generalized purge_devices(filter=...) (BACKLOG)

**Goal:** [Captured for future planning, surfaced during v1.6 retest] Generalize the `purge_failed_discoveries` tool added in v1.6.x into a `purge_devices(filter=...)` superset. Filters to support: by hostname (decommissioned host removal), by `last_seen < N days ago` (stale-device sweep), by `status='error'` (current behavior — keep as a named alias), by IP range. The focused `purge_failed_discoveries` shipped in v1.6.0 should remain as a named alias / convenience wrapper so existing flows don't break.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

### Phase 999.6: ZFS ARC memory accounting on TrueNAS / ZFS hosts (BACKLOG)

**Goal:** [Captured during v1.6 live validation] TrueNAS and other ZFS hosts show high `memory_used` because the ARC fills available RAM by design — that's not memory pressure, it's healthy caching. Two options to evaluate: (a) detect ZFS via `/proc/spl/kstat/zfs/arcstats` and subtract ARC size from used (like `htop -ZFS` does), or (b) keep the raw number but label the device as ZFS-aware in the analyzer so high-memory-usage flags become advisory rather than alerting. Same problem may apply to other cache-heavy systems (BSD's UBC, macOS purgeable memory, etc.). Also revisit the `df /` design choice — for NAS hosts the boot pool is uninformative; consider gathering all mounted filesystems or surfacing the data pool separately.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

### Phase 999.7: Discover tool error-path guidance consistency (BACKLOG)

**Goal:** [Captured during v1.6 retest] The `ssh_discover` and `ssh_execute_command` tool descriptions include actionable guidance ("If authentication fails with 'No credentials found', run `homelab-mcp credentials add <hostname> <username>`"). The `discover_and_map` and `bulk_discover_and_map` descriptions only mention auto-injection ("omit if credentials were stored with `credentials add`") without telling the user what to do when resolution fails. Propagate the same error-path pointer to both schemas so the AI client surfaces consistent recovery guidance regardless of which discovery tool was invoked. Pure docstring change; no code path touched.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

### Phase 999.8: Rename docker-adjacent tools to `docker_*` (BACKLOG)

**Goal:** [Captured during v1.7 scoping 2026-04-25] Several tools that operate on Docker containers/images are not named with a `docker_` prefix, hiding the family from users browsing the tool list. Audit the tool registry, identify all Docker-adjacent tools, and rename them with the `docker_*` convention (matching the `proxmox_*` and `ssh_*` family naming). Naming-only refactor — no behavior changes. Leave deprecation aliases for one minor version. Out of scope for v1.7 (drift integration only).
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

### Phase 999.9: `probe_pending_updates` advisory family (BACKLOG)

**Goal:** [Captured during v1.7 scoping 2026-04-25] Sibling concept to drift, not part of it. Advisory probes that surface "this system needs attention" signals that don't fit the sitemap-vs-live-state divergence model: pending OS updates (apt/dnf/zypper), self-hosted-app update notifications (Nextcloud admin API, Plex, etc.), kernel-update-required-for-running-modules state, certificate expiry, etc. Asymmetric across distros — Nextcloud surfaces nag messages because it has an update channel; Ubuntu silently sits with `apt list --upgradable` available only when SSH'd in. Goal is a normalized advisory output across the homelab. Likely a separate top-level tool (`probe_homelab_advisories` or similar) or its own MCP Resource. Could fold into a future "Homelab Health Check" entry point alongside drift output. Out of v1.7/v1.7.1/v1.7.2 scope.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)
