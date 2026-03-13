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

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 | 5 | 15 | Initial milestone — established verification loop, gap closure, and documentation patterns |
| v1.1 | 6 | 16 | Tech-debt-first ordering; Wave-0 TDD scaffolding; audit confirmed 0 gaps needed |
| v1.2 | 5 | 10 | PyPI distribution; full MCP protocol surface; integration checker found cross-phase param mismatch |

### Cumulative Quality

| Milestone | Tests | Key Metric |
|-----------|-------|------------|
| v1.0 | 479 | 19/19 requirements satisfied, 5/5 E2E flows verified |
| v1.1 | ~500+ | 22/22 requirements satisfied, 6/6 E2E flows, 0 gap closure phases |
| v1.2 | 603 | 20/20 requirements satisfied (18 full, 2 partial), 1 integration semantic mismatch in tech debt |

### Top Lessons (Verified Across Milestones)

1. Verification loops are essential — they caught 2 real gaps in v1.0 that would have shipped as bugs
2. Phase ordering matters — security after architecture (v1.0); tech debt before features (v1.1); quality gate last (v1.2)
3. Upgrade tooling when first encountered — deferring mypy upgrade from Phase 06 to Phase 08 added friction across 3 phases
4. "Build infrastructure, wire it later" fails — v1.0 proxmox_session was orphaned; v1.1 fixed it by treating tech debt as Phase 1
5. Integration-level tests required for cross-phase contracts — unit tests verify individual components; integration checker is the only thing that caught the PRMT-02 parameter mismatch across Phase 14 and Phase 15
