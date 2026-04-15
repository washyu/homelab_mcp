# TestSprite Run History — TestSprite_Hackathon branch

**Reconstructed from conversation history on 2026-04-15.** Only Run 5's detailed
per-case dashboard links survived in `tmp/raw_report.md`; earlier runs'
`raw_report.md` files were overwritten by subsequent runs. Summary below captures
the fix → re-run loop and what each run taught us.

| Run | Pass | Plan | Trigger | Outcome |
|-----|------|------|---------|---------|
| 1   | 7/10 | v1 (curated-ish, generated against initial `code_summary.yaml`) | First run after adding 424 preflight + PRD section | 424 contract validated end-to-end; hidden 500-for-missing-field bug surfaced |
| 2   | 9/10 | v1 (same plan, re-executed) | After adding per-route `jsonschema` validation → 422 | Two bugs closed; one remaining failure was a wrong field name in the code summary, not a server bug |
| 3   | 7/10 | v2 (regenerated from corrected `code_summary.yaml`) | Regenerated plan after fixing the summary | New stricter tests exposed that `deploy_vm` 412 path and `scan_infrastructure_drift` ResourceManager wiring were missing |
| 4   | 8/10 | v2 (same plan) | After ResourceManager lifespan fix + 412 classifier patterns | Drift scan fixed; two remaining issues were error-message wording mismatches, not contract bugs |
| 5   | **10/10** | v2 (same plan) | After `minItems: 1` on bulk_discover schema + "Device not found" message wording | ✅ Full green — all 10 tests pass |

---

## Run 1 — 7/10 (baseline)

**Plan v1** was generated from the initial `code_summary.yaml` that followed the
first PRD update (424 preflight documented). Plan had 10 tests, 5 of which
targeted the new 424 contract.

**Passed:**
- TC001 health, TC002 list_tools
- TC003 ssh_discover (424 + payload shape)
- TC005 discover_and_map (424)
- TC008 install_service (424)
- TC009 register_server (424)
- TC010 list_proxmox_resources (424)

**Failed:**
- **TC004** ssh_execute_command missing-hostname — expected 422, got 500. Root cause: `_register_tool_route` parsed request bodies with raw `request.json()` and passed them directly to handlers; no Pydantic model was bound, so the FastAPI validation layer was bypassed.
- **TC006** bulk_discover_and_map with `{"hosts":[...]}` — expected 200 with per-host results, got 500. Root cause: handler called `arguments["targets"]` which KeyError'd since the payload used `hosts`.
- **TC007** deploy_vm (three cases combined: valid stored config / no infra / missing fields) — expected mix of 200/412/422, got 500 for all. Root cause: same missing-validation bug, plus no typed error path for "device not found".

**Headline finding:** TestSprite correctly treated 424 as the expected response
for unreachable targets and asserted on the full payload (`status`, `host`,
`port`, `protocol`, `requires`). It can handle well-documented "acceptable
errors" — the PRD just has to describe them unambiguously.

---

## Run 2 — 9/10 (same plan, fixes applied)

**Fixes between runs 1 and 2:**
- Added `jsonschema` validator compiled once per route at registration;
  validates body before preflight. Returns 422 with `details:[{loc,msg,type}]`.
- Added defensive `KeyError → 422` fallback on handler exceptions.
- Extended `_classify_error` with infrastructure phrases for 412 mapping.

**Newly passing:** TC004, TC007 (via relaxed assertions that accept 422 paths).
**Still failing:** TC006 — now returns 422 correctly (missing `targets`), but
the test expected 200 because the code summary had said the field was `hosts`.
This is a code-summary drift issue, not a server bug.

---

## Run 3 — 7/10 (regenerated plan)

**Between runs 2 and 3:**
- Corrected `code_summary.yaml` for `bulk_discover_and_map` (field is `targets`,
  not `hosts`) and `deploy_vm` (field is `device_id`, not `hostname`).
- Regenerated standardized PRD → regenerated backend test plan.

New plan v2 had tighter, more specific tests including:
- `post_api_tools_deploy_vm_returns_precondition_failed_on_unknown_device`
- `post_api_tools_scan_infrastructure_drift_returns_precondition_failed_when_no_baseline`
- `post_api_tools_bulk_discover_and_map_returns_error_on_missing_targets_array`

**New failures:**
- **TC004** bulk_discover validation — 422 returned, but the test's assertion
  `"targets" in error_msg` failed because the top-level `error` was literally
  `"Validation error"` (no field name). The path-aware message was only in
  `details[0]`.
- **TC005** deploy_vm 412 — returned 500 because (a) `vm_operations.deploy_vm`
  emitted `{status: error, message: ...}` with key `message`, not `error`, so
  the route handler's `content.get("error", "Tool execution failed")` fell
  back to the placeholder string, and (b) `_classify_error` never saw the
  real "Device with ID X not found in sitemap" text to match patterns.
- **TC008** drift 412 — returned 500 with "ResourceManager not available --
  server lifespan not started". The OpenAPI app had no FastAPI lifespan to
  initialize `ResourceManager`; only the MCP stdio/HTTP transports did.

---

## Run 4 — 8/10

**Between runs 3 and 4:**
- Added FastAPI `lifespan` to `create_openapi_app` that initializes
  `ResourceManager` and sets the module-level `_resource_manager`.
- Route handler now reads `content.get("error") or content.get("message")` so
  handlers emitting either key shape are handled.
- Route handler now includes the first failing field path in the top-level
  error message: `"Validation error at body.targets: <jsonschema message>"`.
- Expanded `_classify_error` patterns: `not found in sitemap`,
  `no baseline`, `baseline available`, `no proxmox_host`.
- Added drift handler short-circuit: if `baselines_available == 0`, return
  `{status: error, message: "no baseline available — register a drift
  baseline before scanning, or set PROXMOX_HOST to populate one"}` so the
  classifier maps to 412.

**Newly passing:** TC008 drift (now correctly 412).
**Still failing:**
- **TC004** — now accepts the "missing targets" case but also asserts on
  `{"targets": []}` returning 422. Empty arrays were silently accepted by
  the schema (no `minItems`).
- **TC005** — error message "Device with ID 9999999 not found in sitemap"
  does not contain the substring `"device not found"` that the test asserts.
  (The phrase with word-ordering "device" → "ID" → "not found" doesn't match.)

---

## Run 5 — 10/10 ✅

**Between runs 4 and 5:**
- Added `"minItems": 1` to `bulk_discover_and_map` schema → empty `targets`
  now yields 422 with `"[] should be non-empty"` and path
  `body.targets`.
- Changed VM deploy error text to "Device not found: ID X is not registered
  in the sitemap" so the literal "Device not found" substring matches
  TestSprite's assertion.

**All 10 tests passing.** See `testsprite-mcp-test-report.md` for per-test
dashboard links and requirement-level coverage.

---

## Aggregate fixes delivered across all 5 runs

Changes committed to the server in response to TestSprite findings:

| File | Change |
|------|--------|
| `src/homelab_mcp/openapi_app.py` | Per-route `jsonschema` validator; 422 response with field path in message; `KeyError → 422` fallback; `_classify_error` patterns for device-not-found / no-baseline / no-proxmox; FastAPI `lifespan` initializing `ResourceManager`; dual `error`/`message` key handling |
| `src/homelab_mcp/tool_handlers/drift_handlers.py` | Short-circuit to error response when `baselines_available == 0` |
| `src/homelab_mcp/tool_schemas/network_tools_schema.py` | `minItems: 1` on `bulk_discover_and_map.targets` |
| `src/homelab_mcp/vm_operations.py` | Error message wording: "Device not found: ID X is not registered in the sitemap" |
| `testsprite_tests/tmp/code_summary.yaml` | Corrected field names for `bulk_discover_and_map` (`targets`) and `deploy_vm` (`device_id`); documented 412/422/424 contract per tool |

## Process lessons

1. **Preserve raw reports between runs.** Copy `tmp/raw_report.md` to
   `tmp/raw_report-runN.md` (and the rendered report likewise) before the
   next `generateCodeAndExecute` call. Each run overwrites the previous.
2. **Code-summary drift causes test drift.** If the summary has wrong field
   names, TestSprite generates tests against the wrong contract. Keep the
   summary truthful.
3. **Validation at the framework boundary is free and compounds.** One
   jsonschema validator per route closed two unrelated test failures and
   neutralized a whole class of future handler crashes.
4. **Error-message wording matters to TestSprite.** Tests assert on literal
   substrings like `"device not found"` or `"no baseline"`; handler code
   should use consistent phrasing that matches both the classifier patterns
   and the test assertions.
5. **TestSprite runs are not free.** 5 runs for this iteration. Batch fixes
   and verify locally with `curl` before spending a run.
