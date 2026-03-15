---
gsd_state_version: 1.0
milestone: v1.3
milestone_name: Credentials & Release Automation
status: Roadmap ready — begin with Phase 17
stopped_at: Completed 18-02-PLAN.md — Extend credential_store with credential_type param and JSON registry
last_updated: "2026-03-15T01:59:40.069Z"
last_activity: 2026-03-14 — v1.3 roadmap created (Phases 17-20)
progress:
  total_phases: 4
  completed_phases: 1
  total_plans: 4
  completed_plans: 3
  percent: 80
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-14)

**Core value:** Every tool in the server actually works — a Proxmox homelabber can install this, connect it to any MCP client, and reliably manage their infrastructure through AI.
**Current focus:** v1.3 — Credentials & Release Automation (Phase 17 next)

## Current Position

Phase: 17 — Credential Store Foundation (not started)
Plan: —
Status: Roadmap ready — begin with Phase 17
Last activity: 2026-03-14 — v1.3 roadmap created (Phases 17-20)

Progress: [████████░░] 80%

## Performance Metrics

**Velocity:**
- Total plans completed: 0 (v1.3, in progress)
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
| Phase 17-credential-store-foundation P01 | 25 | 2 tasks | 3 files |
| Phase 18-credentials-cli-version P01 | 4 | 2 tasks | 2 files |
| Phase 18-credentials-cli-version P02 | 1 | 1 tasks | 1 files |

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

Key constraints for v1.3 (from research):
- `credential_store.py` must have no homelab_mcp imports — circular import prevention
- Every keyring call path must catch `NoKeyringError`, `RuntimeError`, and `Exception` — headless Linux is the primary deploy target
- Never call keyring at module import time or during server startup — only at first lookup
- `parser.set_defaults(func=_run_server)` + `getattr(args, 'func', _run_server)(args)` dispatch pattern — prevents bare `homelab-mcp` regression
- `sanitize_error(e)` from `log_filter.py` in every except block touching credential values — prevents credential leak in logs
- PyPI OIDC trusted publisher must be manually registered at pypi.org before pushing any v* tag
- [Phase 17-credential-store-foundation]: Lazy import keyring inside each function body — prevents D-Bus probing during server startup
- [Phase 17-credential-store-foundation]: Assign keyring.get_password result to typed variable (str | None) to satisfy mypy warn_return_any
- [Phase 17-credential-store-foundation]: credential_store.py imports only stdlib logging — no homelab_mcp imports (circular import prevention, mirrors prompt_registry.py constraint)
- [Phase 18-credentials-cli-version]: Local import pattern inside test function bodies used for all new symbols — consistent with Phases 12-17 pattern
- [Phase 18-credentials-cli-version]: test_bare_invocation_starts_server is GREEN because bare invocation behavior already exists — guards against regression
- [Phase 18-credentials-cli-version]: Handler functions tested directly (_cmd_credentials_add/list/remove) via argparse.Namespace — avoids argparse dispatch complexity
- [Phase 18-credentials-cli-version]: type: ignore[return-value] in plan was wrong mypy code — corrected to no-any-return for json.loads Any return
- [Phase 18-credentials-cli-version]: _SERVICE_NAME string kept alongside _SERVICE_NAMES dict for backward compatibility

### Pending Todos

None.

### Blockers/Concerns

- PyPI OIDC trusted publisher setup (Phase 20) requires one-time manual step at pypi.org/manage/project/homelab-mcp/settings/publishing/ before the first production tag push
- PRMT-02 parameter mismatch carried from v1.2 — resolved in Phase 20

## Session Continuity

Last session: 2026-03-15T01:59:40.067Z
Stopped at: Completed 18-02-PLAN.md — Extend credential_store with credential_type param and JSON registry
Resume file: None
