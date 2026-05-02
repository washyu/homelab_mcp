# Phase 44: Sitemap CRUD Completion (CRUD-PARITY) — Context

**Gathered:** 2026-05-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Close the v1.7 detection→correction loop on the sitemap-CRUD surface by shipping two new MCP tools that give a user/agent a clean inventory-only path to drop sitemap rows when drift surfaces a divergence:

- **`remove_device(device_id, dry_run=False)`** — pure SQL DELETE on the sitemap row plus cascade DELETE on `discovery_history` for that `device_id`. No SSH dial, no Ansible runs, no Terraform plans on the handler call path. Preserves any keyring credential entry bound to the row's `ssh_credential_id`. `dry_run=True` returns the would-delete row payload without writing.
- **`purge_devices(filter_type, value, dry_run=False)`** — generalized superset of the existing `purge_failed_discoveries`. Single mutually-exclusive filter per call, picked by `filter_type` enum: `hostname`, `last_seen_older_than_days`, `status`, `ip_range`. `dry_run=True` returns the candidate set without deletion. `purge_failed_discoveries` is preserved as a named alias that delegates to `purge_devices` with the failed-discovery filter (status='error' OR hostname IN (NULL,'','unknown')).
- Tool descriptions explicitly contrast the three delete paths so an MCP client surfaces the right tool for the right intent: `remove_device` (one row, inventory-only), `purge_devices` (bulk, filter-based, inventory-only), `decommission_device` (one row, host-side cleanup + DELETE). Wording-parity rule applied across schema description and `docs/tool-reference.md` prose.
- `docs/tool-reference.md` documents both new tools with example invocations, plus a one-line cross-reference in the `decommission_device` section pointing to `remove_device` as the right choice when the user wants inventory-only deletion.
- Full unit suite remains green (≥907 passing, no skips introduced); new tests cover: `remove_device` happy path, `dry_run` preview, missing-`device_id` error path, credential-preservation invariant; `purge_devices` per-filter behavior and `purge_failed_discoveries` alias parity. Ruff + mypy clean. AST guard added so the `remove_device` handler's call path is provably free of SSH / Ansible / Terraform invocations.

Out of this phase:

- Hostname pattern matching (glob, SQL LIKE) on the `purge_devices` `hostname` filter — the value is an exact hostname string. "Purge all `test-*` rows" use case is served by `last_seen_older_than_days` or `ip_range`, or by the agent walking `get_network_sitemap` and calling `remove_device` per row.
- Composite/ANDed `purge_devices` filters (e.g., "error rows older than 7 days" in a single call). Single-filter shape is locked. Compound queries require either two calls or pre-filtering by the agent.
- Hostname-as-input on `remove_device`. `device_id` is the only identity input; agent looks up via `get_network_sitemap` when only the hostname is known.
- Touching `decommission_device` semantics. Phase 44 is purely additive on the sitemap-CRUD surface; `decommission_device` keeps its existing host-cleanup-on-DELETE shape. The cross-reference in `docs/tool-reference.md` is wording-only.
- Schema migration. No new columns, no DDL changes. New tools operate on existing `devices` and `discovery_history` tables.
- Touching the keyring resolution path. `remove_device` MUST NOT call `delete_credential` / `keyring.delete_password` / any credential-cleanup helper — keyring entries outlive the sitemap row by design (SC-2 lets a subsequent `discover_and_map` re-bind without forcing the user to re-add credentials).
- Auto-promotion or any drift-side surfacing of "this row has been stale for N days, want to purge?" UX hints. Drift report (Phase 39 D-01) already points users at `decommission_device` / `purge_failed_discoveries`; updating those pointers to mention `remove_device` / `purge_devices` is part of SC-4's wording-parity sweep, not a new UX behavior.

</domain>

<decisions>
## Implementation Decisions

### `purge_devices` filter API shape

- **D-01 (single mutually-exclusive filter per call):** `purge_devices` schema shape is `{filter_type: str (enum), value: any, dry_run: bool}`. Exactly one filter applied per call. The `filter_type` enum is `["hostname", "last_seen_older_than_days", "status", "ip_range"]`. `value`'s shape varies per `filter_type` (string for hostname/status, integer for last_seen, CIDR string for ip_range). Composite/ANDed filters are NOT supported — compound queries (e.g., "error rows older than 7 days") require two calls or agent-side pre-filtering. Mirrors the existing single-purpose `purge_failed_discoveries` shape and keeps the SQL builder + `dry_run` semantics simple.
- **D-01a (response shape mirrors `purge_failed_discoveries`):** Response payload matches the existing tool: `{status: "success", dry_run: bool, purged_count: int, purged_devices: list[dict]}`. Each row in `purged_devices` carries the full sitemap row dict (id, hostname, connection_ip, status, error_message, last_seen) so the agent can confirm what would be / was deleted. `default=str` JSON serialization for datetime fields, identical to existing handler.
- **D-01b (validation at handler boundary):** `value` shape validation lives in the handler, not the JSON Schema. JSON Schema declares `value` as a permissive `oneOf` (string | integer) and the handler dispatches on `filter_type` to validate the value's shape (e.g., `int` for `last_seen_older_than_days`, valid CIDR for `ip_range`). MCP framework does not enforce inputSchema (Phase 38 RESEARCH.md §5 finding) — handler-side validation is the actual enforcement. Structured error envelope on bad value shape with a hint pointing at the expected format.
- **D-01c (zero-match returns success with empty list):** A filter that matches no rows returns `{status: "success", dry_run: ?, purged_count: 0, purged_devices: []}`, NOT an error. Matches Phase 37 D-01 four-bucket invariant ("empty match returns an empty result, never a scope error") and the existing `purge_failed_devices` behavior.

### `purge_devices` filter syntax (per-`filter_type` value semantics)

- **D-02 (`hostname` = exact match):** `value` is the literal hostname string. SQL: `WHERE hostname = ?`. No wildcards, no globs, no pattern-translation. Loses the "purge all `test-*` rows in one call" use case — that's served by `ip_range` (if the test rig is on its own subnet), `last_seen_older_than_days` (if the rows are stale), or by the agent calling `remove_device` per row after a `get_network_sitemap` query. Trade-off accepted: simplest possible semantics, no escape-character footguns, no glob-vs-LIKE translation layer.
- **D-03 (`ip_range` = CIDR notation):** `value` is a CIDR string like `192.168.1.0/24`, `10.0.0.0/8`, `192.168.1.42/32` (single IP), or `2001:db8::/32` (IPv6). Handler uses `ipaddress.ip_network(value, strict=False)` and per-row `ipaddress.ip_address(row['connection_ip']) in net` for the membership check. Python-side filtering after `SELECT * FROM devices` (NOT a SQL string-match) — SQL string-matching on IPs is fragile across `connection_ip` formats (IPv4, IPv6, hostname-as-IP fallback rows). The standard-library `ipaddress` module already handles IPv6, single-IP, and non-byte-aligned subnets for free.
- **D-03a (skip rows where `connection_ip` is not a valid IP):** During the per-row CIDR membership scan, rows whose `connection_ip` doesn't parse as an IP (e.g., zombie rows where `connection_ip` is the hostname-fallback or empty string) are silently skipped — they never match the filter. No error raised; the row stays in sitemap. If the user wants to purge those, they use `filter_type='hostname'` with the empty/unknown value or `filter_type='status'` with `'error'`.
- **D-04 (`last_seen_older_than_days`):** `value` is an integer N. Match: rows whose `last_seen < (now_utc - N days)`. Reuses Phase 42 W2 canonical-UTC convention — `now_utc = datetime.now(UTC)` and `last_seen` is parsed as ISO-format UTC. Boundary is exclusive (`<`, not `<=`) so `N=0` matches everything older than this instant (effectively "purge any row older than now," useful as a sanity-check filter). SQL: `WHERE last_seen < ?` with the threshold computed in Python and bound as a string (existing pattern — `last_seen` is `TEXT`, ISO-format).
- **D-05 (`status`):** `value` is the literal status string. SQL: `WHERE status = ?`. Existing valid statuses observed in the codebase: `'success'`, `'error'`. The `purge_failed_discoveries` alias passes `status='error'` AND the empty/null/unknown hostname zombie-row clause (D-08); a raw `purge_devices(filter_type='status', value='error')` matches ONLY by status (no hostname clause). The alias does more than the bare filter — see D-08.

### `remove_device` identity convention

- **D-06 (`device_id` only):** `remove_device(device_id: int, dry_run: bool = False)`. Schema: `{device_id: integer, dry_run: boolean (default false)}`, `required: ["device_id"]`. Matches `decommission_device` exactly — zero ambiguity about which row is being deleted, since `id` is the surrogate PK and hostnames can drift after rebinding (e.g., a `discover_and_map` after the row was created with a degenerate hostname). Agent looks up via `get_network_sitemap` when the user only knows the hostname; small extra round-trip but eliminates the hostname-collision class of bugs entirely.
- **D-06a (response shape):** `{status: "success", dry_run: bool, removed_device: dict | None}`. `removed_device` is the full row payload that was deleted (or would be deleted, on dry_run); `None` only when the device_id doesn't exist (which is a structured-error case, D-06b). Single-row analog of D-01a's `purged_devices` list shape.
- **D-06b (missing `device_id` → structured error, not exception):** When `device_id` doesn't resolve to an existing row, return `{status: "error", error: "Device {device_id} not found in sitemap", hint: "Run get_network_sitemap to see current device IDs."}` — same structured-error envelope pattern as `update_device_fingerprint`'s missing-hostname branch (`network_handlers.py:120-127`). Do NOT raise; the MCP framework surfaces the error envelope to the agent.
- **D-06c (cascade `discovery_history` BEFORE `devices`):** The new adapter method follows the existing `purge_failed_devices` two-step pattern (`database.py:646-654`): `DELETE FROM discovery_history WHERE device_id = ?` first, then `DELETE FROM devices WHERE id = ?`. No FK CASCADE on the schema (existing convention — Phase 35 / Phase 38 didn't add one and Phase 44 doesn't change schema). Wrapped in a single transaction so a failure mid-cascade doesn't orphan rows.

### `purge_failed_discoveries` alias semantics

- **D-07 (alias preserved verbatim, no caller break):** `purge_failed_discoveries` stays registered as a distinct MCP tool with its existing schema (`{dry_run: boolean}`, `required: []`) and existing description. Its handler delegates to a shared internal helper that `purge_devices` also uses, so the SQL behavior is byte-identical. Existing callers see no change; the description gets a small "(equivalent to `purge_devices` with the failed-discovery filter)" parenthetical added per SC-4's wording-parity sweep.
- **D-08 (failed-discovery filter is a multi-clause SQL filter, not just `status='error'`):** The existing `purge_failed_devices` impl matches `status='error' OR hostname IS NULL OR hostname='' OR hostname='unknown'` (`database.py:633-637`). This is a 4-clause OR, NOT just `status='error'`. The `purge_failed_discoveries` alias preserves all four clauses (the zombie-row hostname check is part of "failed discovery"). Calling `purge_devices(filter_type='status', value='error')` matches ONLY `status='error'` — it does NOT match the zombie-hostname rows. This is intentional: the alias retains its broader semantics; the bare `status` filter is precisely what the user asked for. Tool descriptions should call out this difference so an agent doesn't assume `purge_devices(filter_type='status', value='error')` is a drop-in replacement for `purge_failed_discoveries`.

### Tool description wording-parity (SC-4)

- **D-09 (three-tool contrast block in every description):** Each of the three delete-tool descriptions (`remove_device`, `purge_devices`, `decommission_device`) ends with a one-sentence "Use X for ...; use Y for ...; use Z for ..." contrast block, identical wording across all three. Template:
  > "Use `remove_device` for inventory-only deletion of one row; use `purge_devices` for bulk filter-based inventory deletion; use `decommission_device` when host-side cleanup (stop services, remove from clusters) is required before deletion."
  Mirrors Phase 37 D-08 / Phase 40 D-04 / `resolve_proxmox_credentials` consistency convention — one canonical sentence reused verbatim so MCP clients surface the same disambiguation across tool entries.
- **D-09a (docs/tool-reference.md cross-reference):** `decommission_device`'s `docs/tool-reference.md` entry gets a one-line "See also: `remove_device` for inventory-only deletion (no host-side cleanup)." cross-reference. New entries for `remove_device` and `purge_devices` include example invocations covering happy path + dry_run + each filter type.

### AST guard for "no host-side actions" (SC-6)

- **D-10 (handler-body AST guard, Phase 37 D-11 / Phase 40 D-06 idiom):** New AST meta-test in `tests/test_ast_regression.py` that walks the body of `handle_remove_device` (in whichever `tool_handlers/` module it lands — see D-12) and the new adapter method `delete_device_by_id` (in `database.py`), asserting the AST does not contain references to a fixed forbidden-symbol list:
  - `ssh_connect`, `asyncssh` (any name from these — imports, calls, attribute access)
  - `subprocess.run`, `subprocess.Popen`, `subprocess.call`, `subprocess.check_call`, `subprocess.check_output` with argv that includes `'ansible-playbook'` or `'terraform'`. Simpler implementation: forbid ALL `subprocess.*` calls in the handler body (handler should be pure DB work — no shell needed). Most defensive scope.
  - `keyring.delete_password`, `keyring.set_password`, `delete_credential`, `delete_proxmox_credential` (any keyring or credential-mutation symbol)
  - `decommission_network_device`, `_stop_all_device_services`, `_remove_from_clusters`, `_execute_migration_plan` (the existing decommission helpers — explicitly banned to prevent "let's just call decommission internally" drift). Targeted symbol-list match.
- **D-10a (guard scope = body-level only, not transitive):** Matches Phase 37 D-11 / Phase 40 D-06 / Phase 38.1 D-15 precedent — the guard walks the named function's AST, not the call graph. Keeping the handler body minimal (just `validate_device_id` + `db_adapter.delete_device_by_id` + response shape) is what makes this guard hold; if the planner is tempted to extract a helper, the helper goes into the guard's named-function list. New helpers added in this phase get explicit names in the test class. Matches `feedback_regression_test_scope.md` — AST guards for footgun-class drift, not whole-tree scans.
- **D-10b (test class naming):** New test class `TestPhase44RemoveDeviceCallPath` in `tests/test_ast_regression.py`, sibling to existing `TestPhase37/38.1/40` classes. Each forbidden-symbol assertion is its own `test_*` method so failures pinpoint which symbol regressed.

### Preview-tool variants (Phase 15 / Phase 38 D-05c convention)

- **D-11 (ship `remove_device_preview` and `purge_devices_preview` thin delegates):** Both new tools get `*_preview` siblings registered in the schema + handler registries. Each preview handler is one line: `return await handle_X({**arguments, "dry_run": True})`. `readOnlyHint=True` annotation on each (per `tool_annotations.py` convention — same as existing `decommission_device_preview` at line 46 and `update_device_fingerprint_preview`). Matches the established Phase 15 `*_preview` convention; belt-and-braces for MCP clients that key off the `_preview` naming pattern even when the underlying tool already has `dry_run`.
- **D-11a (preview delegates honor SC-2 credential-preservation invariant trivially):** Preview path makes no DB writes (delegates with `dry_run=True`), so the keyring-untouched and discovery-history-untouched invariants hold by construction.

### Code organization

- **D-12 (handler module placement):** Both new handlers (`handle_remove_device`, `handle_purge_devices`, plus their `_preview` siblings) land in `src/homelab_mcp/tool_handlers/network_handlers.py` — the same file as `handle_purge_failed_discoveries` and the existing sitemap-CRUD handlers. NOT in `infrastructure_handlers.py` (which carries the host-side `decommission_device` semantics — keeping the new pure-SQL tools out of that file is half the AST guard's job). Schemas land in `src/homelab_mcp/tool_schemas/network_tools_schema.py` adjacent to the existing `purge_failed_discoveries` schema entry. Tool registry in `src/homelab_mcp/tool_handlers/__init__.py` adds the four new entries (`remove_device`, `remove_device_preview`, `purge_devices`, `purge_devices_preview`) to `TOOL_HANDLERS`.
- **D-13 (adapter method `delete_device_by_id` on `DatabaseAdapter` ABC + both concretes):** New abstract method on `DatabaseAdapter` (`database.py:147`-area) with SQLite (`SQLiteAdapter`) and Postgres (`PostgreSQLAdapter`) implementations. Signature: `delete_device_by_id(device_id: int, dry_run: bool = False) -> dict | None`. Returns the row dict that was (or would be) deleted; returns `None` when the row doesn't exist. SQLite impl mirrors `purge_failed_devices` two-step DELETE pattern (`discovery_history` first, then `devices`); Postgres impl mirrors the same. Single transaction per call.
- **D-14 (shared internal `_purge_devices_by_filter` helper):** A new private helper in `database.py` (or a small `sitemap.py` shim) accepts the parsed filter (`filter_type`, `value`, `dry_run`) and dispatches to the right SQL clause. `purge_failed_discoveries`'s handler calls this helper with the failed-discovery sentinel filter; `purge_devices`'s handler calls it with the user-supplied filter. Both go through the same SQL execution path so the test surface is unified. The helper does NOT live in the handler module — keeps `network_handlers.py` thin and the AST guard cleaner.

### Tests (SC-6)

- **D-15 (functional + unit tests, no integration scaffolding needed):** Per `feedback_regression_test_scope.md` — Phase 44 ships new tools (new-feature shape, not footgun-removal), so functional + unit tests carry the load. AST guard (D-10) is the one footgun-class meta-test, justified by SC-6's explicit "regression protection against future 'let's just call decommission internally' drift" wording. Recommended test files (planner picks final naming):
  - `tests/test_remove_device.py` (new) or extend `tests/test_network_handlers.py` — `remove_device` happy path, dry_run preview shape, missing-`device_id` error envelope (D-06b), credential-preservation invariant (assert keyring contents unchanged after delete — fixture stubs `keyring.get_password` and verifies no `delete_password` was called).
  - `tests/test_purge_devices.py` (new) or extend `tests/test_network_handlers.py` — per-filter behavior (one test per `filter_type`), dry_run preview, zero-match success path (D-01c), bad-`value`-shape error envelope (D-01b), CIDR matching incl. IPv6 + single-IP `/32` (D-03), `last_seen_older_than_days` boundary case (D-04), `status` filter NOT matching zombie rows (D-08).
  - `tests/test_purge_failed_discoveries_alias.py` (new) or extend existing — alias parity test: assert `purge_failed_discoveries()` and the equivalent four-clause filter via the shared helper produce byte-identical row sets on a seeded DB. Locks D-07 + D-08.
  - `tests/test_database.py` (extend) — `delete_device_by_id` adapter round-trip on SQLite (and Postgres via the existing integration harness if it covers `purge_failed_devices`).
  - `tests/test_ast_regression.py` (extend) — `TestPhase44RemoveDeviceCallPath` per D-10b. One `test_*` per forbidden symbol.

### Documentation (SC-5)

- **D-16 (docs/tool-reference.md sweep):** New entries for `remove_device`, `remove_device_preview`, `purge_devices`, `purge_devices_preview` with example invocations covering happy path + dry_run + each filter type. Updated `decommission_device` entry: add the one-line "See also: `remove_device` for inventory-only deletion" cross-reference (D-09a) plus the contrast-block sentence (D-09). Updated `purge_failed_discoveries` entry: add the parenthetical "(equivalent to `purge_devices` with the failed-discovery filter)" + contrast-block sentence. No new top-level docs; everything threads into the existing tool-reference structure.
- **D-16a (no docs/configuration.md changes):** No new env vars, no new config knobs.
- **D-16b (no setup-guide.md changes):** New tools surface through the existing MCP tool catalog; no onboarding-flow changes.

### Claude's Discretion

- Exact name of the adapter method (`delete_device_by_id` recommended; `remove_device_row` would also work — `delete` is more SQL-idiomatic, `remove` mirrors the MCP tool name). Planner picks; recommend `delete_device_by_id` for symmetry with `get_all_devices` / `store_device`.
- Whether the shared filter-dispatch helper (D-14) lives in `database.py` (next to the adapter methods it wraps) or in `sitemap.py` (next to the existing `purge_failed_devices` shim at line 201). Either is fine; recommend `database.py` because the dispatch is purely SQL-builder logic and `sitemap.py`'s `NetworkSiteMap` is already a thin wrapper.
- Exact AST-guard implementation strategy: per-symbol `ast.NodeVisitor` walk vs `ast.dump` substring match. Per-visitor walk recommended (mirrors Phase 38.1 D-15's `_FORBIDDEN_CONTINUE_FUNCTIONS` walk); substring match acceptable for simpler "no `subprocess.` anywhere in body" checks.
- Exact wording of the contrast block (D-09 template). Planner polishes for actionability matching Phase 37 D-08 / Phase 40 D-04 conventions; the canonical sentence is then copy-pasted verbatim into all three tool descriptions + the `docs/tool-reference.md` overview.
- Whether `last_seen_older_than_days` value=0 (D-04 boundary) is allowed or rejected as nonsense. Recommend allow — it's a useful "purge anything stale right now" filter, not a footgun. Document the exclusive-boundary semantic in the description.
- Whether the SQL builder unifies into one parametrized query string with `WHERE` clauses chosen by `filter_type`, or one query per `filter_type`. One-per-filter recommended (4 small functions, easier to test, no SQL-injection-via-clause-construction surface).
- Whether `purge_devices` description in the schema enumerates the filter_type values (planner adds enum constraint to JSON Schema for IDE/agent autocomplete) or just describes them in prose. Recommend BOTH: JSON Schema `enum` for hard validation + description prose for human-readable intent.
- Whether the credential-preservation test (D-15) uses a real keyring backend or a mock. Mock recommended — matches existing `tests/test_credentials.py` conventions and avoids OS-specific keyring setup in CI.
- Test class naming inside `tests/test_remove_device.py` / `tests/test_purge_devices.py` (`TestPhase44RemoveDevice` vs `TestRemoveDevice` etc.) — planner picks per existing `tests/` conventions.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 44 lock-ins

- `.planning/ROADMAP.md` §Phase 44 — Phase goal + 6 Success Criteria; the scope anchor.
- `.planning/STATE.md` §Roadmap Evolution — Phase 44 origin (promoted from backlog 999.21 + 999.5 after 2026-05-02 validation testing surfaced detection-without-correction-action gap).

### Prior phase decisions (locked, inherited)

- `.planning/milestones/v1.6-phases/35-sitemap-discovery-reliability-fix-discover-and-map-field-los/35-CONTEXT.md` §D-01 — hostname-as-natural-key for sitemap upserts. Phase 44 doesn't change the upsert path; `remove_device` operates on the surrogate `id` PK by deliberate choice (D-06).
- `.planning/phases/36-drift-sitemap-foundation/36-CONTEXT.md` §D-09 — `get_all_devices()` is the single sitemap read funnel. Phase 44's `purge_devices` filter dispatch reads through the same funnel for the CIDR membership scan (D-03) so the row shape is consistent with what drift sees.
- `.planning/phases/37-drift-output-shape-error-hygiene/37-CONTEXT.md` §D-08 — error-message style points users at sitemap CRUD tools (`get_network_sitemap`, `purge_failed_discoveries`, `decommission_device`). Phase 44 D-09 extends this convention: the new contrast-block wording lands in the same drift error messages so an agent surfacing a drift result sees the right delete tool for its intent.
- `.planning/phases/37-drift-output-shape-error-hygiene/37-CONTEXT.md` §D-11 — AST meta-test pattern banning a footgun symbol (PROXMOX_HOST). Phase 44 D-10 follows the same pattern with a different forbidden-symbol set scoped to `handle_remove_device` body.
- `.planning/phases/38-sitemap-fingerprint-schema/38-CONTEXT.md` §D-05c — `*_preview` thin-delegation wrapper convention (Phase 15 origin). Phase 44 D-11 ships `remove_device_preview` and `purge_devices_preview` per this convention.
- `.planning/phases/38-sitemap-fingerprint-schema/38-CONTEXT.md` §D-11 — adapter-method pattern for new sitemap-write paths (`update_device_fingerprint` on `DatabaseAdapter` ABC + concretes). Phase 44 D-13 mirrors for `delete_device_by_id`.
- `.planning/phases/38.1-sitemap-keystore-credential-binding/38.1-CONTEXT.md` §D-15 — body-level AST guard scoped to a named function. Phase 44 D-10a follows the same scope discipline (no transitive call-graph walk).
- `.planning/phases/40-proxmox-vm-lifecycle-polish/40-CONTEXT.md` §D-06 — AST guard scope extension precedent (extending an existing assertion's file/symbol list). Phase 44 D-10 introduces a new test class rather than extending Phase 37's PROXMOX_HOST guard, because the forbidden-symbol set is different in kind (call-path symbols vs string-literal sweeps).
- `.planning/phases/40-proxmox-vm-lifecycle-polish/40-CONTEXT.md` §D-04 — keyring-only credential pattern, hard-error-with-actionable-pointer when env-var/legacy paths are removed. Phase 44 D-06b's missing-`device_id` error envelope follows this convention (structured error, not exception, with hint at the recovery action).

### Memory / user feedback

- `~/.claude/projects/C--Users-washy-projects-mcp-python-server/memory/feedback_regression_test_scope.md` — AST meta-tests guard known footguns; new-feature paths use functional + unit tests only. Phase 44 mostly new-feature (D-15 functional+unit), with ONE AST guard (D-10) explicitly justified by SC-6's "regression protection against future 'let's just call decommission internally' drift" wording.
- `~/.claude/projects/C--Users-washy-projects-mcp-python-server/memory/project_credential_architecture.md` — keyring as single source of truth; missing entry = hard error with CLI pointer. Phase 44 SC-2 (preserve keyring on `remove_device`) lands directly on this principle: the sitemap row is dropped but the keyring entry survives, so a subsequent `discover_and_map` re-binds without forcing the user to re-add credentials.

### Source files (read before changing)

- `src/homelab_mcp/tool_handlers/network_handlers.py:69-84` — `handle_purge_failed_discoveries` current implementation. D-12 places the new handlers in this same file; D-07's alias delegates to the shared filter-dispatch helper.
- `src/homelab_mcp/tool_handlers/infrastructure_handlers.py:36-56,117-123` — `handle_decommission_device` + `handle_decommission_device_preview`. NOT touched by Phase 44, but downstream agents read this to confirm what `remove_device`'s AST guard is keeping out (`ssh_connect`, `_stop_all_device_services`, `_remove_from_clusters`).
- `src/homelab_mcp/tool_schemas/network_tools_schema.py:87-104` — `purge_failed_discoveries` schema entry. New `remove_device` / `purge_devices` schema entries land adjacent; alias description gets the SC-4 wording-parity update.
- `src/homelab_mcp/tool_schemas/infrastructure_tools_schema.py:105-147` — `decommission_device` schema entry. Description gets the SC-4 contrast-block sentence appended.
- `src/homelab_mcp/sitemap.py:201-209` — `NetworkSiteMap.purge_failed_devices` shim. Phase 44 may add a sibling `remove_device(device_id)` shim or call the adapter directly from the handler; planner picks (Claude's Discretion). Either way the shim is thin.
- `src/homelab_mcp/database.py:147-155` — `DatabaseAdapter.purge_failed_devices` ABC. D-13 adds a sibling `delete_device_by_id` ABC method.
- `src/homelab_mcp/database.py:624-656` — `SQLiteAdapter.purge_failed_devices` impl. The two-step DELETE pattern (D-06c) is reused verbatim for `delete_device_by_id`.
- `src/homelab_mcp/database.py:1182` — `PostgreSQLAdapter.purge_failed_devices` impl. Mirror for the new adapter method.
- `src/homelab_mcp/tool_handlers/__init__.py:14-15,29,91,97-98` — handler registry. Add `remove_device`, `remove_device_preview`, `purge_devices`, `purge_devices_preview` entries.
- `src/homelab_mcp/tool_annotations.py:46,66,71` — annotations registry. `remove_device_preview` + `purge_devices_preview` get `readOnlyHint=True`; `remove_device` + `purge_devices` get the destructive-action annotations matching `decommission_device` / `purge_failed_discoveries`.
- `src/homelab_mcp/openapi_app.py:43,154,185-186` — OpenAPI tool list. Add the four new tool names.
- `src/homelab_mcp/drift_detection.py:60-61,126,209,227-228` — drift error/guidance messages currently point at `decommission_device` / `purge_failed_discoveries`. Phase 44 SC-4 wording-parity sweep updates these to mention `remove_device` / `purge_devices` where appropriate (planner picks per-message; e.g., the missing-bucket recovery pointer in `_drift_message` gains `remove_device` as the inventory-only option).
- `src/homelab_mcp/server.py:157,1022` — server-level error messages mentioning `purge_failed_discoveries`. Same SC-4 sweep — planner reads each occurrence in context and updates wording per D-09.
- `tests/test_ast_regression.py` — D-10 adds `TestPhase44RemoveDeviceCallPath` class with one `test_*` per forbidden symbol. Sibling to existing `TestPhase37/38.1/40` classes.
- `docs/tool-reference.md` — D-16 sweep (new entries + cross-reference + contrast-block sentence updates).

### External / library reference

- Python `ipaddress` stdlib (https://docs.python.org/3/library/ipaddress.html) — `ip_network(value, strict=False)` and `ip_address(addr) in net` for D-03's CIDR membership check. Handles IPv4, IPv6, single-IP `/32` and `/128`, non-byte-aligned subnets natively. `strict=False` accepts host bits set (e.g., `192.168.1.42/24` doesn't raise).
- SQL parametrized query convention — Phase 44 SQL uses `?` placeholders for SQLite and `%s` for Postgres, identical to existing adapter impls. No string interpolation in query construction (Bandit S608 already in use across the codebase).

### Pattern / architecture reference

- `purge_failed_devices` two-step DELETE (`database.py:646-654`) — manual cascade because `discovery_history` has no FK CASCADE. D-06c reuses verbatim for `delete_device_by_id`.
- `update_device_fingerprint` missing-hostname error envelope (`network_handlers.py:120-127`) — structured-error pattern for "row not found" cases. D-06b mirrors for missing `device_id`.
- `decommission_device_preview` thin delegation (`infrastructure_handlers.py:117-123`) — `*_preview` convention's canonical impl. D-11's `remove_device_preview` / `purge_devices_preview` are line-for-line copies with the underlying handler swapped.
- Phase 37 D-11 PROXMOX_HOST AST guard — body-level scan for forbidden literals. D-10 follows the same scope shape with a forbidden-symbol set instead of a forbidden-literal set.
- Phase 42 W2 canonical UTC convention (`datetime.now(UTC).isoformat()` writes; `last_seen` parses as UTC ISO) — D-04's `last_seen_older_than_days` boundary computation reuses this.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`purge_failed_devices` impl** (`database.py:624-656` SQLite, `:1182` Postgres) — two-step DELETE template; the failed-discovery 4-clause OR is the source-of-truth SQL for D-08's alias semantics.
- **`handle_purge_failed_discoveries`** (`network_handlers.py:69-84`) — response-shape template for D-01a (`status`, `dry_run`, `purged_count`, `purged_devices`).
- **`handle_decommission_device_preview` + `handle_update_device_fingerprint_preview`** — `*_preview` thin-delegation template for D-11. One-liner: delegate with `dry_run=True` injected.
- **`handle_update_device_fingerprint` missing-hostname error envelope** (`network_handlers.py:120-127`) — D-06b's missing-`device_id` envelope mirrors structurally.
- **`DatabaseAdapter` ABC + concrete `SQLiteAdapter`/`PostgreSQLAdapter`** — D-13's `delete_device_by_id` slots into the existing pattern (abstract method + 2 impls).
- **`tool_handlers/__init__.py` + `tool_schemas/__init__.py` registries** — D-12's four new tool entries plug in via the existing registration pattern.
- **Phase 37 D-11 + Phase 38.1 D-15 + Phase 40 D-06 AST-guard test classes** — D-10 follows the same shape with a new forbidden-symbol set.
- **`ipaddress` stdlib** — D-03's CIDR membership check is one stdlib import; no third-party dep needed.

### Established Patterns

- **Sitemap CRUD handler module placement** — sitemap-write handlers live in `tool_handlers/network_handlers.py` (purge_failed_discoveries, update_device_fingerprint). D-12 places the new handlers there.
- **Hostname-as-natural-key for sitemap upserts** (Phase 35 D-01) — Phase 44 explicitly opts for `id` PK on `remove_device` (D-06) because the upsert key and the row identity for delete are different concerns.
- **Two-step DELETE for cascading discovery_history** (purge_failed_devices) — no FK CASCADE in schema, manual cascade in adapter. D-06c reuses.
- **Structured error envelopes** (`{status: "error", error: ..., hint: ...}`) — D-06b + D-01b follow.
- **Response shape `{status, dry_run, purged_count, purged_devices}`** for bulk-delete tools (purge_failed_discoveries) — D-01a reuses.
- **`*_preview` thin-delegation convention** (Phase 15, used by Phase 38 + decommission_device) — D-11 ships both new tools with siblings.
- **Body-level AST guard with named-function scope** (Phase 37/38.1/40) — D-10/D-10a/D-10b adopt.
- **Wording-parity contrast block in tool descriptions** (Phase 37 D-08 sitemap-CRUD-tool error pointers) — D-09 extends with a 3-tool delete contrast.
- **No AST meta-tests for pure-feature paths; functional+unit only** (`feedback_regression_test_scope.md`) — D-15 functional + D-10 single AST guard for the call-path footgun.

### Integration Points

- **`tool_handlers/__init__.py` `TOOL_HANDLERS` dict** — single registration point; 4 new entries.
- **`tool_schemas/network_tools_schema.py` + `tool_schemas/infrastructure_tools_schema.py`** — schema entries land here; the latter only gets a description-text update for `decommission_device` (D-09).
- **`tool_annotations.py`** — `_preview` reads + destructive writes get the appropriate annotation flags (D-11).
- **`openapi_app.py` tool lists** — 4 new tool names added in 2-3 places (lines 43, 154, 185-186).
- **`drift_detection.py` error/guidance messages** — SC-4 wording-parity sweep updates the recovery pointers (lines 60-61, 126, 209, 227-228).
- **`server.py` error messages** mentioning `purge_failed_discoveries` (lines 157, 1022) — same SC-4 sweep.
- **`database.py` `DatabaseAdapter` ABC** — D-13's new abstract method slots in next to `purge_failed_devices`; impls land in both concretes.
- **`tests/test_ast_regression.py`** — new `TestPhase44RemoveDeviceCallPath` test class.

</code_context>

<specifics>
## Specific Ideas

- **Single filter, enum-typed `filter_type`, was the conscious simplicity choice.** User picked the CLI-style `(filter_type, value)` shape over a composite filter object specifically to keep the SQL builder + dry_run semantics simple. Compound queries ("error rows older than 7 days") cost two calls or agent-side pre-filtering; the design accepts that trade because the homelab single-user use-cases are dominated by single-filter calls. If composite ANDed filters become a pain point in practice, the schema can be relaxed later (single → composite is additive, not breaking).
- **Hostname filter is exact-match, not glob/LIKE — deliberately.** User picked the simplest possible semantics over the "purge all `test-*` rows in one call" use case. That use case is served by `ip_range` (test rig on its own subnet), `last_seen_older_than_days` (test rows go stale quickly), or by the agent walking `get_network_sitemap` and calling `remove_device` per row. No glob-vs-LIKE translation layer; no escape-character footguns; no surprise behavior when a hostname literally contains `%` or `*`.
- **CIDR for `ip_range`, with `ipaddress.ip_network(strict=False)` and Python-side filtering.** Standard, unambiguous, IPv6-supporting, single-IP-supporting. Python-side filtering after `SELECT *` (NOT a SQL string-match) because `connection_ip` formats vary (IPv4, IPv6, hostname-as-IP fallback for zombie rows). Rows whose `connection_ip` doesn't parse as an IP are silently skipped on a CIDR scan — consistent with the broader "purge_devices is a precise-match tool" philosophy.
- **`device_id` only on `remove_device` (no hostname kwarg).** User picked symmetry with `decommission_device` over symmetry with `update_device_fingerprint`. Reasoning: hostname can drift (rebinding after `discover_and_map`), `id` is the surrogate PK that stays stable, and the small extra round-trip via `get_network_sitemap` eliminates the hostname-collision class of bugs entirely. Agent ergonomics: trivial — every drift report already surfaces `id` per row.
- **`purge_failed_discoveries` alias is NOT a thin wrapper over `purge_devices(filter_type='status', value='error')`.** The alias preserves the existing 4-clause OR semantics (`status='error' OR hostname IN (NULL,'','unknown')`); the bare `status` filter matches ONLY `status='error'`. This difference is deliberate — and called out in tool descriptions so an agent doesn't assume drop-in equivalence. The shared internal helper exists to unify the SQL execution path, not to flatten the semantic difference.
- **AST guard targets the `handle_remove_device` body and the new adapter method specifically — body-level only, not transitive.** Matches Phase 37/38.1/40 precedent. Keeping the handler body minimal (validate → adapter call → response shape) is what makes the guard hold; if the planner extracts a helper, the helper goes into the guard's named-function list. The forbidden-symbol set targets the actual recurrence vector ("let's just call decommission internally") plus the adjacent footguns (`asyncssh`, subprocess→ansible/terraform, keyring delete).
- **Preview siblings ship even though `dry_run` is already a first-class param.** Belt-and-braces for MCP clients that key off the `_preview` naming convention (matches `decommission_device_preview`'s precedent — that tool also takes `dry_run`). Each is a one-liner; the cost is trivial; the convention consistency pays off in MCP client surfacing.

</specifics>

<deferred>
## Deferred Ideas

Captured during 44 discussion — preserved so v1.7.1 / v1.7.2 / v1.8 / future phases pick them up.

- **Composite/ANDed `purge_devices` filters.** User explicitly picked single-filter shape (D-01). If "error rows older than 7 days in a single call" becomes a frequent ask, relax the schema to accept a `filters: [{filter_type, value}, ...]` list with implicit AND. Schema change is additive (legacy `(filter_type, value)` calls still work) — not a breaking change. → **v1.8 candidate** if the use case emerges.
- **Hostname pattern matching (glob or SQL LIKE).** User picked exact-match (D-02). If the agent finds itself walking `get_network_sitemap` + `remove_device` loops to express "purge all `test-*`" patterns frequently, add a `hostname_pattern` filter type with explicit pattern syntax (recommend SQL LIKE — pass-through, no translation layer). Distinct from the bare `hostname` filter so semantics stay unambiguous. → **v1.8 candidate.**
- **Hostname kwarg on `remove_device`.** User picked `device_id`-only (D-06). If round-trip-via-`get_network_sitemap` proves friction-heavy in practice, add a hostname kwarg (xor with device_id, handler-side validated). Schema change is additive. → **v1.8 candidate.**
- **Drift report bucket-level "purge candidates" surface.** Drift's `unreachable[]` with `status: "missing"` (Phase 39 D-01) already carries `last_seen` and a recovery pointer. A future enrichment could pre-compute "candidates for `purge_devices(filter_type='last_seen_older_than_days', value=X)`" and surface them as a structured payload the agent can pipe directly into the new tool. → **v1.7.2 / v1.8** as drift-UX-polish, depends on real-world drift signal volume.
- **Auto-purge mode.** A scheduled/triggered "every Monday, purge anything stale > 30 days" workflow. Conflicts with the milestone-locked "alert, not silent acceptance" stance for drift but could legitimately apply to clearly-failed rows (`status='error'` older than N days). → **v1.8** as a scheduled-jobs phase candidate.
- **`remove_device` cascade to keyring binding metadata** (NOT the keyring entry itself — the binding pointer in `ssh_credential_id` / `proxmox_credential_id`). Phase 44 D-06c cascades only `discovery_history`. The credential-binding metadata is row-level on `devices` (and dies with the row, by definition). If a future schema introduces a separate binding table (e.g., for many-to-many credential-host bindings v1.7.1 might consider), the cascade scope expands. → **v1.7.1 LIFE-* if the lifecycle hooks introduce a binding table.**
- **FK CASCADE on `discovery_history.device_id`.** Manual two-step DELETE (D-06c) reuses the existing pattern. A future schema migration could add `ON DELETE CASCADE` to the FK definition, eliminating the manual step. Mechanical change; deferred because Phase 44 is non-schema-changing by design (avoids migration risk in a CRUD-completion phase). → **v1.8 candidate.**
- **`purge_devices(filter_type='status', value='error')` matching zombie hostnames.** D-08 deliberately keeps the bare `status` filter narrow (only `status='error'`). If users assume the bare filter is a drop-in for `purge_failed_discoveries` and miss the zombie rows, consider either renaming the alias or expanding the bare filter. → **v1.8 candidate** if the discrepancy causes confusion.
- **Tool-description contrast block as a shared constant.** D-09 mandates verbatim copy-paste across three tool descriptions. A future refactor could extract the contrast sentence into a module-level constant and concatenate at registration time, ensuring the three descriptions never drift out of sync. → **v1.8 candidate** as schema-construction-helper polish.
- **Per-VM `remove_device` semantics.** Phase 44's `remove_device` operates on host-level sitemap rows. Per-VM rows (when v1.7.1 lifecycle hooks add them) might want a separate `remove_vm` tool with cascade to host-row VM lists. → **v1.7.1 LIFE-* territory.**
- **Confirm-token / two-call confirmation flow.** Some MCP clients prefer "call A returns a token; call B with the token actually deletes" for destructive ops. Phase 44 sticks with `dry_run` + tool annotations (`destructive_hint`) which is the existing convention across the codebase. → **v1.8 candidate** if MCP clients add native confirm-token plumbing.
- **Bulk `remove_device` (multiple device_ids in one call).** Phase 44 ships single-row `remove_device`; bulk is `purge_devices`. If a use case emerges for "delete these 5 specific device_ids" without a filter expression, add `remove_devices` (plural, list of ids). → **v1.8 candidate.**

</deferred>

---

*Phase: 44-sitemap-crud-completion*
*Context gathered: 2026-05-02*
