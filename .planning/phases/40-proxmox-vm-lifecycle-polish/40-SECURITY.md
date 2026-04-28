---
phase: 40-proxmox-vm-lifecycle-polish
audit_date: 2026-04-28
auditor: Claude (gsd-secure-phase)
threats_total: 17
threats_closed: 17
threats_open: 0
unregistered_flags: 0
asvs_level: not configured
status: SECURED
---

# Phase 40 Security Audit — Proxmox VM Lifecycle Polish

## Summary

All 17 declared threats verified CLOSED. Wave 1 (Plans 01+02) landed runtime + schema mitigations; Wave 2 (Plan 03) landed test + AST-guard mitigations. No unregistered attack surface in SUMMARY threat flags. All `accept` dispositions documented in PLAN context (D-03/D-04/D-05) and threat register. No `transfer` dispositions remain unfulfilled — the receiving plans (02 and 03) shipped in the same phase.

## Threat Verification Table

| Threat ID | Category | Disposition | Evidence |
|-----------|----------|-------------|----------|
| T-40-01 | I (URL leak in vm_status except branch) | mitigate | `src/homelab_mcp/proxmox_api.py:620-671` `_classify_vm_status_error` constructs `message` from inputs only. Grep `request_info` count = 0 across the file. Helper does not read `exc.request_info` / `exc.url`. |
| T-40-02 | I (env-var name leak in missing-host ValueError) | mitigate | `proxmox_api.py:522-529` ValueError text references only `homelab-mcp credentials add --type proxmox` CLI form; no env-var names. Grep `PROXMOX_HOST` count = 0 in file. |
| T-40-03 | T (credential-pointer phishing) | mitigate | `proxmox_api.py:522-529` mirrors canonical wording from `resolve_proxmox_credentials` raise (file count of `homelab-mcp credentials add --type proxmox` = 9, including new ValueError + sibling raise + docstrings). Literal grep-able. |
| T-40-04 | E (auth bypass — tier-0 UUID + env-var auth) | accept | Documented in 40-01-PLAN `<threat_model>` and CONTEXT D-04. Verified preserved: lines 479-481 PROXMOX_USER/PASSWORD/API_TOKEN reads still present (grep count = 35 incl. credential_id ≥ 4 — tier-0 short-circuit intact). No regression from this phase. |
| T-40-05 | D (substring-match heuristic format drift) | accept | Documented in 40-01-PLAN `<threat_model>` and CONTEXT. `proxmox_api.py:651-658` logs warning on heuristic miss; legacy fallback still surfaces error. v1.8 fixture refresh deferred. |
| T-40-06 | T (schema/runtime divergence) | transfer | Receiving plans landed in same phase: Plan 02 swept `proxmox_tools_schema.py` (PROXMOX_HOST count = 0) + rewrote `INFRA_REQUIREMENTS["Proxmox"]` at `openapi_app.py:59`. Plan 03 added AST guard. Transfer fulfilled. |
| T-40-07 | T (schema/runtime divergence on create_proxmox_vm) | mitigate | `tool_schemas/proxmox_tools_schema.py:312` declares `"required": ["node", "vmid", "name", "host"]`. Schema now matches runtime `ValueError` at `proxmox_api.py:522`. |
| T-40-08 | I (credential-pointer phishing in INFRA_REQUIREMENTS + schema) | mitigate | `openapi_app.py:59` rewritten to point at `homelab-mcp credentials add --type proxmox` (per-node + cluster-scope). `proxmox_tools_schema.py` host descriptions (4 sites) reference the same CLI literal. |
| T-40-09 | T (silent description drift) | mitigate | `grep PROXMOX_HOST tool_schemas/proxmox_tools_schema.py` = 0; AST guard at `tests/test_ast_regression.py:630-636` extends `_DRIFT_SURFACE_FILES` to lock invariant. |
| T-40-10 | I (over-aggressive sweep — 6 sibling tools optional host) | accept | Documented in 40-02-PLAN `<threat_model>` T-40-10 + 40-02-SUMMARY decisions section. Scope-bound per CONTEXT D-05; deferred to v1.7.1 LIFE-* / v1.8 mechanical sweep. Runtime ValueError (Plan 01 POL-03) still fires for those tools' missing-host calls. |
| T-40-11 | D (schema-rejection back-compat for v1.6 clients) | accept | Documented in 40-02-PLAN `<threat_model>` T-40-11 + CONTEXT D-03. Deliberate breaking change; v1.7 milestone-open announced env-var deprecation. Documented in milestone close notes. |
| T-40-12 | I (URL-leak regression test) | mitigate | `tests/test_proxmox_api.py:2375-2397` `test_get_vm_status_returns_vm_not_found_shape` injects `request_info.url = "https://internal-proxmox.local/api2/..."` and asserts `"/api2/" not in result["message"]` and `"internal-proxmox.local" not in result["message"]`. |
| T-40-13 | T (schema drift — auth bypass via missing required host) | mitigate | `tests/test_proxmox_api.py:2457-2470` `test_create_proxmox_vm_schema_requires_host` asserts `"host" in schema["required"]` and `"PROXMOX_HOST" not in host_desc`. |
| T-40-14 | T (credential-pointer phishing wording drift) | mitigate | `tests/test_proxmox_api.py:2484-2493` asserts literal `homelab-mcp credentials add --type proxmox` and `--scope cluster:` substrings, plus PROXMOX_HOST absence. Schema test at line 2467 asserts same literal in description. |
| T-40-15 | I (env-var name reintroduction) | mitigate | `tests/test_ast_regression.py:630-636` `_DRIFT_SURFACE_FILES` includes `proxmox_api.py` and `tool_schemas/proxmox_tools_schema.py`; lines 686-690 add `INFRA_REQUIREMENTS.get("Proxmox", "")` dict-value scan. CI fails on PROXMOX_HOST reintroduction. |
| T-40-16 | D (fixture brittleness across PVE versions) | accept | Documented in 40-03-PLAN `<threat_model>` T-40-16. Tests inject 2 body wordings ("does not exist" + LXC conf-missing); fallback test (`test_get_vm_status_unmatched_error_falls_through_to_legacy_shape` at line 2434) ensures graceful degradation. v1.8 fixture refresh deferred. |
| T-40-17 | T (env leakage between tests) | mitigate | `tests/test_proxmox_api.py:2479` `with patch.dict(os.environ, {}, clear=True)` ensures hermeticity in `test_get_proxmox_client_no_host_raises_actionable_error`. |

## Accepted Risks Log

| Threat ID | Reason | Reference |
|-----------|--------|-----------|
| T-40-04 | Tier-0 UUID short-circuit + PROXMOX_USER/PASSWORD/API_TOKEN env-var auth path preserved per Phase 38.1 CR-04 review (deliberate SC-5 back-compat). No regression introduced. | 40-01-PLAN threat register; 40-CONTEXT D-04 |
| T-40-05 | Substring-match heuristic may miss future PVE wording changes; degrades gracefully to legacy fallback with logger.warning telemetry. Fixture refresh deferred to v1.8. | 40-01-PLAN threat register; 40-CONTEXT |
| T-40-10 | Schema/runtime divergence on 6 sibling Proxmox tools (manage/clone/delete/get_config/create_lxc/delete_preview) deferred per CONTEXT D-05 scope. Runtime ValueError still fires when host omitted. | 40-02-PLAN threat register; 40-CONTEXT D-05; 40-02-SUMMARY |
| T-40-11 | Schema-rejection breaking change for v1.6-pinned MCP clients with cached create_proxmox_vm schema. Deliberate per v1.7 milestone-open env-var deprecation announcement. | 40-02-PLAN threat register; 40-CONTEXT D-03 |
| T-40-16 | Test heuristic injects two body wordings; future PVE wording changes break helper, not tests. Fallback test ensures degraded-but-non-crashing behavior. v1.8 fixture refresh deferred. | 40-03-PLAN threat register |

## Transfer Verification

| Threat ID | Transfer Target | Status |
|-----------|----------------|--------|
| T-40-06 | Plan 40-02 schema sweep (D-05) + Plan 40-03 AST guard (D-06) | FULFILLED — both plans landed: `proxmox_tools_schema.py` PROXMOX_HOST count = 0; `openapi_app.py` INFRA_REQUIREMENTS["Proxmox"] rewritten; AST guard in test_ast_regression.py extended. |

## Unregistered Flags

None. All three SUMMARY.md files explicitly state "Threat Flags: None — this plan reduces threat surface" / equivalent. No new endpoints, auth paths, file access, or schema changes at trust boundaries beyond those captured in the threat register.

## Auditor Notes

- Verification methodology: each `mitigate` threat verified by direct grep/Read against implementation file at the cited line range; each `accept` threat verified by reference to PLAN threat register narrative; the single `transfer` threat verified by checking the receiving plans' artifacts shipped.
- Cross-file invariants validated:
  - `grep PROXMOX_HOST` returns 0 in: `proxmox_api.py`, `tool_schemas/proxmox_tools_schema.py`, `openapi_app.py`.
  - `grep request_info` returns 0 in: `proxmox_api.py` (URL-leak guard).
  - `grep "homelab-mcp credentials add --type proxmox"` returns 9 in `proxmox_api.py` (canonical wording reuse).
  - PROXMOX_USER/PROXMOX_PASSWORD/PROXMOX_API_TOKEN/credential_id paths preserved (combined grep count = 35).
- Auditor did not modify any implementation files. Only `SECURITY.md` written.
