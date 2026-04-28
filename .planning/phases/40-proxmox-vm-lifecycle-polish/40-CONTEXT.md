# Phase 40: Proxmox VM Lifecycle Polish — Context

**Gathered:** 2026-04-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Polish two specific Proxmox tool failure paths so a user hitting Bug I or Bug G gets a structured, actionable error instead of leaked HTTP internals or pointers to deprecated configuration:

- **POL-01 (Bug I):** `get_proxmox_vm_status` — when the VMID does not exist on the target node, return a structured `vm_not_found` error with `node`, `vmid`, `vm_type`, and `host` echoed back, plus a recovery pointer to `list_proxmox_resources`. No raw HTTP 500 leak. No internal Proxmox API URL in the message.
- **POL-02 (Bug G — schema half):** `create_proxmox_vm` schema declares `host` accurately versus runtime. Schema and runtime agree.
- **POL-03 (Bug G — error half):** When `create_proxmox_vm` cannot resolve credentials (or `host` is missing), the error points to `homelab-mcp credentials add --type proxmox` (with cluster-scope hint). Never mentions `PROXMOX_HOST`.

Out of this phase:

- URL-leak / `sanitize_error(e)` polish for the other 5 proxmox tools (`manage_proxmox_vm`, `clone_proxmox_vm`, `delete_proxmox_vm`, `list_proxmox_resources`, `get_proxmox_node_status`, `create_proxmox_lxc`) — same root cause as Bug I but not in POL-01..03 scope. → v1.7.1 lifecycle hooks (LIFE-* phases will rewrite their error paths anyway).
- Removing the deprecated `PROXMOX_USER` / `PROXMOX_PASSWORD` / `PROXMOX_API_TOKEN` env-var auth path. v1.6 deprecated env-var-as-source-of-truth; this phase only removes `PROXMOX_HOST`. The other env vars stay readable as the resolver-bypass fallback (proxmox_api.py:496-504 deliberate behavior).
- New MCP tools or schema additions. Polish-only phase.
- Drift-family changes — POL-01..03 are independent of drift work.

</domain>

<decisions>
## Implementation Decisions

### POL-01: VM-not-found detection (`get_proxmox_vm_status`)

- **D-01:** Detect VM-not-found by inspecting the `aiohttp.ClientResponseError`: `e.status == 500` AND the response body contains `"does not exist"` or the supplied `vmid` as a substring (Proxmox's QEMU/LXC error wording for missing VMID; LXC variant differs but both contain the VMID). Handle `e.status == 404` similarly for missing-node case (defensive — covers the "node typo" sibling failure mode without expanding requirements). When the body cannot be read or wording doesn't match, fall back to the existing generic-error response shape — acceptable graceful degradation if Proxmox changes its error format. Zero extra round-trips on the happy path.
- **D-02:** Return shape on detection:
  ```
  {
    "status": "error",
    "error_kind": "vm_not_found",
    "node": str,
    "vmid": int,
    "vm_type": "qemu" | "lxc",
    "host": str,
    "message": str,   # e.g., "VM 9999 (qemu) not found on node 'pve1' at host 'homelab-pve1'. Run list_proxmox_resources to see available VMs."
  }
  ```
  - `error_kind` is the programmatic discriminator — agents key off it. `message` is the human sentence.
  - `status: "error"` retained (binary success/error contract — every other proxmox tool does this).
  - All four input fields echoed per ROADMAP SC-1 ("hostname and VMID echoed back").
  - The current sanitized exception wording (which currently includes the API URL because `sanitize_error` only redacts credentials, not URLs) MUST NOT be inserted into `message`. Construct the sentence from the inputs.

### POL-02: `host` parameter shape (`create_proxmox_vm`)

- **D-03:** Mark `host` as **required** in the `create_proxmox_vm` schema. New `required` list: `["node", "vmid", "name", "host"]`. Description rewrite (recommended starting point — planner may polish):
  > "Proxmox host. Any node hostname covered by your registered credential (per-node) or cluster-scope token. Register with `homelab-mcp credentials add --type proxmox <host> <username>`, or `... --scope cluster:<name> <token_id>` for cluster tokens."
  - Cleanest schema/runtime alignment now that POL-03 (D-04) hard-removes the env-var fallback.
  - Breaking schema change. Acceptable: v1.7 milestone-open already announced the env-var deprecation direction; users registering via CLI per CRED-04 are unaffected. Document in milestone close notes.
  - The existing description text "Proxmox host (optional)" is removed.

### POL-03: PROXMOX_HOST env-var fate

- **D-04:** **Hard-remove** the env-var fallback at `src/homelab_mcp/proxmox_api.py:474`. Delete the line `host = host or os.getenv("PROXMOX_HOST")`. Rewrite the line 521 ValueError text to:
  > `"Proxmox host required. Run `homelab-mcp credentials add --type proxmox <host> <username>` to register a node, or `... --scope cluster:<name> <token_id>` for cluster tokens."`
  - Affects every proxmox tool consistently (shared helper). Symmetric with v1.6's `mcp_admin` cleanup direction and Phase 38.1's keystore-binding architecture (no env-var dominance over keyring resolution).
  - Makes POL-02's "host required" load-bearing — a caller that previously relied on PROXMOX_HOST now MUST supply `host` (schema enforces for `create_proxmox_vm`; other tools surface the rewritten ValueError pointing at credentials add).
  - Does NOT touch `PROXMOX_USER` / `PROXMOX_PASSWORD` / `PROXMOX_API_TOKEN` env-var reads at proxmox_api.py:479-481 — those remain the resolver-bypass fallback per the existing CR-04 (Phase 38.1 review) deliberate behavior. Phase 40 scope is `PROXMOX_HOST` only.

### Sweep scope (ripple)

- **D-05:** **Sweep all `PROXMOX_HOST env var` mentions in `src/homelab_mcp/tool_schemas/proxmox_tools_schema.py` description text.** Lines 48, 54, 76 (and any other matches) — rewrite to point at `homelab-mcp credentials add --type proxmox` or omit the env-var sentence where redundant. Mechanical, description-text only — no schema shape change for tools other than `create_proxmox_vm` (POL-02 D-03). Closes the schema-runtime divergence everywhere, not just for the two POL-named tools.
- **D-06:** **Extend the AST guard** introduced in Phase 37 D-11 to revert-proof the cleanup. Add `src/homelab_mcp/proxmox_api.py` and `src/homelab_mcp/tool_schemas/proxmox_tools_schema.py` to the existing `tests/test_ast_regression.py` PROXMOX_HOST-zero-matches assertion. Matches the regression-test scope memory (AST guards for known footguns; PROXMOX_HOST is now one across the drift + proxmox surfaces).
- **D-07:** **Defer URL-leak ripple** to v1.7.1. The other 5 proxmox tools (`manage_proxmox_vm`, `clone_proxmox_vm`, `delete_proxmox_vm`, `list_proxmox_resources`, `get_proxmox_node_status`, `create_proxmox_lxc`) still wrap `f"...: {sanitize_error(e)}"` and have the same URL-leak vulnerability as Bug I. v1.7.1 LIFE-* phases will rewrite their error paths for lifecycle-hook integration. Captured in Deferred Ideas.

### Claude's Discretion

- Exact substring-match list for D-01's body-scan ("does not exist", vmid as substring). Planner verifies against actual Proxmox response shapes (test fixture from a live host or PVE 8.x docs). If LXC wording materially differs, the helper accepts a tuple of acceptable patterns.
- Whether the `vm_not_found` detection logic lives inline in `get_proxmox_vm_status` (proxmox_api.py:612-650) or in a small helper `_classify_vm_status_error(exc, node, vmid, vm_type, host) -> dict | None` returning the structured response or None. Helper recommended — mirrors Phase 39's `_classify_probe_outcome` pattern (per-row classification with reason enum) and isolates the substring-match heuristic for unit testing.
- Exact `message` wording in the `vm_not_found` response. D-02 template is a starting point; planner polishes to match Phase 37 D-08 / Phase 39 D-07 actionability conventions.
- Exact ValueError wording in D-04. Template provided; planner picks the final phrasing. The `homelab-mcp credentials add --type proxmox` exact form is canonical (matches `resolve_proxmox_credentials` line 433-440 already-shipped wording — keep it consistent).
- Whether the AST guard (D-06) reuses the existing assertion (string list of files) or factors into a helper. Existing assertion list — minimal change, matches Phase 37 D-11's pattern.
- Whether `host` becoming required (D-03) propagates to the OpenAPI app schema (`openapi_app.py`). Planner verifies — if openapi_app surfaces tool schemas, it inherits automatically; if it duplicates the schema, both must update.
- Whether existing tests that pass `host=None` to `create_proxmox_vm` need updating. Planner runs the test suite, fixes failures inline.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 40 lock-ins

- `.planning/ROADMAP.md` §Phase 40 — Phase goal + 3 Success Criteria (closes Bug I, Bug G schema half, Bug G error half); the scope anchor.
- `.planning/REQUIREMENTS.md` §Polish (POL-*) — POL-01, POL-02, POL-03 + Coverage Map (Bug G → POL-02 + POL-03; Bug I → POL-01).

### Prior phase decisions (locked, inherited)

- `.planning/phases/37-drift-output-shape-error-hygiene/37-CONTEXT.md` §D-11 — AST meta-test pattern banning `PROXMOX_HOST` in drift files. Phase 40 D-06 extends the same assertion to `proxmox_api.py` and `proxmox_tools_schema.py`.
- `.planning/phases/37-drift-output-shape-error-hygiene/37-CONTEXT.md` §D-08 — error-message style points users at sitemap CRUD tools, never deprecated env vars. Phase 40 follows the convention for the proxmox-family error rewrites.
- `.planning/milestones/v1.6-phases/34-cluster-scoped-proxmox-credentials/34-CONTEXT.md` §D-09/D-10 — `resolve_proxmox_credentials` per-node → cluster tier walk; cluster-scope tokens cover any node hostname in their cluster_name. POL-02 D-03's "any node hostname covered by your cluster-scope token" wording lands directly on this resolver behavior.
- `.planning/phases/38.1-sitemap-keystore-credential-binding/38.1-CONTEXT.md` §D-14 — `credential_id` keyword on `resolve_proxmox_credentials` and `get_proxmox_client`. Phase 40 does not change the binding path; the env-var-removal at proxmox_api.py:474 must NOT regress the existing tier-0 UUID short-circuit.

### Memory / user feedback

- `~/.claude/projects/C--Users-washy-projects-mcp-python-server/memory/feedback_regression_test_scope.md` — AST meta-tests guard known footguns; D-06 (extend PROXMOX_HOST AST guard to proxmox_api + schema) qualifies (PROXMOX_HOST removal is footgun-class — copy-paste from old code is the recurrence vector). New behavior (vm_not_found detection D-01/D-02) gets functional + unit tests, not AST guards.
- `~/.claude/projects/C--Users-washy-projects-mcp-python-server/memory/project_credential_architecture.md` — keyring-only credential pattern; missing entry = hard error with CLI pointer. POL-03 D-04 lands directly on this principle.

### Source files (read before changing)

- `src/homelab_mcp/proxmox_api.py:612-650` — `get_proxmox_vm_status` current implementation. POL-01 D-01/D-02 changes the `except (aiohttp.ClientError, ValueError)` block to: detect `aiohttp.ClientResponseError` with `status` attribute, classify via the new helper, return the structured `vm_not_found` shape on match, fall through to the existing generic-error response otherwise.
- `src/homelab_mcp/proxmox_api.py:443-528` — `get_proxmox_client`. POL-03 D-04 deletes line 474 and rewrites line 521. The credential-resolver branch at 495-517 is unchanged. Tier-0 UUID short-circuit (Phase 38.1 D-14) preserved.
- `src/homelab_mcp/proxmox_api.py:842-927` — `create_proxmox_vm` runtime. No code changes here directly; the schema change in `proxmox_tools_schema.py` (POL-02 D-03) and the shared `get_proxmox_client` rewrite (POL-03 D-04) are sufficient to satisfy POL-02/03. Verify: existing handler at `tool_handlers/proxmox_handlers.py:143-160` already passes `arguments.get("host")` — once the schema makes host required, the handler will always receive a value and never trigger the new ValueError.
- `src/homelab_mcp/tool_schemas/proxmox_tools_schema.py` — schema definitions for all proxmox tools.
  - Lines 222-294 (`create_proxmox_vm`): POL-02 D-03 — add `"host"` to `required`, rewrite description.
  - Lines 48, 54, 76 (and any other "PROXMOX_HOST env var" mentions): D-05 — sweep description text.
- `src/homelab_mcp/tool_handlers/proxmox_handlers.py:143-160` — `handle_create_proxmox_vm`. Verify the `validate_hostname(host)` call at line 148 still fires when host becomes required (it should — `validate_hostname` runs unconditionally on the supplied value).
- `src/homelab_mcp/openapi_app.py` — POL-02 D-03 (Claude's Discretion): planner verifies whether this file surfaces or duplicates the proxmox tool schemas; if duplicated, the host-required + description rewrite applies here too.
- `tests/test_ast_regression.py` — Phase 37 D-11 PROXMOX_HOST assertion. D-06 extends the file list to include `proxmox_api.py` + `proxmox_tools_schema.py`.
- `tests/test_proxmox_*.py` (planner verifies exact filenames) — functional tests for `get_proxmox_vm_status` and `create_proxmox_vm`. New tests:
  - `vm_not_found` shape — fixture mocks `aiohttp.ClientResponseError(status=500)` with body containing "does not exist"; assert response shape per D-02.
  - `host` schema required — assert schema declares `"host"` in `required` list (mechanical schema test).
  - `create_proxmox_vm` no-host error — call without `host` (where the test bypasses schema validation, e.g., direct runtime call); assert ValueError text matches D-04 wording and contains `homelab-mcp credentials add --type proxmox` and does NOT contain `PROXMOX_HOST`.

### External / Proxmox API reference

- Proxmox VE API — `GET /nodes/{node}/qemu/{vmid}/status/current` returns HTTP 500 with body `{"data":null,"errors":{"vmid":"..."}}` (or similar) when the VMID does not exist. Documented at https://pve.proxmox.com/pve-docs/api-viewer/. Planner confirms exact body wording against PVE 8.x via either a live host or doc lookup before locking the substring-match list in D-01.
- `GET /nodes/{node}/lxc/{vmid}/status/current` — analogous shape for LXC. Same handling.

### Pattern / architecture reference

- `sanitize_error()` (`log_filter.py:64-77`) — credential-redaction only. Does NOT redact API URLs. Phase 40 D-02 constructs the `vm_not_found` message from inputs (no `sanitize_error(e)` wrap), so URL leak is closed for this code path. The wider URL-leak class in other tools is deferred per D-07.
- `resolve_proxmox_credentials` error-message wording at `proxmox_api.py:433-440` — already references `homelab-mcp credentials add --type proxmox`. POL-03 D-04's ValueError rewrite uses identical phrasing for cross-error consistency.
- Phase 39 `_classify_probe_outcome` pattern (per-row classification helper). Phase 40 Claude's Discretion suggests `_classify_vm_status_error` as a sibling helper — same classify-and-return-or-None shape.
- Phase 36/37 structured-error shape: `{status: "error", message: "..."}` is the binary contract. POL-01 D-02 extends it with `error_kind` + echoed inputs without breaking the contract.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`get_proxmox_vm_status` skeleton** at `proxmox_api.py:612` — already structured as try/except returning a `{status, message}` dict. POL-01 only changes the `except` branch.
- **`resolve_proxmox_credentials` ValueError wording** at `proxmox_api.py:433-440` — canonical `homelab-mcp credentials add --type proxmox` / cluster-scope phrasing. Reuse verbatim in POL-03 D-04 for consistency.
- **Phase 37 PROXMOX_HOST AST guard** in `tests/test_ast_regression.py` — file list assertion. POL D-06 extends the list, no new test scaffolding.
- **`aiohttp.ClientResponseError`** carries `status` (HTTP code) and reads its body via `e.message` plus the optional `e.response`/awaiting; planner confirms which idiom is used elsewhere in the codebase. Phase 35 SSH probes have similar try/except shape but different exception class.
- **`Literal["qemu", "lxc"]`** type pattern — `get_proxmox_vm_status` accepts `vm_type: str = "qemu"`; the response shape D-02 echoes the supplied `vm_type`.

### Established Patterns

- **Per-row classification with reason enum + human message** (Phase 38.1 D-08, Phase 39 D-08) — POL-01 D-02 follows: `error_kind: "vm_not_found"` is the enum; `message` is the human sentence.
- **Hard-error-with-actionable-pointer** (CRED-05 from v1.6) — POL-03 D-04 lands directly on this pattern. No silent fallback when the env var is missing; instead a structured ValueError with the CLI command to fix it.
- **AST meta-test for footgun removal** (Phase 35 D-15, Phase 38.1 D-15/D-16, Phase 37 D-11) — D-06 extends the established pattern. Targeted file list, no whole-tree scan.
- **Schema-runtime contract** — Phase 37 already cleaned up drift schema lies. POL-02 D-03 closes the same gap on the proxmox surface.

### Integration Points

- **`get_proxmox_client` line 474** — single-point change for env-var removal; affects every proxmox tool through shared helper.
- **`get_proxmox_vm_status` line 645 except block** — single-point change for VM-not-found classification.
- **`create_proxmox_vm` schema `required` array** at `proxmox_tools_schema.py:292` — single-list change for POL-02 D-03.
- **`tests/test_ast_regression.py` PROXMOX_HOST file list** — single-list change for D-06.

</code_context>

<specifics>
## Specific Ideas

- **Proxmox returns HTTP 500, not 404, on missing VMID.** This is a Proxmox API quirk — the body carries the diagnostic, not the status code. POL-01 D-01's status+body double-check is the consequence. Pure status-code matching would either over-match (any 500) or under-match (skip the case entirely).
- **`error_kind` is the discriminator, `message` is the sentence.** Mirrors Phase 38.1 / Phase 39 not_eligible reason enums. Agents key off `error_kind`; humans read `message`. Don't conflate.
- **Echo the inputs back; don't pass through the exception.** ROADMAP SC-1 says "hostname and VMID echoed back" — the response is constructed from the inputs to `get_proxmox_vm_status`, not from `e.request_info` or `e.message`. This is what closes the URL-leak (the URL only exists in the exception payload; we never read from it).
- **`host` becomes required because the env-var path goes away.** POL-02 and POL-03 are coupled. Without POL-03's hard-remove, "mark host required" would be schema-only theater (runtime would still accept None via env var). With it, schema and runtime are honest.
- **The other 5 proxmox tools have the same URL-leak as Bug I, but are out of scope.** Captured as deferred. v1.7.1 LIFE-* phases own those rewrites because lifecycle hooks must update sitemap on create/destroy and that work touches the same error paths.
- **AST guard is footgun-protection, not feature-spec.** Per memory `feedback_regression_test_scope.md` — D-06 (PROXMOX_HOST ban extension) qualifies because copy-paste of legacy code is the recurrence vector. New `vm_not_found` behavior gets functional + unit tests, not AST coverage.
- **Reuse `resolve_proxmox_credentials` wording verbatim.** That function already raises with the exact `homelab-mcp credentials add --type proxmox` phrasing. POL-03's `get_proxmox_client` ValueError lands on identical text — one canonical sentence for "no creds, here's how to add some".

</specifics>

<deferred>
## Deferred Ideas

Captured during 40 discussion — preserved so v1.7.1 / v1.7.2 / v1.8 / future phases pick them up.

- **URL-leak / structured-error polish for the other 5 proxmox tools.** Same root as Bug I (POL-01) — `manage_proxmox_vm`, `clone_proxmox_vm`, `delete_proxmox_vm`, `list_proxmox_resources`, `get_proxmox_node_status`, `create_proxmox_lxc` all wrap `sanitize_error(e)` which leaks the API URL when the underlying exception is `aiohttp.ClientResponseError`. Out of POL-01..03 scope. → **v1.7.1 LIFE-* phases** (lifecycle hooks rewrite these error paths anyway when adding sitemap-update side effects).
- **Shared `_format_proxmox_error(exc, **inputs) -> dict` helper.** Could replace the inline classify-or-fallback pattern across all proxmox tools. Considered for D-07; rejected as scope creep. → **v1.7.1 follow-up** when the URL-leak ripple is in scope.
- **Removing `PROXMOX_USER` / `PROXMOX_PASSWORD` / `PROXMOX_API_TOKEN` env-var fallback.** Phase 40 only removes `PROXMOX_HOST`. The auth env vars remain readable as the explicit-auth bypass per CR-04 (Phase 38.1 review) — env-var dominance over keyring is intentional for environments that have always configured Proxmox via env vars (SC-5 back-compat from v1.3). → **v1.8 candidate** if/when CRED-* migration completes for Proxmox auth.
- **Schema-required propagation to other "host (optional)" parameters.** POL-02 makes `host` required only on `create_proxmox_vm`. The other 6 proxmox tools still declare `host` optional. With env-var fallback gone (D-04), all tools require a host at runtime — the schema for the others now also lies. → **v1.7.1 / v1.8** mechanical schema sweep when ripple D-07 is in scope.
- **Body-pattern fixture refresh against PVE 8.x.** D-01's substring list ("does not exist", vmid) is based on memory of Proxmox error wording. A periodic fixture-refresh task — capture real error responses from a live PVE host — would catch wording drift across PVE versions. → **v1.8** as a test-infrastructure phase candidate.
- **`error_kind` enumeration on the proxmox surface.** POL-01 introduces `vm_not_found`. Future tools could carry `node_not_found`, `cluster_unreachable`, `task_failed`, etc., for programmatic agent dispatch. → **v1.7.1 / v1.8** as the lifecycle phases populate the enum naturally.
- **OpenAPI app duplicate-schema audit.** If `openapi_app.py` duplicates rather than imports the proxmox tool schemas, every schema-text change has to land in two places. → **planner verifies during research** (Claude's Discretion above).

</deferred>

---

*Phase: 40-proxmox-vm-lifecycle-polish*
*Context gathered: 2026-04-27*
