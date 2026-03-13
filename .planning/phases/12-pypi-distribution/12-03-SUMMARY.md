---
phase: 12-pypi-distribution
plan: "03"
subsystem: packaging
tags: [importlib-resources, hatchling, pypi, wheel, yaml, service-templates]

requires:
  - phase: 12-pypi-distribution/12-02
    provides: main() entry point, importlib.metadata version unification, __main__.py

provides:
  - importlib.resources-based template loading in service_installer.py (TEMPLATES_DIR removed)
  - YAML file inclusion in wheel via hatchling include glob
  - dist/homelab_mcp-1.2.0-py3-none-any.whl with 10 YAML files bundled
  - Fixed test mocking infrastructure for service_installer tests (src. prefix patch target)

affects: [pypi-distribution, service-installer, packaging]

tech-stack:
  added: []
  patterns:
    - "importlib.resources.files('homelab_mcp').joinpath('service_templates') for package-safe template loading"
    - "Traversable.iterdir() + item.read_text(encoding='utf-8') + item.name.removesuffix('.yaml')"
    - "hatchling include glob: src/homelab_mcp/**/*.yaml for wheel YAML bundling"
    - "patch('src.homelab_mcp.service_installer.files') not 'homelab_mcp...' — src. prefix required when ServiceInstaller imported from src path"

key-files:
  created: []
  modified:
    - src/homelab_mcp/service_installer.py
    - pyproject.toml
    - tests/test_service_installer.py
    - tests/test_ansible.py

key-decisions:
  - "Patch target for importlib.resources.files must match the import path used by ServiceInstaller: src.homelab_mcp.service_installer.files (not homelab_mcp.service_installer.files) because pytest imports ServiceInstaller via src.homelab_mcp path"
  - "test_ansible.py TEMPLATES_DIR patches replaced with _make_files_mock() helper using MagicMock Traversable — tempfile/temp_dir infrastructure removed as no longer needed"
  - "Path import removed from service_installer.py — not used after TEMPLATES_DIR removal"

patterns-established:
  - "importlib.resources pattern: files('homelab_mcp').joinpath('service_templates') — use this for all package resource access"
  - "_make_files_mock(dict) helper pattern for multi-template mocking in test files"

requirements-completed: [PKG-03]

duration: 8min
completed: 2026-03-13
---

# Phase 12 Plan 03: PyPI Distribution - Template Resource Loading Summary

**importlib.resources-based YAML template loading in service_installer.py with hatchling wheel bundling, producing a verified dist/homelab_mcp-1.2.0-py3-none-any.whl containing all 10 service templates**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-13T18:58:13Z
- **Completed:** 2026-03-13T19:06:00Z
- **Tasks:** 2 of 3 (Task 3 awaiting human verification and PyPI publish)
- **Files modified:** 4

## Accomplishments
- Replaced `TEMPLATES_DIR = Path(__file__).parent / "service_templates"` with `importlib.resources.files()` pattern — templates now load correctly from installed wheel
- Added YAML include glob to `[tool.hatch.build.targets.wheel]` in pyproject.toml
- Built `dist/homelab_mcp-1.2.0-py3-none-any.whl` with exactly 10 YAML files verified inside `homelab_mcp/service_templates/`
- All 583 unit tests GREEN after fixing dual-import-path mock target bug and updating test_ansible.py

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix service_installer.py + add YAML wheel include** - `c769a0c` (feat)
2. **Task 2: Build wheel and verify YAML files bundled** - `8fd6696` (feat)
3. **Task 3: Local smoke test and PyPI publish** - PENDING (human-verify checkpoint)

**Plan metadata:** (pending final commit)

## Files Created/Modified
- `src/homelab_mcp/service_installer.py` - Replaced TEMPLATES_DIR with importlib.resources.files(); removed Path import
- `pyproject.toml` - Added `include = ["src/homelab_mcp/**/*.yaml"]` under `[tool.hatch.build.targets.wheel]`
- `tests/test_service_installer.py` - Fixed patch targets from `homelab_mcp.service_installer.files` to `src.homelab_mcp.service_installer.files`
- `tests/test_ansible.py` - Replaced TEMPLATES_DIR patch with _make_files_mock() helper; removed tempfile/Path infrastructure

## Decisions Made
- Patch target for `importlib.resources.files` must be `src.homelab_mcp.service_installer.files` because pytest imports `ServiceInstaller` via `from src.homelab_mcp.service_installer import ServiceInstaller` — the `src.` prefix creates a separate module object in `sys.modules` from the `homelab_mcp.service_installer` module (verified empirically)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed wrong patch target for importlib.resources.files in test_service_installer.py**
- **Found during:** Task 1 (TDD GREEN phase — tests still failing after implementation)
- **Issue:** Tests patched `homelab_mcp.service_installer.files` but `ServiceInstaller` was imported from `src.homelab_mcp.service_installer` — two different module objects in sys.modules, patch missed the actual `files` reference
- **Fix:** Changed all 10 patch locations in test_service_installer.py from `"homelab_mcp.service_installer.files"` to `"src.homelab_mcp.service_installer.files"`; updated Wave 0 comment in docstring
- **Files modified:** tests/test_service_installer.py
- **Verification:** 32/32 tests in test_service_installer.py pass GREEN
- **Committed in:** c769a0c (Task 1 commit)

**2. [Rule 1 - Bug] Updated test_ansible.py to use importlib.resources mock instead of removed TEMPLATES_DIR**
- **Found during:** Task 2 (full unit test suite run — 1 ERROR found)
- **Issue:** TestAnsibleServiceIntegration.setup_method and 3 inline `with patch()` blocks in TestAnsibleServiceTemplateProcessing still patched `src.homelab_mcp.service_installer.TEMPLATES_DIR` which no longer exists
- **Fix:** Added `_make_files_mock(templates: dict)` helper; replaced TEMPLATES_DIR patches with `src.homelab_mcp.service_installer.files` mock; removed tempfile/Path imports and temp_dir infrastructure
- **Files modified:** tests/test_ansible.py
- **Verification:** 583/583 unit tests GREEN, 7 skipped
- **Committed in:** 8fd6696 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2x Rule 1 - Bug)
**Impact on plan:** Both fixes necessary for test correctness after removing TEMPLATES_DIR. No scope creep — all changes directly caused by the importlib.resources migration.

## Issues Encountered
- Python module import path duality: `src.homelab_mcp.service_installer` and `homelab_mcp.service_installer` are different module objects even in editable install mode. The `files` function imported in each module occupies a different namespace slot. `unittest.mock.patch` patches by attribute name on the module object, so patch target must match the module path used at instantiation time.

## User Setup Required

**PyPI publish requires manual steps.** See plan 12-03 checkpoint (Task 3) for:
- Run `uvx --from ./dist/homelab_mcp-1.2.0-py3-none-any.whl homelab-mcp --help` smoke test
- Set `PYPI_TOKEN` and run `uv publish --token $PYPI_TOKEN`
- Verify with `uvx homelab-mcp --help` from PyPI

## Next Phase Readiness
- Wheel is built and verified locally — ready for smoke test and PyPI publish
- All unit tests GREEN — no regressions from Plan 03 changes
- Task 3 (human-verify checkpoint) requires user to run smoke test and optionally publish

---
*Phase: 12-pypi-distribution*
*Completed: 2026-03-13*

## Self-Check: PASSED
- src/homelab_mcp/service_installer.py: present, TEMPLATES_DIR absent, importlib.resources.files present
- pyproject.toml: include = ["src/homelab_mcp/**/*.yaml"] present
- dist/homelab_mcp-1.2.0-py3-none-any.whl: exists with 10 YAML files
- Commits c769a0c and 8fd6696: present in git log
- 583 unit tests GREEN
