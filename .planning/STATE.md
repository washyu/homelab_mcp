---
gsd_state_version: 1.0
milestone: v1.6
milestone_name: Credential Architecture Cleanup
status: executing
stopped_at: Phase 33.1 context gathered
last_updated: "2026-04-22T00:00:00.000Z"
last_activity: 2026-04-22 -- Phase 33.1 context gathered (CONTEXT.md + DISCUSSION-LOG.md written)
progress:
  total_phases: 2
  completed_phases: 0
  total_plans: 5
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-20 after v1.6 start)

**Core value:** Every tool in the server actually works — a Proxmox homelabber can install this, connect it to any MCP client, and reliably manage their infrastructure through AI.
**Current focus:** Phase 33 — keyring-single-source-of-truth

## Current Position

Phase: 33 (keyring-single-source-of-truth) — EXECUTING
Plan: 1 of 5
Status: Executing Phase 33
Last activity: 2026-04-21 -- Phase 33 execution started

Progress: [░░░░░░░░░░] 0%

## Milestone Origin

v1.6 anchors on the Phase 33 idea originally drafted at commit `8ac2270` on 2026-04-19 (credential-cleanup branch). That commit's narrative labeled v1.4/v1.5 as "parked/broken" — superseded. v1.4/v1.4.1/v1.5 all shipped cleanly. v1.6 picks up the actual credential cleanup scope from that commit's SPEC without the stale narrative.

## Deferred Items (carried from v1.5 close)

| Category | Item | Status | Notes |
|----------|------|--------|-------|
| tech_debt | 31-VERIFICATION.md missing | deferred | Phase 31 merged on plan-SUMMARY evidence; Phase 32 revert-proof regressions re-prove each fix via integration |
| tech_debt | 31-VALIDATION.md draft | deferred | Nyquist validation incomplete |
| tech_debt | 32-VALIDATION.md missing | deferred | No Nyquist VALIDATION.md for regression-tests phase |
| tech_debt | SUMMARY frontmatter shape inconsistency | deferred | 32-01 flat vs 32-02..05 nested |
| v1.7_candidate | SSH-04 per-call timeout handshake | deferred | Not credential-architecture; v1.7 candidate |
| v1.7_candidate | QUAL-01 Proxmox iso/cdrom exclusivity | deferred | Schema correctness; v1.7 candidate |
| v1.7_candidate | HTTP-01 HTTP flag truthy variants | deferred | Ergonomic polish; v1.7 candidate |
| v1.7_candidate | SSH-03/SSH-05/ERR-02 credential-adjacent | deferred | Scoped out of v1.6 Tier A — could fit v1.6.x or v1.7 |

## Accumulated Context

### Decisions

Full v1.0-v1.5 decision logs in `.planning/milestones/v{X.Y}-ROADMAP.md`.

Active patterns established through v1.5:

- `contextlib.suppress(Exception)` around `websocket.close()` — idempotent cleanup for PTY session teardown
- Quoted return annotations for non-subscriptable third-party classes (e.g., `'asyncssh.SSHCompletedProcess'`) — defers evaluation safely under mypy and runtime
- AST meta-tests for lint-style regression guards — catches tautological-assertion bugs that no single positive regression test can catch
- Report computed/derived values in error messages (`effective_timeout`), not raw decorator parameters
- JSON Schema `enum` keyword for fixed-choice MCP tool parameters — validated at framework boundary before handler runs

Key constraints carried forward:

- `credential_store.py` must have no homelab_mcp imports — circular import prevention
- Every keyring call path must catch `NoKeyringError`, `RuntimeError`, and `Exception` — headless Linux primary deploy target
- `_sudo_run` helper is the only path for sudo invocation — single consistent `check=` forwarding
- PyPI OIDC trusted publisher registered at pypi.org; `git tag v*` push triggers publish

### Pending Todos

None.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 5 | we are missing the new cli arguments for the keystore in the command line help output | 2026-03-15 | 88e972f | [5-we-are-missing-the-new-cli-arguments-for](./quick/5-we-are-missing-the-new-cli-arguments-for/) |
| 6 | update README and setup docs to reflect v1.3 (PyPI/uvx, credentials CLI, Python 3.12+) | 2026-03-15 | 1357903 | [6-update-readme-and-setup-docs-to-reflect-](./quick/6-update-readme-and-setup-docs-to-reflect-/) |
| 7 | fix ssh tool schemas so the model knows about keyring auto-inject | 2026-03-15 | d261600 | [7-fix-ssh-tool-schemas-so-the-model-knows-](./quick/7-fix-ssh-tool-schemas-so-the-model-knows-/) |

### Blockers/Concerns

- PyPI OIDC trusted publisher must remain registered at pypi.org/manage/project/homelab-mcp/settings/publishing/ for future `git tag v*` pushes
- Human-only verifiable items: `homelab-mcp --version` in installed env, TTY echo suppression for `credentials add` — cannot be automated in headless CI
- v1.6 migration implications: users with credentials stored only in the DB `ssh_credentials` table will need to re-add via `credentials add` after the drop — no auto-migration planned (homelab scope, single-user)

## Session Continuity

Last session: 2026-04-21T05:51:51.915Z
Stopped at: Phase 33 context gathered
Resume file: .planning/phases/33-keyring-single-source-of-truth/33-CONTEXT.md
