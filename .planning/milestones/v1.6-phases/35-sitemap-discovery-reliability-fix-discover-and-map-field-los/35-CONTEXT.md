# Phase 35: Sitemap + Discovery Reliability - Context

**Gathered:** 2026-04-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Close four reliability gaps in the `discover_and_map` / `bulk_discover_and_map` / `analyze_network_topology` tool chain surfaced by Phase 33 live testing (2026-04-21):

1. **Field-loss in the sitemap row** — `ssh_discover_system` returns hardware info that never lands in the `devices` row: `cpu_cores`, `memory_free`/`memory_available`, `disk_filesystem`/`disk_size`/`disk_use_percent`/`disk_mount`, and the entire `usb_devices` / `pci_devices` / `block_devices` collections. The contract between `ssh_discover_system`'s output shape and `sitemap.parse_discovery_output`'s reader never matched.
2. **Zombie sitemap rows on IP change** — `store_device` matches on `(hostname, connection_ip)`; a DHCP lease change or NIC swap produces a second row for the same host. Accumulates over time.
3. **Tool hangs 4+ minutes** — `ssh_discover_system` fires ~10 sequential `conn.run()` shell commands with no per-command timeout. The outer `@ssh_connection_wrapper(timeout_seconds=30.0)` bounds the whole function, but `bulk_discover_and_map` iterates targets serially so N unreachable hosts stack: 8 × 30s ≈ 4 min.
4. **Topology analyzer crashes / misclassifies on null thresholds** — `analyze_network_topology` and `suggest_deployments` mix truthy-check guards, `cpu_cores or 0` coercions, and try/except blocks that catch `ValueError/AttributeError` but not `TypeError`. A device with `cpu_cores=None` gets classified as "low resource" (`None or 0 → 0 <= 2 → True`).

Scope anchor: ROADMAP.md §Phase 35 (no mapped REQ-ID; surfaced by Phase 33 live testing).

Out of this phase:
- Stale-row pruning (`last_seen > N days`) — its own decision on retention and destructiveness; deferred.
- IP-history column on `devices` — `discovery_history` already stores full JSON snapshots per discovery.
- A new `prune_sitemap_duplicates` MCP/CLI tool — the one-time migration handles the collapse idempotently.
- Re-shaping `discover_and_map`'s MCP tool schema — no tool-surface changes; handlers stay thin-delegation wrappers.
- Any credential/auth work — Phase 33 / 33.1 / 34 decisions stand.

</domain>

<decisions>
## Implementation Decisions

### Zombie Row Upsert Key

- **D-01:** `store_device` in both SQLite and Postgres adapters matches existing rows on `hostname` alone (not `hostname AND connection_ip`). When a known hostname is re-discovered with a different `connection_ip`, the existing row is `UPDATE`d in place and `connection_ip` is overwritten. Hostname becomes the natural key for a sitemap row.
- **D-01a (degenerate-hostname fallback):** When the discovered hostname is `""`, `"unknown"`, or `None` (ssh_discover failed to resolve the remote hostname), `store_device` falls back to the legacy `(hostname, connection_ip)` match. Prevents collapsing all error-rows into one poisoned bucket. The fallback branches only on the write path — reads via `get_all_devices()` are unchanged.
- **D-02 (zombie migration):** `migration.py` gains a one-time startup migration step that collapses existing duplicate rows. For each non-degenerate `hostname` with `>1` row in `devices`: keep the row with the greatest `last_seen`, merge **non-null** values from sibling rows into the kept row (field-by-field, non-null wins; ties resolved by `last_seen` desc), delete the siblings. Idempotent — second run finds no duplicates and is a no-op. Degenerate hostnames (`''`, `'unknown'`) are skipped so distinct error rows remain.
- **D-02a:** The migration runs in the same `migration.py` module that hosts Phase 33's `DROP TABLE IF EXISTS ssh_credentials` (D-01) — same "one-time startup step, idempotent, both adapters" pattern. Order: Phase 33's drop runs first (already shipped); Phase 35's dedup runs after, on the now-current schema.
- **D-03 (no IP-history column):** The `devices` table does not gain an `ip_history` column. Auditing "when did this host's IP change" uses `discovery_history`, which already stores the full `ssh_discover_system` JSON payload per discovery (including `connection_ip`). No schema migration for this concern.
- **D-04 (stale pruning deferred):** Not in this phase. Retention window, soft vs hard delete, and opt-in vs automatic are separate decisions. Deferred idea.

### Per-Subprocess SSH Timeout

- **D-05 (per-cmd default 10s):** Every `conn.run(...)` call inside `ssh_discover_system` (hostname, nproc, cpuinfo, free, df, ip, uptime, os-release, lsusb, lspci, lsblk) is wrapped with a 10-second per-command timeout. Implementation is planner's call — either a small helper (`_run_with_timeout(conn, cmd, timeout=10.0)`) that wraps `asyncio.wait_for(conn.run(cmd, check=False), timeout=10.0)`, or inline `asyncio.wait_for` calls. 10s is the ceiling for any single info-gathering shell command over SSH on a healthy homelab host.
- **D-06 (partial-success mode):** When a per-subprocess timeout fires, catch `TimeoutError` at the call site, leave the corresponding field `None`, and record the command name in an internal `timed_out_commands: list[str]` accumulator. Continue executing the remaining commands. The final `ssh_discover_system` JSON response gains two top-level keys when any timeout fires:
  - `"partial": true` — marker the caller (sitemap, topology analyzer) can branch on.
  - `"timed_out_commands": ["lsblk", "lspci", ...]` — list of skipped commands.
  When no timeouts fire, neither key is emitted (back-compat with existing callers). `status` stays `"success"` for partial results — timeouts on individual probes are not full-discovery failures.
- **D-07 (bulk parallelism):** `bulk_discover_and_store` switches from serial `for` loop to `asyncio.gather(*[_discover_one(t) for t in targets], return_exceptions=True)`, gated by `asyncio.Semaphore(10)` to cap concurrent SSH sessions. Each call is individually wrapped by `ssh_connection_wrapper` and now by the per-cmd timeouts inside `ssh_discover_system`. `return_exceptions=True` ensures a single-host failure does not abort the batch — exceptions are converted to the same `{"status": "error", ...}` shape the existing code produces.
- **D-07a (progress emission under parallelism):** `emit_progress` calls retain per-host granularity — each coroutine emits `"Discovering <hostname> (i/total)"` and `"Completed <hostname> (i/total)"` lines around its `discover_and_store` call. Ordering is interleaved rather than strictly sequential; the `i/total` counter increments by completion order, not by position in `targets`. Acceptable for the homelab UX.
- **D-08 (overall wrapper 120s):** `@ssh_connection_wrapper(timeout_seconds=...)` on `ssh_discover_system` bumps from `30.0` to `120.0`. Rationale: per-cmd 10s × ~10 commands = 100s worst-case healthy-but-slow discovery; 120s gives a 20s cushion for SSH handshake + sudo probe. The per-cmd timeout is now the primary guardrail; the outer wrapper becomes a safety net, not the primary control.

### Discovery Schema Reconciliation (Claude's Discretion, with guidance)

The field-loss bug is a straight contract mismatch between `ssh_discover_system`'s output shape (emits `cpu.count`, `memory.total`, `memory.used`, `disk.total`, `disk.used`, `disk.available`; collects `usb_devices`/`pci_devices`/`block_devices`) and `sitemap.parse_discovery_output` / `NetworkDevice` / the `devices` table (reads `cpu.cores`, `memory.free`/`memory.available`, `disk.filesystem`/`disk.size`/`disk.use_percent`/`disk.mount`; has no columns for usb/pci/block).

- **D-09 (guidance):** Planner picks canonical direction. Recommended: fix **both** ends.
  - Align `ssh_discover_system` to emit the sitemap-expected names (`cpu.cores` not `count`; add `memory.free`/`memory.available` from `free -b` output; emit `disk.filesystem`/`disk.size`/`disk.use_percent`/`disk.mount` from `df -B1 -T /` and mount info).
  - Extend `NetworkDevice`, the `devices` table (SQLite + Postgres), and `store_device` to accept and persist `usb_devices` / `pci_devices` / `block_devices` as JSON columns (mirrors the existing `network_interfaces` JSON-column pattern at `database.py:171`, `sitemap.py:97-98`).
  - `parse_discovery_output` extraction extended to populate the new fields.
- **D-09a (canonical field names):** Canonical field names are the sitemap/`NetworkDevice` forms — they surface in `get_network_sitemap` output and drive downstream analyzers. `ssh_discover_system` is the upstream producer and bends to match the downstream contract, not the other way around.
- **D-09b (schema columns vs JSON):** `usb_devices` / `pci_devices` / `block_devices` persist as JSON-encoded TEXT columns on `devices` (parallel to `network_interfaces`). Not normalized sub-tables — homelab scope; querying usb devices across the fleet is not a documented workflow.
- **D-09c (back-compat):** Column additions use `ALTER TABLE devices ADD COLUMN ...` inside the same one-time migration step as D-02's zombie dedup (or immediately adjacent). Legacy rows get `NULL` defaults; `get_all_devices` returns the new fields as `None` for pre-existing devices until re-discovered.

### Null-Threshold Defensiveness (Claude's Discretion, with guidance)

`analyze_network_topology` and `suggest_deployments` in `sitemap.py` mix guard styles. Known problem sites:
- `sitemap.py:200-201` — `cpu_cores is not None and cpu_cores <= 2` is correct.
- `sitemap.py:255-257` — `cpu_cores = device.get("cpu_cores") or 0; if cpu_cores >= 4:` — coerces None to 0; a device with unknown cpu_cores silently fails the `>= 4` check. Low-impact false negative, but inconsistent.
- `sitemap.py:296-297` — `cpu_cores = device.get("cpu_cores") or 0; if cpu_cores <= 2:` — **false-positive bug**: None-cpu device is classified as a low-resource upgrade candidate.
- `sitemap.py:179-197`, `sitemap.py:269-284` — `if device.get("disk_use_percent"):` guards are truthy-safe, but the `except (ValueError, AttributeError)` swallows `TypeError` inconsistently across call sites.

- **D-10 (threshold-input set):** "Threshold input" = any device field that drives a numeric comparison in an analyzer. For Phase 35: `cpu_cores` (int), `memory_total` (parseable str → GB), `disk_use_percent` (percent str). When any of these is `None` or empty, the device is **skipped** for that comparison — never coerced to zero, never falsely classified.
- **D-11 (skip pattern):** Planner picks between (a) inline `if field is None: continue` guards at each site or (b) a small helper `_has_threshold_data(device, *fields) -> bool` used across all three analyzers. Preference for (b) — matches the Phase 32/33.1 "extract a small private helper" idiom.
- **D-12 (log level):** Skipped-device events log at `DEBUG` (same as the existing `logger.debug("Skipping device %s ...")` calls at `sitemap.py:193-197` and `:283-284`). Not `INFO` — routine null data should not spam info logs.
- **D-13 (no silent coercion):** The `cpu_cores or 0` / `memory_total or ""` coercion patterns are removed. Guard explicitly or skip.

### Tests (AST Meta-Tests Applicable)

Phase 35 is footgun-removal (bug-fix class per `memory/feedback_regression_test_scope.md`) — AST meta-tests from the Phase 32 / 33 D-15 / 33.1 D-09 pattern apply. New-feature AST exclusion (Phase 34 D-13…D-16) does NOT apply here.

- **D-14 (upsert AST guard):** Scan `src/homelab_mcp/database.py` and verify the `store_device` match SQL in both adapters does not re-introduce `hostname = ? AND connection_ip = ?` as the primary match clause (the degenerate-fallback branch is a separate code path). Revert-proof regression.
- **D-15 (per-cmd timeout AST guard):** Scan `src/homelab_mcp/ssh_tools.py` `ssh_discover_system` body and assert every `conn.run(...)` call is either wrapped by `asyncio.wait_for` or by the per-cmd helper chosen in D-05. Fails on re-introduction of unbounded `conn.run()`.
- **D-16 (null-threshold AST guard):** Scan `src/homelab_mcp/sitemap.py` `analyze_network_topology` and `suggest_deployments` bodies; fail the test if `cpu_cores or 0`, `memory_total or ""`, or the equivalent coercion patterns reappear on threshold fields (exact pattern set is planner's call; principle is "threshold fields never coerced").
- **D-17 (functional tests):**
  - D-17a: `store_device` UPDATE-in-place when hostname matches and connection_ip changes.
  - D-17b: Migration collapses pre-existing duplicate hostnames; idempotent on second run.
  - D-17c: Per-subprocess timeout skips the field, marks `partial: true`, lists the command.
  - D-17d: `bulk_discover_and_map` with 10 unreachable hosts completes in `< ~1.5 × single-host timeout` (parallelism proof), not `10 × single-host timeout`.
  - D-17e: Analyzer skips devices with `cpu_cores=None` in both topology and suggestion paths; no low-resource false positive.

### Claude's Discretion

- Exact helper name and signature for the per-cmd timeout wrapper (D-05) — `_run_with_timeout`, `_run_cmd`, or inline `asyncio.wait_for` is all acceptable.
- Exact shape of the `timed_out_commands` entries (D-06) — `["lsblk", "lspci"]` simple list vs `[{"cmd": "lsblk", "timeout_s": 10.0}, ...]` — planner picks.
- Exact migration placement (D-02a) — new function inside `migration.py` vs inline in `init_schema` — either is acceptable.
- Concrete error messages and log strings throughout.
- Whether the per-cmd timeout and overall timeout values are env-var tunable (offered during discussion; recommended default was plain constants, env var deferred unless the planner sees value).
- Canonical direction on the schema mismatch in D-09 (fix both ends is recommended, not mandated).
- Whether `suggest_deployments` also adopts the `partial: true` awareness — i.e., should it skip devices marked partial? Planner's call; reasonable default is "treat partial devices like any other device — skip per-field on null, include what's there".

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 35 Scope

- `.planning/ROADMAP.md` §Phase 35 — Phase description; four-bug enumeration is the scope anchor.
- `.planning/REQUIREMENTS.md` §v1.6 Requirements — no REQ-ID maps to Phase 35 (surfaced by Phase 33 live testing, not in original v1.6 requirements).
- `.planning/PROJECT.md` §Constraints + §Key Decisions — MCP SDK lowlevel.Server conventions, keyring-only credential constraints, async-throughout pattern for SSH/network code.

### Prior Phase Decisions (locked, inherited)

- `.planning/phases/33-keyring-single-source-of-truth/33-CONTEXT.md` §Regression Guards — D-15 AST meta-test pattern (scan source for forbidden strings), D-01 one-time `DROP TABLE` startup migration pattern (shape reused for D-02 zombie dedup).
- `.planning/phases/33.1-ssh-tool-family-keyring-uniformity-drop-hardcoded-mcp-admin-/33.1-CONTEXT.md` §D-09 — AST schema-scan meta-test pattern.
- `.planning/phases/34-cluster-scoped-proxmox-credentials/34-CONTEXT.md` §D-09 — `async def` propagation discipline + explicit `feedback_regression_test_scope.md` rule (new-feature phases exclude AST meta-tests, bug-fix phases include them; Phase 35 is the latter).

### Memory / User Feedback

- `~/.claude/projects/C--Users-washy-projects-mcp-python-server/memory/feedback_regression_test_scope.md` — AST meta-tests guard known footguns (this phase qualifies); new-feature phases use functional + unit tests only. Drives D-14 / D-15 / D-16.

### Source Files Affected

- `src/homelab_mcp/sitemap.py`
  - `parse_discovery_output()` (~lines 54-117) — extraction shape for CPU/memory/disk/network/os; add usb/pci/block per D-09.
  - `NetworkDevice` dataclass (~lines 16-39) — field list; extend for usb/pci/block per D-09b.
  - `store_device()` delegates to adapter (~line 119-122).
  - `analyze_network_topology()` (~lines 137-218) — null-threshold guards per D-10/D-11/D-12.
  - `suggest_deployments()` (~lines 239-309) — same.
  - `bulk_discover_and_store()` (~lines 349-391) — parallelize per D-07.
  - `discover_and_store()` (~lines 312-346) — unchanged except for propagating partial-response keys.
- `src/homelab_mcp/database.py`
  - SQLite `init_schema()` (~lines 128-200) and `store_device()` (~lines 210-305).
  - Postgres `init_schema()` (~lines 511-580) and `store_device()` (~line 580+).
  - Both adapter `store_device` match clauses change per D-01; both table schemas add columns per D-09c.
- `src/homelab_mcp/ssh_tools.py`
  - `ssh_discover_system()` (~lines 226-438) — per-cmd timeout per D-05/D-06; output-shape alignment per D-09.
  - Wrapper decorator (line 224) — `timeout_seconds` bump per D-08.
- `src/homelab_mcp/error_handling.py`
  - `ssh_connection_wrapper()` (~lines 229-285) — unchanged; existing `effective_timeout = kwargs.pop("timeout", None) or timeout_seconds` already supports per-call override.
- `src/homelab_mcp/migration.py`
  - New one-time startup step per D-02 / D-02a (zombie dedup) and D-09c (schema column adds).
- `src/homelab_mcp/tool_handlers/network_handlers.py`
  - Unchanged (handlers are thin delegation wrappers; no MCP tool surface changes per D-domain out-of-scope).
- `tests/test_sitemap.py`, `tests/test_database.py`, `tests/test_ssh_tools.py`, or new `tests/test_discovery_reliability.py` — D-14…D-17 coverage.

### External / OS Contract

- `free -b`, `df -B1 /`, `lsusb`, `lspci`, `lsblk -J` — command contracts consumed by `ssh_discover_system`; the planner may need to add/modify the parsing to emit the canonical field names per D-09 (e.g., `df -B1 -T /` to expose filesystem; compute `use_percent` as `used / total * 100`).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `error_handling.ssh_connection_wrapper()` already exposes per-call timeout override via `effective_timeout = kwargs.pop("timeout", None) or timeout_seconds`. The D-08 120s default is a decorator-arg change — no new machinery required.
- `asyncio.wait_for(...)` is the established primitive across the project (see `error_handling.py:55` for the outer-wrapper use; matches PTY-shell pattern in `shell_session.py`). Per-cmd timeouts (D-05) use the same primitive.
- `asyncio.Semaphore(N)` + `asyncio.gather(return_exceptions=True)` is the idiomatic pattern for capped parallelism in the project's async code (mirrors the Proxmox concurrent-probe pattern from Phase 34).
- `migration.py` already hosts the Phase 33 `DROP TABLE IF EXISTS ssh_credentials` startup step. D-02's zombie dedup and D-09c's column adds live in the same module using the same idempotent-startup shape.
- `discovery_history` table + `NetworkSiteMap.store_discovery_history` already exist and carry the full per-discovery JSON. No new audit-trail infrastructure needed (D-03).
- `network_interfaces` JSON-column pattern at `database.py:171` (schema) / `sitemap.py:97-98` (writer) / `sitemap.py:320-324` (reader) is the template for `usb_devices` / `pci_devices` / `block_devices`.

### Established Patterns

- **One-time startup migration:** Phase 33 D-01 (`DROP TABLE IF EXISTS ssh_credentials`). Idempotent, both SQLite + Postgres adapters touched. Phase 35 D-02 / D-09c follow this shape.
- **AST meta-test regression guard:** Phase 32 / 33 D-15 / 33.1 D-09. Test parses `src/homelab_mcp/*.py` and fails on re-introduction of the patched anti-pattern. Phase 35 D-14 / D-15 / D-16 extend the same mechanism.
- **Small private helper for cross-site concerns:** `_sudo_run` (Phase 26 / v1.4), `_keyring_key` (Phase 34 D-03), `_parse_scope_arg` (Phase 34 Plan 04). Candidate for D-11's `_has_threshold_data` and D-05's `_run_with_timeout`.
- **Canonical field-name alignment:** Downstream consumer dictates names, upstream producer conforms. Matches the Phase 33 D-19 convention where `list_registered_servers` was rewritten to read the registry rather than the DB — reader drives contract.

### Integration Points

- `store_device` in `database.py` is the single write funnel for sitemap rows. Every code path (`discover_and_store`, `bulk_discover_and_store`, and any future writer) flows through it. Changing the match key there fixes all callers.
- `bulk_discover_and_store` in `sitemap.py` is the only serial-iteration hotspot. Parallelizing it fixes the 4-min hang surface without touching handler code.
- `parse_discovery_output` is the only reader of `ssh_discover_system`'s JSON; extending it for usb/pci/block is mechanical and localized.
- Analyzer changes in `sitemap.py` touch two methods only (`analyze_network_topology`, `suggest_deployments`); no handler or schema ripple.

</code_context>

<specifics>
## Specific Ideas

- **D-01 user-confirmed default:** The user explicitly chose hostname-only match over "hostname OR connection_ip" and over "keep + reconcile". Reasoning: one host = one sitemap row is the intended mental model, DHCP IP drift is expected, the match key should reflect that.
- **Degenerate-hostname fallback (D-01a):** Surfaced as a follow-up during discussion. `parse_discovery_output` writes `hostname="unknown"` on JSON-decode error and `""` on missing hostname in the JSON. Hostname-only matching would collapse all failed discoveries into one row; the degenerate fallback preserves the Phase-33-pre-existing distinct-error-row behavior.
- **D-07 concurrency cap of 10:** User-chosen over uncapped `asyncio.gather`. Reasoning: small homelab inventories (typically <20 hosts) fit comfortably in one wave; FD exhaustion and SSH-session flood on larger inventories is prevented with a fixed cap.
- **Regression-test shape:** User implicitly accepted the footgun-removal / AST-meta-test classification by choosing the "Claude's Discretion" option for the two unasked areas. Phase 35 is a bug-fix phase; AST meta-tests are the right regression-guard shape per `memory/feedback_regression_test_scope.md`.
- **Claude's Discretion areas (D-09 / D-10):** User deferred both discovery schema reconciliation and null-threshold defensiveness to the planner. The guidance embedded in D-09 / D-10 / D-11 / D-12 / D-13 represents the recommended defaults extracted from codebase analysis during the scout step; the planner can refine them but does not need to re-solicit user input for routine implementation decisions.

</specifics>

<deferred>
## Deferred Ideas

- **IP-history column on `devices`** — `discovery_history` already provides the audit trail; a dedicated column is convenience, not correctness. Candidate for a future UX-polish phase if quick IP-change queries become a documented need.
- **Automatic stale-row pruning (`last_seen > N days`)** — Separate decision: retention window, soft vs hard delete, opt-in vs automatic. Not in Phase 35 scope.
- **`prune_sitemap_duplicates` standalone tool** — The one-time migration handles the collapse idempotently. A standalone tool would be redundant unless a user wants to re-trigger the collapse without a server restart.
- **Per-subprocess and overall timeout env-var tunables** — Offered during discussion; user accepted plain-constant defaults. If future production deployments need tuning without a code change, the planner can revisit during implementation. Mentioned in Claude's Discretion.
- **Normalized sub-tables for usb/pci/block inventory** — Homelab scope; JSON-column persistence is sufficient. A "query usb devices across the fleet" workflow would warrant its own schema phase.

</deferred>

---

*Phase: 35-sitemap-discovery-reliability-fix-discover-and-map-field-los*
*Context gathered: 2026-04-24*
