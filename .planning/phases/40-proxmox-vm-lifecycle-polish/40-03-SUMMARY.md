---
phase: 40-proxmox-vm-lifecycle-polish
plan: 03
type: execute
status: complete
wave: 2
requirements:
  - POL-01
  - POL-02
  - POL-03
key-files:
  modified:
    - tests/test_proxmox_api.py
    - tests/test_ast_regression.py
  created: []
---

# Plan 40-03 Summary

## What was built

Phase 40 verification wave: turned the Wave 1 production changes into automated proofs.

**`tests/test_proxmox_api.py`** — three new test classes:

- `TestPhase40VmNotFoundShape` — 4 tests covering `_classify_vm_status_error`:
  - 500 + "does not exist" body → full vm_not_found shape; URL-leak guard explicit (`/api2/`, `internal-proxmox.local` absence asserted)
  - LXC variant (vmid-as-substring path)
  - 404 defensive path
  - Unmatched-body fallback to legacy `{status, message}` shape
- `TestPhase40CreateProxmoxVmSchema` — `host` is in `PROXMOX_TOOLS["create_proxmox_vm"]["inputSchema"]["required"]`; description carries `homelab-mcp credentials add --type proxmox`; no `PROXMOX_HOST` mention
- `TestPhase40GetProxmoxClientNoHost` — `get_proxmox_client(host=None)` raises `ValueError` with credentials-CLI hint and `--scope cluster:` mention; no `PROXMOX_HOST` text; no legacy "must be provided or set" wording. Hermetic via `patch.dict(os.environ, {}, clear=True)`.

**`tests/test_ast_regression.py`** — extended `TestPhase37DriftHygiene`:

- `_DRIFT_SURFACE_FILES` now includes `proxmox_api.py` and `tool_schemas/proxmox_tools_schema.py` (5 entries)
- Added `INFRA_REQUIREMENTS.get("Proxmox", "")` dict-value scan (alongside the existing "Drift Detection" scan)
- Class docstring, method docstring, comment block, violation message, and final assert message now cite Phase 37 D-11 + Phase 40 D-06 / POL-03
- The previous "openapi_app.py is intentionally NOT in this list — Proxmox is Phase 40 territory" carve-out is gone — now actively enforced

## Commits

- `c95226a` test(40-03): add Phase 40 functional tests for vm_not_found shape, host-required schema, and missing-host ValueError
- `9549f83` test(40-03): extend AST regression guard to cover proxmox_api.py + proxmox_tools_schema.py + INFRA_REQUIREMENTS['Proxmox'] (Phase 40 D-06)

## Verification

- `uv run pytest tests/test_proxmox_api.py::TestPhase40VmNotFoundShape tests/test_proxmox_api.py::TestPhase40CreateProxmoxVmSchema tests/test_proxmox_api.py::TestPhase40GetProxmoxClientNoHost -x` → 6 passed
- `uv run pytest tests/test_ast_regression.py -x` → 15 passed
- `uv run pytest tests/test_proxmox_api.py -x` → 103 passed
- `uv run pytest tests/ -m "not integration" -q` → 872 passed, 15 skipped (was 866 pre-Plan-03 → +6 new tests)
- `uv run ruff check tests/test_proxmox_api.py tests/test_ast_regression.py` → All checks passed
- Grep gates: `Phase 40 D-06` ≥ 4 (got 12); `proxmox_api.py` in tuple ≥ 1; `tool_schemas/proxmox_tools_schema.py` in tuple ≥ 1; `INFRA_REQUIREMENTS.get("Proxmox"` ≥ 1

## Deviations from Plan

**Executed inline rather than in a worktree subagent.** The original Wave 2 executor agent was spawned with `isolation="worktree"`, but the harness created its worktree from `b580d30` (main) instead of credential-cleanup HEAD `4eca7a7`. The agent's required `git reset --hard` to the correct base was sandbox-denied, leaving the worktree without the Wave 1 production code that this plan's regression tests are meant to guard. The orchestrator switched to inline execution on the main working tree to unblock — same edits, same commits, same verification gates.

No production code touched. No scope creep.

## Pre-existing failure noted (not introduced by Phase 40)

`tests/integration/test_credential_binding_round_trip.py::test_add_then_discover_then_drift_succeeds_with_ip_phase381` fails on credential-cleanup HEAD: `drift_detection.py:419` calls `get_proxmox_client(host=h, session=session)` without threading `credential_id`, violating the Phase 38.1 binding contract that this test enforces. Verified the failure is present on the pre-Phase-40 base commit `4423553` (file was unchanged by Phase 40 work). Out of scope for Phase 40; flagged here for later triage.

## Requirements completed

POL-01 (vm_not_found shape) + POL-02 (host required) + POL-03 (missing-host ValueError) now have automated regression guards. Phase 40 D-06 AST guard now revert-proofs PROXMOX_HOST removal across the Proxmox surface.
