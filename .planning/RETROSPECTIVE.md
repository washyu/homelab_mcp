# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — MVP

**Shipped:** 2026-03-11
**Phases:** 5 | **Plans:** 15 | **Tasks:** 30

### What Was Built
- MCP SDK migration with ResourceManager lifecycle and graceful shutdown
- Security hardening: SSH TOFU, Proxmox SSL, input validation, credential redaction
- Functional completeness: stub implementations, silent exception elimination, tool annotations (49 tools)
- MCP protocol compliance: logging notifications, Origin validation, localhost bind
- Full documentation: setup guide, tool reference, configuration reference

### What Worked
- Phase ordering (architecture → security → functionality → compliance → docs) was correct — each phase built cleanly on prior
- Gap closure pattern (02-04, 02-05) caught real wiring gaps that initial plans missed — verification loop works
- Defense-in-depth approach for input validation (centralized in ssh_connect + handler-level) covered more attack surface
- Schema files as source of truth for tool documentation prevented drift
- AST-based regression test for silent exception handlers prevents future regressions

### What Was Inefficient
- ResourceManager.proxmox_session was built but never wired to consumers — last-mile wiring missed across Phase 1
- Some ROADMAP.md plan checkboxes not consistently updated (mix of [x] and [ ] despite all being complete)
- Nyquist VALIDATION.md frontmatter never flipped to compliant=true post-execution — bookkeeping gap

### Patterns Established
- ToolError exception pattern for MCP isError compliance (leverages SDK auto-behavior)
- CredentialFilter on root logger + sanitize_error() at error response boundaries
- Pure ASGI middleware pattern for HTTP middleware (vs BaseHTTPMiddleware)
- progress.py module pattern to break circular imports in server → handler → module chains

### Key Lessons
1. Verification loops catch real gaps — Phase 2 needed two additional gap closure plans after initial verification found missing wiring
2. "Build infrastructure, wire it later" creates orphaned exports — FUNC-05 Proxmox session pooling infrastructure exists but was never consumed
3. Documentation phases benefit from parallel execution — no dependencies between docs files, both plans ran in Wave 1

### Cost Observations
- Model mix: orchestrator on opus, researchers/planners/executors/verifiers on sonnet
- Timeline: 3 days from project init to milestone completion
- Notable: 15 plans executed across 5 phases with minimal rework (only 2 gap closure plans needed)

---

## Milestone: v1.1 — Safety & Observability

**Shipped:** 2026-03-12
**Phases:** 6 | **Plans:** 16

### What Was Built
- Tech debt resolution: Proxmox shared session threading, HTTP API key auth, vm_providers structured errors
- MCP Resources protocol: list/read/subscribe with live Proxmox, SQLite, and SSH data sources
- Dry-run mode for all 6 destructive tools with structured `{mode, would_affect, risk_level, reversible}` contract
- Infrastructure drift detection: config drift (CPU/mem/net changed outside MCP) + state drift (offline VMs/services)
- `drift_baselines` SQLite table auto-updated after every successful mutation to prevent false positives
- `notifications/resources/list_changed` wired to discovery operations for MCP client cache coherence
- Mypy upgraded to v1.18.1 with asyncssh/aiohttp stubs — eliminated pre-commit hook workarounds

### What Worked
- Fixing tech debt (Phase 06) first before features was the right call — proxmox_session threading was a prerequisite for both Phase 09 (resource readers) and Phase 11 (drift detection)
- Wave-0 TDD scaffolding for Phase 11 worked cleanly — test files started RED, went GREEN as implementation landed
- Local import pattern for `get_resource_manager` (established Phase 06) was reused cleanly in Phases 09 and 11 without re-solving the circular import problem
- Phase 08 (Dry-Run) and Phase 07 (Resources Plumbing) running somewhat independently after Phase 06 — kept parallelism in the plan
- Audit at end confirmed all 22 requirements met without needing gap closure phases

### What Was Inefficient
- Multiple `--no-verify` commits early in the milestone (Phases 06-08) for pre-existing mypy errors — fixed properly in Phase 08-04 by upgrading mypy, but should have been addressed first
- Dry-run handlers returning flat dict instead of content-wrapped format — a design inconsistency caught in audit but not addressed; adds small cognitive load for future consumers
- Phase 10 verification had pytest timeout requiring asyncio.run() workaround — root cause not investigated
- SUMMARY files in Phase 09 used `dependency_graph` frontmatter format instead of `requirements-completed` field — caused partial status in 3-source audit matrix

### Patterns Established
- `session: aiohttp.ClientSession | None = None` optional parameter on all Proxmox API functions (backward-compatible extension)
- `MUTATING_TOOLS: frozenset[str]` constant for O(1) membership check before notification dispatch
- `UNIQUE(node, vmid, vm_type) + INSERT OR REPLACE` for SQLite upsert — no application-level conflict handling needed
- Wave-0 test stub pattern: create RED test stubs in Phase N-01, implement to GREEN in subsequent plans
- `try/except` swallowing baseline errors in mutation handlers — handler always returns result even if baseline update fails

### Key Lessons
1. Upgrade tooling early — the mypy version conflict was known in Phase 06 and deferred to Phase 08; fixing it earlier would have eliminated ~5 `--no-verify` workarounds
2. Response format consistency matters — dry-run returning a flat dict vs content-wrapped is a minor inconsistency now but grows as a footgun for future phases adding dry-run support
3. Test timeout investigation should happen at failure time, not deferred — Phase 10 pytest timeout was accepted and worked around rather than diagnosed
4. Phase 11 (most complex) ran cleanly because it had stable infrastructure from Phases 06-10 — phase ordering was correct

### Cost Observations
- Timeline: 2 days from roadmap creation to milestone complete (2026-03-11 → 2026-03-12)
- Notable: 22 requirements across 6 phases with zero gap closure phases needed — clean first-pass execution

---

## Milestone: v1.2 — Protocol Completeness

**Shipped:** 2026-03-13
**Phases:** 5 | **Plans:** 10

### What Was Built
- PyPI distribution: published `homelab-mcp` 1.2.0 — `uvx homelab-mcp` now works; version unified via `importlib.metadata`; service_templates YAML bundled via `importlib.resources`
- `homelab://drift/latest` MCP Resource with `notifications/resources/updated` push after each drift scan
- MCP Prompts capability with three workflow templates (decommission preview workflow, deploy service pre-flight, homelab health check)
- 6 `*_preview` tool variants with `readOnlyHint=True` so MCP clients skip confirmation dialogs; 56 total tools
- Full quality gate: ruff + mypy exit 0; 9 targeted bandit nosec annotations

### What Worked
- Wave-0 TDD pattern scaled well across 3 feature phases (13, 14, 15) — RED stubs in plan-01, GREEN in plan-02 was fast and caught the test structure before implementation
- Local import inside test function bodies pattern (established in v1.1) completely eliminated collection-level ImportError problems for not-yet-implemented symbols
- Thin delegation handlers for preview tools (3-line `return await handle_parent({**args, "dry_run": True})`) kept all dry-run logic centralized in parent handlers — zero duplication
- Deferred circular import pattern (import inside function body) correctly handled the `resource_readers ↔ server` circular dependency without restructuring
- Quality gate as final phase (16) was the right call — swept the entire src/ tree for issues introduced across all 4 prior phases in one pass

### What Was Inefficient
- Integration checker (run at audit time) caught a parameter mismatch in PRMT-02 that unit tests missed — `test_decommission_workflow_prompt` checked for the tool name but not that the example parameter matched the schema. A more thorough prompt test would have caught this earlier.
- SUMMARY.md files lack `requirements_completed` frontmatter — forced the 3-source audit cross-reference to fall back to VERIFICATION.md detail only; partial signal from source 2 throughout v1.2
- `gsd-tools milestone complete` CLI created archive files but left REQUIREMENTS.md and ROADMAP.md in place — the AI step to delete originals and rewrite ROADMAP.md is still fully manual. This is expected behavior per the workflow design but worth noting.

### Patterns Established
- `importlib.metadata.version("pkg")` with `PackageNotFoundError` fallback pattern for all version-reporting sites in a package
- `importlib.resources.files("pkg").joinpath("subdir")` for data file access in installed packages (replaces `__file__`-relative paths)
- `readOnlyHint=True` + delegation wrapper as the standard pattern for adding preview variants of destructive tools
- Frozenset constants (`DRIFT_SCAN_TOOLS`, `MUTATING_TOOLS`) for O(1) membership checks before notification dispatch
- PyPI publish workflow: `uv build` → `uv publish --token $PYPI_TOKEN` → confirm with `uvx homelab-mcp --help`

### Key Lessons
1. Prompt parameter alignment is a cross-cutting concern — verifying that a prompt's argument names match the tool schema it references requires an integration-level test, not just a string-contains unit test. Add this to future prompt test scaffolds.
2. SUMMARY.md `requirements_completed` frontmatter should be populated — the 3-source cross-reference degrades gracefully without it but loses early signal; either populate it during execution or acknowledge the gap per-milestone.
3. PyPI distribution is a one-time manual bootstrap — OIDC Trusted Publisher setup at pypi.org is required before CI can auto-publish. Doing it manually for v1.2 was correct; automate in v1.3+.
4. Quality gate as the last phase works well when the prior phases are disciplined about ruff/mypy during execution — Phase 16 had very little to fix because Phases 12-15 already kept the code clean.

### Cost Observations
- Timeline: 1 day (2026-03-13) — most compact milestone to date
- Notable: 5 phases, 10 plans, 56 tools shipped with zero gap closure phases needed; single integration mismatch (PRMT-02) found at audit but accepted as tech debt

---

## Milestone: v1.3 — Credentials & Release Automation

**Shipped:** 2026-03-15
**Phases:** 4 | **Plans:** 9

### What Was Built
- Headless-safe `credential_store.py` with OS keyring + JSON hostname registry; lazy function-body import pattern prevents D-Bus probing at startup
- `homelab-mcp credentials add/list/remove` CLI subcommands with secure password prompting; `--type proxmox` for Proxmox credentials
- `homelab-mcp --version` flag via `importlib.metadata`; `set_defaults` argparse dispatch preserved bare invocation behavior
- Credential auto-inject: Tier 2 keyring lookup in `resolve_ssh_credentials()` and keyring fallback in `get_proxmox_client()`; log-safe (password never appears in output)
- GitHub Actions OIDC trusted publishing — tag-gated, no stored secrets, gated on test-and-quality passing; version bumped to 1.3.0
- Fixed PRMT-02: 5-step decommission workflow resolves hostname→`device_id` via `get_network_sitemap` before calling `decommission_device`

### What Worked
- Wave-0 TDD pattern continued to scale — 4 of 9 plans were RED scaffold plans, all turned GREEN cleanly in subsequent plans
- Headless-safety design (lazy keyring import, catch-all error wrapping, startup-silent pattern) worked first time — no headless regressions
- `credential_store.py` with zero homelab_mcp imports (mirrors `prompt_registry.py` constraint) kept circular imports clean from day one
- Module-level imports in `ssh_tools.py`/`proxmox_api.py` for monkeypatch compatibility was a pragmatic tradeoff — test isolation preserved while lazy-import benefits kept in `credential_store.py` itself
- PRMT-02 fix was clean — integration checker had already identified the exact problem in v1.2 audit; fix required only prompt text change in `_build_decommission_result()`

### What Was Inefficient
- `gsd-tools milestone complete` CLI still leaves ROADMAP.md and REQUIREMENTS.md in place; the AI step to delete and rewrite ROADMAP.md remains fully manual — consistent with v1.2 observation
- Phase 18 plan execution required two small corrections to mypy annotation approach (`no-any-return` vs `return-value`); a sharper pre-plan type annotation review would have caught this
- Human-only verifiable items (TTY echo suppression, `homelab-mcp --version` in installed env) remain as tech debt — cannot be automated in headless CI

### Patterns Established
- Lazy keyring import inside each function body (not module level) — prevents D-Bus probing at server startup
- JSON hostname registry as enumerable sidecar to OS keyring — keyring stores secrets, registry stores the host list
- `_SERVICE_NAMES: dict[str, str]` for credential type namespacing with backward-compat `_SERVICE_NAME` string
- Module-level credential imports in consumer modules (`ssh_tools`, `proxmox_api`) for pytest-mock compatibility
- `parser.set_defaults(func=_run_server)` + `getattr(args, 'func', _run_server)(args)` dispatch for safe subparser addition
- OIDC trusted publishing: `permissions: id-token: write` at job level + `pypa/gh-action-pypi-publish@release/v1`; no `PYPI_TOKEN` secret needed

### Key Lessons
1. Circular import prevention patterns compound well — once established (`prompt_registry.py` has no homelab_mcp imports; `credential_store.py` mirrors the same constraint), new modules naturally follow the pattern
2. Monkeypatch compatibility and lazy imports are in tension — the resolution (lazy in the store, module-level in consumers) is the right split: credentials module stays safe, test harness stays capable
3. OIDC trusted publishing requires one-time manual setup at pypi.org before the first `git tag v*` push — document this in README before v1.4 or it will surprise future contributors
4. Prompt correctness (argument name matching tool schema) should be regression-tested with a dedicated integration assertion — the PRMT-02 bug survived v1.2 unit tests and was only caught by the integration checker

### Cost Observations
- Timeline: 1 day (2026-03-14 → 2026-03-15) — same pace as v1.2
- Notable: 15/15 audit score; zero gap closure phases needed; single-day execution of 4 phases × 9 plans

---

## Milestone: v1.4.1 — Security Patch

**Shipped:** 2026-04-01
**Phases:** 1 | **Plans:** 2

### What Was Built
- TOFU TOCTOU race condition closed — `threading.Lock` widened to cover entire check+store sequence in `validate_host_public_key` (SEC-02)
- Shell command injection eliminated in `setup_remote_mcp_admin` — SFTP-based tmpfile delivery replaces f-string key interpolation (SEC-01)

### What Worked
- Scoping down from full v1.5 (9 requirements) to v1.4.1 patch (2 security-critical) was the right call — ships the urgent fixes without blocking on 7 lower-severity items
- TDD pattern (RED tests → GREEN implementation) continued to hold for both plans
- SFTP tmpfile delivery pattern is clean and reusable — could apply to any future command that needs to pass untrusted content to remote hosts

### What Was Inefficient
- Phase 30 was originally scoped under v1.5 with Phases 31-32 planned but never created — the full v1.5 milestone definition was premature given the gap between security-critical (SEC-01/02) and correctness (SSH/ERR/QUAL) items
- Worktree-based execution had to adapt tests to the worktree's older API rather than main branch — delta between branches caused extra test adjustment work

### Patterns Established
- SFTP tmpfile delivery: write to local tmpfile → SFTP upload → remote commands read from file → finally cleanup both local and remote
- Caller-holds-lock: lock acquired at the method that does check-then-act; inner methods are dumb writers

### Key Lessons
1. Patch releases are valuable for shipping security fixes fast — don't block critical security fixes behind a full milestone of lower-severity items
2. SFTP-based content delivery is the correct pattern for passing untrusted content to remote hosts — eliminates an entire class of shell injection vulnerabilities

### Cost Observations
- Timeline: 1 day (2026-04-01) — fastest milestone
- Notable: 1 phase, 2 plans, 2 security findings closed; 7 deferred to next milestone

---

## Milestone: v1.4 — Real-World Reliability

**Shipped:** 2026-03-20
**Phases:** 9 | **Plans:** 16

### What Was Built
- SSH TOFU bug fixes: known_hosts comment field leak stripped; dead `asyncio.Lock` replaced with `threading.Lock`
- PTY interactive shell fixed: inverted dimensions (24×80 → 80×24), blocking read replaced with `asyncio.wait_for`, explicit `[Connection closed]` EOF notification
- `connect_to_device` onboarding prompt with keyring desync warning log
- Keyring auto-resolve for `setup_mcp_admin` and `update_mcp_admin_groups` — no explicit password required at call site
- `_sudo_run` helper with `sudo -S` stdin piping — eliminates shell injection and bootstrap timeout for password-based sudo
- Full tool schema sync: 7+ mismatches fixed (phantom `port`, SSH timeout, Proxmox hidden params)
- Prompt correctness fixes: `host=` → `hostname=`, phantom `list_installed_services` → `get_service_status`; regression guards added

### What Worked
- Milestone audit mid-way caught real E2E gaps that the original 5-phase scope would have missed — gap closure phases (26-29) extended the milestone but shipped a correct product
- Wave-0 TDD pattern continued to hold — RED assertions written before all fixes, GREEN confirmed implementation correctness
- `_sudo_run` abstraction was a clean extraction — all three call sites (setup, groups, ssh_execute_command) adopted it uniformly
- Regression guards (pytest assertions for `host=` absence, phantom tool absence) prevent exact-same bugs re-occurring silently; CI now owns that contract
- Schema sync + handler wiring tests together (Phases 26-27) treated as a paired phase — schema and behavior verified in lockstep

### What Was Inefficient
- Phases 26-29 were not in the original roadmap — they were discovered via audit after Phases 21-25 shipped. The 5 original phases fixed all real-world bugs but left tool schemas, prompt parameter names, and phantom prompt tools as accumulated drift. A pre-planning schema/prompt integrity check would have caught these before phase planning.
- SUMMARY.md `one_liner` frontmatter field remained empty across all phases — `gsd-tools summary-extract` cannot extract accomplishments without it; the CLI auto-populated empty accomplishments in MILESTONES.md. Requires manual correction at milestone close.
- Phase 25 SUMMARY.md accomplishments section was empty — the summary file was committed without filling in the key bullets. Pattern: summary file structure created but content not fully populated.

### Patterns Established
- `_sudo_run(conn, cmd, password, error_prefix)` helper — single point for all `sudo -S` stdin piping; centralizes error classification
- `asyncio.wait_for(stdout.read(1), timeout=0.05)` non-blocking PTY read pattern — tunable, replaces blocking `read(4096)`
- `threading.Lock()` for synchronous TOFU callback — `asyncio.Lock` cannot be acquired from sync callbacks in asyncssh
- Paired schema+test phases: fix schema in phase N, add handler wiring and regression guard tests in phase N+1
- Regression guard pattern: `assert "bad_token" not in prompt_text` at test suite level blocks future drift via CI

### Key Lessons
1. Milestone audit is valuable mid-scope, not just post-completion — the v1.4 audit found gaps that would have left deploy and onboarding workflows broken; treating audit gaps as first-class phases is the right response
2. Prompt parameter correctness is a system property, not a unit property — prompt text uses parameter names that tool schemas must match; add cross-reference tests as part of any new prompt's test scaffold
3. Schema drift accumulates silently — 7+ mismatches between inputSchema and function signatures existed across 4 modules with zero failures because MCP silently ignores undeclared params. A periodic schema integrity check should be part of quality gate or CI.
4. SUMMARY.md completeness matters for downstream tooling — `gsd-tools summary-extract` and milestone CLI depend on structured frontmatter; empty `one_liner` fields are a recurring friction point at milestone close
5. Paired fix+test phases are more reliable than fix phases alone — Phase 26 (schema fix) without Phase 27 (regression tests) would leave the fixes undocumented and easy to accidentally revert

### Cost Observations
- Timeline: 5 days (2026-03-15 → 2026-03-19) — longest v1.x milestone due to 4 audit gap closure phases
- Notable: 9 phases (5 planned + 4 gap closure); all 23 requirements met; all 4 prompts now have correct parameter names and no phantom tool references

---

## Milestone: v1.5 — Critical Bug Fixes

**Shipped:** 2026-04-20
**Phases:** 2 | **Plans:** 7

### What Was Built
- 5 CodeRabbit PR #39 critical/high findings closed in Phase 31 (WS-01, ERR-01, SSH-01, SSH-02, SCH-01)
- 5 revert-proof regression tests in Phase 32 across `test_http_app.py`, `test_ssh_tools.py`, `test_error_handling.py`, `test_tools.py`
- AST meta-guard for tautological-assertion detection (extended in 32-05 gap closure to catch `Compare(Constant in X)` form)
- `_sudo_run` helper with consistent `check=` forwarding across both sudo auth branches
- `contextlib.suppress(Exception)` pattern for idempotent websocket cleanup

### What Worked
- Integration checker caught Phase 31 SUMMARY-only merge before it reached the close gate — the audit step's `tech_debt` verdict (vs `passed`) accurately surfaced the missing VERIFICATION.md without blocking a sound functional result
- Revert-proof regression tests made the missing Phase-31 VERIFICATION.md an acceptable debt item rather than a risk — the test suite itself proves each fix's behavior change under the revert-then-test experiment
- 32-02 → 32-05 scope gap closure worked cleanly: AST detector's initial form missed the `d25c915` pre-fix mutation shape, D-05 mutation experiment surfaced it, 32-05 extended the detector in a single plan
- Inline ROADMAP reconcile (Path B of `/gsd-plan-milestone-gaps`) avoided creating a Phase 33 "tech debt cleanup" phase for 3 one-line edits — kept the milestone close fast without sweeping problems under the rug

### What Was Inefficient
- Phase 31 shipped without running the phase-level verifier gate — merged on plan-SUMMARY evidence alone; a one-command gate step was skipped
- Both v1.5 VALIDATION.md (Nyquist) files incomplete: 31 is `status: draft`, 32 is absent entirely — Nyquist bookkeeping drifted further from the spec in this milestone
- SUMMARY frontmatter shape inconsistency between 32-01 (flat `requirements-completed: [...]`) and 32-02..05 (nested `requirements:`) — both parse but extraction is non-uniform; this has been a recurring pattern (see v1.1 Phase 09 note) and should be fixed at the template level rather than per-milestone
- 7 quick-task audit-open false positives flagged at milestone close — the tool's `status: missing` heuristic doesn't match the actual PLAN.md/SUMMARY.md convention; noise that requires human triage every close

### Patterns Established
- AST meta-tests as lint-style regression guards — parse the test file itself and walk the AST for tautological patterns; catches a class of bugs that positive regression tests can't
- `contextlib.suppress(Exception)` around idempotent cleanup calls — cleaner than try/except, matches module's existing contextlib usage
- Quoted return annotations (`'ClassName'`) for non-subscriptable third-party types — defers evaluation under both mypy and runtime
- Report computed/derived values in error messages (not raw decorator parameters) — users see the actual constraint they were subject to

### Key Lessons
1. **Phase-level verifier gate is not optional** — Phase 31 shipped without it and the milestone audit had to use Phase-32 integration evidence as a compensating control; the debt was acceptable *this time* because regressions were revert-proof, but the next bug-fix milestone must run the verifier before Phase 32 starts
2. **`tech_debt` as a distinct audit verdict is useful** — it's the right answer when functional coverage is sound but process gates are missing; forces an explicit "acknowledge or fix" decision at milestone close rather than a binary pass/fail
3. **Inline reconcile beats a cleanup phase for 3-line bookkeeping fixes** — `/gsd-plan-milestone-gaps` Path B saved a whole phase lifecycle for what was a 2-minute edit
4. **Revert-proof regression tests are a valid compensating control** for a missing phase VERIFICATION.md — but only when the integration checker confirms 0 broken/0 weak wirings; a weaker-wired milestone wouldn't get this free pass

### Cost Observations
- Model mix: orchestrator on opus, executors on sonnet (standard pattern)
- Timeline: 19 days elapsed (Apr 2-20) but active work was concentrated in 2 days (Apr 19-20)
- Notable: Phase 32 shipped 5 plans including a mid-phase scope gap-closure (32-05) inside the same day — gap closure workflow worked well at the plan level, not just the milestone level

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 | 5 | 15 | Initial milestone — established verification loop, gap closure, and documentation patterns |
| v1.1 | 6 | 16 | Tech-debt-first ordering; Wave-0 TDD scaffolding; audit confirmed 0 gaps needed |
| v1.2 | 5 | 10 | PyPI distribution; full MCP protocol surface; integration checker found cross-phase param mismatch |
| v1.3 | 4 | 9 | Credential store + CLI; OIDC auto-publish; PRMT-02 fix; monkeypatch/lazy-import tension resolved |
| v1.4 | 9 | 16 | Real-world reliability: TOFU fix, PTY fix, sudo piping, schema sync, prompt correctness; 4 audit gap phases |
| v1.4.1 | 1 | 2 | Security patch: SFTP key delivery (SEC-01), TOFU lock widening (SEC-02); scoped down from v1.5 |
| v1.5 | 2 | 7 | Bug-fix-only milestone from CodeRabbit PR #39; revert-proof regressions + AST meta-guards; `tech_debt` close (first time) — Phase-31 VERIFICATION.md gate skipped, debt acknowledged |

### Cumulative Quality

| Milestone | Tests | Key Metric |
|-----------|-------|------------|
| v1.0 | 479 | 19/19 requirements satisfied, 5/5 E2E flows verified |
| v1.1 | ~500+ | 22/22 requirements satisfied, 6/6 E2E flows, 0 gap closure phases |
| v1.2 | 603 | 20/20 requirements satisfied (18 full, 2 partial), 1 integration semantic mismatch in tech debt |
| v1.3 | ~620+ | 15/15 requirements satisfied, 4/4 E2E flows, 0 gap closure phases; PRMT-02 tech debt resolved |
| v1.4 | ~650+ | 23/23 requirements satisfied; 4 audit gap phases added mid-milestone; all prompts correct |
| v1.4.1 | ~650+ | 2/2 security requirements satisfied; 7 deferred; patch release model validated |
| v1.5 | ~660+ | 6/6 requirements functionally satisfied (5 via partial traceability through Phase-32 integration); 5/5 revert-proof flows; 4 bookkeeping items deferred as `tech_debt` |

### Top Lessons (Verified Across Milestones)

1. Verification loops are essential — they caught 2 real gaps in v1.0 that would have shipped as bugs
2. Phase ordering matters — security after architecture (v1.0); tech debt before features (v1.1); quality gate last (v1.2)
3. Upgrade tooling when first encountered — deferring mypy upgrade from Phase 06 to Phase 08 added friction across 3 phases
4. "Build infrastructure, wire it later" fails — v1.0 proxmox_session was orphaned; v1.1 fixed it by treating tech debt as Phase 1
5. Integration-level tests required for cross-phase contracts — unit tests verify individual components; integration checker is the only thing that caught the PRMT-02 parameter mismatch across Phase 14 and Phase 15
6. Milestone audit as mid-milestone gate is worth scheduling — v1.4 audit found schema/prompt drift that wouldn't have been caught otherwise; 4 gap phases was the right response vs deferring to v1.5
7. Patch releases for security-critical fixes — don't bundle urgent security fixes with lower-severity items; v1.4.1 shipped SEC-01/SEC-02 in one day while v1.5 full scope would have taken much longer
8. **Phase-level VERIFICATION.md gate is not optional** (v1.5) — Phase 31 shipped without one; closed as `tech_debt` on Phase-32 integration evidence, but the workflow should block phase merge until the gate runs
9. **`tech_debt` audit verdict is a feature, not a bug** (v1.5) — distinct from `passed` and `gaps_found`; forces explicit acknowledge/resolve decision at milestone close when functional coverage is sound but process gates are missing
10. **Inline reconcile for one-line bookkeeping drift** (v1.5) — `/gsd-plan-milestone-gaps` Path B beats creating a cleanup phase when the gap is 3 edits; reserve phase creation for real work
