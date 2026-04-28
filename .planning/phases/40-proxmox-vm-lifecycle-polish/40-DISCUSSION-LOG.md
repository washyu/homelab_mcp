# Phase 40: Proxmox VM Lifecycle Polish - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-27
**Phase:** 40-proxmox-vm-lifecycle-polish
**Areas discussed:** POL-01 detection + shape, POL-02 host param shape, POL-03 PROXMOX_HOST env-var fate, Sweep scope (ripple)

---

## POL-01: VM-not-found detection

| Option | Description | Selected |
|--------|-------------|----------|
| Inspect status + body | Catch ClientResponseError, check e.status == 500 AND scan response body for "does not exist" / vmid mention. Cheapest — zero extra round-trips. Risk: if Proxmox changes wording, falls back to generic error (acceptable degradation). Handle 404 too if the node itself is missing. | ✓ |
| Pre-check via /cluster/resources | Call /cluster/resources first, look for {vmid, node} match, only call status/current if found. Authoritative — no string matching. Cost: extra API round-trip on every status call. | |
| Status code only | Treat any 500 from /status/current as "VM not found". Simplest. Risk: false positives — a real Proxmox internal error (auth glitch, node down) would also surface as "VM not found" which is a misleading recovery hint. | |

**User's choice:** Inspect status + body (recommended).
**Notes:** Locks the substring-match list to "does not exist" + vmid; planner refreshes against live PVE 8.x fixture before implementation. Graceful degradation to generic-error wording on wording drift is acceptable.

---

## POL-01: Error response shape

| Option | Description | Selected |
|--------|-------------|----------|
| Structured fields + message | `{status: 'error', error_kind: 'vm_not_found', node, vmid, vm_type, host, message: '...'}`. Programmatically discriminable; echoes the inputs back per ROADMAP SC-1. | ✓ |
| Message-only | Keep existing `{status: 'error', message: '...'}` shape; just sanitize the message to echo vmid/node/host without the API URL. Minimal structural change. Agents must parse the message to detect "not found". | |
| New top-level status value | Use `{status: 'not_found', node, vmid, ...}` instead of `{status: 'error'}`. More semantic but breaks the binary success/error contract used everywhere else in the proxmox tool family. | |

**User's choice:** Structured fields + message (recommended).
**Notes:** `error_kind: "vm_not_found"` is the discriminator; `message` is the human sentence. Inputs echoed back from the function arguments, NOT pulled from the exception payload (which is what closes the URL leak).

---

## POL-02: `host` parameter shape

| Option | Description | Selected |
|--------|-------------|----------|
| Mark required + cluster-aware description | Add `host` to required list. Description: "Proxmox host (any node hostname covered by your registered credential or cluster-scope token). Register with `homelab-mcp credentials add --type proxmox`." Cleanest schema/runtime alignment. Breaking change for env-var users. | ✓ |
| Keep optional + auto-pick from cluster keyring | Schema stays optional; runtime walks credential_store for cluster-scope entries when host is None. Pro: matches "I have one cluster, just create the VM" mental model. Con: ambiguous if multiple clusters; new code path. | |
| Keep optional + clearer description only | No code change to runtime; rewrite description to clarify env-var semantics. Honest about current behavior but contradicts POL-03's intent. | |

**User's choice:** Mark required + cluster-aware description (recommended).
**Notes:** Coupled with POL-03 D-04 — schema-required becomes load-bearing only because env-var fallback is hard-removed. Without the coupling, this would be schema-only theater.

---

## POL-03: PROXMOX_HOST env-var fate

| Option | Description | Selected |
|--------|-------------|----------|
| Hard-remove fallback + rewrite error | Delete `host = host or os.getenv('PROXMOX_HOST')` at line 474. Rewrite line 521 ValueError to point at credentials add. Affects every proxmox tool consistently. Symmetric with v1.6 deprecation direction. | ✓ |
| Soft-deprecate with warning | Keep env-var fallback, log a deprecation warning when it fires. Rewrite the error text only. Pro: zero breakage. Con: dual-path for one more milestone; AST guard can't catch the env var leaking back. | |
| Fix only create_proxmox_vm error path | Leave shared `get_proxmox_client` unchanged. Wrap create_proxmox_vm specifically. Pro: tightest scope match. Con: schema-runtime divergence persists everywhere else; OTHER proxmox tools still surface PROXMOX_HOST. | |

**User's choice:** Hard-remove fallback + rewrite error (recommended).
**Notes:** Reuses the canonical `homelab-mcp credentials add --type proxmox` wording from `resolve_proxmox_credentials` (proxmox_api.py:433-440) for cross-error consistency. Does NOT touch PROXMOX_USER/PASSWORD/API_TOKEN env-var reads — those stay per CR-04 Phase 38.1 deliberate behavior.

---

## Sweep — schema descriptions

| Option | Description | Selected |
|--------|-------------|----------|
| Sweep all proxmox schema descriptions | Rewrite every "uses PROXMOX_HOST env var" phrase in proxmox_tools_schema.py. Mechanical, low risk — description text only. Closes schema-runtime divergence everywhere. | ✓ |
| Touch only POL-02 (create_proxmox_vm) schema | Update only the create_proxmox_vm host description. Pro: tightest scope. Con: descriptions lie about runtime everywhere except the one tool we touched. | |

**User's choice:** Sweep all proxmox schema descriptions (recommended).
**Notes:** Description-text-only sweep; no schema shape change for tools other than `create_proxmox_vm`.

---

## Sweep — AST guard

| Option | Description | Selected |
|--------|-------------|----------|
| Extend AST guard to proxmox_api.py + schema | Add proxmox_api.py and proxmox_tools_schema.py to the existing `tests/test_ast_regression.py` PROXMOX_HOST-zero-matches assertion. Revert-proof. Matches regression-test scope memory. | ✓ |
| Functional tests only | Validate cleanup with functional tests (call create_proxmox_vm without host, expect credentials-add error; call get_proxmox_vm_status with bogus vmid, expect vm_not_found shape). No AST guard. Smaller test surface. Con: nothing prevents the env-var pattern from creeping back via copy-paste. | |

**User's choice:** Extend AST guard (recommended).
**Notes:** PROXMOX_HOST removal is footgun-class — copy-paste from old code is the recurrence vector. AST guard ban list extension matches Phase 37 D-11 precedent. Functional tests for the new behavior (vm_not_found shape) sit alongside.

---

## Sweep — error-shape ripple

| Option | Description | Selected |
|--------|-------------|----------|
| Defer to v1.7.1 / lifecycle phase | Phase 40 polishes only POL-named tools. Leave URL-leak surface in other 5 tools for v1.7.1 lifecycle hooks. Capture as Deferred Idea. Keeps phase scope tight. | ✓ |
| Add a shared _format_proxmox_error helper | Extract a helper that wraps aiohttp.ClientResponseError and redacts the API URL. Apply in get_proxmox_vm_status AND mechanically swap in the other 5 tools. Pro: one fix for the whole URL-leak class. Con: scope creep; risks dragging behavior changes into untested-by-this-phase tools. | |
| Polish only get_proxmox_vm_status, no helper | Inline URL-redacting + structured-fields logic only in POL-01 path. Other tools keep wrapping sanitize_error(e) raw. Min diff. Con: v1.7.1 has to rebuild the same logic. | |

**User's choice:** Defer to v1.7.1 / lifecycle phase (recommended).
**Notes:** v1.7.1 LIFE-* phases will rewrite those error paths anyway when adding sitemap-update side effects. Captured in Deferred Ideas as the v1.7.1 follow-up + shared helper candidate.

---

## Claude's Discretion

- Exact substring-match list for D-01 body-scan ("does not exist", vmid as substring) — planner verifies against actual Proxmox PVE 8.x response shapes.
- Whether vm_not_found classification lives inline or in a helper `_classify_vm_status_error` (helper recommended, mirrors Phase 39 `_classify_probe_outcome`).
- Exact `message` wording for the `vm_not_found` shape — D-02 template polished by planner.
- Exact ValueError wording in D-04 — planner picks final phrasing using the canonical `homelab-mcp credentials add --type proxmox` form.
- Whether the AST guard reuses the existing assertion (recommended, minimal change) or factors into a helper.
- Whether `host` becoming required propagates to `openapi_app.py` — planner verifies whether that file imports or duplicates the proxmox schema.
- Whether existing tests pass `host=None` to `create_proxmox_vm` and need updating — planner runs the test suite, fixes inline.

## Deferred Ideas

- URL-leak / structured-error polish for the other 5 proxmox tools — v1.7.1 LIFE-*.
- Shared `_format_proxmox_error(exc, **inputs) -> dict` helper — v1.7.1 follow-up.
- Removing `PROXMOX_USER` / `PROXMOX_PASSWORD` / `PROXMOX_API_TOKEN` env-var fallback — v1.8 candidate.
- Schema-required propagation to other "host (optional)" parameters — v1.7.1 / v1.8 mechanical sweep.
- Body-pattern fixture refresh against PVE 8.x — v1.8 test-infrastructure phase.
- `error_kind` enumeration on the proxmox surface — v1.7.1 / v1.8.
- OpenAPI app duplicate-schema audit — planner verifies during research.
