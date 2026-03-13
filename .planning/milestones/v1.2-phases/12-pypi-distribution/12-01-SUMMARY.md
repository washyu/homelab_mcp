---
phase: 12-pypi-distribution
plan: "01"
subsystem: testing
tags: [pytest, tdd, wave-0, importlib-resources, importlib-metadata, packaging, pypi]

# Dependency graph
requires: []
provides:
  - "Wave 0 test scaffold for PKG-01 (entry point), PKG-02 (version unification), PKG-03 (template loading)"
  - "tests/test_packaging.py with 4 RED tests defining the Plan 02 and 03 implementation contracts"
  - "tests/test_service_installer.py updated: TEMPLATES_DIR patch replaced with importlib.resources.files mock"
  - "test_templates_loaded_from_package: PKG-03 contract test"
affects: [12-02, 12-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Wave 0 TDD: write RED tests before implementation to define contracts"
    - "importlib.resources mock pattern: patch homelab_mcp.service_installer.files using MagicMock Traversable"
    - "_make_fake_traversable() + _make_fake_files_fn() helpers for fake Traversable in tests"

key-files:
  created:
    - tests/test_packaging.py
  modified:
    - tests/test_service_installer.py

key-decisions:
  - "Wave 0 tests are intentionally RED at commit time -- correctness is verified by pytest --collect-only, not by test passage"
  - "Patch target for Plan 03: homelab_mcp.service_installer.files (not src.homelab_mcp.service_installer.TEMPLATES_DIR)"
  - "test_server_version_dynamic checks server._version != '0.2.0' rather than a specific value, to remain valid across Plan 02 changes"

patterns-established:
  - "Fake Traversable pattern: MagicMock with .iterdir() yielding fake file items, each with .is_file(), .name, .read_text()"
  - "files() mock pattern: MagicMock(return_value=fake_pkg) where fake_pkg.joinpath('service_templates') returns traversable"

requirements-completed: [PKG-01, PKG-02, PKG-03]

# Metrics
duration: 4min
completed: 2026-03-13
---

# Phase 12 Plan 01: Wave 0 Test Scaffold Summary

**Four-test PKG-01/PKG-02 scaffold in test_packaging.py and importlib.resources.files mock pattern replacing TEMPLATES_DIR patch across all TestServiceInstaller classes**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-03-13T18:46:48Z
- **Completed:** 2026-03-13T18:50:38Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created `tests/test_packaging.py` with 4 Wave 0 RED tests defining PKG-01 (main() entry point) and PKG-02 (version unification) contracts
- Updated `tests/test_service_installer.py`: removed all `TEMPLATES_DIR` patching (5 classes), replaced with `homelab_mcp.service_installer.files` mock using a MagicMock Traversable pattern
- Added `test_templates_loaded_from_package` as the PKG-03 contract test referenced in VALIDATION.md
- All 32 tests in test_service_installer.py and 4 tests in test_packaging.py collected by pytest without import errors

## Task Commits

Each task was committed atomically:

1. **Task 1: Create tests/test_packaging.py (Wave 0 scaffold)** - `a4f40ae` (test)
2. **Task 2: Update tests/test_service_installer.py patch target** - `c8bc8c3` (test)

## Files Created/Modified

- `tests/test_packaging.py` - Wave 0 scaffold: test_main_help, test_main_module_entry, test_version_unified, test_server_version_dynamic (all RED until Plans 02/03)
- `tests/test_service_installer.py` - TEMPLATES_DIR patch removed; homelab_mcp.service_installer.files mock in place; test_templates_loaded_from_package added; module-level template dicts extracted as constants

## Decisions Made

- Wave 0 tests are intentionally RED at commit time -- correctness is verified by `pytest --collect-only`, not test passage
- Patch target for Plan 03 is `homelab_mcp.service_installer.files` (the importlib.resources.files function as imported in the module), not the old `src.homelab_mcp.service_installer.TEMPLATES_DIR` constant
- `test_server_version_dynamic` checks `server._version != "0.2.0"` rather than a specific expected value, to remain a valid assertion across Plan 02 changes

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Pre-commit hooks (ruff lint + ruff format) auto-fixed minor style issues on both commits. Re-staged and recommitted each time. No logic changes from linter.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Wave 0 scaffold complete; Plans 02 and 03 can now proceed
- Plan 02 must: rename package to `homelab-mcp`, add `main()` to server.py, create `__main__.py`, switch version to importlib.metadata
- Plan 03 must: remove TEMPLATES_DIR constant, add `files` import from importlib.resources, update `_load_service_templates()` to use package resources
- The RED tests in both files will become GREEN as Plans 02 and 03 land

---
*Phase: 12-pypi-distribution*
*Completed: 2026-03-13*
