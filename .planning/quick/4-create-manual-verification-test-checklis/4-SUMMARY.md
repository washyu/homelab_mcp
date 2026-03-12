---
quick: 4
phase: quick
plan: 4
subsystem: documentation
tags: [qa, manual-testing, v1.1, drift-detection, dry-run, mcp-resources, notifications]
dependency_graph:
  requires: []
  provides: [MANUAL-TESTS.md]
  affects: []
tech_stack:
  added: []
  patterns: []
key_files:
  created:
    - MANUAL-TESTS.md
  modified: []
decisions:
  - "Reflected actual MUTATING_TOOLS set (only discover_and_map and bulk_discover_and_map) rather than plan template which incorrectly implied create_proxmox_vm triggers notifications"
  - "Added v1.1 requirement traceability table (Section 8) mapping all 22 requirement IDs to checklist sections"
  - "Used 50 tools count (confirmed from schema files) not 49 from annotations comment"
metrics:
  duration: "~5 minutes"
  completed_date: "2026-03-12"
  tasks_completed: 1
  files_created: 1
---

# Quick Task 4: Create Manual Verification Test Checklist — Summary

**One-liner:** 296-line human-executable QA checklist for v1.1, organized in 7 sections covering all 22 requirements with concrete steps and expected outcomes.

## What Was Built

`MANUAL-TESTS.md` at the repo root — a complete post-install QA checklist for the v1.1 Safety & Observability milestone. Any user with a live Proxmox homelab can work through this document sequentially to verify that all v1.1 features are working correctly.

### Document Structure

| Section | Feature Area | Requirements Covered |
|---------|-------------|---------------------|
| Prerequisites | Setup gate | — |
| 1: Server Startup + Tool Discovery | Tool count, schema verification | DEBT-01 |
| 2: Dry-Run Mode | 6 destructive tools + regression | DRY-01 through DRY-07 |
| 3: MCP Resources Protocol | resources/list, resources/read, error handling | RES-01 through RES-06 |
| 4: Resource Notifications | discover_and_map, bulk_discover_and_map, dry-run suppression | RES-07, DEBT-03 |
| 5: Drift Detection | Initial scan, state drift, config drift, auto-baseline, persistence | DRFT-01 through DRFT-05 |
| 6: Automated Test Suite | pytest, ruff, mypy regression gate | — |
| 7: HTTP Auth | Bearer token auth, /health bypass | DEBT-02 |

Each checkbox item specifies: the exact tool to call, the parameters to pass, and the expected output — with no ambiguity.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected notification trigger tools in Section 4**
- **Found during:** Task 1, reading server.py MUTATING_TOOLS
- **Issue:** Plan template's Section 4.3 described `create_proxmox_vm` as triggering notifications. The actual implementation's `MUTATING_TOOLS` frozenset only contains `discover_and_map` and `bulk_discover_and_map`. Destructive/mutating Proxmox tools do not trigger notifications.
- **Fix:** Section 4 was rewritten to accurately reflect the two tools that actually trigger `notifications/resources/list_changed`. Section 4.3 was changed from "Notification after create_proxmox_vm" to "Notification after bulk_discover_and_map".
- **Files modified:** MANUAL-TESTS.md (creation, no prior version)

### Additions

- Added a **v1.1 Requirement Traceability Table** at the end of the document, mapping all 22 requirement IDs (DRY-01 through DEBT-03) to their corresponding checklist sections. This was not in the plan but makes the checklist more useful for milestone sign-off.

## Self-Check

- [x] MANUAL-TESTS.md exists at `/home/shaun/projects/mcp_python_server/MANUAL-TESTS.md`
- [x] 296 lines (above 100-line minimum)
- [x] Contains 7 sections with checkbox items
- [x] Covers all v1.1 feature areas: dry-run, MCP resources, resource notifications, drift detection, automated tests
- [x] Each checkbox has a concrete, actionable step with expected output
- [x] Sign-off table present at end
- [x] Requirement traceability table covers all 22 v1.1 requirements
- [x] Commit ef99f32 verified

## Self-Check: PASSED
