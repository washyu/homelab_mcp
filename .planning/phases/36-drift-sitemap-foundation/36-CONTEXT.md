# Phase 36: Drift ↔ Sitemap Foundation - Context

**Gathered:** 2026-04-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the sitemap the single source of truth for drift detection. The parallel `drift_baselines` SQLite table is dropped on both adapters; `scan_infrastructure_drift` iterates sitemap rows directly and resolves Proxmox API credentials via `resolve_proxmox_credentials` (Phase 34 D-09). After Phase 36, no production code path reads from a parallel baseline data layer — the only `drift_baselines` reference that remains is the one-time `DROP TABLE` migration step.

Scope anchor: ROADMAP.md §Phase 36 + REQUIREMENTS.md §DRFT-11, DRFT-12, DRFT-21.

**This phase delivers exactly three requirements** (DRFT-11, DRFT-12, DRFT-21) plus the SC-4 AST meta-test guarding the architectural decision. Output shape work, four-bucket transparency, and unknown/missing/changed classification are explicitly Phase 37 / Phase 39 territory and stay out of this phase.

Out of this phase:
- Four-bucket output shape, consistent shape across filter scopes (`node=*`, `vm_type=qemu/lxc`), sitemap-CRUD-tool error pointers — Phase 37 (DRFT-13/14/15/16). The one minor leak from this principle is D-03 (precondition removal), which is necessary to satisfy DRFT-12's "successful scan" success criterion.
- Sitemap fingerprint schema (kernel version, package fingerprint, capability probes) — Phase 38 (DRFT-20).
- Unknown / missing / changed detection — Phase 39 (DRFT-17/18/19).
- Proxmox VM lifecycle polish (Bug I, Bug G) — Phase 40 (POL-01/02/03).
- Lifecycle hooks (`create_proxmox_vm` / `delete_proxmox_vm` / etc. updating sitemap on success) — v1.7.1 LIFE-01..04.
- Sitemap tags / role-aware drift / role profiles — v1.7.2 TAGS-* + ROLE-*.
- Reconciling pre-existing rows in `drift_baselines` table on upgrade — DRFT-21 explicitly drops without auto-migration; users with active baseline rows lose them and re-establish via discovery.

</domain>

<decisions>
## Implementation Decisions

### scan_drift Interim Behavior (DRFT-11 / DRFT-12)

- **D-01 (2-bucket interim probe):** After Phase 36, `scan_drift` iterates Proxmox-host candidate rows in the sitemap, resolves each through `resolve_proxmox_credentials`, and probes `GET /cluster/status` per resolved host. Each row classifies into one of two buckets:
  - `probed-OK` — credential resolved AND `/cluster/status` returned a parseable list (HTTP 200, JSON list-of-dicts).
  - `unreachable` — credential resolved but probe raised `aiohttp.ClientError` / `asyncio.TimeoutError`, OR resolve_proxmox_credentials raised `CredentialNotFoundError` and the row was a candidate at all (see D-10).
  No detection runs in Phase 36 — no `unknown` (Phase 39 DRFT-17), no `changed` (Phase 39 DRFT-19), no `missing` (Phase 39 DRFT-18). 4-bucket transparency is Phase 37's DRFT-14.
- **D-02 (per-row record shape, "mid"):** Each entry in the response array carries:
  ```
  {
    "hostname": str,
    "connection_ip": str,
    "scope": "node" | "cluster",
    "cluster_name": str | None,
    "status": "probed-ok" | "unreachable",
    "error": str | None,
    "scan_timestamp": str  # ISO timestamp; same value on every entry from one scan
  }
  ```
  `scope` and `cluster_name` come directly from the `resolve_proxmox_credentials` return tuple (Phase 34 D-09: `tuple[str, Literal["node", "cluster"], str | None]`). `error` is populated only on `unreachable`; carries a sanitized message via `error_handling.sanitize_error()`. Top-level response = `{status: "success", scan_timestamp, scanned: N, probed_ok: [...], unreachable: [...]}`.
- **D-03 (remove precondition error):** Delete the `if result.get("summary", {}).get("baselines_available", 0) == 0:` early-return in `tool_handlers/drift_handlers.py` `handle_scan_infrastructure_drift`. Empty sitemap (zero candidate rows) returns a successful empty-result response: `{status: "success", scan_timestamp, scanned: 0, probed_ok: [], unreachable: []}`. Aligns with Phase 37's DRFT-13 ("empty match returns an empty result, never a scope error") even though the full DRFT-13 work lands in Phase 37 — necessary leak because DRFT-12 SC-2 requires "successful scan that resolves credentials" with no env vars set, which conflicts with the current "0 baselines = error" precondition.
- **D-04 (filter params inert passthrough):** `scan_infrastructure_drift` MCP tool schema retains `node` (str, optional) and `vm_type` ("qemu"|"lxc"|"all", default "all"). Both are passed to `scan_drift` as before; `scan_drift` accepts them in its signature for back-compat but **does not act on them** in Phase 36 — filter semantics stabilize in Phase 37 (DRFT-13). Tool schema description gains a one-line note: `"Filter semantics under Phase 37 redesign — node/vm_type currently inert"`. This avoids a tool-surface breaking change and lets MCP clients keep their wiring.

### `drift_baselines` Table Removal (DRFT-21)

- **D-05 (one-time migration drop, both adapters):** `migration.py` gains a new step in `run_sqlite_migrations` and `run_postgres_migrations` that drops `drift_baselines`. Same idempotent shape as Phase 33 D-01 (`DROP TABLE IF EXISTS ssh_credentials`) and Phase 35 D-02 (zombie dedup):
  - SQLite: `SELECT name FROM sqlite_master WHERE type='table' AND name='drift_baselines'` → if found, `DROP INDEX IF EXISTS idx_drift_baselines_node_vmid` + `DROP TABLE drift_baselines`.
  - Postgres: `SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'drift_baselines')` → if found, `DROP INDEX IF EXISTS idx_drift_baselines_node_vmid` + `DROP TABLE drift_baselines`.
  Both run on every server start; idempotent (no-op on the second invocation and on fresh installs).
- **D-06 (remove init_schema creation):** Delete the `CREATE TABLE drift_baselines` block from `database.py:205-221` (SQLite `init_schema`). Postgres `init_schema` (`database.py:595-665`) does not create the table — no removal needed there, only the safety drop in the migration step. Also delete the `CREATE TABLE drift_baselines` block from `migration.py:224-247` (the auto-create-on-startup path) and the `applied_migrations.append("create_drift_baselines_table")` line.
- **D-07 (remove adapter methods):** Remove the four database-adapter methods entirely:
  - `DatabaseAdapter.upsert_drift_baseline` (ABC, `database.py:69-79`)
  - `DatabaseAdapter.get_drift_baseline` (ABC, `database.py:81-89`)
  - `DatabaseAdapter.get_all_drift_baselines` (ABC, `database.py:91-94`)
  - `SQLiteAdapter.upsert_drift_baseline` (`database.py:451-481`)
  - `SQLiteAdapter.get_drift_baseline` (`database.py:482-507`)
  - `SQLiteAdapter.get_all_drift_baselines` (`database.py:509-527`)
  - `PostgreSQLAdapter.upsert_drift_baseline` (`database.py:917-936`)
  - `PostgreSQLAdapter.get_drift_baseline` (`database.py:928`)
  - `PostgreSQLAdapter.get_all_drift_baselines` (`database.py:937`)
  After Phase 36 these methods do not exist on any adapter. Tests covering them are deleted (D-16).
- **D-08 (migration banner):** When the drop step finds and removes the table, emit a `stderr` notice mirroring the Phase 33 `ssh_credentials` banner shape:
  ```
  Dropped legacy drift_baselines table (v1.7: sitemap is now the single source of truth for drift)
  NOTE: Pre-existing baseline rows are not preserved (per DRFT-21 architectural decision).
        Drift now reports against the live sitemap; no manual baseline registration is needed.
  ```
  Row count is *not* logged — counting requires a `SELECT COUNT(*)` before the DROP that complicates idempotency. Banner appears only on the run that performed the drop; second run is silent.

### Credential Resolution Wiring (DRFT-12)

- **D-09 (scan_drift uses resolve_proxmox_credentials per row):** For each candidate sitemap row, `scan_drift` calls `get_proxmox_client(host=row["hostname"], session=session)`. `get_proxmox_client` is already `async def` (Phase 34) and already calls `resolve_proxmox_credentials(host)` internally when `host` is set and no explicit auth is provided (`proxmox_api.py:370-378`). No new resolver call is needed in `scan_drift` — passing the sitemap row's `hostname` is sufficient. The probe is `await client.get("/cluster/status")`.
- **D-09a (probe error classification):** Wrap the per-row probe in `try/except (aiohttp.ClientError, ValueError, asyncio.TimeoutError, CredentialNotFoundError)` and classify exception → `unreachable` bucket. The exception message goes through `error_handling.sanitize_error()` before landing in the row's `error` field (Phase 33/34 sanitization convention; never leak raw URLs or internal API paths — also reinforces POL-01's spirit even though POL-01 itself is Phase 40).
- **D-09b (no PROXMOX_HOST env-var fallback in scan_drift):** `scan_drift` MUST NOT call `os.getenv("PROXMOX_HOST")` directly, and MUST NOT pass any `host=` derived from env vars. The only `host` source is the sitemap row's `hostname` field. This is the codification of DRFT-15's "no `PROXMOX_HOST` mention" rule on the scan path; the wider rule (every drift-family error message points to sitemap CRUD tools, never `PROXMOX_HOST`) is fully Phase 37 (DRFT-15) but the success path is Phase 36's responsibility.

### Proxmox-Host Identification in Sitemap (Claude's Discretion, with guidance)

- **D-10 (recommended approach):** `scan_drift` iterates **every** non-degenerate row from `db_adapter.get_all_devices()`. For each row, attempt `resolve_proxmox_credentials(hostname)` via the implicit call inside `get_proxmox_client`. Rows that raise `CredentialNotFoundError` are silently skipped — that row is not a registered Proxmox host. Rows that resolve are probed; result lands in `probed-OK` or `unreachable` per D-01.
  - Rationale: cluster entries don't have a usable hostname (Phase 34 D-02: `hostname=""`), so iterating the keyring registry doesn't give a clean lookup direction. Per-row resolve handles per-node and cluster entries uniformly through the existing tier-walk in `proxmox_api.py:194-329`.
  - Phase 39 will introduce a richer "unknown infrastructure" bucket that needs to distinguish "row is not Proxmox" from "row is Proxmox but cred missing". Phase 36 doesn't need that distinction — both fall out of the probe set.
- **D-10a (degenerate rows excluded):** Sitemap rows with `status == "error"` or with `hostname` in `("", "unknown", None)` are excluded from the iteration upfront. These are Phase-35-pre-existing zombie rows (the degenerate-fallback branch from Phase 35 D-01a) and would never resolve to a real Proxmox host. Skip cleanly at the top of the loop, before any cred-resolution attempt.
- **D-10b (planner override):** If during planning the planner finds that calling `resolve_proxmox_credentials` on every sitemap row produces unacceptable noise (e.g., thousands of `DEBUG: proxmox resolve host=X tier=node MISS` log lines), the planner may add a fast-path filter — e.g., "only probe rows whose `hostname` matches a per-node `proxmox` registry entry OR whose probe response from a cluster entry succeeded once before". Optional optimization; default is the simpler per-row resolve.

### `update_baseline_after_mutation` Cleanup (Claude's Discretion, with guidance)

- **D-11 (recommended: remove entirely):** Delete the function `update_baseline_after_mutation` from `drift_detection.py:228-279` and remove its three callsites in `tool_handlers/proxmox_handlers.py`:
  - `handle_create_proxmox_lxc` (lines 118, 143-152)
  - `handle_create_proxmox_vm` (lines 158, 182-191)
  - `handle_clone_proxmox_vm` (lines 197, 214-223)
  Each removal includes the `from ..drift_detection import update_baseline_after_mutation` deferred import and the surrounding `if result.get("status") == "success": try/except` block. Lifecycle hooks (sitemap-update on VM create/destroy) land in v1.7.1 LIFE-01..04 — replacing these callsites with sitemap-update stubs in Phase 36 prejudges that work and creates a half-implementation.
- **D-11a (keep `_diff_vm_config`?):** The helper `_diff_vm_config` at `drift_detection.py:19-54` is currently used only inside `scan_drift`. Phase 36's 2-bucket interim doesn't compare configs, so the helper has zero callers after the refactor. Recommended: delete it. Phase 39 will add config-change detection (DRFT-19) and may reintroduce a similar helper, but the new one will compare sitemap-stored fingerprints against live probes — different shape, different fields — so reusing the dead helper is unlikely.
- **D-11b (test deletion):** Tests in `tests/test_drift_detection.py` covering `update_baseline_after_mutation` (the `TestUpdateBaselineAfterMutation` class, ~lines 219-240) are deleted alongside the function. Phase 36 SUMMARY notes the test class deletion explicitly.

### Tests / Regression Discipline (footgun-removal class)

Phase 36 dissolves Bug J (parallel data layer not integrated with sitemap) — footgun-removal per `memory/feedback_regression_test_scope.md`. AST meta-tests apply (Phase 32 / 33 / 35 D-14 pattern). New-feature AST exclusion (Phase 34 D-13..D-16) does NOT apply.

- **D-12 (AST meta-test, SC-4 codification):** New test file (planner picks name; recommended `tests/test_drift_baselines_removed.py`). Scan every `*.py` file under `src/homelab_mcp/` and assert that the strings `drift_baselines`, `get_all_drift_baselines`, `upsert_drift_baseline`, and `get_drift_baseline` appear ONLY in `src/homelab_mcp/migration.py`. Any other module containing any of those strings = test fail. The `migration.py` allowance lets the `DROP TABLE` cleanup step survive while guarding every other call site against re-introduction. Mirrors Phase 33 D-15 / Phase 33.1 D-09 / Phase 35 D-14 mechanics.
- **D-13 (AST meta-test, scan-path specific):** Same test file. Scan `src/homelab_mcp/drift_detection.py` and assert NO substring match for `drift_baseline` (singular or plural), `db_adapter.get_all_drift_baselines`, or `db_adapter.execute_query` with a literal containing `drift_baselines`. Independent guard against drift_detection.py reading the parallel layer via any path. Pinning `drift_detection.py` specifically (not just "outside migration.py") is belt-and-braces — the SC-4 wording is "any future code path on the drift-scan call chain" and `drift_detection.py` is the only code on that chain.
- **D-14 (functional test, scan_drift 2-bucket):** New test in `tests/test_drift_detection.py` (rewriting the existing class). Mock `db_adapter.get_all_devices()` to return 3 rows: `pve1` (Proxmox node), `truenas1` (NAS, no Proxmox cred), `pi-lab` (Proxmox host but unreachable). Mock `resolve_proxmox_credentials`:
  - `pve1` → `("token@node", "node", None)`
  - `truenas1` → raises `CredentialNotFoundError`
  - `pi-lab` → `("token@cluster", "cluster", "homelab-prod")`
  Mock `ProxmoxAPIClient.get("/cluster/status")`:
  - `pve1` → list payload (success)
  - `pi-lab` → raises `aiohttp.ClientError` (unreachable)
  Assert response shape per D-02; assert `probed_ok` contains `pve1`; `unreachable` contains `pi-lab`; `truenas1` is in neither (silently skipped per D-10).
- **D-15 (functional test, migration idempotency):** Two cases per adapter:
  - Fresh DB (no `drift_baselines` table): migration runs cleanly, no banner, no error. Second run: same.
  - Pre-populated DB (has `drift_baselines` with 3 baseline rows): first run drops the table + emits banner. Second run finds no table, no banner, no error.
  SQLite test uses `:memory:` adapter; Postgres test guarded by `pytest.mark.integration` (uses Docker per existing pattern in `tests/integration/`).
- **D-16 (test rewrite scope):** `tests/test_drift_detection.py` and `tests/test_drift_wiring.py` are heavily mocked against `get_all_drift_baselines`. `tests/test_database.py` has the `TestDriftBaselines` class covering all four adapter methods (`upsert_drift_baseline`, `get_drift_baseline`, `get_all_drift_baselines`, `test_get_drift_baseline_unknown_vmid`, `test_get_all_drift_baselines`).
  - `tests/test_database.py` `TestDriftBaselines` class — **delete entirely** (D-07 removes the methods).
  - `tests/test_drift_detection.py` — **rewrite** against the 2-bucket sitemap-iteration model; the existing test classes are obsolete. `TestUpdateBaselineAfterMutation` deletes per D-11b.
  - `tests/test_drift_wiring.py` — **rewrite/delete** as needed; the wiring it tests (handler → drift_detection → db_adapter.get_all_drift_baselines) no longer exists.
  - `tests/test_drift_resource.py` — keep but verify the cached payload shape change (D-18) doesn't break the test; rewrite the fixtures if so.

### Drift Resource (homelab://drift/latest)

- **D-18 (resource cache pass-through):** `set_latest_drift_report(result)` in `tool_handlers/drift_handlers.py:39` continues to cache whatever `scan_drift` returned. After Phase 36 the cached payload is the 2-bucket interim shape per D-01/D-02. The resource description in `resource_readers.py:131` may need a one-line tweak ("structured 2-bucket scan report — shape stabilizes in Phase 37") but the resource URL and reader are unchanged. Phase 37 (DRFT-13/14) revisits the resource description when the canonical shape lands.

### MCP Tool Surface (DRFT-16)

- **D-17 (no new MCP tools):** Phase 36 introduces zero new MCP tools. Bug C (no register/list/delete drift_baseline tools) is dissolved architecturally — the existing sitemap CRUD tools (`discover_and_map`, `get_network_sitemap`, `purge_failed_discoveries`, `decommission_device`) are the baseline-lifecycle tools. Drift docs and any error message pointing at "where do baselines come from?" reference the sitemap CRUD tools. The `scan_infrastructure_drift` tool schema gets the inert-passthrough description tweak per D-04 but no schema property changes.

### Documentation

- **D-19 (docs sweep, narrow):** `docs/configuration.md`, `docs/setup-guide.md`, and `docs/tool-reference.md` reference `PROXMOX_HOST` in several places. Phase 36 does NOT do a full PROXMOX_HOST sweep — that's Phase 37 (DRFT-15) on the error-message side and likely a docs-side cleanup follow-up. The narrow scope here:
  - `docs/tool-reference.md` `scan_infrastructure_drift` entry (find by tool name) — update description to remove "register a drift baseline" language; mention "iterates the sitemap" instead. No PROXMOX_HOST text exists on the drift tool today.
  - Any `register_drift_baseline` / `list_drift_baselines` / `delete_drift_baseline` mention in `docs/` → grep and remove. (None expected, but verify — Bug C says these tools were assumed but never built; docs may have been written speculatively.)
  Wider PROXMOX_HOST sweep (configuration.md / setup-guide.md mentions of `PROXMOX_HOST` for general Proxmox setup) is out of scope — the env var still works as a credential-fallback for `get_proxmox_client` callers that pass an explicit `host=`, so the docs are not factually wrong. Phase 37 will revisit when DRFT-15 codifies the error-message rule.

### Claude's Discretion

- Exact name and module of the AST meta-test file (D-12/D-13) — `tests/test_drift_baselines_removed.py` recommended; `tests/test_no_drift_baselines.py` or extending `tests/test_no_drift_module_reads.py` if a similar file exists are equally fine.
- Exact `stderr` banner phrasing for D-08 — the recommended text is illustrative, not mandatory.
- Whether `scan_drift` returns `probed_ok` and `unreachable` as top-level keys or nests them under a `coverage: {...}` sub-dict. Top-level recommended (Phase 37 will likely promote these to `buckets: {probed_ok, unreachable, unknown, missing}` when DRFT-14 lands).
- Whether the per-row `error` field on `unreachable` rows includes the exception class name (`"aiohttp.ClientError: Cannot connect to host pve1.home"`) or just the message (`"Cannot connect to host pve1.home"`). Sanitized message recommended (no class-name leak).
- Whether `_diff_vm_config` (D-11a) is deleted in Phase 36 or kept dormant. Deletion recommended; keeping creates dead code that Phase 39's AST meta-test for changed-detection might flag.
- Whether the migration banner (D-08) emits row count on the drop. Recommended NOT to count — adds a `SELECT COUNT(*)` before the DROP that's pure UX and complicates the idempotency proof.
- Whether the planner adds an optional fast-path filter for D-10 (only probe sitemap rows whose hostname appears in a known proxmox registry). Default per-row resolve recommended; optimization deferred to Phase 39 if log noise is an issue.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 36 Scope

- `.planning/ROADMAP.md` §Phase 36 — Phase goal + 4 Success Criteria (SC-1..SC-4); the scope anchor.
- `.planning/REQUIREMENTS.md` §Active Requirements — DRFT-11 (sitemap-as-source-of-truth), DRFT-12 (resolve_proxmox_credentials wiring), DRFT-21 (drop drift_baselines table); §Coverage Map (Bug J→DRFT-11+DRFT-21 root-cause dissolve).
- `.planning/PROJECT.md` §Constraints + §Key Decisions — keyring-only credential constraints, async-throughout pattern for SSH/Proxmox call chains, MCP tool-surface conventions (handlers stay thin-delegation wrappers).
- `.planning/STATE.md` §v1.7 Phase Summary + §Phase Ordering Constraints — confirms Phase 36 runs first in isolation; DRFT-21 is one-way.

### Prior Phase Decisions (locked, inherited)

- `.planning/milestones/v1.6-phases/33-keyring-single-source-of-truth/33-CONTEXT.md` §Regression Guards — D-15 AST meta-test pattern (scan source for forbidden strings); D-01 one-time `DROP TABLE IF EXISTS` startup migration pattern (shape directly reused for D-05).
- `.planning/milestones/v1.6-phases/33.1-ssh-tool-family-keyring-uniformity-drop-hardcoded-mcp-admin-/33.1-CONTEXT.md` §D-09 — AST schema-scan meta-test pattern (test file structure inspires D-12).
- `.planning/milestones/v1.6-phases/34-cluster-scoped-proxmox-credentials/34-CONTEXT.md` §D-09, §D-10, §D-12 — `resolve_proxmox_credentials` signature (returns `tuple[str, Literal["node", "cluster"], str | None]`), the per-node→cluster→error tier order, and the `registry_entries[0]` shortcut removal that Phase 34 already shipped (relevant context: Phase 36 inherits the post-shortcut state).
- `.planning/milestones/v1.6-phases/35-sitemap-discovery-reliability-fix-discover-and-map-field-los/35-CONTEXT.md` §D-01 (hostname-as-natural-key for sitemap rows), §D-09 (canonical field-name alignment principle), §D-14/D-15/D-16 (AST meta-test idiom), §D-02 (one-time idempotent migration in `migration.py`).

### Memory / User Feedback

- `~/.claude/projects/C--Users-washy-projects-mcp-python-server/memory/feedback_regression_test_scope.md` — AST meta-tests guard known footguns (Phase 36 qualifies because it dissolves Bug J); new-feature phases use functional + unit tests only. Drives D-12, D-13.
- `~/.claude/projects/C--Users-washy-projects-mcp-python-server/memory/project_credential_architecture.md` — Keyring is source of truth; missing entry = hard error with CLI pointer. Drives D-09b (no PROXMOX_HOST env-var fallback) and the spirit of D-08 (clean error messages).

### Source Files Affected

- `src/homelab_mcp/drift_detection.py` (entire file rewrite)
  - `scan_drift()` (lines 57-225) — replace baseline-iteration with sitemap-iteration per D-01/D-02/D-09; remove config_drift/state_drift dual-array structure in favor of the 2-bucket shape.
  - `_diff_vm_config()` (lines 19-54) — delete per D-11a.
  - `update_baseline_after_mutation()` (lines 228-279) — delete per D-11.
  - `CONFIG_DRIFT_FIELDS` constant (line 16) — delete; no longer used.
- `src/homelab_mcp/database.py`
  - `DatabaseAdapter.upsert_drift_baseline` ABC (lines 69-79) — delete per D-07.
  - `DatabaseAdapter.get_drift_baseline` ABC (lines 81-89) — delete per D-07.
  - `DatabaseAdapter.get_all_drift_baselines` ABC (lines 91-94) — delete per D-07.
  - `SQLiteAdapter.init_schema` `CREATE TABLE drift_baselines` block (lines 205-221) — delete per D-06.
  - `SQLiteAdapter.upsert_drift_baseline` (lines 451-481) — delete per D-07.
  - `SQLiteAdapter.get_drift_baseline` (lines 482-507) — delete per D-07.
  - `SQLiteAdapter.get_all_drift_baselines` (lines 509-527) — delete per D-07.
  - `PostgreSQLAdapter.upsert_drift_baseline` (lines 917-936) — delete per D-07.
  - `PostgreSQLAdapter.get_drift_baseline` (~line 928) — delete per D-07.
  - `PostgreSQLAdapter.get_all_drift_baselines` (line 937) — delete per D-07.
- `src/homelab_mcp/migration.py`
  - SQLite `drift_baselines` auto-create block (lines 224-247) — delete per D-06; replace with the DROP step per D-05.
  - Postgres migration — add the `DROP TABLE IF EXISTS drift_baselines` step per D-05; mirrors the SQLite addition.
  - `applied_migrations.append("create_drift_baselines_table")` line — delete; replace with `applied_migrations.append("drop_drift_baselines_table")` on the drop branch.
- `src/homelab_mcp/tool_handlers/drift_handlers.py`
  - `handle_scan_infrastructure_drift` (entire body) — remove the precondition early-return per D-03; pass-through to the new `scan_drift` signature.
- `src/homelab_mcp/tool_handlers/proxmox_handlers.py`
  - `handle_create_proxmox_lxc` (lines 116-153) — remove `update_baseline_after_mutation` import + call site per D-11.
  - `handle_create_proxmox_vm` (lines 156-192) — remove import + call site per D-11.
  - `handle_clone_proxmox_vm` (lines 195-224) — remove import + call site per D-11.
- `src/homelab_mcp/tool_schemas/drift_tools_schema.py`
  - `DRIFT_TOOLS["scan_infrastructure_drift"]` (entire) — update `description` per D-04 (note about filter inertness in Phase 36); leave `inputSchema` properties intact (`node`, `vm_type` stay).
- `src/homelab_mcp/resource_readers.py`
  - drift resource description (~line 131) — optional one-line tweak per D-18.
- `docs/tool-reference.md`
  - `scan_infrastructure_drift` entry — update description per D-19.
- Test files (rewrite scope per D-16):
  - `tests/test_drift_detection.py` — full rewrite for 2-bucket shape; delete `TestUpdateBaselineAfterMutation`.
  - `tests/test_drift_wiring.py` — full rewrite or delete.
  - `tests/test_database.py` `TestDriftBaselines` class (~line 361) — delete.
  - `tests/test_drift_resource.py` — verify shape; rewrite fixtures if needed.
  - New: `tests/test_drift_baselines_removed.py` (or planner's pick) — D-12/D-13 AST meta-tests.

### External / Proxmox API

- Proxmox VE API: `GET /cluster/status` — already used by Phase 34's `resolve_proxmox_credentials` to disambiguate cluster entries. Phase 36 reuses the same endpoint as the per-host probe; standalone Proxmox nodes return a list with no `type=cluster` row but the call still succeeds (HTTP 200 + parseable list), which is sufficient for the `probed-OK` classification.

### Architecture / Patterns Reference

- `error_handling.py` `sanitize_error()` (line referenced via existing imports) — used per D-09a to scrub probe exception messages before they land in the per-row `error` field.
- `proxmox_api.py:194-329` `resolve_proxmox_credentials()` — per Phase 34 D-09; the resolver Phase 36 wires `scan_drift` into.
- `proxmox_api.py:332-396` `get_proxmox_client()` — already async (Phase 34); already calls `resolve_proxmox_credentials` when host is set and no explicit auth (lines 370-378). Phase 36 just passes `host=row["hostname"]` and lets the existing machinery resolve.
- `tool_handlers/proxmox_handlers.py` deferred-import pattern (`from ..drift_detection import update_baseline_after_mutation` inside each handler body) — the imports come out cleanly per D-11.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `resolve_proxmox_credentials(host, session)` already exists (Phase 34 D-09); returns the resolver telemetry (`scope`, `cluster_name`) that D-02's per-row record needs verbatim. No new resolver logic required.
- `get_proxmox_client(host=..., session=...)` already calls the resolver internally when host is set and no explicit auth (`proxmox_api.py:370-378`). `scan_drift` doesn't need to call the resolver directly — passing `host=row["hostname"]` is sufficient and gets the resolver telemetry surfaced via `get_proxmox_client`'s logging (proves SC-2 in production logs).
- `error_handling.sanitize_error()` is the established convention for scrubbing exception messages before they hit user-visible payloads (Phase 33/34). D-09a reuses unchanged.
- `migration.py` already hosts the Phase 33 `DROP TABLE IF EXISTS ssh_credentials` and Phase 35 zombie-dedup steps. D-05's drop step lands in the same module using the identical `IF EXISTS` + idempotent-startup shape.
- `db_adapter.get_all_devices()` (already implemented on both adapters per Phase 35) is the sitemap iteration entry point for D-09. No new adapter method needed.
- AST meta-test infrastructure: Phase 32 introduced `tests/test_no_*.py` files; Phase 33/33.1/35 extended the pattern. D-12/D-13 add another file in the same idiom — `pathlib.Path` walks `src/homelab_mcp/`, reads each `.py`, asserts forbidden strings absent.

### Established Patterns

- **One-time idempotent startup migration** with `IF EXISTS` guard — D-05 mirrors Phase 33 D-01 / Phase 35 D-02 verbatim.
- **AST meta-test as regression guard** for footgun-removal phases — D-12/D-13 follow Phase 32 / 33 D-15 / 33.1 D-09 / 35 D-14 mechanics. New-feature phases (Phase 34) explicitly skip this; Phase 36 is bug-fix class.
- **Two-tier resolver, no third tier** — Phase 34 locked the resolver shape; Phase 36 doesn't extend it, only consumes it.
- **`hostname` as natural key** — Phase 35 D-01 made hostname the upsert key for sitemap rows. Phase 36's `scan_drift` iterates `get_all_devices()` which returns rows keyed by hostname.
- **Thin-delegation MCP tool handlers** — `handle_scan_infrastructure_drift` is a passthrough wrapper; D-03 simplifies it further but doesn't change its shape.
- **No new MCP tools for adjacent CRUD** — Phase 33 D-06 (CLI-only credential CRUD) and Phase 36 D-17 (no new drift baseline tools) follow the same restraint principle: dissolve the bug architecturally, don't ship more surface.

### Integration Points

- `db_adapter.get_all_devices()` is the single read funnel for sitemap rows. Every code path that needs to "iterate the sitemap" flows through it. D-09's iteration uses this entry point directly.
- `get_proxmox_client(host, session)` is the single funnel for credential resolution + Proxmox API client construction. D-09's per-row probe uses it; the resolver telemetry surfaces via the function's internal logging.
- `scan_drift` is the only function that reads `drift_baselines` today (per `grep -rn "get_all_drift_baselines" src/`). Replacing its data source replaces 100% of production reads — D-12's AST meta-test enforces this on the source side.
- `update_baseline_after_mutation` is the only function that writes `drift_baselines` today (per `grep -rn "upsert_drift_baseline" src/`). Removing it (D-11) eliminates 100% of production writes.
- `migration.py` is the only module that retains `drift_baselines` references after the cleanup — the migration step needs the table name as a string for the `DROP TABLE IF EXISTS` statement. D-12 codifies this exception.

</code_context>

<specifics>
## Specific Ideas

- **Phase 36 is foundation-only.** User explicitly chose the 2-bucket interim shape over both the minimal stub (which doesn't satisfy SC-2) and the full 4-bucket shape (which bleeds Phase 37 work into Phase 36). The choice locks Phase 36 to: data-source replacement + cred-resolution wiring + table drop + minimal probe to prove the success path. No detection logic, no shape work beyond what SC-2 requires.
- **Resolver telemetry in the per-row record.** User picked the "mid" shape (D-02) that includes `scope` and `cluster_name` from the Phase 34 resolver tuple. This means production logs + tool output both show how each Proxmox host's credential was resolved (per-node vs cluster) — direct verification that DRFT-12 is wired. Useful for the SC-2 verification AND for Phase 39 detection later (knowing which scope a host resolved through is downstream signal).
- **Empty sitemap is success, not error.** User chose to remove the precondition entirely (D-03) over rewording it. Aligns with the architectural principle that drift = (sitemap state vs live state); zero sitemap rows = zero coverage, not an error condition. The full DRFT-13 work (consistent shape across filter scopes) is Phase 37, but D-03's piece of it lands here because DRFT-12 SC-2 demands "successful scan with no env vars" and the current precondition fires on that path.
- **Inert filter passthrough.** User chose to keep the `node` / `vm_type` schema params as documented inert passthroughs over either dropping them or reinterpreting them. Avoids tool-surface breaking change for any wired MCP client; defers the filter-semantics decision to Phase 37 where DRFT-13 explicitly addresses it. Schema description tweak (one line) is the only schema change in Phase 36.
- **Per-row resolve over registry-walk** (D-10, Claude's Discretion): the recommended approach iterates every sitemap row and lets `CredentialNotFoundError` filter the non-Proxmox set. Asymmetric registry walk (cluster entries have `hostname=""`) makes the alternative direction awkward. Phase 39's "unknown infrastructure" bucket can refine this if needed.
- **Function deletion over stubbing** (D-11, Claude's Discretion): user implicitly accepted the deferred-areas defaults. `update_baseline_after_mutation` removal is total — no half-implementation, no "for v1.7.1 to fill in" stubs. v1.7.1 LIFE-01..04 owns lifecycle hooks cleanly and starts from zero.
- **Migration banner mirrors Phase 33** (D-08, Claude's Discretion): same shape as the `ssh_credentials` drop banner. No row count to keep idempotency simple.

</specifics>

<deferred>
## Deferred Ideas

- **Four-bucket output shape and consistent shape across filter scopes** — Phase 37 (DRFT-13/14). Phase 36 lands a 2-bucket interim that Phase 37 expands.
- **`unknown` / `missing` / `changed` detection** — Phase 39 (DRFT-17/18/19). Phase 36 does no classification; Phase 37 sets up the shape; Phase 39 fills in the detection.
- **Sitemap fingerprint schema (kernel version, package fingerprint, capability probes)** — Phase 38 (DRFT-20). Phase 36's 2-bucket probe doesn't need any fingerprint comparison; Phase 39's `changed` detection will.
- **Lifecycle hooks (sitemap-update on VM create/destroy)** — v1.7.1 LIFE-01..04. Phase 36 removes `update_baseline_after_mutation` callsites without replacement; v1.7.1 starts from a clean slate.
- **Sitemap tags / role-aware drift / role profiles** — v1.7.2 TAGS-* + ROLE-*. Phase 36 doesn't tag sitemap rows by role; per-row resolve handles Proxmox identification structurally.
- **PROXMOX_HOST sweep across `docs/configuration.md`, `docs/setup-guide.md`** — Phase 37 (DRFT-15) handles the error-message side; broader docs sweep can land in a docs phase or as part of v1.8 polish. Phase 36 only touches the `scan_infrastructure_drift` doc entry.
- **Auto-update sitemap when drift detected** — already declared out of scope at the milestone level (REQUIREMENTS.md §Out of Scope). Drift reports differences; user accepts via re-running `discover_and_map`.
- **Restoring `drift_baselines` rows from `discovery_history`** — DRFT-21 explicitly drops without auto-migration; pre-existing baseline rows are not preserved. No "best-effort migration to populate fingerprints from discovery_history" path.
- **Persistence of the per-host probe telemetry** — Phase 36 returns the 2-bucket shape live per scan; nothing is persisted. The resource cache (`homelab://drift/latest`) holds the latest scan result in-memory only (per existing v1.2 Phase 13 design). No new persistence in Phase 36.
- **Proxmox-host fast-path filter (D-10b)** — only probe rows whose hostname appears in a known proxmox registry entry. Optional optimization deferred unless log noise becomes an issue. Default per-row resolve is intentionally simple.
- **`node`/`vm_type` filter semantics rationalization** — Phase 37 (DRFT-13). Phase 36 keeps both as inert passthroughs.

</deferred>

---

*Phase: 36-drift-sitemap-foundation*
*Context gathered: 2026-04-25*
