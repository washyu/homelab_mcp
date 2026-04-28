---
phase: 40-proxmox-vm-lifecycle-polish
verified: 2026-04-28T00:00:00Z
status: passed
score: 3/3 must-haves verified
overrides_applied: 0
---

# Phase 40: Proxmox VM Lifecycle Polish Verification Report

**Phase Goal:** A user hitting Bug I (querying a nonexistent VMID) or Bug G (calling `create_proxmox_vm` without configured credentials) gets a clean structured error that tells them what to do next, never a raw HTTP 500 leak or a pointer to a deprecated env var.

**Verified:** 2026-04-28
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| #   | Truth   | Status     | Evidence       |
| --- | ------- | ---------- | -------------- |
| 1 (POL-01) | A user calling `get_proxmox_vm_status` with a nonexistent VMID sees a structured `VM not found` error with hostname and VMID echoed back — no raw HTTP 500, no internal Proxmox API URL leaked | VERIFIED | `_classify_vm_status_error` defined at `src/homelab_mcp/proxmox_api.py:620` and invoked from the except branch at line 709. Helper returns dict with keys `error_kind="vm_not_found"`, `node`, `vmid`, `vm_type`, `host`, `message`. Message is constructed solely from input parameters (verified: `grep request_info` returns 0 across the file). URL-leak guard explicit in test `TestPhase40VmNotFoundShape::test_get_vm_status_returns_vm_not_found_shape` which injects a sentinel URL `internal-proxmox.local/api2/...` and asserts its absence from the result message. All 4 vm_not_found tests pass. |
| 2 (POL-02) | `create_proxmox_vm` schema declares `host` required in a way that matches runtime behavior under cluster-scope keyring resolution | VERIFIED | `tool_schemas/proxmox_tools_schema.py:312` shows `"required": ["node", "vmid", "name", "host"]`. The host property at line 302-310 has a description pointing at `homelab-mcp credentials add --type proxmox` (per-node + cluster-scope forms). Runtime `get_proxmox_client` (line 522) raises ValueError when host is None, so schema (host required) and runtime (host required) agree. Test `TestPhase40CreateProxmoxVmSchema::test_create_proxmox_vm_schema_requires_host` asserts `"host" in required` and passes. |
| 3 (POL-03) | When `create_proxmox_vm` cannot resolve credentials, error message points to `homelab-mcp credentials add --type proxmox` (with `--scope cluster:<name>` note) — no message mentions `PROXMOX_HOST` | VERIFIED | `proxmox_api.py:522-529` shows the rewritten ValueError: `"Proxmox host required. Run \`homelab-mcp credentials add --type proxmox <host> <username>\`... \`homelab-mcp credentials add --type proxmox --scope cluster:<name> <token_id>\` for cluster tokens."`. `grep PROXMOX_HOST src/homelab_mcp/proxmox_api.py` returns 0. Test `TestPhase40GetProxmoxClientNoHost::test_get_proxmox_client_no_host_raises_actionable_error` asserts both substrings present and `PROXMOX_HOST` absent. Passes hermetically via `patch.dict(os.environ, {}, clear=True)`. |

**Score:** 3/3 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `src/homelab_mcp/proxmox_api.py` | `_classify_vm_status_error` helper, rewired except branch, env-var-free `get_proxmox_client`, ValueError with credentials-add wording | VERIFIED | Helper at line 620, call site at line 709, ValueError at line 522, docstring updated at line 458. `grep PROXMOX_HOST` = 0; `grep _classify_vm_status_error` = 2; `grep "homelab-mcp credentials add --type proxmox"` = 9; `grep request_info` = 0. |
| `src/homelab_mcp/tool_schemas/proxmox_tools_schema.py` | `create_proxmox_vm` schema with `host` required + description sweep | VERIFIED | `required` list includes `"host"` at line 312; 4 host-property descriptions reference credentials CLI; `grep PROXMOX_HOST` = 0; `grep "homelab-mcp credentials add --type proxmox"` = 4. |
| `src/homelab_mcp/openapi_app.py` | `INFRA_REQUIREMENTS["Proxmox"]` rewritten to mirror Drift Detection phrasing | VERIFIED | Line 59: `"Proxmox": "a Proxmox VE host. Configure credentials with 'homelab-mcp credentials add --type proxmox' (per-node) or '--scope cluster:<name>' (cluster-wide)."`. `grep PROXMOX_HOST` = 0. |
| `tests/test_proxmox_api.py` | New tests for vm_not_found shape, host-required schema, missing-host ValueError | VERIFIED | 3 new test classes present at lines 2349, 2454, 2473: `TestPhase40VmNotFoundShape` (4 tests), `TestPhase40CreateProxmoxVmSchema` (1 test), `TestPhase40GetProxmoxClientNoHost` (1 test). All 6 pass. |
| `tests/test_ast_regression.py` | Extended `_DRIFT_SURFACE_FILES` + `INFRA_REQUIREMENTS["Proxmox"]` scan | VERIFIED | Tuple at line 630-636 contains 5 entries including `proxmox_api.py` and `tool_schemas/proxmox_tools_schema.py`. New dict-value scan at line 686-690 checks `INFRA_REQUIREMENTS.get("Proxmox", "")`. AST guard test passes. |

### Key Link Verification

| From | To  | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| `get_proxmox_vm_status` except branch | `_classify_vm_status_error` helper | synchronous call before fallback return | WIRED | Line 709 `classified = _classify_vm_status_error(e, node=node, vmid=vmid, vm_type=vm_type, host=host or "")`; line 716-717 `if classified is not None: return classified`; line 718-721 falls through to legacy `{"status": "error", "message": "..."}`. |
| `get_proxmox_client` | ValueError with credentials-add pointer | raise statement when host is None | WIRED | Lines 522-529 raise ValueError with both `homelab-mcp credentials add --type proxmox` and `--scope cluster:` literal substrings present. |
| `create_proxmox_vm` schema `required` array | MCP client agents | JSON Schema `required` list | WIRED | `PROXMOX_TOOLS["create_proxmox_vm"]["inputSchema"]["required"] == ["node", "vmid", "name", "host"]` confirmed via Python import and tested. |
| `INFRA_REQUIREMENTS["Proxmox"]` | OpenAPI documentation surface | dict literal | WIRED | Line 59 contains both `homelab-mcp credentials add --type proxmox` and `--scope cluster:<name>`; PROXMOX_HOST absent. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Phase 40 functional tests pass | `uv run pytest tests/test_proxmox_api.py::TestPhase40VmNotFoundShape tests/test_proxmox_api.py::TestPhase40CreateProxmoxVmSchema tests/test_proxmox_api.py::TestPhase40GetProxmoxClientNoHost -v` | 6 passed | PASS |
| AST regression guard passes | `uv run pytest tests/test_ast_regression.py::TestPhase37DriftHygiene -v` | 2 passed | PASS |
| Full unit test suite green | `uv run pytest tests/ -m "not integration" -q --no-cov` | 872 passed, 15 skipped, 25 deselected | PASS |
| Phase 40 module suites green | `uv run pytest tests/test_proxmox_api.py tests/test_proxmox_resolver.py tests/test_proxmox_tools_schema.py tests/test_openapi_infra_requirements.py tests/test_ast_regression.py --no-cov -q` | 139 passed | PASS |
| `PROXMOX_HOST` absent from proxmox surface files | `grep -c PROXMOX_HOST src/homelab_mcp/proxmox_api.py src/homelab_mcp/tool_schemas/proxmox_tools_schema.py src/homelab_mcp/openapi_app.py` | 0 / 0 / 0 | PASS |
| Schema runtime check | `uv run python -c "from src.homelab_mcp.tool_schemas.proxmox_tools_schema import PROXMOX_TOOLS; assert 'host' in PROXMOX_TOOLS['create_proxmox_vm']['inputSchema']['required']"` (run via SUMMARY verification) | exit 0 | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ---------- | ----------- | ------ | -------- |
| POL-01 | 40-01, 40-03 | `get_proxmox_vm_status` returns clean structured "VM not found" error on nonexistent VMID — not raw HTTP 500 with internal API URL leaked (Bug I) | SATISFIED | Helper `_classify_vm_status_error` constructs message from inputs only; URL-leak test (`/api2/`, `internal-proxmox.local` absence asserted) passes. |
| POL-02 | 40-02, 40-03 | `create_proxmox_vm` `host` schema reflects runtime behavior — schema and runtime agree (Bug G schema half) | SATISFIED | Schema `required` includes `host`; runtime ValueError fires when host=None. Both tests pass. |
| POL-03 | 40-01, 40-03 | `create_proxmox_vm` error messages on missing credentials point to `credentials add --type proxmox` / cluster scope, never `PROXMOX_HOST` (Bug G error half) | SATISFIED | ValueError text contains canonical CLI pointer + cluster-scope hint; PROXMOX_HOST grep count 0 in proxmox_api.py. Test asserts both substrings present and PROXMOX_HOST absent. |

All 3 requirement IDs from PLAN frontmatter (POL-01, POL-02, POL-03) accounted for and SATISFIED. No orphaned requirements: REQUIREMENTS.md maps POL-01/02/03 only to Phase 40, all three claimed by plans 40-01/02/03.

### Anti-Patterns Found

None. The Phase 40 surface was scanned for:
- TODO/FIXME/placeholder comments in modified files: none introduced
- Empty implementations: none
- Hardcoded empty data: helper returns structured dict with all required keys populated from real inputs
- Fetch/handler patterns ignoring response: not applicable (sync error classifier)

### Threat Mitigations Verified

- **T-40-01 URL leak (Bug I):** Helper does not read `request_info`; grep `request_info` count = 0 in proxmox_api.py; test asserts sentinel URL absence in result message.
- **T-40-02 env-var pointer (Bug G error half):** ValueError mentions canonical CLI; grep `PROXMOX_HOST` count = 0 in proxmox_api.py.
- **T-40-07 schema/runtime divergence:** Schema requires host; runtime requires host. Convergent.
- **T-40-15 env-var name reintroduction:** AST guard now covers `proxmox_api.py`, `tool_schemas/proxmox_tools_schema.py`, and `INFRA_REQUIREMENTS["Proxmox"]` — any future PROXMOX_HOST reintroduction blocks CI.

### Gaps Summary

None. All 3 roadmap success criteria are observable in the codebase, all 3 requirement IDs (POL-01, POL-02, POL-03) are SATISFIED with code evidence and passing tests, all key links are WIRED, and the regression-guard AST test now revert-proofs the PROXMOX_HOST removal across the Proxmox surface.

The full unit test suite (872 passing) is green. No anti-patterns or stubs introduced. The plan's noted pre-existing failure (`tests/integration/test_credential_binding_round_trip.py::test_add_then_discover_then_drift_succeeds_with_ip_phase381`) was confirmed in 40-03-SUMMARY.md as pre-existing on the base commit and unrelated to Phase 40 — it does not affect Phase 40 goal achievement.

---

_Verified: 2026-04-28_
_Verifier: Claude (gsd-verifier)_
