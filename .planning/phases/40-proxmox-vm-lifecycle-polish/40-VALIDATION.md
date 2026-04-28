---
phase: 40
slug: proxmox-vm-lifecycle-polish
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-28
---

# Phase 40 — Validation Strategy

> Reconstructed retroactively from PLAN/SUMMARY artifacts after phase completion. Every requirement (POL-01, POL-02, POL-03) has at least one automated regression guard; the Phase 40 D-06 AST guard extension revert-proofs the PROXMOX_HOST removal across the Proxmox surface.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio + pytest-mock |
| **Config file** | `pytest.ini` (rootdir) + `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/test_proxmox_api.py tests/test_proxmox_tools_schema.py tests/test_openapi_infra_requirements.py tests/test_ast_regression.py --no-cov -q` |
| **Full suite command** | `uv run pytest tests/ -m "not integration" --no-cov -q` |
| **Estimated runtime** | ~3s for the Phase 40 surface (~30s for full unit suite) |

---

## Sampling Rate

- **After every task commit:** Run the per-task command from the Per-Task Verification Map.
- **After every plan wave:** Run the quick run command above.
- **Before `/gsd-verify-work`:** Full suite must be green.
- **Max feedback latency:** ~3s for Phase 40 surface tests.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 40-01-01 | 01 | 1 | POL-01 | T-40-01 (URL leak) | `_classify_vm_status_error` constructs message from inputs only; never reads `exc.request_info`; URL substring `/api2/` absent from result | unit | `uv run pytest tests/test_proxmox_api.py::TestPhase40VmNotFoundShape -x -v` | ✅ | ✅ green |
| 40-01-02 | 01 | 1 | POL-03 | T-40-02 (env-var pointer) | `get_proxmox_client(host=None)` raises ValueError pointing at `homelab-mcp credentials add --type proxmox` and `--scope cluster:`; never mentions `PROXMOX_HOST` | unit | `uv run pytest tests/test_proxmox_api.py::TestPhase40GetProxmoxClientNoHost tests/test_proxmox_api.py::TestGetProxmoxClient -x -v` | ✅ | ✅ green |
| 40-02-01 | 02 | 1 | POL-02 | T-40-07 (schema/runtime divergence) | `PROXMOX_TOOLS["create_proxmox_vm"]["inputSchema"]["required"]` contains `"host"`; zero `PROXMOX_HOST` in `proxmox_tools_schema.py`; host descriptions point at the credentials CLI | unit | `uv run pytest tests/test_proxmox_tools_schema.py -x -v` | ✅ | ✅ green |
| 40-02-02 | 02 | 1 | POL-02 (D-05 ripple) | T-40-08 (credential-pointer phishing) | `INFRA_REQUIREMENTS["Proxmox"]` mirrors Drift Detection phrasing; references credentials-add CLI; no `PROXMOX_HOST`; no `register_server` pointer | unit | `uv run pytest tests/test_openapi_infra_requirements.py -x -v` | ✅ | ✅ green |
| 40-03-01 | 03 | 2 | POL-01 + POL-02 + POL-03 | T-40-12, T-40-13, T-40-14 | Functional regression tests for vm_not_found shape (canonical, LXC vmid-substring, 404 defensive, fallback), host-required schema, missing-host ValueError | unit | `uv run pytest tests/test_proxmox_api.py::TestPhase40VmNotFoundShape tests/test_proxmox_api.py::TestPhase40CreateProxmoxVmSchema tests/test_proxmox_api.py::TestPhase40GetProxmoxClientNoHost -x -v` | ✅ | ✅ green |
| 40-03-02 | 03 | 2 | D-06 (cross-cutting) | T-40-15 (env-var name reintroduction) | AST guard scans `proxmox_api.py`, `tool_schemas/proxmox_tools_schema.py`, and `INFRA_REQUIREMENTS["Proxmox"]` for `PROXMOX_HOST`; reintroduction blocks CI | unit | `uv run pytest tests/test_ast_regression.py::TestPhase37DriftHygiene -x -v` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. pytest + pytest-asyncio + pytest-mock were already installed and configured pre-Phase-40; no new fixtures, conftest changes, or framework installs were required. The two new test files added by Plan 02 (`tests/test_proxmox_tools_schema.py`, `tests/test_openapi_infra_requirements.py`) follow the existing test layout conventions.

---

## Manual-Only Verifications

All phase behaviors have automated verification.

The deferred ripple to the 5 sibling Proxmox tools (`manage_proxmox_vm`, `clone_proxmox_vm`, `delete_proxmox_vm`, `list_proxmox_resources`, `get_proxmox_node_status`, `create_proxmox_lxc`) is **explicitly out of scope** for Phase 40 per CONTEXT D-07 and is tracked for v1.7.1 LIFE-* phases. Those tools' `f"...: {sanitize_error(e)}"` wrappers and optional-host claims are left intact and are not part of Phase 40's validation surface.

---

## Cross-Plan Integration Gate

The Wave 2 cross-plan integration gate is `uv run pytest tests/ -m "not integration" --no-cov -q` — confirmed green per `40-VERIFICATION.md`: 872 passed, 15 skipped on 2026-04-28.

The pre-existing failure noted in `40-03-SUMMARY.md` (`tests/integration/test_credential_binding_round_trip.py::test_add_then_discover_then_drift_succeeds_with_ip_phase381`) is in the integration tier (Docker-required) and was confirmed pre-existing on the base commit `4423553` — it is unrelated to Phase 40 and tracked separately.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify
- [x] Sampling continuity: every task in every plan has an automated command (no 3-task gap)
- [x] Wave 0 covers all MISSING references (none — existing infrastructure sufficient)
- [x] No watch-mode flags (all commands are one-shot pytest invocations)
- [x] Feedback latency < ~3s for Phase 40 surface
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-04-28 (retroactive reconstruction from completed-phase artifacts; all 22 Phase 40 tests green at validation time)
