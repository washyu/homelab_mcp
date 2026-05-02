---
gsd_state_version: 1.0
milestone: v1.7
milestone_name: Drift Architectural Fix
status: ready_to_plan
stopped_at: Completed 42-03-PLAN.md (gate re-run green post fixture migration; Phase 42 complete)
last_updated: "2026-05-02T15:27:21.941Z"
last_activity: 2026-05-02 -- Phase 43 execution started
progress:
  total_phases: 15
  completed_phases: 10
  total_plans: 25
  completed_plans: 19
  percent: 67
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-25 — v1.7 opened)

**Core value:** Every tool in the server actually works — a Proxmox homelabber can install this, connect it to any MCP client, and reliably manage their infrastructure through AI.
**Current focus:** Phase 43 — phase-38-documentation-cleanup

## Current Position

Milestone: v1.7 Drift Architectural Fix
Phase: 999.1
Plan: Not started
Status: Ready to plan
Last activity: 2026-05-02

Progress: [███████░░░] 76%

## v1.7 Phase Summary

| Phase | Goal | Requirements |
|-------|------|--------------|
| 36. Drift ↔ Sitemap Foundation | Sitemap becomes single source of truth; `drift_baselines` table dropped | DRFT-11, DRFT-12, DRFT-21 |
| 37. Drift Output Shape & Error Hygiene | Consistent shape across filter scopes; four-bucket coverage; sitemap-CRUD-tool error pointers | DRFT-13, DRFT-14, DRFT-15, DRFT-16 |
| 38. Sitemap Fingerprint Schema | Kernel/package/capability fields on sitemap rows so OS-level changes surface as drift | DRFT-20 |
| 39. Drift Detection Cases | Detect unknown / missing / changed infrastructure | DRFT-17, DRFT-18, DRFT-19 |
| 40. Proxmox VM Lifecycle Polish | Clean error messages on VM-not-found and missing-credentials paths | POL-01, POL-02, POL-03 |

**Coverage:** 14 / 14 requirements mapped, 0 orphans, 0 duplicates.

## Milestone Origin

v1.7 surfaced during a 2026-04-25 retest of the v1.6 codebase. Live testing of the drift detection family produced 10 distinct bugs (A-J) of which 9 trace to a single architectural gap: the drift module maintains its own baseline data layer that was never integrated with the sitemap or keyring.

**Architectural decision (2026-04-25):** Sitemap is the single source of truth for drift detection. The parallel `drift_baselines` table is dropped — sitemap rows are the baseline. This dissolves Bug J at its root rather than integrating two data layers. Drift becomes "stored sitemap state ≠ current live-probe state" with three buckets: unknown (manually-created infra not in sitemap), missing (sitemap rows that no longer probe-respond), changed (probe values differ from stored).

**Scope split:** Originally scoped 32 requirements across drift unification, lifecycle hooks across 7 tool families, and role-aware drift. Split into v1.7 / v1.7.1 / v1.7.2 for shippability:

- **v1.7 Drift Architectural Fix** (this milestone) — DRFT-11..21 + POL-01..03 (14 reqs). Drop parallel baseline table, wire scan_infrastructure_drift to sitemap, detect unknown/missing/changed buckets, capture kernel/package/capability fingerprints, polish Bug I + G. 5 phases (36-40).
- **v1.7.1 Infrastructure Lifecycle Hooks** — LIFE-01..12 (12 reqs). Every infra-mutating tool family updates sitemap on create/destroy. Estimated 5-7 phases.
- **v1.7.2 Role-Aware Drift** — TAGS-01..03 + ROLE-01..03 (6 reqs); promotes backlog 999.4. Gateway routing/NAT drift, NAS service-health drift. Estimated 3-5 phases.

Bug I (`get_proxmox_vm_status` HTTP 500 leak) bundled into v1.7 as adjacent polish. Pending OS / app update advisories captured as 999.9 backlog (sibling to drift, not part of it).

## Phase Ordering Constraints

- **Phase 36 first, in isolation.** DRFT-21 (drop `drift_baselines` table) is a one-way migration. DRFT-11 (drift iterates sitemap) and DRFT-12 (resolve creds via `resolve_proxmox_credentials`) are foundational rewrites. All three must land before any phase that depends on the unified data model.
- **Phase 38 before Phase 39.** DRFT-20 (sitemap schema extension) must land before DRFT-19 (changed-detection) — the changed bucket compares against the new fingerprint fields.
- **Phase 37 and Phase 38 parallelizable** — they touch different code paths (drift output shape vs sitemap schema extension) and both depend only on Phase 36.
- **Phase 40 independent.** POL-01/02/03 are adjacent polish on Proxmox VM lifecycle tools; can run any time after milestone open. Bundled at end for clean separation from drift work.

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

### Roadmap Evolution

- Phase 38.1 inserted after Phase 38: Sitemap-keystore credential binding (URGENT) — Claude Desktop UAT on 2026-04-26 surfaced Bug O (sitemap stores hostnames, keyring keyed by IP/FQDN, no normalization → drift returns scanned: 0 on documented happy path) and Bug N (drift eligibility heuristic invisible to users). Architectural decision: each sitemap row carries a stable `keystore_id` reference rather than relying on hostname/IP join inference. Blocks Phase 39 — drift detection cases depend on credential resolution working end-to-end.
- Phase 39.1 inserted after Phase 39: Thread credential_id through drift_detection._enum_one + extend Phase 38.1 AST guard. Closes Phase 38.1 R6 regression surfaced in 38.1-VERIFICATION.md. Bisected to Phase 39 commit e05df24 (DRFT-17). (URGENT)

### Decisions

Full v1.0-v1.6 decision logs in `.planning/milestones/v{X.Y}-ROADMAP.md`. Key patterns established through v1.6 (carry forward into v1.7):

- **Keyring as single source of truth** for remote credentials (CRED-04). v1.7's drift integration must resolve through `resolve_ssh_credentials` / `resolve_proxmox_credentials`, never bypass with env vars or DB reads
- **`CredentialNotFoundError` with actionable pointer** instead of silent fallback (CRED-05) — v1.7 error messages should follow this pattern (`credentials add <hostname>` etc.), not env-var pointers
- **Cluster-scoped Proxmox tokens** with node→cluster→error precedence (CRED-08) — drift integration must respect this resolution order
- **Hostname-only sitemap upsert** with degenerate-hostname fallback (Phase 35) — drift baseline keys should follow the same convention
- **AST meta-tests as regression guard pattern** — class of bugs that no positive regression test catches (33.1 D-08 mcp_admin defaults, 35 D-14/D-15/D-16 hostname-only/timeout-wrapped/no-coercion). v1.7 should consider similar guards: Phase 36 candidate (no parallel-table reads on drift-scan call chain), Phase 38 candidate (every new probe `conn.run` is timeout-wrapped)
- **`_run_with_timeout(10s)` per-subprocess SSH probe wrapping** (Phase 35) — drift live-state probes (Phase 38, 39) must follow this pattern
- **`Semaphore(10) + asyncio.gather`** for bulk discovery (Phase 35) — drift bulk scans (Phase 39) should use the same fanout pattern
- **`contextlib.suppress(Exception)` around cleanup** — idempotent cleanup pattern; applies to drift baseline cleanup hooks on VM destroy
- **Wave-0 TDD pattern (RED tests before implementation)** — established v1.1, used through v1.6; expected for every v1.7 plan

Key constraints carried forward:

- `credential_store.py` must have no homelab_mcp imports — circular import prevention
- Every keyring call path must catch `NoKeyringError`, `RuntimeError`, and `Exception` — headless Linux primary deploy target
- `_sudo_run` helper is the only path for sudo invocation
- PyPI OIDC trusted publisher registered at pypi.org; `git tag v*` push triggers publish
- [Phase ?]: Phase 42-01: B1 fix uses (hostname, ssh_credential_id) tuple key for SSH probe map — preserves multi-credential attribution; B3 verified-already-done via three existing dedupe layers (no warm-up loop needed)
- [Phase ?]: Phase 42 complete after Plan 02 fixture migration

### Pending Todos

None at v1.7 ROADMAP-complete. Will be populated as phase planning progresses.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 5 | we are missing the new cli arguments for the keystore in the command line help output | 2026-03-15 | 88e972f | [5-we-are-missing-the-new-cli-arguments-for](./quick/5-we-are-missing-the-new-cli-arguments-for/) |
| 6 | update README and setup docs to reflect v1.3 (PyPI/uvx, credentials CLI, Python 3.12+) | 2026-03-15 | 1357903 | [6-update-readme-and-setup-docs-to-reflect-](./quick/6-update-readme-and-setup-docs-to-reflect-/) |
| 7 | fix ssh tool schemas so the model knows about keyring auto-inject | 2026-03-15 | d261600 | [7-fix-ssh-tool-schemas-so-the-model-knows-](./quick/7-fix-ssh-tool-schemas-so-the-model-knows-/) |

### Blockers/Concerns

- PyPI OIDC trusted publisher must remain registered at pypi.org/manage/project/homelab-mcp/settings/publishing/ for future `git tag v*` pushes
- **Phase 36 migration risk:** DRFT-21 drops the `drift_baselines` table without auto-migration. Pre-existing baseline rows are not reconciled — homelab single-user scope, mirrors v1.6 CRED-04 keyring migration. Document clearly in phase plan and release notes
- **Phase 38/39 live-test verifiability:** capability probes (GPU passthrough, Vulkan/ML availability) likely cannot be fully exercised in headless CI; expect manual verification on a real Proxmox host with a passthrough-capable GPU as part of milestone close

## Session Continuity

Last session: 2026-05-01T23:05:39.712Z
Stopped at: Completed 42-03-PLAN.md (gate re-run green post fixture migration; Phase 42 complete)
Resume command: `/gsd-verify-work 42` to run the Phase 42 verifier
