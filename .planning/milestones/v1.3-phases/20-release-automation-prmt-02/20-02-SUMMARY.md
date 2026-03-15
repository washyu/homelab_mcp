---
phase: 20-release-automation-prmt-02
plan: "02"
subsystem: cicd
tags: [pypi, oidc, github-actions, trusted-publishing, release-automation]

# Dependency graph
requires:
  - phase: 12-pypi-distribution
    provides: homelab-mcp package on PyPI (1.2.0), pyproject.toml structure
provides:
  - publish-to-pypi job in main.yml (OIDC trusted publishing, tag-gated)
  - pyproject.toml version bumped to 1.3.0
affects: [future release tagging, v1.3 release, pypi trusted publisher setup]

# Tech tracking
tech-stack:
  added: [pypa/gh-action-pypi-publish@release/v1]
  patterns:
    - "OIDC trusted publishing: permissions id-token: write at job level, no stored secrets"
    - "Tag gate: if startsWith(github.ref, 'refs/tags/v') scopes publish to v* tags only"
    - "Test gate: needs: [test-and-quality] blocks publish if tests fail"

key-files:
  created: []
  modified:
    - .github/workflows/main.yml
    - pyproject.toml

key-decisions:
  - "Repository name on GitHub is 'homelab_mcp' (underscore) — use this when registering PyPI trusted publisher at pypi.org/manage/project/homelab-mcp/settings/publishing/"
  - "publish-to-pypi depends directly on test-and-quality, NOT on the release job — avoids anti-pattern of sequential publish after GitHub release"
  - "permissions: id-token: write placed at job level, not workflow level — minimizes OIDC scope per GitHub security best practice"
  - "pypa/gh-action-pypi-publish@release/v1 (not @master) — @master is deprecated per PyPA documentation"
  - "No PYPI_API_TOKEN stored anywhere — OIDC trusted publisher replaces API token entirely"

patterns-established:
  - "OIDC publish pattern: environment name pypi + id-token: write + pypa/gh-action-pypi-publish@release/v1"

requirements-completed: [CICD-01, CICD-02, CICD-03]

# Metrics
duration: continuation (checkpoint approved)
completed: "2026-03-15"
---

# Phase 20 Plan 02: Release Automation (PyPI Publish Job) Summary

**OIDC-based PyPI publish job added to main.yml: tag-gated on v* tags, blocked by test failures, no stored secrets — plus pyproject.toml bumped to 1.3.0**

## Performance

- **Duration:** continuation (checkpoint approved by user)
- **Started:** 2026-03-15T03:56:43Z
- **Completed:** 2026-03-15T04:01:42Z
- **Tasks:** 2 (1 auto + 1 checkpoint)
- **Files modified:** 2

## Accomplishments

- Added `publish-to-pypi` job to `.github/workflows/main.yml` using OIDC trusted publishing
- Tag guard (`if: startsWith(github.ref, 'refs/tags/v')`) ensures only v* tags trigger the publish job, not branch pushes
- Test gate (`needs: [test-and-quality]`) ensures publish is blocked if unit tests or quality checks fail
- No `PYPI_API_TOKEN` or any PyPI secret stored in GitHub secrets — authentication is entirely via OIDC
- Bumped `pyproject.toml` version from `1.2.0` to `1.3.0`
- User acknowledged PyPI trusted publisher registration requirement (one-time manual step before first tag push)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add publish-to-pypi job and bump version to 1.3.0** - `27335b4` (feat)

**Plan metadata:** TBD (docs: complete plan)

## Files Created/Modified

- `.github/workflows/main.yml` - Added `publish-to-pypi` job (OIDC, tag-gated, test-gated)
- `pyproject.toml` - Version bumped from 1.2.0 to 1.3.0

## Decisions Made

- **Repository name correction:** The GitHub repository is named `homelab_mcp` (underscore), not `mcp_python_server`. When registering the PyPI trusted publisher, the Repository field must be set to `homelab_mcp`.
- **No repository name in YAML:** OIDC trusted publishing does not require the repository name to be hardcoded in the workflow YAML — GitHub Actions provides it via context automatically. The workflow file is correct as-is.
- `publish-to-pypi` depends directly on `test-and-quality`, not on `release` — avoids the anti-pattern where publish must wait for a GitHub Release to be created first.
- `permissions: id-token: write` scoped to the publish job only, not at workflow level — follows principle of least privilege.

## Deviations from Plan

None — plan executed exactly as written. The user-provided correction about the repository name (`homelab_mcp` vs `mcp_python_server`) affects only the PyPI trusted publisher registration instructions (external, manual step), not the workflow YAML itself.

## User Setup Required

**Before pushing any `v1.3.0` tag, register the PyPI trusted publisher:**

1. Go to: https://pypi.org/manage/project/homelab-mcp/settings/publishing/
2. Add a new trusted publisher with:
   - **Owner:** your GitHub username or org
   - **Repository:** `homelab_mcp` (underscore — confirmed by user)
   - **Workflow filename:** `main.yml`
   - **Environment:** `pypi`

This is a one-time setup. Without it, the publish job will receive a 403 from PyPI on the first v* tag push.

**Optional dry-run verification:**

```bash
git tag v1.3.0-rc1 && git push origin v1.3.0-rc1
# Watch GitHub Actions — confirm publish-to-pypi job triggers
# Delete after:
git push origin --delete v1.3.0-rc1
```

## Issues Encountered

None.

## Next Phase Readiness

- Phase 20 plan 02 complete — CICD-01, CICD-02, CICD-03 all satisfied
- All v1.3 phases (17, 18, 19, 20) are now complete
- To publish v1.3.0: register PyPI trusted publisher (see User Setup above), then `git tag v1.3.0 && git push origin v1.3.0`

---
*Phase: 20-release-automation-prmt-02*
*Completed: 2026-03-15*
