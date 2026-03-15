---
phase: 18-credentials-cli-version
plan: "02"
subsystem: auth
tags: [keyring, credentials, proxmox, json-registry, python]

# Dependency graph
requires:
  - phase: 17-credential-store-foundation
    provides: store_credential/get_credential/delete_credential with keyring lazy-import pattern
  - phase: 18-credentials-cli-version-01
    provides: Wave 0 RED tests for credential_type param and registry functions
provides:
  - credential_store.py with _SERVICE_NAMES dict (ssh/proxmox namespacing)
  - credential_store.py with _REGISTRY_PATH constant
  - register_credential, unregister_credential, list_credentials registry API
  - credential_type="ssh" default param on all three keyring functions (backward-compatible)
affects: [18-03-credentials-cli, 19-version-flag]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_SERVICE_NAMES dict pattern for multi-service keyring namespacing"
    - "JSON file registry (read/write) for credential metadata tracking"
    - "Upsert pattern: filter-out then append for idempotent registration"

key-files:
  created: []
  modified:
    - src/homelab_mcp/credential_store.py

key-decisions:
  - "type: ignore[return-value] in plan was wrong mypy code — corrected to no-any-return (actual error from json.loads returning Any)"
  - "Keep _SERVICE_NAME string alongside _SERVICE_NAMES dict for backward compatibility with any Phase 19 references"

patterns-established:
  - "Registry functions use _REGISTRY_PATH module-level constant (patchable via monkeypatch in tests)"
  - "_load_registry returns [] on missing file or parse error (safe default for fresh install)"

requirements-completed: [CRED-01, CRED-02, CRED-03, CRED-04, CRED-05, CRED-06]

# Metrics
duration: 1min
completed: 2026-03-15
---

# Phase 18 Plan 02: Credentials CLI Version Summary

**Extended credential_store.py with proxmox service namespacing (_SERVICE_NAMES), JSON metadata registry (register/unregister/list), and backward-compatible credential_type param on all keyring functions**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-15T01:57:20Z
- **Completed:** 2026-03-15T01:58:36Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Added `_SERVICE_NAMES = {"ssh": "homelab-mcp", "proxmox": "homelab-mcp-proxmox"}` for Proxmox credential namespacing
- Added `_REGISTRY_PATH` constant pointing to `~/.homelab_mcp/credential_registry.json`
- Extended all three keyring functions with `credential_type: str = "ssh"` (fully backward-compatible)
- Added five new functions: `_load_registry`, `_save_registry`, `register_credential`, `unregister_credential`, `list_credentials`
- All 15 tests in `test_credential_store.py` GREEN (9 Phase 17 + 6 Phase 18 registry tests)

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend credential_store with credential_type param and JSON registry** - `b9b4230` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `src/homelab_mcp/credential_store.py` - Extended with _SERVICE_NAMES, _REGISTRY_PATH, credential_type param, and registry functions

## Decisions Made

- The plan specified `# type: ignore[return-value]` for the `json.loads` return in `_load_registry`, but mypy reported the actual error code as `no-any-return`. Fixed inline (Rule 1 auto-fix).
- Kept `_SERVICE_NAME = "homelab-mcp"` string alongside new `_SERVICE_NAMES` dict for backward compatibility.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Wrong mypy type: ignore comment code**
- **Found during:** Task 1 (quality checks after writing file)
- **Issue:** Plan specified `# type: ignore[return-value]` but mypy reported `[no-any-return]` as the actual error; `[return-value]` was "unused" causing additional error
- **Fix:** Changed to `# type: ignore[no-any-return]`
- **Files modified:** src/homelab_mcp/credential_store.py
- **Verification:** mypy reported "Success: no issues found in 1 source file"
- **Committed in:** b9b4230 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - incorrect type ignore code in plan)
**Impact on plan:** Single-line fix, no scope impact. mypy clean after correction.

## Issues Encountered

- ruff-format reformatted the list comprehensions in register_credential and unregister_credential (collapsed multi-line conditions to single line). Pre-commit hook modified the file, requiring re-staging before the commit succeeded. Normal pre-commit behavior.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- credential_store.py is complete and ready for Plan 03 (CLI commands implementation)
- `register_credential`, `unregister_credential`, `list_credentials` are importable by CLI handler functions
- All Phase 18 Wave 0 RED tests for the credential store are now GREEN
- Phase 18 CLI tests in `test_credentials_cli.py` remain RED (as expected, awaiting Plan 03)

---
*Phase: 18-credentials-cli-version*
*Completed: 2026-03-15*
