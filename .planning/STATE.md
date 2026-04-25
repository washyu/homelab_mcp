---
gsd_state_version: 1.0
milestone: v1.7
milestone_name: Drift Integration & Polish
status: defining_requirements
stopped_at: v1.7 opened — defining requirements
last_updated: "2026-04-25T00:00:00.000Z"
last_activity: 2026-04-25 -- v1.7 milestone opened (drift integration scope locked)
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-25 — v1.7 opened)

**Core value:** Every tool in the server actually works — a Proxmox homelabber can install this, connect it to any MCP client, and reliably manage their infrastructure through AI.
**Current focus:** v1.7 Drift Integration & Polish — defining requirements

## Current Position

Milestone: v1.7 Drift Integration & Polish
Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-04-25 -- v1.7 milestone opened, scope locked

Progress: [          ] 0% — requirements not yet defined

## Milestone Origin

v1.7 surfaced during a 2026-04-25 retest of the v1.6 codebase. Live testing of the drift detection family produced 10 distinct bugs (A-J) of which 9 trace to a single architectural gap: the drift module maintains its own baseline data layer that was never integrated with the sitemap or keyring. `discover_and_map`, `create_proxmox_vm`, and `delete_proxmox_vm` all touch the sitemap; the drift module reads from a separate baseline table and doesn't know about either. v1.7 closes that integration gap and extends the principle to every infrastructure-mutating tool family (Proxmox VM/LXC, Terraform, Ansible, community scripts, docker-adjacent tools, services catalog). Bug I (`get_proxmox_vm_status` HTTP 500 leak) is bundled as adjacent polish.

## Deferred Items (carried from v1.6 close)

| Category | Item | Status | Notes |
|----------|------|--------|-------|
| tech_debt | 31-VERIFICATION.md missing | deferred | Phase 31 merged on plan-SUMMARY evidence; Phase 32 revert-proof regressions re-prove each fix |
| tech_debt | 31-VALIDATION.md draft | deferred | Nyquist validation incomplete |
| tech_debt | 32-VALIDATION.md missing | deferred | No Nyquist VALIDATION.md for regression-tests phase |
| tech_debt | 33-VERIFICATION.md missing | deferred | Phase 33 merged on plan-SUMMARY evidence; integration checker supplied retroactive verification |
| tech_debt | 33/33.1/34/35 VALIDATION.md gaps | deferred | Non-blocking; revert-proof regression + AST meta-tests provide equivalent coverage per CLAUDE.md |
| tech_debt | SUMMARY frontmatter shape inconsistency | deferred | 32-01 flat vs 32-02..05 nested |
| v1.8_candidate | Cross-cutting `mcp_admin` cleanup | deferred | ~20 sites in `infrastructure_crud.py`, `vm_operations.py`, `ssh_connection.py`, `service_installer.py`, schemas. Out of v1.7 scope (drift integration only) |
| v1.8_candidate | SSH-04 per-call timeout handshake | deferred | Out of v1.7 scope |
| v1.8_candidate | QUAL-01 Proxmox iso/cdrom exclusivity | deferred | Out of v1.7 scope |
| v1.8_candidate | HTTP-01 HTTP flag truthy variants | deferred | Out of v1.7 scope |
| v1.8_candidate | ERR-02 resolver error wrapping | deferred | Out of v1.7 scope |
| v1.8_candidate | Rename docker-adjacent tools to `docker_*` | deferred | Captured as 999.8 backlog; naming-only refactor; out of v1.7 |

## Accumulated Context

### Decisions

Full v1.0-v1.6 decision logs in `.planning/milestones/v{X.Y}-ROADMAP.md`. Key patterns established through v1.6 (carry forward into v1.7):

- **Keyring as single source of truth** for remote credentials (CRED-04). v1.7's drift integration must resolve through `resolve_ssh_credentials` / `resolve_proxmox_credentials`, never bypass with env vars or DB reads
- **`CredentialNotFoundError` with actionable pointer** instead of silent fallback (CRED-05) — v1.7 error messages should follow this pattern (`credentials add <hostname>` etc.), not env-var pointers
- **Cluster-scoped Proxmox tokens** with node→cluster→error precedence (CRED-08) — drift integration must respect this resolution order
- **Hostname-only sitemap upsert** with degenerate-hostname fallback (Phase 35) — drift baseline keys should follow the same convention
- **AST meta-tests as regression guard pattern** — class of bugs that no positive regression test catches (33.1 D-08 mcp_admin defaults, 35 D-14/D-15/D-16 hostname-only/timeout-wrapped/no-coercion). v1.7 should consider similar guards for "infrastructure-mutating tool registers baseline" invariants
- **`_run_with_timeout(10s)` per-subprocess SSH probe wrapping** (Phase 35) — drift live-state probes must follow this pattern
- **`Semaphore(10) + asyncio.gather`** for bulk discovery (Phase 35) — drift bulk scans should use the same fanout pattern
- **`contextlib.suppress(Exception)` around `websocket.close()`** — idempotent cleanup pattern; applies to drift baseline cleanup hooks on VM destroy

Key constraints carried forward:

- `credential_store.py` must have no homelab_mcp imports — circular import prevention
- Every keyring call path must catch `NoKeyringError`, `RuntimeError`, and `Exception` — headless Linux primary deploy target
- `_sudo_run` helper is the only path for sudo invocation
- PyPI OIDC trusted publisher registered at pypi.org; `git tag v*` push triggers publish

### Pending Todos

None at v1.7 open. Will be populated as phase planning progresses.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 5 | we are missing the new cli arguments for the keystore in the command line help output | 2026-03-15 | 88e972f | [5-we-are-missing-the-new-cli-arguments-for](./quick/5-we-are-missing-the-new-cli-arguments-for/) |
| 6 | update README and setup docs to reflect v1.3 (PyPI/uvx, credentials CLI, Python 3.12+) | 2026-03-15 | 1357903 | [6-update-readme-and-setup-docs-to-reflect-](./quick/6-update-readme-and-setup-docs-to-reflect-/) |
| 7 | fix ssh tool schemas so the model knows about keyring auto-inject | 2026-03-15 | d261600 | [7-fix-ssh-tool-schemas-so-the-model-knows-](./quick/7-fix-ssh-tool-schemas-so-the-model-knows-/) |

### Blockers/Concerns

- PyPI OIDC trusted publisher must remain registered at pypi.org/manage/project/homelab-mcp/settings/publishing/ for future `git tag v*` pushes
- Migration consideration for v1.7: existing rows in the parallel drift baseline table (if any) need a reconciliation strategy when the data layer integrates with sitemap — TBD during phase planning
- Live-test-only verifiability: integration of drift hooks with VM lifecycle / Terraform / Ansible / community scripts likely cannot be fully exercised in headless CI; expect manual verification on a real Proxmox cluster as part of milestone close

## Session Continuity

Last session: 2026-04-25T00:00:00.000Z
Stopped at: v1.7 milestone opened — scope locked, defining requirements next
Resume command: continue this session, or `/gsd-plan-phase 36` once REQUIREMENTS.md and ROADMAP.md are written
