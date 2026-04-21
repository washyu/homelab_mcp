---
gsd_state_version: 1.0
milestone: v1.5
milestone_name: Critical Bug Fixes
status: shipped
stopped_at: v1.5 milestone closed 2026-04-20 (audit verdict tech_debt — 4 bookkeeping items deferred)
last_updated: "2026-04-20T00:00:00.000Z"
last_activity: 2026-04-20 -- milestone v1.5 archived; ROADMAP collapsed; REQUIREMENTS.md recreated fresh for next milestone
progress:
  total_phases: 2
  completed_phases: 2
  total_plans: 7
  completed_plans: 7
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-20 after v1.5 close)

**Core value:** Every tool in the server actually works — a Proxmox homelabber can install this, connect it to any MCP client, and reliably manage their infrastructure through AI.
**Current focus:** Planning next milestone (run `/gsd-new-milestone`)

## Current Position

Phase: v1.5 shipped (Phases 31-32 complete)
Plan: —
Status: Between milestones. v1.5 archived with `tech_debt` verdict accepted.
Last activity: 2026-04-20 -- v1.5 milestone closed; archive files in `.planning/milestones/v1.5-*`

Progress: [██████████] v1.5 100%

## Deferred Items

Items acknowledged and deferred at milestone close on 2026-04-20:

| Category | Item | Status | Notes |
|----------|------|--------|-------|
| tech_debt | 31-VERIFICATION.md missing | deferred | Phase 31 merged on plan-SUMMARY evidence; Phase 32 revert-proof regressions re-prove each fix via integration, but the formal Phase-31 gate was skipped |
| tech_debt | 31-VALIDATION.md draft | deferred | `status: draft`, `nyquist_compliant: false`, `wave_0_complete: false` — Nyquist validation incomplete |
| tech_debt | 32-VALIDATION.md missing | deferred | No Nyquist VALIDATION.md for regression-tests phase |
| tech_debt | SUMMARY frontmatter shape inconsistency | deferred | 32-01 uses flat `requirements-completed: [REG-01]`; 32-02..05 use nested `requirements:\n - REG-01`. Both parse; extraction via `summary-extract --fields requirements_completed` picks up only the flat form |
| quick_task | 1-fix-ruff-ci-cd-pipeline-failures | deferred (false-positive) | audit-open flagged `status: missing` but PLAN.md + SUMMARY.md exist on disk — pre-existing bookkeeping artifact from earlier milestone |
| quick_task | 2-run-all-pre-commit-checks-before-push | deferred (false-positive) | Same as above |
| quick_task | 3-fix-windows-cross-platform-ci-failures | deferred (false-positive) | Same as above |
| quick_task | 4-create-manual-verification-test-checklis | deferred (false-positive) | Same as above |
| quick_task | 5-we-are-missing-the-new-cli-arguments-for | completed (audit false-positive) | Shipped in v1.3 at commit 88e972f (see Quick Tasks Completed table below) |
| quick_task | 6-update-readme-and-setup-docs-to-reflect- | completed (audit false-positive) | Shipped in v1.3 at commit 1357903 |
| quick_task | 7-fix-ssh-tool-schemas-so-the-model-knows- | completed (audit false-positive) | Shipped in v1.3 at commit d261600 |

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

- PyPI OIDC trusted publisher must remain registered at pypi.org/manage/project/homelab-mcp/settings/publishing/ for future `git tag v*` pushes to trigger the publish job (one-time, stable)
- Human-only verifiable items: `homelab-mcp --version` in installed env, TTY echo suppression for `credentials add` — cannot be automated in headless CI

## Session Continuity

Last session: 2026-04-20 (v1.5 milestone close)
Stopped at: v1.5 archived; next action is `/gsd-new-milestone`
Resume file: —
