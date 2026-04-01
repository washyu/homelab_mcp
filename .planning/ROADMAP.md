# Roadmap: Homelab MCP Server

## Milestones

- ✅ **v1.0 MVP** — Phases 1-5 (shipped 2026-03-11)
- ✅ **v1.1 Safety & Observability** — Phases 6-11 (shipped 2026-03-12)
- ✅ **v1.2 Protocol Completeness** — Phases 12-16 (shipped 2026-03-13)
- ✅ **v1.3 Credentials & Release Automation** — Phases 17-20 (shipped 2026-03-15)
- ✅ **v1.4 Real-World Reliability** — Phases 21-29 (shipped 2026-03-20)
- 🚧 **v1.5 Security & Correctness Hardening** — Phases 30-32 (in progress)

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
<summary>✅ v1.4 Real-World Reliability (Phases 21-29) — SHIPPED 2026-03-20</summary>

- [x] Phase 21: Core SSH Reliability (2/2 plans) — completed 2026-03-15
- [x] Phase 22: Agent Guidance (2/2 plans) — completed 2026-03-15
- [x] Phase 23: Workflow Completeness (2/2 plans) — completed 2026-03-15
- [x] Phase 24: Keyring-based Password Handling (2/2 plans) — completed 2026-03-15
- [x] Phase 25: Sudo Password Piping (1/1 plan) — completed 2026-03-15
- [x] Phase 26: Sync Tool Schema (3/3 plans) — completed 2026-03-15
- [x] Phase 27: Update Tests for Tool Parameters (2/2 plans) — completed 2026-03-15
- [x] Phase 28: Fix Prompt Parameter Names (1/1 plan) — completed 2026-03-19
- [x] Phase 29: Fix deploy_service_workflow Phantom Tool (1/1 plan) — completed 2026-03-20

Full details: `.planning/milestones/v1.4-ROADMAP.md`

</details>

### 🚧 v1.5 Security & Correctness Hardening (In Progress)

**Milestone Goal:** Close all security and correctness issues identified in the v1.4 PR review — no new features, just making the existing tools provably safe and correct.

- [ ] **Phase 30: Security Fixes** — Eliminate shell injection and close TOFU race condition
- [ ] **Phase 31: SSH Reliability** — Fix keyring disambiguation, timeout propagation, and credential resolution in verify_mcp_admin_access
- [ ] **Phase 32: Error Handling, Schema & Tests** — Wrap credential errors, close dead WebSocket sessions, enforce schema exclusivity, fix test coverage gap

## Phase Details

### Phase 30: Security Fixes
**Goal**: Known attack surfaces in the SSH setup path are provably closed — public key content never reaches a shell string, and TOFU cannot write conflicting keys under concurrent load
**Depends on**: Phase 29
**Requirements**: SEC-01, SEC-02
**Success Criteria** (what must be TRUE):
  1. Calling `setup_mcp_admin` or `add_to_sudoers` with a public key containing shell metacharacters (spaces, backticks, `$()`) does not execute arbitrary commands on the remote host — the key is delivered via tmpfile or heredoc, never interpolated
  2. Two concurrent first-connections to the same host cannot each pass the existence check and write different keys — the second write is blocked until the first completes, so `known_hosts` ends with exactly one entry per host after any race
  3. Tests exercise both the injection-safe path and the lock serialization behavior — no manual verification required
**Plans**: TBD

### Phase 31: SSH Reliability
**Goal**: The SSH connection layer makes the right decision every time — correct credentials, correct timeout, correct user — with no silent fallback to a wrong value
**Depends on**: Phase 30
**Requirements**: SSH-01, SSH-02, SSH-03
**Success Criteria** (what must be TRUE):
  1. Calling an SSH tool against a host that has multiple stored usernames and no explicit `username` argument raises a disambiguation error naming the conflicting entries — the call never silently proceeds with the wrong user
  2. A connection that exceeds the caller-supplied `timeout` fails during the handshake, not after — the timeout argument reaches `ssh_connect()` directly rather than being intercepted only by the outer `asyncio.wait_for`
  3. `verify_mcp_admin_access()` uses the port and credentials returned by `resolve_ssh_credentials()` — a host stored with a non-standard port is verified on that port, not port 22
  4. Tests cover all three behaviors with mocked SSH and keyring layers
**Plans**: TBD

### Phase 32: Error Handling, Schema & Tests
**Goal**: Credential errors surface as JSON payloads, dead WebSocket sessions are cleaned up automatically, the Proxmox schema rejects invalid combinations, and the EOF regression test covers production code
**Depends on**: Phase 31
**Requirements**: ERR-01, ERR-02, QUAL-01, QUAL-02
**Success Criteria** (what must be TRUE):
  1. Calling any SSH tool when `resolve_ssh_credentials()` raises `CredentialNotFoundError` returns a JSON error payload — no unhandled exception propagates to the MCP caller
  2. When the PTY reader hits EOF or an error, the WebSocket is closed and the paired read/write tasks are cancelled — a client can observe the connection close rather than hanging indefinitely
  3. Submitting a Proxmox VM creation request that includes both `iso` and `cdrom` is rejected at schema validation — the API never receives a mutually exclusive combination
  4. The `test_http_app.py` EOF regression test invokes `handle_shell_websocket` from `http_app.py` — removing the production function causes the test to fail, confirming it exercises real code
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
| 21. Core SSH Reliability | v1.4 | 2/2 | Complete | 2026-03-15 |
| 22. Agent Guidance | v1.4 | 2/2 | Complete | 2026-03-15 |
| 23. Workflow Completeness | v1.4 | 2/2 | Complete | 2026-03-15 |
| 24. Keyring-based Password Handling | v1.4 | 2/2 | Complete | 2026-03-15 |
| 25. Sudo Password Piping | v1.4 | 1/1 | Complete | 2026-03-15 |
| 26. Sync Tool Schema | v1.4 | 3/3 | Complete | 2026-03-15 |
| 27. Update Tests for Tool Parameters | v1.4 | 2/2 | Complete | 2026-03-15 |
| 28. Fix Prompt Parameter Names | v1.4 | 1/1 | Complete | 2026-03-19 |
| 29. Fix deploy_service_workflow Phantom Tool | v1.4 | 1/1 | Complete | 2026-03-20 |
| 30. Security Fixes | v1.5 | 1/2 | In Progress|  |
| 31. SSH Reliability | v1.5 | 0/TBD | Not started | - |
| 32. Error Handling, Schema & Tests | v1.5 | 0/TBD | Not started | - |
