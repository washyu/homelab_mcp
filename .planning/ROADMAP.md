# Roadmap: Homelab MCP Server

## Milestones

- ✅ **v1.0 MVP** — Phases 1-5 (shipped 2026-03-11)
- ✅ **v1.1 Safety & Observability** — Phases 6-11 (shipped 2026-03-12)
- ✅ **v1.2 Protocol Completeness** — Phases 12-16 (shipped 2026-03-13)
- ✅ **v1.3 Credentials & Release Automation** — Phases 17-20 (shipped 2026-03-15)
- ✅ **v1.4.1 Security Patch** — Phase 30 (shipped 2026-04-01)
- ✅ **v1.5 Critical Bug Fixes** — Phases 31-32 (shipped 2026-04-20)
- 🚧 **v1.6 Credential Architecture Cleanup** — Phases 33-34 (in progress)

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

### v1.6 Credential Architecture Cleanup (In Progress)

**Milestone Goal:** The OS keyring becomes the single source of truth for remote credentials. Parallel DB `ssh_credentials` storage, `mcp_admin` hardcoded fallbacks, and the `setup_mcp_admin` bootstrap tool are removed. Proxmox API tokens can be stored at cluster scope so one credential serves all nodes in a datacenter.

- [x] **Phase 33: Keyring Single Source of Truth** — Drop DB `ssh_credentials` table; remove `mcp_admin` defaults; remove `setup_mcp_admin` tool; fix `register_server` verify-bypass (CRED-04, CRED-05, CRED-06, CRED-07) (completed 2026-04-21)
- [ ] **Phase 34: Cluster-Scoped Proxmox Credentials** — Add cluster-scope credential storage and auto-inject; per-node tokens remain supported and take precedence (CRED-08)

## Phase Details

### Phase 33: Keyring Single Source of Truth
**Goal**: The OS keyring is the only place remote credentials are stored; all hardcoded fallbacks and MCP-side credential-write paths are removed
**Depends on**: Nothing (builds on v1.5 shipped state)
**Requirements**: CRED-04, CRED-05, CRED-06, CRED-07
**Success Criteria** (what must be TRUE):
  1. The `ssh_credentials` table no longer exists in the SQLite schema; no server code reads or writes to it; existing installs' tables are documented as orphaned (users re-add via `credentials add`)
  2. SSH tools with no keyring entry for a host raise an actionable `CredentialNotFoundError` naming `credentials add <hostname>` — they do NOT log in as `mcp_admin` with a default password
  3. `setup_mcp_admin` is no longer exposed in `tools.py`; the handler function is removed; its schema is removed; MCP clients see one fewer tool; onboarding docs point at `credentials add` + `connect_to_device`
  4. `register_server` calls `resolve_ssh_credentials()` and rejects registration with an actionable error if credentials are absent or invalid; there is no code path that accepts a registration without verified credentials
  5. All existing SSH tests pass with the DB path removed; new regression tests prove keyring-only behavior

**Plans:** 5/5 plans complete
  - [x] 33-01-PLAN.md � Wave 0: Land failing regression tests (AST meta-test, resolver + register_server TDD, prompt assertion flips)
  - [x] 33-02-PLAN.md � Wave 1: Drop ssh_credentials table + delete DB credential methods (CRED-04)
  - [x] 33-03-PLAN.md � Wave 2: Two-tier resolve_ssh_credentials + --key-path CLI + credentials remove subcommand (CRED-05)
  - [x] 33-04-PLAN.md � Wave 3: Tool-surface cleanup (setup_mcp_admin/update_server_credentials/remove_server removed; list_registered_servers rewritten) (CRED-06)
  - [x] 33-05-PLAN.md � Wave 4: register_server verify-only rewrite + connect_to_device prompt rewrite (CRED-07)

### Phase 33.1: SSH Tool Family Keyring Uniformity — drop hardcoded mcp_admin default in sitemap.discover_and_store and bulk_discover_and_store; route ssh_discover, ssh_execute_command, update_mcp_admin_groups, start_interactive_shell, bulk_discover_and_map through resolve_ssh_credentials uniformly; docstring sweep; bulk target schema cleanup. Gap from Phase 33 live testing 2026-04-21. (INSERTED)

**Goal:** [Urgent work - to be planned]
**Requirements**: TBD
**Depends on:** Phase 33
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd-plan-phase 33.1 to break down)

### Phase 34: Cluster-Scoped Proxmox Credentials
**Goal**: One Proxmox API token stored at cluster scope serves all nodes in the same datacenter; per-node tokens override when both exist
**Depends on**: Phase 33 (keyring-only foundation)
**Requirements**: CRED-08
**Success Criteria** (what must be TRUE):
  1. `credentials add --type proxmox --scope cluster:<cluster_name>` stores a cluster-scoped token in the keyring alongside per-node entries
  2. `get_proxmox_client(node)` resolves credentials in priority order: per-node → cluster → error; resolution is observable via debug log
  3. A Proxmox cluster discovery step populates a `cluster_name` for each node registered to the same datacenter; cluster lookup uses that name
  4. Docs and `credentials list` output distinguish per-node from cluster-scoped credentials
  5. Per-node credentials from v1.3/v1.4 continue to work unchanged (backward-compatible precedence)

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
| 33. Keyring Single Source of Truth | v1.6 | 5/5 | Complete   | 2026-04-21 |
| 34. Cluster-Scoped Proxmox Credentials | v1.6 | 0/? | Not started | - |

### Phase 35: Sitemap + Discovery Reliability — fix discover_and_map field-loss (cpu_cores, memory_free, disk_*, usb/pci/block devices missing from sitemap row despite being in ssh_discover output); upsert zombie sitemap rows on hostname/IP match; add per-subprocess SSH timeout so tool doesn't hang 4+ minutes; topology analyzer defensively skip devices with null threshold values. Surfaced by Phase 33 live testing 2026-04-21.

**Goal:** [To be planned]
**Requirements**: TBD
**Depends on:** Phase 34
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd-plan-phase 35 to break down)

## Backlog

### Phase 999.1: MCP tool CRUD for registered servers (BACKLOG)

**Goal:** [Captured for future planning] Add MCP-side tools (or confirm CLI parity) for server-registration CRUD beyond `register_server` verify: renaming `display_name`, changing the registered username, unregistering from sitemap while preserving history. Phase 33 removed `update_server_credentials` + `remove_server` MCP tools (D-20/D-21). The replacements are CLI-only (`credentials remove`) and CLI doesn't touch sitemap rows. Live testing flagged the gap.
**Requirements:** TBD
**Plans:** 0 plans

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

### Phase 999.4: Sitemap device tags / categories (BACKLOG)

**Goal:** [Captured for future planning] Add a `tags` or `category` field to sitemap rows so `get_network_sitemap` is filterable (PVE hosts, NAS, routers, Pi endpoints, etc.). Parity with Proxmox's existing tag model (`community-script;docker` on LXC). Flat table is fine for a few hosts; pain grows with the homelab.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)
