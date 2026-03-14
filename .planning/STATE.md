---
gsd_state_version: 1.0
milestone: v1.3
milestone_name: Credentials & Release Automation
status: defining_requirements
stopped_at: null
last_updated: "2026-03-14T00:00:00.000Z"
last_activity: 2026-03-14 — Milestone v1.3 started
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-13)

**Core value:** Every tool in the server actually works — a Proxmox homelabber can install this, connect it to any MCP client, and reliably manage their infrastructure through AI.
**Current focus:** Planning v1.3 milestone

## Current Position

Phase: — (between milestones)
Plan: —
Status: Defining requirements
Last activity: 2026-03-14 — Milestone v1.3 started

Progress: [████████░░] 80%

## Performance Metrics

**Velocity:**
- Total plans completed: 0 (v1.2)
- Average duration: — min
- Total execution time: — hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 12-pypi-distribution P01 | 4 | 2 tasks | 2 files |
| Phase 12-pypi-distribution P02 | 15 | 2 tasks | 6 files |
| Phase 12-pypi-distribution P03 | 8 | 2 tasks | 4 files |
| Phase 12-pypi-distribution P03 | 45 | 3 tasks | 4 files |
| Phase 13-drift-resource P01 | 2 | 1 tasks | 1 files |
| Phase 13-drift-resource P02 | 132 | 2 tasks | 3 files |
| Phase 14-mcp-prompts P01 | 1 | 1 tasks | 1 files |
| Phase 14-mcp-prompts P02 | 4 | 2 tasks | 3 files |
| Phase 15-preview-tool-split P01 | 2 | 2 tasks | 2 files |
| Phase 15-preview-tool-split P02 | 4 | 2 tasks | 12 files |
| Phase 16-quality-gate P01 | 8 | 2 tasks | 4 files |

## Accumulated Context

### Decisions

Full v1.0 decision log in `.planning/milestones/v1.0-ROADMAP.md`.
Full v1.1 decision log in `.planning/milestones/v1.1-ROADMAP.md`.

Key architectural patterns carried into v1.2:
- Local import of `get_resource_manager` inside handler functions (not module level) — avoids circular import
- `build_dry_run_response()` returns flat dict; `_convert_result` fallback handles MCP wrapping
- `MUTATING_TOOLS: frozenset[str]` for O(1) membership check before notification dispatch
- New modules stay thin — business logic in dedicated modules, `server.py` is registration hub only
- `INSERT OR REPLACE` + UNIQUE constraint for SQLite upsert (established in drift_baselines, extend for drift_latest_report)
- [Phase 12-pypi-distribution]: Wave 0 tests are intentionally RED at commit time -- correctness verified by pytest --collect-only
- [Phase 12-pypi-distribution]: PKG-03 patch target: homelab_mcp.service_installer.files (importlib.resources.files as imported), replacing src.homelab_mcp.service_installer.TEMPLATES_DIR
- [Phase 12-pypi-distribution]: Package renamed from homelab-mcp-server to homelab-mcp (enables uvx homelab-mcp)
- [Phase 12-pypi-distribution]: importlib.metadata version pattern with try/except PackageNotFoundError -> fallback 'unknown' used in all 4 locations
- [Phase 12-pypi-distribution]: main() entry point imports argparse/asyncio/os/sys locally to avoid module-level import overhead on server startup
- [Phase 12-pypi-distribution]: Patch target for importlib.resources.files must be src.homelab_mcp.service_installer.files due to dual module path in sys.modules when ServiceInstaller imported via src. prefix
- [Phase 12-pypi-distribution]: _make_files_mock(dict) helper pattern established for multi-template mocking in tests replacing TEMPLATES_DIR patch approach
- [Phase 12-pypi-distribution]: homelab-mcp 1.2.0 published to PyPI; uvx homelab-mcp --help confirmed working from PyPI index — PKG-03 complete
- [Phase 13-drift-resource]: Wave 0 tests use local imports inside test function bodies — avoids collection-level ImportError for symbols not yet implemented
- [Phase 13-drift-resource]: test_drift_resource_notification checks DRIFT_SCAN_TOOLS membership instead of MCP session mocking — simpler and sufficient for verifying DRFT-10 wiring constant
- [Phase 13-drift-resource]: set_latest_drift_report accepts None to support test teardown — widens signature from dict to dict|None
- [Phase 13-drift-resource]: server.py and resource_readers.py committed together because mypy pre-commit hook requires both when server.py imports read_drift_resource
- [Phase 14-mcp-prompts]: Wave 0 tests use local imports inside test function bodies — avoids collection-level ImportError for prompt_registry.py not yet implemented
- [Phase 14-mcp-prompts]: Plain def (non-async) test functions throughout — get_prompt_result is synchronous
- [Phase 14-mcp-prompts]: prompt_registry.py imports only mcp.types/mcp.shared.exceptions — no homelab_mcp imports (circular import prevention)
- [Phase 14-mcp-prompts]: HOMELAB_PROMPTS is dict[str, types.Prompt] keyed by name; @server.list_prompts() registration auto-advertises PromptsCapability
- [Phase 15-preview-tool-split]: Wave 0 tests use local imports inside test function bodies — avoids collection-level ImportError (consistent with Phase 13/14 pattern)
- [Phase 15-preview-tool-split]: test_preview_tool_schema_has_no_dry_run_param uses pytest.skip() rather than ERROR when schema not present — keeps test RED not ERROR
- [Phase 15-preview-tool-split]: Preview handlers inject dry_run=True transparently — callers never set it and schemas never expose it
- [Phase 15-preview-tool-split]: Delegation pattern keeps preview handler logic to 3 lines; all dry-run logic lives in the parent handler
- [Phase 16-quality-gate]: Use list syntax ["psycopg2", "psycopg2.*"] in mypy override — single string does not suppress submodule imports
- [Phase 16-quality-gate]: nosec annotations are inline with specific B-code and justification comment — not bare nosec, not on the line above
- [Phase 16-quality-gate]: Do NOT install types-psycopg2 stubs — psycopg2 is optional soft-dependency; false coverage risk

### Pending Todos

None.

### Blockers/Concerns

None for v1.3 — v1.2 shipped cleanly. Tech debt from v1.2:
- PRMT-02: decommission_device_workflow prompt uses hostname= but tool needs device_id= (see v1.2-MILESTONE-AUDIT.md)

## Session Continuity

Last session: 2026-03-13T22:06:11.022Z
Stopped at: Completed 16-quality-gate Plan 01 — all three quality gates (ruff, mypy, bandit) passing cleanly
Resume file: None
