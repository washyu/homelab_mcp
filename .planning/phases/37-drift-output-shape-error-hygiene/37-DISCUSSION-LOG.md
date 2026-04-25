# Phase 37: Drift Output Shape & Error Hygiene - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-25
**Phase:** 37-drift-output-shape-error-hygiene
**Areas discussed:** Filter semantics (DRFT-13), 4-bucket shape + naming (DRFT-14), Error-message scope (DRFT-15), DRFT-16 AST lock-in

---

## Filter Semantics (DRFT-13)

### Q1: What should the `node` filter actually do in Phase 37?

| Option | Description | Selected |
|--------|-------------|----------|
| Hostname exact-match (Recommended) | `node=pve1` keeps only sitemap rows where `hostname == "pve1"`. Simple, predictable, matches Phase 35's hostname-as-natural-key convention. Empty match = empty buckets, status: success. | ✓ |
| Hostname substring/prefix match | `node=pve` matches pve1, pve2, pve3. More flexible but introduces a wildcard-like feature without explicit syntax — ambiguous. Could surprise users. | |
| Proxmox node-name (from /cluster/status) | Filter against the Proxmox-internal node name returned by /cluster/status, not the sitemap hostname. More accurate to the word "node" but requires probing first then filtering — expensive and out-of-order. | |
| Stay inert | Keep accepting the param but don't act on it. Continues Phase 36's stance. SC-1 still satisfied (shape always consistent). Defer real semantics to Phase 39 when per-VM data lands. | |

**User's choice:** Hostname exact-match (Recommended)
**Notes:** Aligns with Phase 35 D-01 hostname-as-natural-key. No surprise wildcard semantics; defers richer filter syntax to a future phase.

### Q2: What should `vm_type=qemu` / `vm_type=lxc` do before Phase 39 ships per-VM detection?

| Option | Description | Selected |
|--------|-------------|----------|
| Stay inert with explicit doc note (Recommended) | `vm_type` accepts qemu/lxc/all but doesn't change the host-level scan. Schema description: "Reserved for Phase 39 per-VM detection; currently filters at host level only (no-op)." SC-1 satisfied because shape stays consistent across all values. Avoids prejudging Phase 39's semantics. | ✓ |
| Filter at host level (drop hosts with no matching VM type) | Probe each host's VM list and drop hosts that have zero qemu (or zero lxc) VMs. Adds an extra API call per host. Premature — Phase 39 will do the per-VM enumeration anyway. | |
| Remove the param from the schema | Drop `vm_type` from inputSchema entirely; reintroduce it in Phase 39 with real semantics. Cleaner schema but is a surface-level breaking change for any client that wires the param today. | |

**User's choice:** Stay inert with explicit doc note (Recommended)
**Notes:** Avoids surface-level breaking change; defers real semantics to Phase 39 per-VM detection.

### Q3: For invalid filter values (e.g., garbage `node=`, schema-rejected `vm_type=potato`), what should the response be?

| Option | Description | Selected |
|--------|-------------|----------|
| Schema enum on vm_type + accept any string for node (Recommended) | MCP enum already constrains vm_type to qemu/lxc/all (schema-level rejection). `node` accepts any string — if it doesn't match any sitemap row, return success with empty buckets. No special validation. | ✓ |
| Validate `node` against existing sitemap hostnames | Reject `node=` values that don't match any sitemap row with status: error + suggestion. More helpful but breaks SC-1 ("empty match returns empty result, never scope error"). | |
| Coerce + sanitize node input | Strip whitespace, lowercase, validate it looks like a hostname. Adds complexity for marginal benefit. | |

**User's choice:** Schema enum on vm_type + accept any string for node (Recommended)
**Notes:** Closes Bugs A and E by removing the error class entirely. Empty match = success, not error.

---

## 4-Bucket Shape + Naming (DRFT-14)

### Q1: Bucket naming — how should we reconcile `unreachable` (SC-2) and `missing` (Phase 39 DRFT-18)?

| Option | Description | Selected |
|--------|-------------|----------|
| Match SC-2 exactly: probed_ok / unreachable / unknown / changed (Recommended) | Phase 37 ships the names from SC-2 verbatim. Phase 39 enriches the existing `unreachable` bucket with last-seen timestamp + decommission_device pointer (DRFT-18 becomes an enrichment, not a new bucket). Keeps tool-surface stable across phases. | ✓ |
| Rename `unreachable` → `missing` now | Anticipate Phase 39's DRFT-18 wording. Cleaner end-state but contradicts SC-2's explicit naming AND breaks Phase 36's `unreachable` shape. Surface-level breaking change for any client wired to Phase 36's interim. | |
| Both `unreachable` (transient) AND `missing` (persistent) as 5 separate buckets | 5 buckets: probed_ok / unreachable (probe failed this scan) / missing (failed N consecutive scans) / unknown / changed. Requires persistence machinery (consecutive-fail counter or last-success timestamp) that doesn't exist yet — prejudges Phase 39 work. | |

**User's choice:** Match SC-2 exactly: probed_ok / unreachable / unknown / changed (Recommended)
**Notes:** Forward-looking design decision encoded in CONTEXT.md D-04 — Phase 39 will see "missing IS unreachable, enriched in-place" as a locked convention.

### Q2: Should Phase 37 always pre-allocate all 4 buckets in the response (with empty arrays for `unknown` / `changed` until Phase 39 fills them)?

| Option | Description | Selected |
|--------|-------------|----------|
| Always present, empty arrays for unimplemented (Recommended) | Response always includes all 4 keys: probed_ok, unreachable, unknown, changed. `unknown` and `changed` are `[]` until Phase 39. Client code can iterate without key-existence checks. SC-1 satisfied (consistent shape regardless of filter scope). | ✓ |
| Only include populated buckets | Omit `unknown` and `changed` from the response until Phase 39 implements them. Smaller response but breaks SC-1 spirit — client must do `result.get("unknown", [])` everywhere. | |
| Always present + Phase 37 marker on unimplemented | All 4 buckets present + a top-level `pending_buckets: ["unknown", "changed"]` field telling clients these are reserved-but-unimplemented. Honest about partial coverage but clutters the shape. | |

**User's choice:** Always present, empty arrays for unimplemented (Recommended)

### Q3: Should Phase 37 also lock the per-row record shape for `unknown` and `changed` now (so Phase 39 just populates), or punt the record shape to Phase 39?

| Option | Description | Selected |
|--------|-------------|----------|
| Punt the per-row shape to Phase 39 (Recommended) | Phase 37 reserves `unknown: []` and `changed: []` as empty arrays but doesn't define what their per-row records contain. Phase 39 introduces the records when DRFT-17/19 detection logic lands — the shape needs to align with the actual detection (host+vmid for unknown, per-field diff for changed). Defining now prejudges Phase 38 fingerprint schema. | ✓ |
| Lock minimal common envelope now | Define a minimal shape both buckets share: `{hostname, scan_timestamp, kind: "unknown"\|"changed", details: {...}}`. Phase 39 fills `details`. Predictable for clients but constrains Phase 39. | |
| Fully define both record shapes now | Speculatively define `unknown` (host+vmid+vmtype+pointer) and `changed` (per-field diff) records based on Phase 39's success criteria. Maximal predictability but high risk of needing rework when Phase 38's fingerprint schema actually lands. | |

**User's choice:** Punt the per-row shape to Phase 39 (Recommended)

### Q4: Should the response include per-bucket count fields, or keep just the existing top-level `scanned` (sum)?

| Option | Description | Selected |
|--------|-------------|----------|
| Keep `scanned` + add per-bucket `counts: {probed_ok, unreachable, unknown, changed}` (Recommended) | Top-level `scanned: N` (sum, unchanged from Phase 36) PLUS a `counts` sub-dict with per-bucket sizes. Clients can check coverage at a glance without iterating arrays. Sum kept for compatibility with Phase 36-shape clients. | ✓ |
| Replace `scanned` with `counts` | Remove `scanned`; clients must read `counts.probed_ok + counts.unreachable + ...`. Cleaner but breaks Phase 36 clients. | |
| Just `scanned`, no per-bucket counts | Minimum change from Phase 36. Clients use `len(result["probed_ok"])` etc. Smaller response but less convenient. | |

**User's choice:** Keep `scanned` + add per-bucket `counts: {...}` (Recommended)

---

## Error-Message Scope for DRFT-15

### Q1: What's the scope of the DRFT-15 PROXMOX_HOST sweep — drift surface only, or wider?

| Option | Description | Selected |
|--------|-------------|----------|
| Drift surface only (Recommended) | Touch only the drift-family files: openapi_app.py:60 (drift OpenAPI description), docs/tool-reference.md scan_infrastructure_drift entry, drift_tools_schema.py description, server.py drift resource description. Leaves proxmox_tools_schema.py and configuration.md/setup-guide.md PROXMOX_HOST mentions for Phase 40 (POL-03) and a future docs phase. Aligns with Phase 36 D-19 deferral. | ✓ |
| Drift surface + proxmox_tools_schema.py | Also rewrite the `get_proxmox_resources` and `get_proxmox_vm_status` schema descriptions to point to `homelab-mcp credentials add --type proxmox` instead of PROXMOX_HOST. Bleeds into Phase 40 territory but knocks out related polish. | |
| Full PROXMOX_HOST sweep across docs + schemas | Rewrite every PROXMOX_HOST reference in src/ and docs/ to point to credentials CLI. Includes configuration.md, setup-guide.md. Big, risky — the env var still works as a fallback in get_proxmox_client; rewriting docs to never mention it could mislead users with legacy setups. | |

**User's choice:** Drift surface only (Recommended)

### Q2: Should the response include a top-level recovery-guidance pointer when buckets are empty (e.g., empty sitemap, or filter matched zero rows)?

| Option | Description | Selected |
|--------|-------------|----------|
| Add `guidance` only when scanned == 0 (Recommended) | When no rows were probed (empty sitemap OR filter excluded everything), include `guidance: "No Proxmox hosts in sitemap. Run discover_and_map to populate, or get_network_sitemap to inspect."`. When scanned > 0, omit the field. Self-documenting recovery, no clutter on the happy path. | ✓ |
| Always include `guidance` field with appropriate text | Top-level `guidance` field always present — contains pointer text relevant to current state (empty sitemap, partial coverage, etc.). More uniform shape but adds noise to successful scans. | |
| No guidance field; rely on docs and empty-buckets to communicate state | Empty buckets speak for themselves. Keeps the response purely data. Discoverability moves entirely to docs/tool-reference.md. | |

**User's choice:** Add `guidance` only when scanned == 0 (Recommended)

### Q3: For the per-row `unreachable.error` field, should it include a recovery pointer (e.g., "consider decommission_device or purge_failed_discoveries") or stay as pure sanitized exception text?

| Option | Description | Selected |
|--------|-------------|----------|
| Keep pure sanitized text (Recommended) | Per-row `error` stays as just the sanitized exception message. Recovery guidance lives in the top-level `guidance` field (when relevant) and in docs. Per-row pointers would duplicate text on every entry and be noise when 50 hosts are unreachable for the same network reason. | ✓ |
| Append recovery pointer per row | Each unreachable row's `error` field gets the sanitized message + "— if this host is decommissioned, run `decommission_device hostname=X`; if temporarily offline, no action needed." Helpful but noisy. | |
| Add a separate per-row `recovery` field | Per-row record gains a `recovery: str \| None` field with the pointer (clean separation from `error`). Recovery text per row that targets that row's specific failure mode. Cleaner structure but requires per-row classification logic. | |

**User's choice:** Keep pure sanitized text (Recommended)

### Q4: Should Phase 37 add an AST meta-test guarding drift-family files against `PROXMOX_HOST` substrings (extending the Phase 36 D-13 pattern)?

| Option | Description | Selected |
|--------|-------------|----------|
| Add AST guard for `PROXMOX_HOST` in drift files (Recommended) | New AST test: scan drift_detection.py, drift_handlers.py, drift_tools_schema.py, and the drift section of openapi_app.py for `PROXMOX_HOST` — must be ZERO matches. Locks in DRFT-15 architecturally; extends Phase 36 D-13 footgun-removal pattern. This phase qualifies as footgun-removal class (Bugs B closure). | ✓ |
| No AST guard; rely on tests + code review | DRFT-15 is enforced by test fixtures + reviewer attention. No new AST file. Less guard surface but matches new-feature phase pattern. | |

**User's choice:** Add AST guard for `PROXMOX_HOST` in drift files (Recommended)

---

## DRFT-16 Architectural Lock-In

### Q1: What scope should the DRFT-16 AST guard cover?

| Option | Description | Selected |
|--------|-------------|----------|
| Forbid the three tool-name strings everywhere in src/ (Recommended) | Extend the Phase 36 AST meta-test (or add a new test in the same file) to scan src/homelab_mcp/ for `register_drift_baseline`, `list_drift_baselines`, `delete_drift_baseline` substrings — must be ZERO matches. Catches accidental reintroduction in tool_schemas/, tools.py, handler files, docs strings, etc. Aligns with Phase 36 D-12's table-name guard pattern. | ✓ |
| Forbid only in tool_schemas/ + tools.py (registry only) | Narrower scan: only the files that define the MCP tool surface. Catches direct reintroduction but misses helper functions, docstrings, and migration code that might mention them. | |
| Rely on Phase 36 D-12 + code review | D-12 guards the table name `drift_baselines` already — adding a tool would likely require touching that string somewhere. Skip the new guard. Risky: tool names could be added without the table name (the bug whose existence Phase 36 ruled out). | |

**User's choice:** Forbid the three tool-name strings everywhere in src/ (Recommended)

### Q2: Should the DRFT-16 guard also forbid these tool names appearing in `docs/` (markdown), or only in src/?

| Option | Description | Selected |
|--------|-------------|----------|
| Source code only — src/ scan (Recommended) | AST meta-test scans src/homelab_mcp/ only. Docs are reviewed by the documentation sweep (D-08). Keeps the test focused on the architectural contract — "no MCP tool with these names exists in code." Markdown drift caught by review and the DRFT-15 sweep. | ✓ |
| Source + docs | Extend scan to docs/. Catches stale tutorial sections that reference removed/never-built tools. Slightly broader test surface; docs normally drift faster than code. | |

**User's choice:** Source code only — src/ scan (Recommended)

### Q3: Where should the DRFT-16 guard live — same test file as Phase 36's existing AST guards, or a new dedicated file?

| Option | Description | Selected |
|--------|-------------|----------|
| Extend existing tests/test_ast_regression.py (Recommended) | Add Phase 37 DRFT-16 assertions alongside Phase 36's existing AST guards. One file = one place to look for footgun-removal regression coverage. Follows established convention from Phase 32/33/35/36. | ✓ |
| New file: tests/test_drift_tool_surface_locked.py | Dedicated file for Phase 37's tool-surface guards. Clearer phase-scoped naming but fragments the AST regression coverage across multiple files. | |

**User's choice:** Extend existing tests/test_ast_regression.py (Recommended)

### Q4: Beyond the AST guard, should Phase 37 add a runtime registry assertion (e.g., at server startup) that explicitly logs/raises if a forbidden tool name appears in TOOLS dict?

| Option | Description | Selected |
|--------|-------------|----------|
| AST guard only — no runtime check (Recommended) | AST meta-test runs on every test invocation and CI. Adding a runtime registry check duplicates enforcement at production cost (extra startup work) for a regression that the test pipeline already catches. | ✓ |
| Add runtime registry check at server startup | On server boot, iterate TOOLS dict and assert no forbidden tool names. Belt-and-braces — catches reintroduction even if tests are skipped. Adds startup cost and a bit of code that only runs to fail. | |

**User's choice:** AST guard only — no runtime check (Recommended)

---

## Claude's Discretion

- Exact wording of the `guidance` text (D-09)
- Exact rewrite text for `openapi_app.py:60`, `drift_tools_schema.py` description, `server.py:151` drift resource description
- Per-bucket `counts` dict key ordering
- Whether `guidance` text branches on "empty sitemap" vs "filter-narrowed-to-zero" cases (identical recommended)
- Whether AST guards in D-11 / D-12 share a helper with Phase 36 D-12 / D-13
- Test fixture style (extend existing class vs new `TestPhase37DriftHygiene`)
- Whether `tests/test_drift_detection.py` extends `TestScanDrift2Bucket` or splits into new test classes

## Deferred Ideas

- `unknown` / `changed` per-row record shape and detection — Phase 39
- "Missing infrastructure" enrichment — Phase 39 DRFT-18 (enriches `unreachable` per D-04)
- Wider PROXMOX_HOST sweep — Phase 40 (POL-03) for proxmox tools; future docs phase for configuration.md / setup-guide.md
- `PROXMOX_HOST` AST guard extended to non-drift files — Phase 40 may add
- Persistence of per-host probe history — Phase 39
- Filter syntax extensions (wildcards, comma-separated lists, Proxmox-internal node names)
- Runtime registry assertion for forbidden tool names
- `vm_type` real semantics — Phase 39
- Lifecycle hooks — v1.7.1
- Sitemap tags / role-aware drift — v1.7.2
