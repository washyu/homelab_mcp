---
phase: 18-credentials-cli-version
plan: "01"
subsystem: testing
tags: [pytest, tdd, keyring, credentials, cli, argparse]

# Dependency graph
requires:
  - phase: 17-credential-store-foundation
    provides: credential_store.py with store_credential, get_credential, delete_credential
provides:
  - TDD test scaffold for Phase 18 credential CLI and --version behaviors (Wave 0 RED tests)
  - tests/test_credential_store.py extended with 6 failing tests for registry + credential_type extensions
  - tests/test_credentials_cli.py with 12 failing tests for CLI commands and --version flag
affects:
  - 18-02 (credential_store.py extensions implementation — tests define the contracts)
  - 18-03 (server.py CLI implementation — tests define expected behavior)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Wave 0 TDD RED tests committed before implementation — all imports inside function bodies via local import pattern
    - monkeypatch.setattr for patching module-level attributes not yet created (avoids collection-level ImportError)
    - TYPE_CHECKING guard for pytest/pytest_mock type annotations in test files

key-files:
  created:
    - tests/test_credentials_cli.py
  modified:
    - tests/test_credential_store.py

key-decisions:
  - "Local import pattern inside test function bodies used for all homelab_mcp symbols that do not exist yet — consistent with Phases 12-17 pattern"
  - "test_bare_invocation_starts_server is GREEN (not RED) because bare invocation behavior already exists — this is correct; the test guards against regression"
  - "Handler functions tested directly (_cmd_credentials_add/list/remove) via argparse.Namespace — avoids argparse dispatch complexity in tests"
  - "TYPE_CHECKING guard used for pytest/pytest_mock type annotations to satisfy ruff F821 without runtime overhead"

patterns-established:
  - "Wave 0 tests use local imports inside test function bodies — avoids collection-level ImportError (consistent with Phase 13/14/15/17 pattern)"

requirements-completed: [CRED-01, CRED-02, CRED-03, CRED-04, CRED-05, CRED-06, CLI-01]

# Metrics
duration: 4min
completed: 2026-03-15
---

# Phase 18 Plan 01: Credentials CLI + --version Wave 0 Test Scaffold Summary

**18 failing RED tests establishing TDD contracts for credential registry functions, credential_type parameter, and CLI commands (add/list/remove for ssh and proxmox) before any implementation**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-15T01:51:28Z
- **Completed:** 2026-03-15T01:55:30Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Extended `tests/test_credential_store.py` with 6 RED tests for Phase 18 credential_store extensions (register_credential, unregister_credential, list_credentials, credential_type parameter)
- Created `tests/test_credentials_cli.py` with 12 test cases covering all CLI behaviors: add/list/remove for ssh and proxmox types, --version flag, and bare invocation
- All 17 Phase 18 RED tests fail with expected errors (AttributeError, ImportError, TypeError), confirming implementation does not exist yet
- All 613 Phase 17 and earlier tests remain GREEN

## Task Commits

Each task was committed atomically:

1. **Task 1: Write failing tests for credential_store registry + credential_type extensions** - `e358eed` (test)
2. **Task 2: Write failing tests for credentials CLI commands and --version flag** - `a3bfebd` (test)

## Files Created/Modified
- `tests/test_credential_store.py` - Extended with 6 RED tests for registry + credential_type extensions
- `tests/test_credentials_cli.py` - Created with 12 RED tests for CLI commands and --version flag

## Decisions Made
- Local import pattern inside test function bodies used for all homelab_mcp symbols that do not exist yet — consistent with Phases 12-17 pattern
- `test_bare_invocation_starts_server` is GREEN (not RED) because bare invocation behavior already exists in the current server; this is correct — it guards against regression rather than testing new code
- Handler functions tested directly (`_cmd_credentials_add`, `_cmd_credentials_list`, `_cmd_credentials_remove`) via `argparse.Namespace` objects — avoids argparse dispatch complexity in tests and follows plan's preferred approach
- `TYPE_CHECKING` guard used for `pytest` and `pytest_mock` type annotations to satisfy ruff F821 without runtime overhead

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ruff F821 undefined name errors in test type annotations**
- **Found during:** Task 1 (commit attempt)
- **Issue:** Used string-quoted `pytest.MonkeyPatch` and `pytest_mock.MockerFixture` in type annotations with `from __future__ import annotations` but `pytest`/`pytest_mock` were not imported
- **Fix:** Added `from typing import TYPE_CHECKING` guard with `import pytest` and `import pytest_mock` under `if TYPE_CHECKING:` block
- **Files modified:** tests/test_credential_store.py
- **Verification:** `ruff check tests/test_credential_store.py` returned clean
- **Committed in:** e358eed (Task 1 commit)

**2. [Rule 1 - Bug] Fixed ruff I001 import sort order in test_credentials_cli.py**
- **Found during:** Task 2 (commit attempt)
- **Issue:** Ruff isort required blank line between stdlib and third-party imports
- **Fix:** Removed TYPE_CHECKING block (unused), applied `ruff check --fix` for import ordering
- **Files modified:** tests/test_credentials_cli.py
- **Verification:** `ruff check tests/test_credentials_cli.py` returned clean
- **Committed in:** a3bfebd (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 - lint/style)
**Impact on plan:** Minor style fixes only. No functional impact on test contracts.

## Issues Encountered
- Pre-commit ruff hook caught import annotation issues on first commit attempt — fixed and recommitted successfully

## Next Phase Readiness
- TDD contracts established for all Phase 18 implementation work
- Plan 18-02: Extend credential_store.py with register_credential, unregister_credential, list_credentials, _REGISTRY_PATH, and credential_type parameter
- Plan 18-03: Extend server.py main() with --version flag and credentials subcommand dispatch

---
*Phase: 18-credentials-cli-version*
*Completed: 2026-03-15*
