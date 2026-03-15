---
phase: 18-credentials-cli-version
plan: "03"
subsystem: cli
tags: [argparse, credentials, keyring, version-flag, subparsers]

# Dependency graph
requires:
  - phase: 18-02
    provides: credential_store with credential_type param, list/store/delete/register/unregister functions
  - phase: 18-01
    provides: failing test scaffold for credentials CLI commands
provides:
  - homelab-mcp --version flag that prints installed version and exits 0
  - homelab-mcp credentials add/list/remove subcommands
  - _cmd_credentials_add, _cmd_credentials_list, _cmd_credentials_remove handler functions in server.py
  - _run_stdio_wrapper encapsulating stdio/HTTP dispatch for set_defaults pattern
affects: [19-release-automation, 20-pypi-publish]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "argparse set_defaults(func=_run_stdio_wrapper) ensures bare invocation starts server"
    - "getattr(args, 'func', fallback)(args) dispatch allows subcommands without breaking default"
    - "Module-level credential_store imports enable monkeypatching in tests"
    - "argparse imported at module level to satisfy mypy for handler function type annotations"

key-files:
  created: []
  modified:
    - src/homelab_mcp/server.py

key-decisions:
  - "Import credential_store functions at module level (not inside function bodies) to support test monkeypatching via homelab_mcp.server.* namespace"
  - "Use dest='hostname'/'username'/'credential_type' in argparse to match test Namespace expectations"
  - "Import argparse at module level to satisfy mypy type checking for handler function signatures"

patterns-established:
  - "set_defaults + getattr dispatch: ensures backward compat when adding subcommands to existing CLI"
  - "Module-level imports for test patchability: functions accessed via monkeypatch must be module-level names"

requirements-completed: [CRED-01, CRED-02, CRED-03, CRED-04, CRED-05, CRED-06, CLI-01]

# Metrics
duration: 2min
completed: 2026-03-15
---

# Phase 18 Plan 03: CLI Handlers and --version Flag Summary

**argparse subcommands for credentials add/list/remove with --version flag, dispatched via set_defaults pattern in server.py main()**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-15T02:00:24Z
- **Completed:** 2026-03-15T02:02:00Z
- **Tasks:** 2 (combined into 1 commit due to simultaneous file changes)
- **Files modified:** 1

## Accomplishments
- Added `homelab-mcp --version` flag using argparse `action="version"` with `_get_version()`
- Added `credentials add/list/remove` subparsers with `--type ssh|proxmox` support
- Added `_run_stdio_wrapper` function and `set_defaults` pattern ensuring bare invocation unchanged
- Added `_cmd_credentials_add/list/remove` handler functions — all 12 CLI tests GREEN
- Full unit suite (630 tests) GREEN; ruff, mypy, bandit all clean

## Task Commits

1. **Task 1+2: --version flag, subparsers, handler functions** - `999678d` (feat)

**Plan metadata:** (docs commit below)

## Files Created/Modified
- `src/homelab_mcp/server.py` - Added argparse at module level, credential_store imports, 4 new functions (_cmd_credentials_add/list/remove, _run_stdio_wrapper), --version flag, subparsers, set_defaults dispatch

## Decisions Made
- Imported credential_store functions at module level rather than inside function bodies — the test monkeypatches `homelab_mcp.server.store_credential` etc., which requires them to be module-level names
- Used `dest="hostname"/"username"/"credential_type"` in argparse arguments to match the `argparse.Namespace` attribute names expected by the test fixture
- Added `argparse` to module-level imports (was previously only a local import in `main()`) to satisfy mypy for handler function type annotations

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Argparse dest names corrected to match test expectations**
- **Found during:** Task 1 (reading test file before writing code)
- **Issue:** Plan specified `add_p.add_argument("host")` and `dest="type"` but tests use `args.hostname`, `args.username`, `args.credential_type`
- **Fix:** Used `add_p.add_argument("hostname")`, `add_p.add_argument("username")`, `--type ... dest="credential_type"` to match test Namespace
- **Files modified:** src/homelab_mcp/server.py
- **Verification:** All 12 test_credentials_cli.py tests GREEN
- **Committed in:** 999678d

**2. [Rule 2 - Missing Critical] Module-level imports for monkeypatching**
- **Found during:** Task 1 (reading test monkeypatch targets)
- **Issue:** Plan specified local imports inside function bodies, but tests patch `homelab_mcp.server.store_credential` etc. — impossible to patch if imported locally
- **Fix:** Added `from .credential_store import delete_credential, list_credentials, register_credential, store_credential, unregister_credential` at module level
- **Files modified:** src/homelab_mcp/server.py
- **Verification:** All 12 test_credentials_cli.py tests GREEN; mypy clean
- **Committed in:** 999678d

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical for testability)
**Impact on plan:** Both corrections required for tests to pass. No scope creep.

## Issues Encountered
- ruff format auto-fixed list comprehension line length on first commit attempt; re-staged and recommitted successfully.

## Next Phase Readiness
- All Phase 18 requirements complete (CRED-01 through CRED-06, CLI-01)
- Credentials CLI fully functional for SSH and Proxmox credential types
- Ready for Phase 19 (release automation) or Phase 20 (PyPI publish)

---
*Phase: 18-credentials-cli-version*
*Completed: 2026-03-15*
