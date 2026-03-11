---
phase: 03-functional-completeness
plan: 01
subsystem: infra
tags: [ssh, sitemap, discovery, service-installer, asyncio]

requires:
  - phase: 02-security-hardening
    provides: "sanitize_error, ssh_connect with host key verification"
provides:
  - "_update_sitemap_after_deployment auto-refreshes sitemap after deploy"
  - "_rediscover_device_after_changes refreshes device info after config updates"
  - "_install_script_service executes template scripts via SSH with env-var config"
affects: [03-functional-completeness, 04-protocol-compliance]

tech-stack:
  added: []
  patterns:
    - "Environment variable injection for script config (not string substitution)"
    - "Graceful discovery failure handling (log warning, don't propagate)"

key-files:
  created: []
  modified:
    - src/homelab_mcp/infrastructure_crud.py
    - src/homelab_mcp/service_installer.py
    - tests/test_infrastructure_crud.py
    - tests/test_service_installer.py

key-decisions:
  - "Config overrides passed as env vars with single-quote escaping to prevent shell injection"
  - "Discovery failures logged as warnings but never propagate (deployment/config change should not fail due to sitemap)"
  - "5-minute SSH timeout for script installations (vs default 30s)"

patterns-established:
  - "Env-var config pattern: export KEY='escaped_value' prepended to script commands"
  - "Graceful secondary-operation pattern: try/except with logger.warning for non-critical post-action steps"

requirements-completed: [FUNC-01, FUNC-02, FUNC-03]

duration: 4min
completed: 2026-03-09
---

# Phase 03 Plan 01: Stub Implementation Summary

**Three stub functions replaced with working implementations: sitemap auto-refresh after deployment, device rediscovery after config changes, and script-based service installation via SSH with env-var config injection**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-09T18:02:31Z
- **Completed:** 2026-03-09T18:07:17Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- _update_sitemap_after_deployment calls discover_and_store for each successful deployment result, skipping failures
- _rediscover_device_after_changes calls discover_and_store with device connection info after config updates
- _install_script_service reads installation_script from template, passes config_override as environment variables, executes via SSH
- Both discovery functions gracefully handle failures (log warning, don't raise)
- Config injection prevented by using env vars instead of string substitution

## Task Commits

Each task was committed atomically (TDD: RED then GREEN):

1. **Task 1: Implement _update_sitemap_after_deployment and _rediscover_device_after_changes**
   - `4a8b2aa` (test: failing tests for sitemap auto-update and device rediscovery)
   - `d21a121` (feat: implement sitemap auto-update and device rediscovery)

2. **Task 2: Implement _install_script_service**
   - `4ef8dad` (test: failing tests for script-based service installation)
   - `7e8e380` (feat: implement script-based service installation via SSH)

## Files Created/Modified
- `src/homelab_mcp/infrastructure_crud.py` - Added logging, discover_and_store import, implemented both sitemap functions
- `src/homelab_mcp/service_installer.py` - Implemented _install_script_service with env-var config and SSH execution
- `tests/test_infrastructure_crud.py` - 5 new tests for sitemap auto-update and device rediscovery
- `tests/test_service_installer.py` - 4 new tests for script-based installation

## Decisions Made
- Config overrides use environment variables with single-quote escaping (prevents shell injection per Pitfall 3 in research)
- Discovery failures are logged as warnings but never propagate up (deployment/config change success is not contingent on sitemap refresh)
- 5-minute SSH timeout for installations (long-running scripts need more time than default 30s)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Three critical stubs now functional, enabling end-to-end tool operation
- deploy_infrastructure, update_device_config, and install_service tools are now fully operational
- Ready for remaining 03-functional-completeness plans

---
*Phase: 03-functional-completeness*
*Completed: 2026-03-09*
