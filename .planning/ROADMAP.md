# Roadmap: Homelab MCP Server

## Milestones

- ✅ **v1.0 MVP** — Phases 1-5 (shipped 2026-03-11)
- ✅ **v1.1 Safety & Observability** — Phases 6-11 (shipped 2026-03-12)
- ✅ **v1.2 Protocol Completeness** — Phases 12-16 (shipped 2026-03-13)
- 📋 **v1.3 Credentials & Release Automation** — Phases 17-20 (planned)

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

### 📋 v1.3 Credentials & Release Automation (Phases 17-20)

- [x] **Phase 17: Credential Store Foundation** - Build `credential_store.py` module with full headless fallback (completed 2026-03-15)
- [x] **Phase 18: Credentials CLI + --version** - Add `credentials add/list/remove` subcommands and `--version` flag (completed 2026-03-15)
- [ ] **Phase 19: Credential Auto-Inject** - Wire keyring into SSH and Proxmox credential resolution paths
- [ ] **Phase 20: Release Automation + PRMT-02** - Automate PyPI publish via OIDC and fix decommission prompt bug

## Phase Details

### Phase 17: Credential Store Foundation
**Goal**: Users have a secure, headless-safe credential storage module that the rest of v1.3 can build on
**Depends on**: Nothing (first phase of v1.3)
**Requirements**: CRED-07
**Success Criteria** (what must be TRUE):
  1. `credential_store.py` can store, retrieve, and delete credentials on a desktop system with OS keyring available
  2. On a headless Linux host with no D-Bus session, every `credential_store` function call returns a safe fallback value — no exception escapes to the caller
  3. The server starts normally on a headless host — no warning about keyring appears at startup, only at the first credential lookup attempt
  4. `keyring>=25.6.0` is listed in `[project.dependencies]` in `pyproject.toml` (promoted from optional)
**Plans**: 1 plan

Plans:
- [ ] 17-01-PLAN.md — TDD: credential_store.py with headless-safe keyring wrapper + pyproject.toml promotion

### Phase 18: Credentials CLI + --version
**Goal**: Users can manage stored SSH and Proxmox credentials from the command line, and can verify their installed version
**Depends on**: Phase 17
**Requirements**: CRED-01, CRED-02, CRED-03, CRED-04, CRED-05, CRED-06, CLI-01
**Success Criteria** (what must be TRUE):
  1. `homelab-mcp credentials add <host> <user>` prompts for password securely and stores the SSH credential without echoing it
  2. `homelab-mcp credentials list` prints stored SSH credential hostnames; `--type proxmox` shows Proxmox hosts; passwords never appear in either output
  3. `homelab-mcp credentials remove <host>` deletes the stored credential and confirms removal
  4. `homelab-mcp credentials add --type proxmox <host> <user>` stores a Proxmox credential; `remove --type proxmox` deletes it
  5. `homelab-mcp --version` prints the installed package version and exits; bare `homelab-mcp` still starts the server unchanged
**Plans**: 3 plans

Plans:
- [ ] 18-01-PLAN.md — TDD Wave 0: write failing test scaffold for credential_store registry + all CLI commands
- [ ] 18-02-PLAN.md — Extend credential_store.py with credential_type param and JSON registry (turn credential_store tests GREEN)
- [ ] 18-03-PLAN.md — Add credentials subcommand handlers and --version flag to server.py (turn all CLI tests GREEN)

### Phase 19: Credential Auto-Inject
**Goal**: SSH and Proxmox tools automatically use stored credentials so users don't need to pass them on every call
**Depends on**: Phase 17
**Requirements**: INJECT-01, INJECT-02, INJECT-03
**Success Criteria** (what must be TRUE):
  1. An SSH tool call with no `username`/`password` arguments succeeds when a matching credential exists in the keyring for that hostname
  2. An SSH tool call with explicit `username`/`password` arguments uses those values even when a keyring credential exists for the same hostname
  3. When `PROXMOX_HOST` and `PROXMOX_TOKEN` env vars are absent, the server connects to Proxmox using credentials from the keyring instead of failing
  4. Log output after auto-inject never contains the injected password value
**Plans**: TBD

### Phase 20: Release Automation + PRMT-02
**Goal**: PyPI releases are fully automated on git tag push, and the decommission workflow prompt no longer causes AI schema validation errors
**Depends on**: Nothing (independent of credential work; benefits from shipping last to use complete v1.3 build)
**Requirements**: CICD-01, CICD-02, CICD-03, CLI-02
**Success Criteria** (what must be TRUE):
  1. Pushing `git tag v1.3.0` to main triggers a publish job in GitHub Actions that uploads the built wheel to PyPI without any API token stored in GitHub secrets
  2. The publish job does not run if the test-and-quality job fails on that same commit
  3. The publish job does not run on non-tag pushes (feature branches, main commits)
  4. An AI following the `decommission_device_workflow` prompt calls `list_devices` to resolve hostname to `device_id` before calling `decommission_device` — no schema validation error occurs
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
| 18. Credentials CLI + --version | 3/3 | Complete   | 2026-03-15 | - |
| 19. Credential Auto-Inject | v1.3 | 0/TBD | Not started | - |
| 20. Release Automation + PRMT-02 | v1.3 | 0/TBD | Not started | - |
