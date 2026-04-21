# Roadmap: Homelab MCP Server

## Milestones

- ✅ **v1.0 MVP** — Phases 1-5 (shipped 2026-03-11)
- ✅ **v1.1 Safety & Observability** — Phases 6-11 (shipped 2026-03-12)
- ✅ **v1.2 Protocol Completeness** — Phases 12-16 (shipped 2026-03-13)
- ✅ **v1.3 Credentials & Release Automation** — Phases 17-20 (shipped 2026-03-15)
- ✅ **v1.4.1 Security Patch** — Phase 30 (shipped 2026-04-01)
- 🔄 **v1.5 Critical Bug Fixes** — Phases 31-32 (in progress)

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

### v1.5 Critical Bug Fixes

- [ ] **Phase 31: Bug Fixes** - Close 5 critical/high bugs from CodeRabbit PR #39 review
- [ ] **Phase 32: Regression Tests** - Regression tests preventing recurrence of all 5 fixed bugs

## Phase Details

### Phase 31: Bug Fixes
**Goal**: All 5 critical and high-priority bugs from PR #39 review are corrected in production code
**Depends on**: Nothing (independent fixes)
**Requirements**: WS-01, ERR-01, SSH-01, SSH-02, SCH-01
**Success Criteria** (what must be TRUE):
  1. Closing a WebSocket PTY session (EOF or connection error) cancels the paired reader task and closes the socket — no zombie sessions accumulate
  2. A timeout error response reports the actual computed effective timeout value, not the raw timeout_seconds parameter passed by the caller
  3. `_sudo_run` with `check=True` raises on non-zero exit code regardless of whether a password was provided — password branch behaves identically to no-password branch
  4. The password propagation test in `test_ssh_tools.py` fails when password is absent — the assertion is not an always-passing ternary
  5. Passing an arbitrary string as `credential_type` to the credentials tool is rejected by schema validation — only "ssh" and "proxmox" are accepted
**Plans:** 2 plans
Plans:
- [x] 31-01-PLAN.md — Fix timeout error message, test assertion, and credential_type schema (ERR-01, SSH-02, SCH-01) — completed 2026-04-19
- [ ] 31-02-PLAN.md — Fix zombie WebSocket PTY sessions and extract _sudo_run helper (WS-01, SSH-01)

### Phase 32: Regression Tests
**Goal**: All 5 fixed bugs have dedicated regression tests that will catch any recurrence before it ships
**Depends on**: Phase 31
**Requirements**: REG-01
**Success Criteria** (what must be TRUE):
  1. A test verifies the WebSocket PTY reader cancels its paired task and closes the socket on EOF — reverting the fix causes the test to fail
  2. A test verifies the timeout error message contains the effective_timeout value — reverting the fix causes the test to fail
  3. A test verifies `_sudo_run(check=True)` raises on non-zero exit in the password branch — reverting the fix causes the test to fail
  4. A test verifies the password assertion in `test_ssh_tools.py` fails when password is not propagated — the test is not unconditionally passing
  5. A test verifies the credentials tool schema rejects non-enum credential_type values — reverting the fix causes the test to fail
**Plans:** 5 plans
Plans:
- [x] 32-01-PLAN.md — WS-01 E2E regression test in tests/test_http_app.py (closes QUAL-02) — completed 2026-04-20
- [x] 32-02-PLAN.md — SSH-01 + SSH-02 regression tests in tests/test_ssh_tools.py (includes AST meta-test with D-05 mutation experiment) — completed 2026-04-20
- [x] 32-03-PLAN.md — ERR-01 regression test in tests/test_error_handling.py (monkeypatched asyncio.wait_for) — completed 2026-04-20
- [x] 32-04-PLAN.md — SCH-01 regression test in tests/test_tools.py (credential_type enum shape) — completed 2026-04-20
- [ ] 32-05-PLAN.md — Gap closure: extend SSH-02 AST detector to catch d25c915 pre-fix Compare(Constant in X) form + D-10 note

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
| 31. Bug Fixes | v1.5 | 1/2 | In Progress | - |
| 32. Regression Tests | v1.5 | 4/4 | In Progress | - |
