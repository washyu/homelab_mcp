---
phase: 17-credential-store-foundation
plan: "01"
subsystem: auth
tags: [keyring, credentials, headless-linux, lazy-import, python]

requires: []
provides:
  - "store_credential(hostname, username, password) -> bool — headless-safe keyring write"
  - "get_credential(hostname, username) -> str | None — headless-safe keyring read"
  - "delete_credential(hostname, username) -> bool — headless-safe keyring delete"
  - "keyring>=25.6.0 promoted to core [project.dependencies]"
affects:
  - phase-18-credential-cli
  - phase-19-credential-auto-inject
  - any module importing from credential_store

tech-stack:
  added: ["keyring>=25.6.0 (promoted from optional-dependencies.security to project.dependencies)"]
  patterns:
    - "Lazy import pattern: import keyring inside each function body with # noqa: PLC0415"
    - "Headless-safe exception order: PasswordDeleteError -> NoKeyringError -> RuntimeError -> Exception"
    - "credential_store.py imports only stdlib logging — no homelab_mcp imports (circular import prevention)"
    - "str | None annotation on result variable to satisfy mypy warn_return_any on keyring.get_password"

key-files:
  created:
    - src/homelab_mcp/credential_store.py
    - tests/test_credential_store.py
  modified:
    - pyproject.toml
    - uv.lock

key-decisions:
  - "Lazy import keyring inside each function body — prevents D-Bus probing during server startup"
  - "Catch NoKeyringError, RuntimeError, and Exception (in that order) — belt-and-suspenders for headless Linux"
  - "PasswordDeleteError caught first in delete_credential — missing entry returns False, not error"
  - "Key format f\"{username}@{hostname}\" allows multiple users per host (root@192.168.1.1 distinct from admin@192.168.1.1)"
  - "No homelab_mcp imports in credential_store.py — mirrors prompt_registry.py constraint from Phase 14"
  - "Assign keyring.get_password result to typed variable (str | None) to satisfy mypy warn_return_any"

patterns-established:
  - "credential_store lazy import pattern: import keyring / import keyring.errors inside try block with # noqa: PLC0415"
  - "Headless fallback pattern: every except block logs logger.warning and returns safe value — no bare pass (bandit B110)"

requirements-completed: [CRED-07]

duration: 25min
completed: "2026-03-15"
---

# Phase 17 Plan 01: Credential Store Foundation Summary

**Headless-safe OS keyring wrapper with lazy imports and broad exception catching — store_credential, get_credential, delete_credential using keyring>=25.6.0 promoted to core dependencies**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-03-15T01:00:00Z
- **Completed:** 2026-03-15T01:25:00Z
- **Tasks:** 2 (TDD: RED + GREEN)
- **Files modified:** 3

## Accomplishments

- `credential_store.py` with 3 headless-safe functions — never raises, always returns `None` or `False` when OS keyring unavailable
- 9 test cases all green, covering success paths, `NoKeyringError`, `RuntimeError`, `PasswordDeleteError`, no-module-level-import (AST check), and pyproject.toml dependency placement
- `keyring>=25.6.0` promoted from `[project.optional-dependencies].security` to `[project.dependencies]` — available to all installs without extras

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Write failing test scaffold** - `f1925d1` (test)
2. **Task 2 (GREEN): Implement credential_store.py** - `0e0839e` (feat)
3. **Task 2 (GREEN): Promote keyring to core deps** - `cee750b` (chore)

_Note: TDD plan split into 3 commits — test scaffold, implementation, dependency promotion_

## Files Created/Modified

- `src/homelab_mcp/credential_store.py` - Headless-safe keyring wrapper with lazy imports and broad exception handling
- `tests/test_credential_store.py` - 9 test cases covering all CRED-07 behaviors
- `pyproject.toml` - Removed `keyring>=25.0.0` from security optional-deps; `keyring>=25.6.0` in core deps (added by `uv add` in preparation)
- `uv.lock` - Updated by `uv sync` after pyproject.toml change

## Decisions Made

- **Lazy import with `result: str | None` annotation:** `keyring.get_password` returns `Any` per mypy; assigning to a typed variable before returning satisfies `warn_return_any` without `type: ignore` suppression
- **`uv add` then manual edit:** `uv add "keyring>=25.6.0"` added it to core deps automatically; manual edit removed duplicate `keyring>=25.0.0` from security extras
- **`uv sync` via `uv sync --directory`:** `uv run` hangs in this shell environment; using venv python directly and `uv sync --directory` works correctly

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added `result: str | None` variable in `get_credential` to satisfy mypy `warn_return_any`**
- **Found during:** Task 2 (GREEN) — pre-commit mypy hook
- **Issue:** `keyring.get_password` returns `Any` in keyring's type stubs; returning it directly from a function typed `str | None` triggers `no-any-return`
- **Fix:** Assigned return value to `result: str | None = keyring.get_password(...)` then `return result`
- **Files modified:** `src/homelab_mcp/credential_store.py`
- **Verification:** `mypy src/homelab_mcp/credential_store.py` — `Success: no issues found`
- **Committed in:** `0e0839e` (Task 2 implementation commit)

**2. [Rule 1 - Bug] Fixed ruff I001 isort order in test file — `import keyring.errors` must come before `from homelab_mcp...` inside test function bodies**
- **Found during:** Task 1 (RED) — pre-commit ruff hook
- **Issue:** ruff isort treats in-function imports as an import block; `keyring.errors` (stdlib-ish) must come before `from homelab_mcp...` (local)
- **Fix:** `ruff check --fix` auto-resolved import ordering
- **Files modified:** `tests/test_credential_store.py`
- **Verification:** `ruff check` — all checks passed
- **Committed in:** `f1925d1` (test scaffold commit, after ruff auto-fix)

---

**Total deviations:** 2 auto-fixed (both Rule 1 - Bug)
**Impact on plan:** Both fixes required for pre-commit hooks to pass. No scope creep, no architectural changes.

## Issues Encountered

- `uv run` hangs in this shell environment (exit code 120). Used `.venv/bin/python` directly and `uv sync --directory` for all operations. Pre-commit hooks continued to work normally via `git commit`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `credential_store.py` ready for Phase 18 (CLI `store-credential` / `get-credential` / `delete-credential` commands)
- `credential_store.py` ready for Phase 19 (auto-inject credentials into SSH operations)
- No blockers — all quality gates pass (ruff, mypy, bandit, 612 unit tests green)

---
*Phase: 17-credential-store-foundation*
*Completed: 2026-03-15*
