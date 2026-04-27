# Phase 38.1 Deferred Items

Out-of-scope discoveries logged during plan execution. Per executor scope rules:
only auto-fix issues directly caused by the current plan's changes; pre-existing
or unrelated breakage gets logged here for follow-up.

## From Plan 09 execution (Wave 5 — round-trip integration)

### Pre-existing integration test failures (NOT Plan 09 caused)

The following tests fail BEFORE Plan 09 lands:

| Test | File | Symptom | Likely cause |
|------|------|---------|--------------|
| TestErrorRecoveryAndRollback::test_discovery_failure_handling | tests/integration/test_full_stack_integration.py | `assert 4 == 2` row count mismatch (sees error rows that prior phases excluded) | Phase 35 / Phase 38.1 R7 — degenerate-hostname rows now persist with eligibility field; counts diverge from Phase 36 expectation |
| TestServiceToVMDeploymentWorkflow::test_service_to_vm_deployment_workflow | tests/integration/test_full_stack_integration.py | `assert 'error' == 'success'` | Pre-existing; not invoked by Plan 09 changes |
| TestEndToEndWorkflowWithMCPTools (4 tests) | tests/integration/test_full_stack_integration.py | `assert 'error' == 'success'` | Pre-existing |
| TestErrorRecoveryAndRollback::test_partial_deployment_failure_recovery | tests/integration/test_full_stack_integration.py | `KeyError: 'error'` | Pre-existing |
| test_complete_homelab_lifecycle | tests/integration/test_full_stack_integration.py | `assert 'error' == 'success'` | Pre-existing |
| TestSitemapIntegration::test_mcp_tools_integration_with_mock_data | tests/integration/test_sitemap_integration.py | n/a (Docker-required) | Likely pre-existing Docker dependency |
| TestSitemapIntegration::test_error_handling_integration | tests/integration/test_sitemap_integration.py | n/a (Docker-required) | Likely pre-existing |
| TestSitemapIntegration::test_discover_populates_fingerprint_against_docker_phase38 | tests/integration/test_sitemap_integration.py | ERROR (Docker setup) | Pre-existing fixture error |

**Verification of pre-existence:** confirmed via `git stash` round-trip — running
`pytest tests/integration/test_full_stack_integration.py::TestErrorRecoveryAndRollback::test_discovery_failure_handling`
on the pre-Plan-09 worktree state (HEAD `0e15d95`) reproduced the same `4 == 2`
assertion failure with the same payload shape (`eligibility` field present on
the rows).

**Recommended follow-up:**
- The `test_full_stack_integration.py` tests appear to encode pre-Phase-35
  expectations about how degenerate-hostname rows are handled. Updating those
  tests to expect the post-Phase-35/38.1 row counts + eligibility shape is a
  separate "test maintenance" task.
- The `test_sitemap_integration.py` Docker tests need Docker to be running —
  outside the scope of unit-level CI. Verifier can choose to mark as
  "Docker-gated" rather than "must-pass-in-CI".

### Pre-commit ruff format reformatting (NOT Plan 09 caused)

The pre-commit hook `ruff format` (run as part of `./scripts/quality-check.sh`)
reformatted 17 files across the codebase, including pre-existing source files
in `src/homelab_mcp/` and tests outside Plan 09's scope. These reformatting
churns are pre-existing format drift accumulated across earlier phases (likely
because Phase 35-38 phases added code without running `ruff format` between
plans).

**Reverted from Plan 09 commits:** all source/test files outside the integration
test were reverted to their committed state via `git checkout --`. Plan 09's own
file got the format applied as a separate `style(38.1-09)` commit (commit
`c8800f0`).

**Recommended follow-up:** run `uv run ruff format src tests` once across the
whole tree as a single dedicated `style(phase-38.1):` commit at phase close, or
defer to a later `chore(repo): reformat with ruff` PR. Per the project's
git-commit-from-feature-branch convention, this can land before the v1.7
milestone tag.
