---
phase: 12-pypi-distribution
plan: "02"
subsystem: packaging
tags: [pypi, importlib-metadata, entry-point, argparse, uv, version-management]

requires:
  - phase: 12-pypi-distribution plan 01
    provides: Wave 0 failing test scaffold (test_packaging.py with 4 RED tests)

provides:
  - homelab-mcp package name (renamed from homelab-mcp-server)
  - version 1.2.0 as single source of truth in pyproject.toml
  - importlib.metadata-backed __version__ in __init__.py
  - _get_version() helper in server.py for dynamic version at Server() init
  - main() console script entry point in server.py
  - _run_stdio() async helper for stdio mode
  - src/homelab_mcp/__main__.py for python -m homelab_mcp support
  - Dynamic version in http_app.py and http_transport.py

affects:
  - 12-03 (YAML template loading - depends on package identity being correct)
  - CI/PyPI publish workflow (package name change affects uvx install URL)

tech-stack:
  added: []
  patterns:
    - "importlib.metadata.version() with try/except PackageNotFoundError for version lookup"
    - "_get_version() module-level helper pattern for deferred version resolution"
    - "main() console script entry point with argparse + asyncio.run() dispatch"

key-files:
  created:
    - src/homelab_mcp/__main__.py
  modified:
    - pyproject.toml
    - src/homelab_mcp/__init__.py
    - src/homelab_mcp/server.py
    - src/homelab_mcp/http_app.py
    - src/homelab_mcp/http_transport.py

key-decisions:
  - "Package renamed from homelab-mcp-server to homelab-mcp (enables uvx homelab-mcp)"
  - "Version bumped to 1.2.0 matching v1.2 milestone"
  - "importlib.metadata used in all four locations eliminating hardcoded version strings"
  - "_get_pkg_version() inline helper in http_app.py; inline try/except in http_transport.py (deprecated file)"

patterns-established:
  - "importlib.metadata version pattern: try/except PackageNotFoundError -> fallback 'unknown'"
  - "main() entry point imports argparse/asyncio/os/sys locally (not at module level)"
  - "HTTP mode dispatch via uvicorn.Server.serve(), stdio mode via _run_stdio()"

requirements-completed: [PKG-01, PKG-02]

duration: 15min
completed: 2026-03-13
---

# Phase 12 Plan 02: Package Rename, Version Unification, and Entry Point Summary

**Package renamed to homelab-mcp, version bumped to 1.2.0, importlib.metadata replaces all four hardcoded version strings, main() entry point and __main__.py added — all 4 packaging tests turn GREEN**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-13T19:00:00Z
- **Completed:** 2026-03-13T19:15:00Z
- **Tasks:** 2
- **Files modified:** 6 (5 modified + 1 created)

## Accomplishments

- Renamed package from `homelab-mcp-server` to `homelab-mcp` and bumped version to 1.2.0 in pyproject.toml
- Eliminated all 4 hardcoded version strings across src/ by using `importlib.metadata.version("homelab-mcp")` with consistent try/except pattern
- Implemented `main()` console script entry point with full argparse CLI (--http, --host, --port, --no-auth, --api-key, --ssl-cert, --ssl-key) mirroring run_server.py behavior
- Created `src/homelab_mcp/__main__.py` enabling `python -m homelab_mcp --help`
- All 4 tests in test_packaging.py turned GREEN; full unit suite (551 tests) still passes

## Task Commits

Each task was committed atomically:

1. **Task 1: Rename package, bump version, unify version strings, add main() and __main__.py** - `45b6273` (feat)
2. **Task 2: Verify full test suite still passes after rename** - no new files; verified 551 tests pass GREEN (no commit needed)

## Files Created/Modified

- `pyproject.toml` - name changed to homelab-mcp, version bumped to 1.2.0
- `src/homelab_mcp/__init__.py` - replaced `__version__ = "0.1.0"` with importlib.metadata lookup
- `src/homelab_mcp/server.py` - added importlib import, `_get_version()` helper, dynamic `Server()` init, `main()` + `_run_stdio()` functions
- `src/homelab_mcp/http_app.py` - added importlib import and `_get_pkg_version()` helper, replaced hardcoded version
- `src/homelab_mcp/http_transport.py` - added importlib import, replaced hardcoded version with inline try/except
- `src/homelab_mcp/__main__.py` (NEW) - delegates to `homelab_mcp.server.main`

## Decisions Made

- Used a named `_get_pkg_version()` helper in `http_app.py` (active code path) for cleanliness; used inline try/except in `http_transport.py` because that module is deprecated/retained for reference only
- `main()` imports `argparse`, `asyncio`, `os`, `sys` locally to avoid adding module-level imports that would slow down server startup when not using the CLI path

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Pre-commit ruff hooks reformatted `server.py` (reordered local imports in `main()` — `import uvicorn` moved before `from homelab_mcp.http_app import create_http_app`). Required re-staging and second commit attempt; both passed cleanly.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- PKG-01 and PKG-02 requirements complete; `uvx homelab-mcp` entry point ready
- Plan 03 (PKG-03: importlib.resources for YAML templates) is next and unblocked
- One pre-existing blocker remains: PyPI Trusted Publisher (OIDC) one-time setup at pypi.org needed before publish

## Self-Check: PASSED

- FOUND: src/homelab_mcp/__main__.py
- FOUND: src/homelab_mcp/server.py
- FOUND: pyproject.toml
- FOUND: .planning/phases/12-pypi-distribution/12-02-SUMMARY.md
- FOUND commit: 45b6273

---
*Phase: 12-pypi-distribution*
*Completed: 2026-03-13*
