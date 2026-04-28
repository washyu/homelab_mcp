---
phase: 40-proxmox-vm-lifecycle-polish
plan: 01
subsystem: proxmox
tags: [proxmox, error-hygiene, credentials, aiohttp, env-var-removal, structured-errors]

# Dependency graph
requires:
  - phase: 33.1
    provides: resolve_proxmox_credentials with credentials-add CLI pointer wording (canonical raise at proxmox_api.py:431-440)
  - phase: 38.1
    provides: tier-0 UUID short-circuit (credential_id keyword path) at get_proxmox_client
  - phase: 39
    provides: _classify_unreachable helper pattern (drift_detection.py:196-229) — analog for the new _classify_vm_status_error
provides:
  - "_classify_vm_status_error helper: structured vm_not_found classification without URL leak"
  - "get_proxmox_vm_status returns {error_kind: 'vm_not_found', node, vmid, vm_type, host, message} on Proxmox 500/404 with matching body"
  - "get_proxmox_client requires explicit host (PROXMOX_HOST env-var fallback removed)"
  - "ValueError on missing host points at `homelab-mcp credentials add --type proxmox` CLI (consistent with sibling raise in resolve_proxmox_credentials)"
affects:
  - 40-02  # POL-02 schema sweep + D-05 description sweep
  - 40-03  # POL-* AST guard extension (D-06) — extends test_ast_regression to lock the PROXMOX_HOST=0 invariant

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Module-private classifier returning dict | None for 'classify or fall through' semantics (mirrors drift_detection._classify_unreachable)"
    - "Substring-match heuristic on aiohttp.ClientResponseError.message for vendor-specific error wording (with logger.warning on miss for format-drift telemetry)"
    - "Echo-inputs-back error message style: construct response from caller-supplied params, never from exception URL fields (Bug I closure)"
    - "Verbatim canonical wording reuse across raise sites for grep-ability (homelab-mcp credentials add --type proxmox literal)"

key-files:
  created: []
  modified:
    - "src/homelab_mcp/proxmox_api.py — added _classify_vm_status_error helper above get_proxmox_vm_status; rewired except branch; deleted PROXMOX_HOST env-var fallback at the old line 474; rewrote ValueError at the old line 521; updated docstring host description"
    - "tests/test_proxmox_api.py — added 6 new tests for the helper + updated 5 existing tests to pass host explicitly (env-var fallback gone) + updated 1 D-12 wording assertion"

key-decisions:
  - "Helper returns dict | None (not a tuple): caller pattern is 'if classified is not None: return it' — Optional dict is the cheapest shape for the caller and matches Phase 39 _classify_unreachable's classify-or-fall-through call shape"
  - "Substring-match on both 'does not exist' literal AND str(vmid): Proxmox QEMU and LXC error wording variants both render the vmid; either match suffices, both miss → fall through to legacy with logger.warning"
  - "Helper does NOT call sanitize_error: that is the legacy fallback's job; the helper closes the URL leak by ignoring the exception's URL fields entirely (constructs message from inputs only)"
  - "Existing tests that relied on PROXMOX_HOST env-var population were updated to pass host explicitly rather than deferred to Plan 03: pytest -x verification gate requires green tests, and the wording change is a legitimate behavior shift that makes the old assertions stale"

patterns-established:
  - "Pattern: Vendor-error classifier helper — module-private function above the public consumer; returns structured dict on match or None to delegate to legacy fallback. Logs on miss for telemetry-driven future fixture refresh."
  - "Pattern: Hard-removal of deprecated env-var fallbacks — delete the os.getenv read line entirely, leave PROXMOX_USER/PASSWORD/API_TOKEN paths intact, and rewrite the validation gate to point at the credentials-add CLI."

requirements-completed: [POL-01, POL-03]

# Metrics
duration: ~25min
completed: 2026-04-28
---

# Phase 40 Plan 01: Proxmox VM Lifecycle Polish — POL-01 + POL-03 Summary

**Adds `_classify_vm_status_error` for structured `vm_not_found` responses (closes Bug I URL-leak) and hard-removes the deprecated `PROXMOX_HOST` env-var fallback in `get_proxmox_client` with a credentials-add CLI pointer (closes Bug G error-half).**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-04-28
- **Completed:** 2026-04-28
- **Tasks:** 2 (both TDD: RED → GREEN)
- **Files modified:** 2 (`src/homelab_mcp/proxmox_api.py`, `tests/test_proxmox_api.py`)

## Accomplishments

- POL-01 D-01/D-02: New `_classify_vm_status_error` helper detects Proxmox 500/404 errors whose body contains `"does not exist"` or the vmid as a substring and returns the structured `vm_not_found` dict (`error_kind`, `node`, `vmid`, `vm_type`, `host`, `message`). The `get_proxmox_vm_status` except branch invokes the helper first; on a non-None classification it returns the structured dict; otherwise it falls through to the existing legacy `{"status": "error", "message": "Failed to get VM status: …"}` response (graceful degradation if Proxmox changes its error format).
- POL-03 D-04: Deleted the `host = host or os.getenv("PROXMOX_HOST")` line from `get_proxmox_client`. Host is now mandatory and supplied explicitly. Rewrote the validation `ValueError` to mirror the canonical wording from `resolve_proxmox_credentials` at lines 431-440, pointing at `homelab-mcp credentials add --type proxmox <host> <username>` and `... --scope cluster:<name> <token_id>`. Updated docstring `host` parameter to remove the env-var reference.
- Tier-0 UUID short-circuit (Phase 38.1 D-14) preserved byte-for-byte; `PROXMOX_USER` / `PROXMOX_PASSWORD` / `PROXMOX_API_TOKEN` env reads explicitly preserved per CONTEXT D-04.
- File-level invariants verified by grep: `PROXMOX_HOST` count = 0, `_classify_vm_status_error` count = 2 (definition + call site), `homelab-mcp credentials add --type proxmox` count = 9 (canonical raise + new ValueError + docstring), `request_info` count = 0 (URL-leak guard).
- 104 / 104 tests in `tests/test_proxmox_api.py` + `tests/test_proxmox_resolver.py` pass; ruff and mypy clean.

## Task Commits

Each task was committed atomically (TDD: RED → GREEN per task):

1. **Task 1 RED: Failing tests for `_classify_vm_status_error` helper** — `78a8c37` (test)
2. **Task 1 GREEN: Add helper + rewire `get_proxmox_vm_status` except branch** — `b48fc7e` (feat)
3. **Task 2 RED: Update get_proxmox_client tests for env-var hard-removal** — `5ef98ff` (test)
4. **Task 2 GREEN: Hard-remove PROXMOX_HOST + rewrite ValueError + update doc + 5 stale tests** — `35f3a84` (feat)

## Files Created/Modified

- `src/homelab_mcp/proxmox_api.py` — Added `_classify_vm_status_error` helper above `get_proxmox_vm_status`; rewrote the except branch to invoke the helper first; deleted the `PROXMOX_HOST` env-var fallback; rewrote the missing-host `ValueError` with credentials-add CLI wording; updated `get_proxmox_client` docstring.
- `tests/test_proxmox_api.py` — Added 6 new tests covering the helper contract (structured dict on 500/404 match, None on non-`ClientResponseError`, None on unrelated status, None on unmatched wording, legacy fallback retained, URL-leak guard). Updated 5 existing tests in `TestGetProxmoxClient` and 1 in `TestGetProxmoxClientAsync` to pass `host` explicitly (env-var fallback removed) and to assert the new credentials-add wording. Updated 2 tests in `TestProxmoxSSLVerification` similarly. Updated 1 stale comment block referencing the old `PROXMOX_HOST` ValueError.

## Decisions Made

- **Helper return shape `dict | None`:** Returning `None` on miss lets the call site delegate to the existing legacy fallback with one `if classified is not None:` line, which exactly mirrors the in-tree precedent (`drift_detection._classify_unreachable`'s classify-or-fall-through pattern). A tuple was considered but rejected: the dict form lets the helper own the entire response shape on the match path while leaving the miss path untouched.
- **Substring match on both literal and str(vmid):** Proxmox QEMU and LXC error wording variants both surface the VMID; matching either keeps the heuristic resilient to minor wording drift while still classifying the intended class of failures. On miss, `logger.warning` records the rendered message snippet (truncated to 120 chars) for future fixture refresh.
- **Helper does NOT call `sanitize_error`:** That is the legacy fallback's job. The helper closes the URL leak by **never reading the exception's URL fields at all**, constructing `message` from caller-supplied parameters only. Grep gate `request_info count == 0` enforces this invariant in source.
- **`vm_type: Literal["qemu", "lxc"]` + `# type: ignore[arg-type]` at the call site:** The public function still types `vm_type: str = "qemu"` (out of scope to change), so the call site narrows via `# type: ignore` rather than a runtime cast. mypy stays clean.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Updated 5 existing tests that asserted the old PROXMOX_HOST env-var behavior**

- **Found during:** Task 2 GREEN (post-source-edit pytest run)
- **Issue:** The plan's Task 2 done block said "any failures from tests passing host=None will be addressed in Plan 03 — this task does not modify tests", but the plan's Task 2 verify gate requires `pytest tests/test_proxmox_api.py tests/test_proxmox_resolver.py -x -v` to pass. With `pytest -x` (fail-fast) and 6 tests asserting old wording or relying on `PROXMOX_HOST` env-var population, the gate was unreachable without test updates.
- **Fix:** Updated the affected tests inline:
    - `test_client_missing_host` — assert new credentials-add wording, `PROXMOX_HOST` absence
    - `test_client_from_env_vars` — pass `host="192.168.1.100"` explicitly (env supplies auth only)
    - `test_client_with_api_token_from_env` — pass `host="proxmox.local"` explicitly
    - `test_client_with_explicit_params_override_env` — drop the `PROXMOX_HOST` override (no longer relevant)
    - `test_client_missing_credentials` — pass `host="192.168.1.100"` explicitly
    - `test_get_proxmox_client_no_host_raises_proxmox_host_valueerror` (renamed to `..._raises_credentials_add_valueerror`) — assert new wording
    - `test_ssl_verify_false_override_via_env` — pass host explicitly
    - `test_get_proxmox_client_default_verify_ssl_true` — pass host explicitly
    - Updated the stale comment at the end of `TestGetProxmoxClientAsync` referencing the old PROXMOX_HOST ValueError wording
- **Files modified:** `tests/test_proxmox_api.py`
- **Verification:** All 104 tests in `tests/test_proxmox_api.py` + `tests/test_proxmox_resolver.py` pass; AST regression suite (`tests/test_ast_regression.py`) green
- **Committed in:** `5ef98ff` (Task 2 RED — initial test updates) and `35f3a84` (Task 2 GREEN — additional tests caught after the source edit)
- **Rationale:** The plan's done-section qualification explicitly anticipates this kind of breakage; the verify gate is the binding contract. Inlining the test updates here is necessary for the verification gate, mirrors the same wording change being asserted in the new RED tests, and keeps the worktree leaving in a green state. This is a Rule 1 fix (tests asserting wording that no longer exists are by definition wrong after a deliberate behavior change).

**2. [Plan correction] `request_info` grep gate required docstring rewording**

- **Found during:** Task 1 GREEN (post-implementation grep)
- **Issue:** The plan asserts `grep -c "request_info" src/homelab_mcp/proxmox_api.py` must return 0, but the helper's docstring contained the literal phrase "exception's URL fields (`request_info.url`, etc.) are never read" to explain the URL-leak guard, which made the grep gate fail.
- **Fix:** Rewrote the docstring sentence to "The exception's URL fields are never read, which is what closes the URL-leak in this code path (Bug I)." — preserves intent without mentioning the literal `request_info` token.
- **Files modified:** `src/homelab_mcp/proxmox_api.py` (helper docstring only)
- **Verification:** `grep -c "request_info" src/homelab_mcp/proxmox_api.py` returns 0
- **Committed in:** `b48fc7e` (Task 1 GREEN commit, applied before commit)

---

**Total deviations:** 2 auto-fixed (1 Rule 1 — bug; 1 plan-text-vs-grep-gate reconciliation)
**Impact on plan:** No scope creep. Both fixes were necessary to satisfy the plan's own verification gates. The behavior change is exactly what the plan specified; the inline test updates simply caught up the existing assertions to the new canonical wording.

## Issues Encountered

- The plan's Task 2 done section ("this task does not modify tests") and its verify gate (`pytest -x` must pass) are mutually inconsistent for tests asserting the old wording. Resolved per the deviation noted above; verifier may want to align these in future plans.

## TDD Gate Compliance

Both tasks followed TDD: RED commit → GREEN commit.

- Task 1: `test(40-01)` `78a8c37` (RED) → `feat(40-01)` `b48fc7e` (GREEN)
- Task 2: `test(40-01)` `5ef98ff` (RED) → `feat(40-01)` `35f3a84` (GREEN)

No REFACTOR passes were necessary — both implementations matched the plan-specified shape on first GREEN.

## Threat Flags

None — this plan reduces threat surface (closes Bug I URL leak T-40-01, closes Bug G env-var pointer T-40-02, mitigates credential-pointer phishing T-40-03 via canonical wording reuse). No new endpoints, auth paths, file access, or schema changes at trust boundaries.

## Self-Check: PASSED

**File-level invariants verified:**
- `src/homelab_mcp/proxmox_api.py` — modified, contains `_classify_vm_status_error` (count=2) and `homelab-mcp credentials add --type proxmox` (count=9); zero `PROXMOX_HOST` references; zero `request_info` references
- `tests/test_proxmox_api.py` — modified, contains the 6 new POL-01 helper tests + updated POL-03 tests
- `.planning/phases/40-proxmox-vm-lifecycle-polish/40-01-SUMMARY.md` — created (this file)

**Commits verified in `git log --oneline`:**
- `78a8c37` test(40-01): add failing tests for _classify_vm_status_error helper — FOUND
- `b48fc7e` feat(40-01): add _classify_vm_status_error helper and rewire except branch — FOUND
- `5ef98ff` test(40-01): update get_proxmox_client tests for env-var hard-removal — FOUND
- `35f3a84` feat(40-01): hard-remove PROXMOX_HOST env-var fallback in get_proxmox_client — FOUND

**Verification gates run before commit (all green):**
- `uv run pytest tests/test_proxmox_api.py tests/test_proxmox_resolver.py` — 104 / 104 passed
- `uv run pytest tests/test_ast_regression.py` — 15 / 15 passed
- `uv run ruff check src/homelab_mcp/proxmox_api.py` — All checks passed
- `uv run mypy src/homelab_mcp/proxmox_api.py` — Success: no issues found
- `grep -c PROXMOX_HOST src/homelab_mcp/proxmox_api.py` → 0
- `grep -c "_classify_vm_status_error" src/homelab_mcp/proxmox_api.py` → 2
- `grep -c "homelab-mcp credentials add --type proxmox" src/homelab_mcp/proxmox_api.py` → 9
- `grep -c request_info src/homelab_mcp/proxmox_api.py` → 0
- `grep -c "PROXMOX_USER\|PROXMOX_PASSWORD\|PROXMOX_API_TOKEN" src/homelab_mcp/proxmox_api.py` → 7 (≥3 required, preserves env-var auth path)
- `grep -c credential_id src/homelab_mcp/proxmox_api.py` → 28 (≥4 required, tier-0 short-circuit preserved)

## Next Phase Readiness

- POL-02 (schema sweep, sibling Plan 40-02) and POL-* AST guard extension (Plan 40-03) can proceed in parallel — they touch `tool_schemas/proxmox_tools_schema.py` and `tests/test_ast_regression.py` respectively, no conflict with this plan's edits.
- The 5 sibling Proxmox tools (`manage_proxmox_vm`, `clone_proxmox_vm`, `delete_proxmox_vm`, `list_proxmox_resources`, `get_proxmox_node_status`, `create_proxmox_lxc`) still wrap exceptions with `f"…: {sanitize_error(e)}"`. Per success_criteria D-07, this URL-leak ripple is **explicitly out of scope** for v1.7 and deferred to v1.7.1 LIFE-* phases.
- No blockers for downstream phases.

---
*Phase: 40-proxmox-vm-lifecycle-polish*
*Plan: 01*
*Completed: 2026-04-28*
