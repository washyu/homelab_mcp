# Roadmap: Homelab MCP Server

## Milestones

- ✅ **v1.0 MVP** — Phases 1-5 (shipped 2026-03-11)
- ✅ **v1.1 Safety & Observability** — Phases 6-11 (shipped 2026-03-12)
- ✅ **v1.2 Protocol Completeness** — Phases 12-16 (shipped 2026-03-13)
- ✅ **v1.3 Credentials & Release Automation** — Phases 17-20 (shipped 2026-03-15)
- 🚧 **v1.4 Real-World Reliability** — Phases 21-23 (in progress)

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

### 🚧 v1.4 Real-World Reliability (In Progress)

**Milestone Goal:** Fix bugs and workflow issues discovered during real Mac testing — interactive shell, SSH credential flow, and TOFU known_hosts handling.

- [ ] **Phase 21: Core SSH Reliability** — Fix TOFU known_hosts corruption and interactive shell streaming
- [ ] **Phase 22: Agent Guidance** — Make credential failures recoverable and shell mode detection actionable
- [ ] **Phase 23: Workflow Completeness** — Add device onboarding prompt and keyring desync warning

## Phase Details

### Phase 21: Core SSH Reliability
**Goal**: SSH connections work correctly for keyring-registered hosts and interactive shell output reaches the browser
**Depends on**: Phase 20
**Requirements**: TOFU-01, TOFU-02, SHELL-01, SHELL-02, SHELL-03
**Success Criteria** (what must be TRUE):
  1. `ssh_discover` succeeds on a host registered only via `credentials add` (no prior `register_server`) without timeout
  2. Interactive shell streams PTY output to the browser in real time — characters appear as typed, not buffered until EOF
  3. Browser tab receives an explicit disconnection message when the shell session ends instead of hanging silently
  4. Shell prompt renders at correct width — lines do not wrap or truncate at column 24
  5. `known_hosts` file entries have exactly three fields (hostname, algorithm, base64) with no trailing comment
**Plans**: TBD

### Phase 22: Agent Guidance
**Goal**: The agent can diagnose credential failures and knows which tools and commands to recommend to the user
**Depends on**: Phase 21
**Requirements**: CRED-01, CRED-02, CRED-03, SHELL-04, SHELL-05
**Success Criteria** (what must be TRUE):
  1. When SSH authentication fails because no credentials exist, the error message names the exact CLI command (`homelab-mcp credentials add`) and tool (`register_server`) needed to fix it
  2. Agent can call `list_keyring_credentials` to see which hosts have stored credentials without asking the user
  3. `ssh_discover` and `ssh_execute_command` tool descriptions tell the agent where to look when credentials are missing
  4. `start_interactive_shell` in stdio mode returns an actionable error explaining the browser-only constraint rather than a dead URL
  5. `start_interactive_shell` schema description states the browser-only requirement so the agent does not report success in non-HTTP deployments
**Plans**: TBD

### Phase 23: Workflow Completeness
**Goal**: The agent has a pre-built onboarding recipe for new devices and detects credential store inconsistencies before they cause silent failures
**Depends on**: Phase 22
**Requirements**: TOFU-03, TOFU-04
**Success Criteria** (what must be TRUE):
  1. Agent can invoke the `connect_to_device` prompt and receive a step-by-step onboarding sequence covering setup, registration, credentials, discovery, and verification
  2. When a hostname exists in the credential registry but the keyring returns no password, a warning appears in server logs identifying the desync condition
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
| 21. Core SSH Reliability | v1.4 | 0/TBD | Not started | - |
| 22. Agent Guidance | v1.4 | 0/TBD | Not started | - |
| 23. Workflow Completeness | v1.4 | 0/TBD | Not started | - |
