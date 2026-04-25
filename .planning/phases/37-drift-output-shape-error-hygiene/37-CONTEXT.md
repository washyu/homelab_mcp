# Phase 37: Drift Output Shape & Error Hygiene - Context

**Gathered:** 2026-04-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Stabilize the `scan_infrastructure_drift` response shape and clean up drift-family error/description text. Phase 36 shipped a 2-bucket interim (`probed_ok` / `unreachable`); Phase 37 expands to 4 buckets per ROADMAP SC-2, defines what `node` and `vm_type` filters mean, ensures every drift-family description/message points to existing sitemap CRUD tools (never deprecated `PROXMOX_HOST` env var), and locks the architectural ban on `register_drift_baseline` / `list_drift_baselines` / `delete_drift_baseline` MCP tools via AST meta-test.

Scope anchor: ROADMAP.md §Phase 37 + REQUIREMENTS.md §DRFT-13/14/15/16.

**This phase delivers exactly four requirements** (DRFT-13, DRFT-14, DRFT-15, DRFT-16) plus two AST regression guards (one per DRFT-15 / DRFT-16) extending the Phase 32/33/35/36 footgun-removal pattern.

Out of this phase:
- `unknown` per-row record shape and detection logic (DRFT-17, Phase 39). Phase 37 reserves the empty bucket; Phase 39 fills it.
- `changed` per-row record shape and detection logic (DRFT-19, Phase 39). Depends on Phase 38 fingerprint schema.
- "Missing infrastructure" enrichment (DRFT-18, Phase 39). Per D-04 below, this enriches the existing `unreachable` bucket — no 5th bucket — so Phase 39 layers data on top of Phase 37's shape.
- Sitemap fingerprint schema (DRFT-20, Phase 38).
- Wider `PROXMOX_HOST` sweep across `proxmox_tools_schema.py`, `configuration.md`, `setup-guide.md`. Phase 40 (POL-03) handles the proxmox tool schemas; broader docs cleanup deferred to a future docs phase or v1.8.
- Runtime registry assertion for forbidden tool names (D-15: AST-only).
- Persistence of per-host probe history (consecutive-fail counter, last_seen_at) — Phase 39 may introduce when DRFT-18 enrichment lands.
- Filter syntax extensions (wildcards, comma-separated lists, `node` filtering against Proxmox-internal node names rather than hostname).
- Lifecycle hooks (sitemap-update on VM create/destroy) — v1.7.1 LIFE-01..04.

</domain>

<decisions>
## Implementation Decisions

### Filter Semantics (DRFT-13)

- **D-01 (`node` = hostname exact-match):** The `node` parameter filters sitemap rows by exact hostname match before iteration. `node="pve1"` keeps only rows where `hostname == "pve1"`; rows iterated and probed are the filtered subset. Filter applies at the row-iteration step inside `scan_drift`, immediately after `db_adapter.get_all_devices()` and before the degenerate-row skip from Phase 36 D-10a. No-match (zero rows after filter) returns success with all four buckets empty — never a `status: "error"`. Aligns with Phase 35 D-01's hostname-as-natural-key convention.
- **D-02 (`vm_type` stays inert at host-scan level):** `vm_type` retains its `enum: [qemu, lxc, all]` schema constraint and continues to accept all three values without changing the host-level scan. The schema description gains an explicit note: `"Reserved for Phase 39 per-VM detection; currently filters at host level only (no-op until per-VM enumeration ships)."` This satisfies SC-1 (consistent shape across all `vm_type` values) without prejudging Phase 39's per-VM semantics. The existing tool surface stays stable; clients wired to `vm_type=qemu` keep working.
- **D-03 (no `node`-value validation; schema enum is the only gate):** MCP enum on `vm_type` provides schema-level rejection of invalid values (e.g., `vm_type=potato` is rejected before reaching `scan_drift`). `node` accepts any string — if it doesn't match any sitemap row, return success with empty buckets. No coercion (no lowercase, no whitespace strip). No "did you mean?" suggestions. Closes Bugs A and E (both manifested as scope errors on missing-baseline filter scopes); Phase 37 simply removes the error class entirely by treating empty match as success.

### 4-Bucket Response Shape (DRFT-14)

- **D-04 (bucket names match ROADMAP SC-2 verbatim):** The four buckets are named `probed_ok`, `unreachable`, `unknown`, `changed`. Phase 39's DRFT-18 ("missing infrastructure") **enriches the existing `unreachable` bucket** with last-seen timestamp + decommission/purge pointers — it does NOT introduce a fifth `missing` bucket. This is a forward-looking design decision so Phase 39 planning sees the locked-in convention: `unreachable` IS the persistent bucket; transient vs persistent distinction (if needed) lives inside the per-row record, not as a separate bucket. Surface stays stable across Phase 37 → Phase 39.
- **D-05 (all 4 bucket keys always present, empty arrays when unimplemented):** Every `scan_drift` response includes all four bucket keys: `probed_ok`, `unreachable`, `unknown`, `changed`. `unknown` and `changed` are `[]` until Phase 39 fills them. Clients can iterate without `dict.get(..., [])` defensive checks. Empty sitemap, filter-narrowed-to-zero, and full-coverage cases all produce the same shape. Enforces SC-1 ("consistent shape across filter scopes").
- **D-06 (per-row record shape for `unknown` / `changed` deferred to Phase 39):** Phase 37 does NOT define what each entry in `unknown[]` or `changed[]` looks like. The shape depends on Phase 38 fingerprint schema (for `changed` per-field diffs) and Phase 39 detection logic (`unknown` needs host+vmid+vmtype+pointer; `changed` needs per-field stored-vs-current). Defining now risks rework when those phases land. The buckets are present-but-empty in Phase 37; record shape lands with the data that fills them.
- **D-07 (top-level `scanned` + new `counts` sub-dict):** Keep Phase 36's `scanned: int` (sum across all four buckets) for backward compatibility with Phase 36 clients. **Add** a `counts: {"probed_ok": N, "unreachable": N, "unknown": N, "changed": N}` sub-dict for per-bucket sizes. Clients can check coverage at a glance without iterating arrays. Final response key order: `status, scan_timestamp, scanned, counts, [guidance,] probed_ok, unreachable, unknown, changed` (guidance present only per D-09).

### Drift-Family Error Hygiene (DRFT-15)

- **D-08 (sweep scope = drift surface only):** Touch only the drift-family files:
  - `src/homelab_mcp/openapi_app.py:60` — Drift Detection description currently says `"a Proxmox VE host with stored baselines. Set PROXMOX_HOST and credentials first"`. Rewrite to remove "stored baselines" + PROXMOX_HOST; reference `discover_and_map` + `homelab-mcp credentials add --type proxmox` instead.
  - `src/homelab_mcp/tool_schemas/drift_tools_schema.py` — Phase 36 D-04 set the inert-passthrough description; Phase 37 rewrites for stable filter semantics + 4-bucket shape (mention bucket names in description; document `vm_type` Phase 39 reservation).
  - `src/homelab_mcp/server.py:151` — drift resource description (Phase 36 D-18 deferred final wording to Phase 37).
  - `docs/tool-reference.md` `scan_infrastructure_drift` entry (~line 576) — update for 4-bucket shape, filter semantics, recovery pointer text.
  - Defer wider sweep: `proxmox_tools_schema.py:48,76` and `proxmox_api.py:357,382` PROXMOX_HOST mentions belong to **Phase 40 (POL-03)** because those are general Proxmox tools (not drift-family). `configuration.md:32` and `setup-guide.md:53,240` env-var documentation stays — the env var is still a working credential fallback for non-drift Proxmox callers; rewriting docs to never mention it could mislead users with legacy setups. A broader docs cleanup phase can land in v1.8.
- **D-09 (top-level `guidance` field, conditional on `scanned == 0`):** When `scanned == 0` (empty sitemap OR filter narrowed to zero rows), the response includes a top-level `guidance: str` field with recovery text pointing to sitemap CRUD tools. Suggested wording (planner picks final): `"No Proxmox hosts in sitemap. Run discover_and_map to populate, get_network_sitemap to inspect what's tracked, or purge_failed_discoveries to clean stale rows."` When `scanned > 0`, the `guidance` key is **absent** from the response (no clutter on the happy path). This satisfies DRFT-15's "drift family error message that suggests a recovery action" without manufacturing an error class — the guidance is informational, not an error.
- **D-10 (per-row `unreachable.error` stays pure sanitized text):** Keep Phase 36 D-09a behavior unchanged — `error` field is the sanitized exception message via `error_handling.sanitize_error()`. No per-row recovery pointer (would duplicate text on every entry; 50 unreachable rows from one network outage = 50 copies of the same pointer). Recovery lives in top-level `guidance` (D-09) and docs (D-08).
- **D-11 (AST meta-test: PROXMOX_HOST forbidden in drift files):** New assertion in `tests/test_ast_regression.py`. Scan `src/homelab_mcp/drift_detection.py`, `src/homelab_mcp/tool_handlers/drift_handlers.py`, `src/homelab_mcp/tool_schemas/drift_tools_schema.py`, AND the Drift Detection block in `src/homelab_mcp/openapi_app.py` (lines around 59–60) for the substring `PROXMOX_HOST` — must be ZERO matches. Locks DRFT-15 architecturally; extends Phase 36 D-13's footgun-removal pattern. Phase 37 qualifies as footgun-removal class (closes Bug B).

### DRFT-16 Architectural Lock-In (No Baseline-Lifecycle MCP Tools)

- **D-12 (AST meta-test: forbidden tool names anywhere in src/):** New assertion in `tests/test_ast_regression.py`. Scan every `*.py` under `src/homelab_mcp/` for the substrings `register_drift_baseline`, `list_drift_baselines`, `delete_drift_baseline` — must be ZERO matches across all source files. Catches reintroduction in `tool_schemas/`, `tools.py`, handler files, docstrings, and any deferred-import paths. Mirrors Phase 36 D-12's table-name guard pattern; codifies that the bug-C tools never exist.
- **D-13 (source-only scan; docs reviewed via D-08):** AST meta-test scans `src/homelab_mcp/` only. Documentation (`docs/`, README, etc.) is reviewed via the D-08 sweep + code review. Keeps the test focused on the architectural contract — "no MCP tool with these names exists in code." Markdown drift in docs is caught by the documentation sweep, not the AST guard.
- **D-14 (extend existing tests/test_ast_regression.py):** Both new assertions (D-11 PROXMOX_HOST guard, D-12 tool-name guard) live in `tests/test_ast_regression.py` alongside Phase 36 D-12/D-13 guards. One file = one place to look for footgun-removal regression coverage. Follows established convention from Phase 32/33/35/36.
- **D-15 (no runtime registry assertion):** AST meta-test only. Server startup does NOT iterate TOOLS dict and assert no forbidden names. CI catches reintroduction at test time; runtime check would duplicate enforcement at production cost (extra startup work) for a regression the test pipeline already gates against merge.

### Claude's Discretion

- Exact wording of the `guidance` text (D-09) — recommended phrasing is illustrative; planner may polish.
- Exact rewrite of the `openapi_app.py:60` Drift Detection description (D-08) — must remove "stored baselines" + PROXMOX_HOST and mention sitemap CRUD tools; specific phrasing flexible.
- Exact rewrite of the `drift_tools_schema.py` description (D-08) — must mention bucket names and `vm_type` Phase 39 reservation; specific phrasing flexible.
- Exact rewrite of the `server.py:151` drift resource description (D-08) — final wording for stable shape; specific phrasing flexible.
- Whether the per-bucket `counts` dict has alphabetical or roadmap-defined ordering of keys (Python preserves insertion order; pick whatever is most readable).
- Whether the `guidance` text under D-09 is identical for "empty sitemap" vs "filter-narrowed-to-zero" cases or branched on which condition applies. Identical recommended (simpler); branched would distinguish "populate the sitemap" (empty) vs "your filter matched nothing" (filter case).
- Whether the AST guards in D-11/D-12 share a common helper for "scan source files for forbidden substrings" (with Phase 36 D-12/D-13) or are independent. Refactoring to share a helper is fine but not required.
- Test fixture style for the new assertions — extend an existing test class in `tests/test_ast_regression.py` or add a new `TestPhase37DriftHygiene` class. New class recommended for phase-scoped readability.
- Whether `tests/test_drift_detection.py` adds new test classes for filter semantics (D-01/D-03) and 4-bucket shape (D-04..D-07) or extends the existing `TestScanDrift2Bucket` class (which Phase 36 named for the interim). Renaming the existing class to `TestScanDrift4Bucket` (or splitting into `TestScanDriftFilterSemantics` + `TestScanDriftBucketShape`) is fine; planner picks.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 37 Scope

- `.planning/ROADMAP.md` §Phase 37 — Phase goal + 4 Success Criteria (SC-1..SC-4); the scope anchor.
- `.planning/REQUIREMENTS.md` §Active Requirements — DRFT-13 (consistent shape across filter scopes), DRFT-14 (4-bucket coverage transparency), DRFT-15 (drift error messages reference sitemap CRUD tools, never PROXMOX_HOST), DRFT-16 (no `register_drift_baseline` / `list_drift_baselines` / `delete_drift_baseline` MCP tools); §Coverage Map (Bugs A/B/C/D/E → DRFT-13/15/16/14/13).
- `.planning/PROJECT.md` §Constraints + §Key Decisions — keyring-only credential constraints, MCP tool-surface conventions (handlers stay thin-delegation wrappers), no PROXMOX_HOST in code paths.
- `.planning/STATE.md` §v1.7 Phase Summary + §Phase Ordering Constraints — Phase 37 follows Phase 36; sets shape for Phase 39 detection.

### Prior Phase Decisions (locked, inherited)

- `.planning/phases/36-drift-sitemap-foundation/36-CONTEXT.md` §Implementation Decisions — D-01 (2-bucket interim shape Phase 37 expands), D-02 (per-row record fields Phase 37 keeps), D-03 (empty sitemap = success Phase 37 generalizes to all filter scopes), D-04 (filter passthrough Phase 37 defines), D-09 (per-row credential resolution Phase 37 doesn't touch), D-09a (sanitize_error wrap Phase 37 keeps), D-10/D-10a (per-row resolve + degenerate-row skip Phase 37 keeps), D-12/D-13 (AST meta-test pattern D-11/D-12 here extend), D-18 (resource description tweak Phase 37 finalizes).
- `.planning/phases/36-drift-sitemap-foundation/36-VERIFICATION.md` — what's already shipped; the post-Phase-36 state Phase 37 builds on (response shape, per-row keys, AST guard structure).
- `.planning/milestones/v1.6-phases/33-keyring-single-source-of-truth/33-CONTEXT.md` §Regression Guards — D-15 AST meta-test pattern (scan source for forbidden strings); the source-scanning idiom D-11/D-12 here reuse.
- `.planning/milestones/v1.6-phases/35-sitemap-discovery-reliability-fix-discover-and-map-field-los/35-CONTEXT.md` §D-01 (hostname-as-natural-key — D-01 here filters by this); §D-14/D-15/D-16 (AST meta-test idiom).
- `.planning/milestones/v1.6-phases/34-cluster-scoped-proxmox-credentials/34-CONTEXT.md` §D-09 — `resolve_proxmox_credentials` signature + tier-walk; Phase 37 doesn't touch but the response's `scope` and `cluster_name` fields (per Phase 36 D-02) come from this resolver.

### Memory / User Feedback

- `~/.claude/projects/C--Users-washy-projects-mcp-python-server/memory/feedback_regression_test_scope.md` — AST meta-tests guard known footguns; new-feature phases skip. Phase 37 qualifies (closes Bugs A/B/C/D/E). Drives D-11 and D-12.
- `~/.claude/projects/C--Users-washy-projects-mcp-python-server/memory/project_credential_architecture.md` — Keyring is the source of truth; missing entry = hard error with CLI pointer; no PROXMOX_HOST in code paths. Drives D-08 (drift surface scrub) and D-11 (PROXMOX_HOST AST guard).

### Source Files Affected

- `src/homelab_mcp/drift_detection.py`
  - `scan_drift()` — extend signature/body for D-01 (hostname filter at row-iteration step), D-04/D-05 (4-bucket envelope with `unknown: []` and `changed: []` always present), D-07 (`counts` sub-dict), D-09 (`guidance` field when `scanned == 0`). Existing per-row record shape (Phase 36 D-02) preserved unchanged for `probed_ok` and `unreachable`.
  - Module docstring — update to reflect Phase 37 4-bucket shape (currently says "2-bucket interim").
- `src/homelab_mcp/tool_handlers/drift_handlers.py`
  - `handle_scan_infrastructure_drift` — passthrough; no shape logic moves into the handler. Docstring update from "2-bucket" to "4-bucket".
- `src/homelab_mcp/tool_schemas/drift_tools_schema.py`
  - `DRIFT_TOOLS["scan_infrastructure_drift"]` `description` — D-08 rewrite for 4-bucket shape, hostname filter semantics, `vm_type` Phase 39 reservation. Remove the Phase 36 "filter semantics under Phase 37 redesign" note.
  - `inputSchema.properties.node.description` — clarify hostname exact-match per D-01.
  - `inputSchema.properties.vm_type.description` — note Phase 39 reservation per D-02.
- `src/homelab_mcp/server.py`
  - Drift resource description (line ~151) — D-08 final wording for stable 4-bucket shape (Phase 36 D-18 deferred to here).
- `src/homelab_mcp/openapi_app.py`
  - Line 60 (`"Drift Detection"` description in the dict) — D-08 rewrite: remove "stored baselines" + "Set PROXMOX_HOST"; reference `discover_and_map` + `homelab-mcp credentials add --type proxmox`.
- `docs/tool-reference.md`
  - `scan_infrastructure_drift` entry (~line 576) — D-08: 4-bucket shape, hostname filter semantics, recovery pointer.
- `tests/test_ast_regression.py`
  - Add D-11 assertion: scan `drift_detection.py`, `drift_handlers.py`, `drift_tools_schema.py`, and `openapi_app.py` Drift section for `PROXMOX_HOST` (zero matches).
  - Add D-12 assertion: scan all `src/homelab_mcp/**/*.py` for `register_drift_baseline`, `list_drift_baselines`, `delete_drift_baseline` (zero matches everywhere).
  - Place new assertions per D-14 in the same file; new `TestPhase37DriftHygiene` class recommended.
- `tests/test_drift_detection.py`
  - Extend `TestScanDrift2Bucket` (or rename to `TestScanDrift4Bucket`) with assertions for: 4-bucket envelope always present, `counts` sub-dict shape, `guidance` field present when `scanned == 0` and absent otherwise, `node` filter narrows iteration to exact-hostname-match, no-match returns success with empty buckets, `vm_type` is inert (same shape across qemu/lxc/all).

### Pattern / Architecture Reference

- `error_handling.py` `sanitize_error()` — D-10 keeps as the sole transformation for per-row `error` fields (Phase 36 D-09a behavior).
- `db_adapter.get_all_devices()` — single sitemap read funnel; D-01 filter applies as a list-comprehension on top.
- Phase 36 AST meta-test structure in `tests/test_ast_regression.py` — established `pathlib.Path` walk + read-each-file + assert-substring-absent pattern. D-11 and D-12 extend with new forbidden-string sets.

### External / Proxmox API

- No new external API calls in Phase 37. The `GET /cluster/status` probe (Phase 36 D-09) stays unchanged. Phase 37 is shape work, not network work.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **Phase 36's per-row record shape** (`hostname, connection_ip, scope, cluster_name, status, error, scan_timestamp`) — Phase 37 keeps this verbatim for `probed_ok` and `unreachable` entries. Only the envelope (top-level keys) expands.
- **`error_handling.sanitize_error()`** — Phase 36 D-09a established usage for per-row error fields; D-10 keeps the convention. No new sanitization layer needed.
- **`db_adapter.get_all_devices()`** — single sitemap read funnel from Phase 35/36; D-01 hostname filter applies as a list-comprehension on the result, no adapter changes.
- **AST meta-test infrastructure in `tests/test_ast_regression.py`** — Phase 36 D-12/D-13 already established the `pathlib.Path` walk + per-file read + forbidden-substring assertion structure. D-11 and D-12 extend the same file with new forbidden-string sets and (optionally) per-file scoping.
- **Phase 36 D-04's schema description marker** — the description text is already a good place to flag phase-staged behavior; D-08 rewrites it for stable Phase 37 shape rather than adding a new mechanism.

### Established Patterns

- **AST meta-test for footgun-removal class phases** — Phase 32/33/35/36 pattern; Phase 37 qualifies (closes Bugs A/B/C/D/E). D-11 and D-12 follow the established mechanics.
- **Schema description as self-documentation** — Phase 36 D-04 used the description to mark filter inertness; Phase 37 D-08 uses it to document the stable 4-bucket shape and `vm_type` Phase 39 reservation.
- **Thin-delegation MCP tool handlers** — `handle_scan_infrastructure_drift` stays a passthrough; D-09's `guidance` field is computed in `scan_drift`, not in the handler. No handler complexity drift.
- **Empty result = success, not error** — Phase 36 D-03 established this for empty sitemap; Phase 37 D-03 generalizes to all filter scopes (no-match `node` filter, etc.).
- **Pre-allocate response keys for client convenience** — D-05 pre-allocates `unknown` and `changed` as `[]` so clients iterate without defensive checks; mirrors Phase 36's `probed_ok: [], unreachable: []` always-present convention.

### Integration Points

- **`scan_drift` is the only function emitting drift response payloads.** Every shape decision (D-01..D-07, D-09) lands in its return dict. No new modules, no new helper files.
- **`handle_scan_infrastructure_drift` is a passthrough.** No shape logic moves into it. Phase 37 keeps the Phase 36 D-03 simplicity.
- **`set_latest_drift_report` (cached for `homelab://drift/latest` resource)** — automatically picks up the new shape. No resource-side code change beyond the description tweak (D-08 / Phase 36 D-18 deferred wording).
- **`tool_schemas/drift_tools_schema.py` is the single source for the MCP tool description.** All client-facing schema text changes land here.
- **`openapi_app.py:59-61`** — the Drift Detection mapping is the OpenAPI/REST surface mirror of the MCP tool description. Must be kept in sync (D-08 touches both).
- **`tests/test_ast_regression.py` is the established AST meta-test home.** D-14 keeps the new Phase 37 guards in this file (no test fragmentation).

</code_context>

<specifics>
## Specific Ideas

- **Match SC-2 wording verbatim for bucket names.** User chose `unreachable` over `missing` (Phase 39's DRFT-18 wording) so Phase 37 doesn't pre-empt Phase 39 work. Phase 39's `missing infrastructure` (DRFT-18) **enriches the existing `unreachable` bucket** with last-seen timestamp + decommission/purge pointers — encoded explicitly in D-04 so Phase 39 planning sees the locked-in convention.
- **Pre-allocation over conditional keys.** User chose all 4 buckets always present (empty arrays for unimplemented `unknown` / `changed`) over only-populated. Mirrors Phase 36 D-03's "empty sitemap is success not error" — consistent shape regardless of state. Clients iterate without defensive checks.
- **Defer per-row record shape for `unknown` and `changed` to Phase 39.** User chose to NOT speculatively define these record shapes. Phase 39's detection logic depends on Phase 38 fingerprint schema; defining records now risks rework. Buckets reserved as `[]`; record shape lands with the data.
- **Additive `counts` rather than replacing `scanned`.** User chose to keep `scanned: int` (sum) AND add `counts: {...}` sub-dict. Backward-compatible with Phase 36 clients; adds the per-bucket convenience without breaking the surface.
- **Narrow DRFT-15 sweep scope.** User chose drift-surface-only over wider PROXMOX_HOST cleanup. `proxmox_tools_schema.py` PROXMOX_HOST mentions belong to Phase 40 (POL-03 explicitly addresses `create_proxmox_vm` error guidance). `configuration.md`/`setup-guide.md` env-var documentation stays — the env var still works as a fallback for non-drift Proxmox callers.
- **Top-level `guidance` field, conditional on `scanned == 0`.** User chose conditional inclusion over always-present. Self-documenting recovery without cluttering the happy path. The `guidance` text is informational — not an "error message" in the strict sense — which is what makes DRFT-15 satisfiable without manufacturing an error class.
- **Per-row `error` stays as pure sanitized text.** User chose no per-row recovery pointer. Per-row pointers would duplicate text on every entry; recovery lives in top-level `guidance` and docs.
- **Source-only AST guard scope for DRFT-16.** User chose to scan `src/homelab_mcp/` only, not `docs/`. Markdown drift caught via the D-08 doc sweep + code review. Keeps the test focused on the architectural contract: "no MCP tool with these names exists in code."
- **Both DRFT-15 (PROXMOX_HOST) and DRFT-16 (tool-name) guards extend the existing footgun-removal pattern.** User chose to add both new AST assertions to `tests/test_ast_regression.py` rather than creating new test files. One file = one place; consistent with Phase 32/33/35/36.
- **AST-only enforcement, no runtime check.** User chose AST guard only over runtime registry assertion. CI catches reintroduction at merge time; runtime check would duplicate enforcement at production cost.

</specifics>

<deferred>
## Deferred Ideas

- **`unknown` per-row record shape and detection** — Phase 39 (DRFT-17). Bucket reserved as `[]` in Phase 37.
- **`changed` per-row record shape and detection** — Phase 39 (DRFT-19). Depends on Phase 38 fingerprint schema. Bucket reserved as `[]` in Phase 37.
- **"Missing infrastructure" enrichment** — Phase 39 (DRFT-18). Per D-04, this enriches the `unreachable` bucket in-place (last-seen timestamp, decommission/purge pointers); does NOT introduce a 5th bucket.
- **Wider PROXMOX_HOST sweep across `proxmox_tools_schema.py`** — Phase 40 (POL-03). Phase 40 owns the `create_proxmox_vm` error guidance and is the natural home for per-tool description rewrites.
- **`PROXMOX_HOST` cleanup in `configuration.md` and `setup-guide.md`** — future docs phase or v1.8. The env var still works as a credential fallback for non-drift Proxmox callers.
- **`PROXMOX_HOST` AST guard extended to non-drift files** — out of scope; Phase 40 may add for proxmox tool family.
- **Persistence of per-host probe history** (consecutive-fail counter, last_seen_at field) — Phase 39 may need for missing-infrastructure enrichment under D-04. Phase 37 has no persistence work.
- **Filter syntax extensions** — wildcards (`node=pve*`), comma-separated lists (`node=pve1,pve2`), or filtering against Proxmox-internal node names rather than sitemap hostname. Out of scope for Phase 37; Phase 39 may add when per-VM enumeration introduces richer filter semantics.
- **Runtime registry assertion for forbidden tool names** — D-15 picks AST-only.
- **Restructured response key ordering** — current order (`status, scan_timestamp, scanned, counts, [guidance,] probed_ok, unreachable, unknown, changed`) is recommended; alternative orderings (alphabetical, buckets-first) are out of scope.
- **`vm_type` real semantics** — defined in Phase 39 (DRFT-17/19) when per-VM detection lands.
- **Lifecycle hooks** (sitemap-update on VM create/destroy) — v1.7.1 LIFE-01..04. Unchanged from Phase 36's deferral.
- **Sitemap tags / role-aware drift** — v1.7.2 TAGS-* + ROLE-*.

</deferred>

---

*Phase: 37-drift-output-shape-error-hygiene*
*Context gathered: 2026-04-25*
