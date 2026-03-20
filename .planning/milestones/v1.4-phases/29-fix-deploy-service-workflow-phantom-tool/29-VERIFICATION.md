---
phase: 29-fix-deploy-service-workflow-phantom-tool
verified: 2026-03-19T00:00:00Z
status: passed
score: 4/4 must-haves verified
re_verification: false
---

# Phase 29: Fix deploy_service_workflow Phantom Tool Verification Report

**Phase Goal:** Fix the phantom tool reference in deploy_service_workflow so MCP clients no longer fail with ValueError on unknown tool
**Verified:** 2026-03-19
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | deploy_service_workflow prompt step 2 references get_service_status (a registered tool), not list_installed_services (a phantom tool) | VERIFIED | `prompt_registry.py` line 114: `Call get_service_status with service_name="{service_name}" and hostname="{target_host}"` |
| 2 | No occurrence of list_installed_services exists anywhere in prompt_registry.py | VERIFIED | `grep list_installed_services src/homelab_mcp/prompt_registry.py` returns 0 matches; grep across entire `src/homelab_mcp/` also returns 0 files |
| 3 | A regression test guards against list_installed_services re-introduction | VERIFIED | `tests/test_mcp_prompts.py` line 159: `test_deploy_service_workflow_no_phantom_tool` exists with negative assertion `assert "list_installed_services" not in combined` |
| 4 | All existing prompt tests continue to pass | VERIFIED | `uv run python -m pytest tests/test_mcp_prompts.py -v` — 10/10 tests passed in 1.44s |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/homelab_mcp/prompt_registry.py` | Fixed deploy_service_workflow prompt with get_service_status in step 2 | VERIFIED | Line 114 contains `get_service_status with service_name="{service_name}" and hostname="{target_host}"` — substantive, wired into get_prompt_result dispatcher |
| `tests/test_mcp_prompts.py` | Regression test for phantom tool and updated PRMT-03 assertion | VERIFIED | `test_deploy_service_workflow_no_phantom_tool` at line 159; PRMT-03 `test_deploy_service_workflow_prompt` at line 63 asserts `get_service_status in combined_text` directly (no longer accepts list_installed_services) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/homelab_mcp/prompt_registry.py` | `get_service_status` tool schema | prompt text references tool by exact registered name with correct parameters | WIRED | `get_service_status` is a registered key in `SERVICE_TOOLS` in `tool_schemas/service_tools_schema.py` with `required: [service_name, hostname]`; prompt uses both params correctly |
| `tests/test_mcp_prompts.py` | `src/homelab_mcp/prompt_registry.py` | negative assertion blocks phantom tool re-introduction | WIRED | Test imports `get_prompt_result`, calls it, and asserts `"list_installed_services" not in combined` — will fail at test time if phantom string reappears |

### Requirements Coverage

No requirement IDs were declared for this phase (requirements: [] in PLAN frontmatter).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | — | — | — |

No TODO/FIXME/placeholder comments or stub implementations found in modified files.

### Human Verification Required

None. The fix is a text substitution in a prompt string. All verification is fully automated via test assertions that exercise the exact runtime path (import → call → text check).

### Gaps Summary

No gaps. All four must-have truths are verified at all three levels (exists, substantive, wired).

- The phantom `list_installed_services` string is absent from `prompt_registry.py` and from the entire `src/homelab_mcp/` directory.
- The replacement `get_service_status` appears at the correct location (step 2 of the deploy workflow) with both required schema parameters (`service_name` and `hostname`).
- The tool `get_service_status` is a real registered tool with `required: [service_name, hostname]` in `service_tools_schema.py`.
- The regression test `test_deploy_service_workflow_no_phantom_tool` is substantive (negative + positive assertion) and wired (directly invokes `get_prompt_result`).
- Both task commits (`5d0d563`, `999142b`) are present in git history.
- All 10 prompt tests pass with no regressions.

---

_Verified: 2026-03-19_
_Verifier: Claude (gsd-verifier)_
