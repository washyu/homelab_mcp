# Phase 36: Drift ↔ Sitemap Foundation — Research

**Researched:** 2026-04-25
**Domain:** Refactor / footgun-removal — drop parallel `drift_baselines` data layer, rewire `scan_drift` to iterate sitemap rows
**Confidence:** HIGH

## Summary

Phase 36 is a footgun-removal class refactor (Bug J dissolution). The CONTEXT.md is exceptionally
prescriptive — line numbers, exact strings, full method enumerations. The research job is **NOT
to redesign**, it is to verify the cited code locations against the live tree, document the
reusable patterns precisely (AST meta-test idiom, idempotent-migration shape), and surface
risks the planner needs to know about before tasking starts.

**All cited code locations were verified.** Most line ranges are accurate within ±2 lines (function
bodies have shifted slightly since CONTEXT was authored). The structural claims — "Postgres
`init_schema` does not create `drift_baselines`", "`get_proxmox_client` already calls the resolver
internally when host is set and no explicit auth", "`migration.py` already has the Phase 33
`DROP TABLE IF EXISTS ssh_credentials` precedent" — are all verified true.

**Two findings the CONTEXT.md does not address:**
1. **`tests/test_proxmox_baseline_hooks.py`** is a dedicated 170-line test file for DRFT-05 baseline
   hooks. CONTEXT.md D-16's test deletion scope does not name it but it MUST be deleted alongside
   `update_baseline_after_mutation` (D-11/D-11b).
2. **`tests/test_proxmox_api.py` lines 1770-1905** carry four `patch("...update_baseline_after_mutation")`
   call-site mocks across `handle_create_proxmox_vm` / `handle_create_proxmox_lxc` schema-passing
   tests. After D-11 removes the function, these patch lines reference a non-existent target and
   will fail at patch-application. They need cleanup (delete the patch line, keep the test).

**Established AST meta-test convention:** the project consolidates AST regression guards in
`tests/test_ast_regression.py` (extended Phase 33 / 33.1 / 35). CONTEXT.md D-12 recommends a new
file `tests/test_drift_baselines_removed.py`; the planner should consider extending the existing
file instead, matching established convention. Both are listed as Claude's discretion in CONTEXT.

**Primary recommendation:** Plan exactly what CONTEXT.md says. Add the two missing test-file
items above to the deletion scope. Place new AST guards in `tests/test_ast_regression.py`
(consolidate with Phase 33/35 pattern) rather than a new file.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Drift scan iteration source | Database / Storage (`db_adapter.get_all_devices()`) | — | Sitemap row IS the baseline post-Phase 36. Single funnel for all sitemap reads (Phase 35). |
| Per-host credential resolution | API / Backend (`resolve_proxmox_credentials` via `get_proxmox_client`) | — | Phase 34 D-09 locked this funnel; Phase 36 only consumes it. |
| Per-host live probe | API / Backend (`ProxmoxAPIClient.get("/cluster/status")`) | — | Same endpoint Phase 34's resolver already uses for cluster disambiguation. |
| Migration orchestration | Database / Storage (`migration.py` startup hook) | — | Idempotent `IF EXISTS` drop on every start; same module as Phase 33 / 35 migrations. |
| MCP tool surface | API / Backend (`drift_handlers.py` thin handler) | — | Phase 36 simplifies, no new tools. |
| Resource cache pass-through | Frontend / Resource (`server.set_latest_drift_report` + `resource_readers.read_drift_resource`) | — | Cached payload is whatever scan returns; D-18 only tweaks description. |
| AST regression guard | Test infrastructure (`tests/test_ast_regression.py`) | — | Consolidated AST guard module; planner-discretion whether to extend or create new file. |

## Standard Stack

### Core (already in dependencies — no new installs)

| Library | Version (verified `uv pip list`) | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 8.4.1 | Test runner | Project-wide convention (CLAUDE.md) [VERIFIED] |
| pytest-asyncio | 1.0.0 | Async test support | All `scan_drift` tests use `@pytest.mark.asyncio` [VERIFIED] |
| pytest-mock | 3.14.1 | `MagicMock`/`AsyncMock` fixtures | Existing drift tests use unittest.mock directly; pytest-mock is available [VERIFIED] |
| aiohttp | 3.12.13 | HTTP client (Proxmox API) | `aiohttp.ClientError` is the probe-failure exception type for D-09a [VERIFIED] |
| asyncssh | 2.21.0 | SSH (unused on Phase 36 drift path) | Phase 39 will use it for missing/changed detection [VERIFIED] |
| psycopg2 | optional (POSTGRESQL_AVAILABLE flag) | Postgres adapter | Used for D-15 `pytest.mark.integration` test [VERIFIED via database.py:15-21] |

### Already-implemented helpers Phase 36 consumes (no new code)

| Symbol | Location | Purpose | Phase 36 Use |
|--------|----------|---------|--------------|
| `db_adapter.get_all_devices()` | `database.py:349` (SQLite), `database.py:790` (Postgres) | Returns all sitemap rows (Phase 35 D-01 hostname-keyed) | D-09 iteration entry point |
| `get_proxmox_client(host=..., session=...)` | `proxmox_api.py:332-396` | Resolver-aware async client constructor | D-09 per-row probe — calls resolver internally at lines 370-378 when `host` is set and no explicit auth |
| `resolve_proxmox_credentials(host, session)` | `proxmox_api.py:194-329` | Per-node→cluster→error resolver, returns `tuple[str, Literal["node", "cluster"], str \| None]` | D-02's `scope` and `cluster_name` fields populated from this tuple via the `get_proxmox_client` internal call |
| `CredentialNotFoundError` | `ssh_tools.py:27`, re-exported `proxmox_api.py:16` | Exception raised when neither resolver tier matches | D-09a / D-10 — silently skip rows that raise this from `get_proxmox_client` |
| `sanitize_error(exc)` | `log_filter.py:64` (re-imported via `error_handling.py:14`) | Redact secrets from exception messages | D-09a — scrub probe exception before placing in per-row `error` field |
| `set_latest_drift_report(result)` | `server.py:83` | Cache scan result for `homelab://drift/latest` | D-18 — pass-through; cached shape becomes the 2-bucket interim |
| `read_drift_resource()` | `resource_readers.py:127-138` | Resource reader; returns `{"drift_detected": None}` before any scan | D-18 — unchanged |
| `DRIFT_SCAN_TOOLS` frozenset | `server.py:171` | Notification wiring for resource-update events | Unchanged in Phase 36 |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Per-row `resolve_proxmox_credentials` (D-10) | Walk keyring registry first, build hostname allowlist | Cluster entries have `hostname=""` (Phase 34 D-02) — registry walk is asymmetric. CONTEXT.md D-10 chose the simple path; D-10b leaves the optimization deferred to Phase 39 if log noise warrants. **Locked: per-row resolve.** |
| New file `tests/test_drift_baselines_removed.py` (D-12) | Extend `tests/test_ast_regression.py` | Established convention is consolidation. Both are CONTEXT-acceptable (Claude's discretion). **Recommended: extend `test_ast_regression.py`.** |

**Installation:** Nothing to install. All tooling already declared.

**Version verification:** Confirmed via `uv pip list` on 2026-04-25 — pytest 8.4.1, pytest-asyncio 1.0.0, aiohttp 3.12.13, asyncssh 2.21.0. [VERIFIED]

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DRFT-11 | `scan_infrastructure_drift` iterates sitemap rows; no parallel baseline read on scan path | D-09 (per-row iteration via `get_all_devices()`); D-12/D-13 AST guards prove zero source-side reads remain |
| DRFT-12 | `scan_infrastructure_drift` resolves Proxmox creds via `resolve_proxmox_credentials`; no `PROXMOX_HOST` coupling on success path | D-09 (passes `host=row["hostname"]` to `get_proxmox_client`, which calls resolver at `proxmox_api.py:370-378`); D-09b enforces no env-var fallback in `scan_drift` |
| DRFT-21 | Drop parallel `drift_baselines` SQLite + Postgres table | D-05 (idempotent `DROP TABLE IF EXISTS` migration step on both adapters), D-06 (delete `CREATE TABLE` from `init_schema` + `migration.py` auto-create), D-07 (delete adapter methods), D-08 (banner) |

## Architecture Patterns

### System Architecture Diagram

```
       MCP client                                    Disk / DB
          │                                              │
          │ scan_infrastructure_drift                    │
          ▼                                              │
┌──────────────────────────────┐                         │
│ tool_handlers/drift_handlers │                         │
│ handle_scan_infrastructure_  │                         │
│ drift                        │  D-03: precondition     │
│ - rm = get_resource_manager()│  check removed          │
│ - result = await scan_drift()│                         │
│ - set_latest_drift_report()  │                         │
│ - return content-wrapped JSON│                         │
└─────────────┬────────────────┘                         │
              │                                          │
              ▼                                          │
┌──────────────────────────────┐                         │
│ drift_detection.scan_drift   │                         │
│ (rewritten per D-01/D-02)    │                         │
│                              │                         │
│ 1. scan_timestamp = now()    │                         │
│ 2. rows = db_adapter.        │ ──────── reads ──────►  │
│      get_all_devices()       │                         │
│ 3. for row in rows:          │                         │
│      skip degenerate (D-10a) │                         │
│      try:                    │                         │
│        client = await        │                         │
│          get_proxmox_client( │                         │
│            host=row[hostname]│                         │
│            session=session)  │                         │
│        status = await        │     ┌──────────────┐    │
│        client.get(           │ ──► │ Proxmox /    │    │
│          "/cluster/status")  │     │ cluster/     │    │
│      except                  │     │ status       │    │
│        CredentialNotFound:   │     │ (live HTTP)  │    │
│          skip silently       │     └──────────────┘    │
│      except                  │                         │
│        (aiohttp.ClientError, │                         │
│         asyncio.TimeoutError,│                         │
│         ValueError):         │                         │
│          unreachable bucket  │                         │
│                              │                         │
│ 4. return {                  │                         │
│     status: success,         │                         │
│     scan_timestamp,          │                         │
│     scanned: len(rows),      │                         │
│     probed_ok: [...],        │                         │
│     unreachable: [...]       │                         │
│    }                         │                         │
└─────────────┬────────────────┘                         │
              │                                          │
              ▼                                          │
   Result cached in                                      │
   server.LATEST_DRIFT_REPORT                            │
   (read by homelab://drift/latest)                      │
```

### Recommended Project Structure (no changes — existing layout preserved)

```
src/homelab_mcp/
├── drift_detection.py        # REWRITE — scan_drift to 2-bucket shape; delete _diff_vm_config + update_baseline_after_mutation + CONFIG_DRIFT_FIELDS
├── database.py               # DELETE drift_baseline ABCs + SQLite impls + Postgres NotImplementedError stubs; delete CREATE TABLE in SQLite init_schema
├── migration.py              # ADD drop step (both adapters); DELETE create-on-startup block
├── tool_handlers/
│   ├── drift_handlers.py     # SIMPLIFY — remove precondition check (D-03)
│   └── proxmox_handlers.py   # CLEAN — remove update_baseline_after_mutation imports + try/except blocks (3 handlers)
├── tool_schemas/
│   └── drift_tools_schema.py # TWEAK description per D-04
└── resource_readers.py       # OPTIONAL one-line description tweak (D-18)

tests/
├── test_drift_detection.py        # FULL REWRITE — 2-bucket model, mocked sitemap iteration
├── test_drift_wiring.py           # REWRITE or DELETE — handler→drift_detection wiring no longer reads get_all_drift_baselines
├── test_drift_resource.py         # KEEP — verify cached-payload shape compatibility
├── test_database.py               # DELETE TestDriftBaselines class (lines 357-468)
├── test_proxmox_baseline_hooks.py # DELETE ENTIRELY (170 lines, all DRFT-05 hook tests)
├── test_proxmox_api.py            # CLEAN — remove four update_baseline_after_mutation patch lines (1784, 1825, 1854, 1893)
├── test_ast_regression.py         # EXTEND — add D-12 + D-13 AST guards (recommended) OR planner picks new file
└── test_migration.py              # MAY NEED ADDITION — D-15 migration idempotency tests (Wave-0 gap)
```

### Pattern 1: Idempotent Startup Migration (D-05) — exact reuse from Phase 33 D-01 / Phase 35 D-02

The drop step must mirror the existing Phase 33 `ssh_credentials` block in `migration.py` verbatim
in shape. The live precedent:

**SQLite shape** ([VERIFIED `migration.py:37-62`]):
```python
# D-01: Drop legacy ssh_credentials table if it still exists (v1.6 cleanup).
cursor = conn.cursor()
cursor.execute(
    """
    SELECT name FROM sqlite_master
    WHERE type='table' AND name='ssh_credentials'
    """
)
if cursor.fetchone():
    cursor.execute("DROP INDEX IF EXISTS idx_ssh_credentials_hostname")
    cursor.execute("DROP INDEX IF EXISTS idx_ssh_credentials_device_id")
    cursor.execute("DROP TABLE IF EXISTS ssh_credentials")
    conn.commit()
    applied_migrations.append("drop_ssh_credentials_table")
    import sys  # noqa: PLC0415
    print("Dropped legacy ssh_credentials table (...)", file=sys.stderr)
    print("NOTE: ...\nRe-add them with: ...", file=sys.stderr)
```

**Postgres shape** ([VERIFIED `migration.py:281-305`]):
```python
cursor.execute(
    """
    SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_name = 'ssh_credentials'
    )
    """
)
if cursor.fetchone()[0]:
    cursor.execute("DROP INDEX IF EXISTS idx_ssh_credentials_hostname")
    cursor.execute("DROP INDEX IF EXISTS idx_ssh_credentials_device_id")
    cursor.execute("DROP TABLE IF EXISTS ssh_credentials")
    conn.commit()
    applied_migrations.append("drop_ssh_credentials_table")
    # ... banner via print(..., file=sys.stderr)
```

**Phase 36 reuse:** copy this exact shape, swap `ssh_credentials` → `drift_baselines`, swap
`idx_ssh_credentials_*` → `idx_drift_baselines_node_vmid` (the only index on the table per
`database.py:219-222`). Drop step lands AFTER the existing Phase 35 stale-constraint addendum
in SQLite (so the order is: ssh_credentials drop → Phase 35 ALTER → zombie dedup → stale-UNIQUE
rebuild → drift_baselines drop). Same place in Postgres (after Phase 35 stale-UNIQUE).

**`applied_migrations.append("drop_drift_baselines_table")`** on the drop branch (mirrors Phase 33
naming).

**Existing CREATE block to delete** ([VERIFIED `migration.py:224-247`]):
```python
# Check if drift_baselines table exists
cursor.execute("""SELECT name FROM sqlite_master WHERE type='table' AND name='drift_baselines'""")
if not cursor.fetchone():
    cursor.execute("""CREATE TABLE IF NOT EXISTS drift_baselines (...)""")
    cursor.execute("""CREATE INDEX IF NOT EXISTS idx_drift_baselines_node_vmid ...""")
    conn.commit()
    applied_migrations.append("create_drift_baselines_table")
```
This block is the auto-create-on-startup path; D-06 removes it. After deletion the surrounding
Phase 35 logic is intact (block was self-contained, no shared state).

### Pattern 2: AST Meta-Test (D-12 / D-13) — exact reuse from Phase 33 D-15 / Phase 35 D-14

**The canonical idiom** ([VERIFIED `tests/test_ast_regression.py:142-178`]):

```python
FORBIDDEN_SOURCE_STRINGS: list[str] = [
    "ssh_credentials",  # D-15: DB table name
    # ... others
]

ALLOWED_EXCEPTIONS: dict[str, set[str]] = {
    "ssh_credentials": {"migration.py"},
}

def test_no_forbidden_strings_in_source() -> None:
    src_root = Path(__file__).parent.parent / "src" / "homelab_mcp"
    assert src_root.exists(), f"Source root not found: {src_root}"
    violations: list[str] = []
    for py_file in sorted(src_root.rglob("*.py")):
        source = py_file.read_text(encoding="utf-8")
        # Fast pre-check
        if not any(forbidden in source for forbidden in FORBIDDEN_SOURCE_STRINGS):
            continue
        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError as e:
            violations.append(f"{py_file}: SyntaxError during AST parse: {e}")
            continue
        all_strings = _collect_string_literals(tree)
        all_ids = _collect_name_and_attr_ids(tree)
        all_tokens = set(all_strings + all_ids)
        for forbidden in FORBIDDEN_SOURCE_STRINGS:
            if forbidden in all_tokens:
                allowed_files = ALLOWED_EXCEPTIONS.get(forbidden, set())
                if py_file.name in allowed_files:
                    continue
                violations.append(f"{py_file.relative_to(src_root.parent.parent)}: contains forbidden identifier/string {forbidden!r}")
    assert not violations, "Phase 33 regression: ..." + "\n".join(f"  - {v}" for v in violations)
```

Helper functions ([VERIFIED `tests/test_ast_regression.py:126-139`]):
```python
def _collect_string_literals(tree: ast.AST) -> list[str]:
    """Walk AST and collect all string constant values."""
    return [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)]

def _collect_name_and_attr_ids(tree: ast.AST) -> list[str]:
    """Walk AST and collect all Name.id and Attribute.attr values."""
    ids: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            ids.append(node.id)
        elif isinstance(node, ast.Attribute):
            ids.append(node.attr)
    return ids
```

**For Phase 36 D-12:** add to `FORBIDDEN_SOURCE_STRINGS`:
- `"drift_baselines"` (table name)
- `"upsert_drift_baseline"` (removed adapter method)
- `"get_drift_baseline"` (removed adapter method)
- `"get_all_drift_baselines"` (removed adapter method)

Add to `ALLOWED_EXCEPTIONS`:
- `"drift_baselines": {"migration.py"}` — D-05 drop step needs the literal table name
  (other three method names should NOT appear anywhere in `migration.py`; Phase 36 deletes the
  CREATE block that referenced them — but those names were never inside `migration.py`'s text,
  the CREATE block uses the bare table name only)

**For Phase 36 D-13 (drift_detection.py-specific):** independent test function asserting that
`Path(src_root / "drift_detection.py").read_text()` contains NONE of the four forbidden strings.
Belt-and-braces guard. Same shape as Phase 35 D-15 (`test_ssh_discover_system_wraps_every_conn_run_phase35`)
which targets a single function in a single file.

**Convention recommendation:** Place both new tests in `tests/test_ast_regression.py` (consolidated
guard module). Functions can be named `test_no_drift_baselines_in_source_phase36()` and
`test_drift_detection_no_baseline_references_phase36()` matching the `_phase{N}` naming in lines
383, 438, 505 of the existing file.

### Pattern 3: 2-Bucket Functional Test (D-14) — mock harness pattern

Drift tests already use the `MagicMock` + `AsyncMock` + `patch` idiom heavily (verified
`tests/test_drift_detection.py:8-77`, `tests/test_drift_wiring.py:73-99`). Phase 36's new
test must mock at three layers:

1. `db_adapter.get_all_devices()` returns a list of 3 sitemap rows
2. `homelab_mcp.proxmox_api.resolve_proxmox_credentials` (or equivalently `get_proxmox_client`)
   per-call side_effect mapping hostname → outcome
3. The resulting `ProxmoxAPIClient.get("/cluster/status")` per-call side_effect mapping host →
   list payload OR `aiohttp.ClientError`

**Patch target order matters:** since `scan_drift` uses `get_proxmox_client` (which internally
calls `resolve_proxmox_credentials`), the simplest mock surface is to patch
`homelab_mcp.drift_detection.get_proxmox_client` directly in the test (matching the existing
`patch("homelab_mcp.drift_detection.get_proxmox_vm_status")` pattern at line 195 of
`test_drift_detection.py`). The mock returns either a `MagicMock` whose `.get` AsyncMock
returns the desired payload, or raises the appropriate exception.

### Anti-Patterns to Avoid

- **Hand-rolling DROP TABLE without `IF EXISTS`** — would break idempotent re-run on fresh installs.
- **Calling `os.getenv("PROXMOX_HOST")` anywhere on `scan_drift`'s call chain** — D-09b explicitly forbids; AST D-13 catches.
- **Adding `host=` parameter to `scan_drift`** — preserves the architectural rule that drift's host source is the sitemap, not callers.
- **Half-deleting `update_baseline_after_mutation`** (e.g., keeping the function but emptying its body to keep imports working) — D-11 demands total removal. The deferred imports in `proxmox_handlers.py` come out cleanly because the imports are inside the `try` blocks themselves.
- **Counting rows before the DROP** — adds a `SELECT COUNT(*)` that complicates idempotency. CONTEXT.md D-08 explicitly prefers no row count.
- **Reusing `_diff_vm_config` on the new path** — Phase 39's changed-detection will compare sitemap-stored fingerprints against live probes (different field shapes). Keeping the helper creates a regression-trap.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Resolver telemetry (scope, cluster_name) for per-row records | Custom resolver call in `scan_drift` | Pass `host=row["hostname"]` to `get_proxmox_client`; let it call resolver at `proxmox_api.py:370-378`; capture the `(scope, cluster_name)` tuple via the function's existing log line at line 373-378 | Phase 34 D-09 already locks this funnel; duplicating is footgun-class regression risk |
| Idempotent DROP TABLE | Custom existence check + per-DB SQL | Reuse the Phase 33 `ssh_credentials` shape verbatim (`SELECT FROM sqlite_master` for SQLite, `SELECT EXISTS FROM information_schema.tables` for Postgres) | Cross-adapter consistency; idempotency proof already vetted in Phase 33's verification |
| Sanitize exception text | `str(e)` or `e.args[0]` directly into JSON payload | `sanitize_error(e)` from `log_filter.py` (re-imported via `error_handling.py:14`) | Phase 33/34 convention; redacts `PVEAPIToken=...`, `password=...`, etc. (see `_SENSITIVE_PATTERNS` in `log_filter.py:16-33`) |
| AST regression guard for forbidden strings | New file with custom walk logic | Extend `tests/test_ast_regression.py:FORBIDDEN_SOURCE_STRINGS` list and reuse `test_no_forbidden_strings_in_source()` body | Established Phase 32/33/33.1/35 idiom; consolidating maintains a single discovery point for all AST guards |

**Key insight:** Phase 36 has zero new external dependencies and zero new infrastructure. It is
100% deletion + redirection. Every facility it needs already exists in the v1.6 codebase.

## Runtime State Inventory (rename / refactor / migration phase)

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Pre-existing rows in `drift_baselines` SQLite table on user installs | **Lost on first server start post-upgrade** (D-05 drops table without migrating rows). Per DRFT-21 architectural decision (homelab single-user scope, mirrors v1.6 CRED-04). User accepts via re-running discovery. Banner (D-08) communicates this. |
| Live service config | None — drift_baselines is a local DB table, no external service holds it | None |
| OS-registered state | None — no Windows Task / launchd / systemd unit references `drift_baselines` | None |
| Secrets / env vars | None — `drift_baselines` rows store config snapshots, not credentials. `PROXMOX_HOST` env var is unrelated to the table; D-09b forbids it on the scan path but the env var continues to exist for `get_proxmox_client`'s back-compat path (`proxmox_api.py:357`) | None |
| Build artifacts | None — pure source change, no compiled artifacts to invalidate | None |

**Production grep confirms scope** ([VERIFIED via Grep on `src/`]):
- `drift_baselines` table name appears only in: `database.py`, `migration.py`
- `upsert_drift_baseline` / `get_drift_baseline` / `get_all_drift_baselines` adapter method names appear only in: `database.py`, `drift_detection.py`
- `update_baseline_after_mutation` appears only in: `drift_detection.py`, `tool_handlers/proxmox_handlers.py`

**The canonical question — "after every file in the repo is updated, what runtime systems still
have the old string cached, stored, or registered?"** — answers cleanly: nothing outside the
local SQLite/Postgres `drift_baselines` table itself, and that table is dropped by D-05.

## Common Pitfalls

### Pitfall 1: Patch Target Drift in test_proxmox_api.py
**What goes wrong:** Four tests at `test_proxmox_api.py:1784, 1825, 1854, 1893` patch
`src.homelab_mcp.drift_detection.update_baseline_after_mutation`. After D-11 deletes the function,
`unittest.mock.patch` raises `AttributeError: <module 'src.homelab_mcp.drift_detection'> does not
have the attribute 'update_baseline_after_mutation'` at patch-application time, BEFORE the test
body runs. Test failure is a noisy `AttributeError`, not an assertion mismatch.
**Why it happens:** CONTEXT.md D-16 only names `test_drift_detection.py`, `test_drift_wiring.py`,
`test_database.py`, and `test_drift_resource.py` as in-scope. The four `test_proxmox_api.py`
patches are not flagged.
**How to avoid:** Add a sub-task to delete those four `patch(...)` lines (the entire patch
context-manager argument). The tests verify schema-passing kwargs to `create_proxmox_vm` /
`create_proxmox_lxc` — drift wiring is incidental in those tests. Tests stay green after the
patch lines are removed because the now-missing `try/except update_baseline_after_mutation` block
in the handlers (deleted by D-11) means there's no side effect to suppress.
**Warning signs:** During Wave 0 (RED), if tests pass without changes after D-11 deletes the
function, the four patches will throw `AttributeError`.

### Pitfall 2: Forgotten test_proxmox_baseline_hooks.py
**What goes wrong:** `tests/test_proxmox_baseline_hooks.py` is a 170-line, 4-test file dedicated
entirely to the DRFT-05 baseline-hook contract (`TestCreateProxmoxVmBaselineHook`,
`TestCreateProxmoxLxcBaselineHook`, `TestCloneProxmoxVmBaselineHook`). After D-11 removes the
hook, every test in this file becomes obsolete and will fail when patches resolve to a
non-existent attribute.
**Why it happens:** CONTEXT.md D-11b mentions `TestUpdateBaselineAfterMutation` (a class inside
`test_drift_detection.py`) but does not call out the standalone hook-test file. Easy to miss.
**How to avoid:** Add `tests/test_proxmox_baseline_hooks.py` to the deletion scope. The file
is self-contained — no other test imports from it.

### Pitfall 3: Postgres NotImplementedError Stubs
**What goes wrong:** Phase 11 originally scoped drift_baselines as SQLite-only. The Postgres
adapter has stub methods at `database.py:917-939` that raise `NotImplementedError("drift baseline
CRUD is SQLite-only in Phase 11")`. CONTEXT.md correctly identifies these as deletion targets
under D-07, but cites them at lines 917-936 / 928 / 937 — actual lines are 917-926, 928-935, 937-939.
Off-by-three in two cases.
**Why it happens:** CONTEXT.md was authored before the most recent file edits; line drift is
within ±3 lines.
**How to avoid:** Implementation tasks should resolve the deletion by symbol name (function
identifier), not by line number. Delete the function definitions for `upsert_drift_baseline`,
`get_drift_baseline`, `get_all_drift_baselines` on `PostgreSQLAdapter` regardless of exact line.
**Warning signs:** None — the delete-by-symbol approach handles drift transparently.

### Pitfall 4: D-04 Schema Description Phrasing
**What goes wrong:** The current schema description (`drift_tools_schema.py:5-9`) says "Returns
structured report with drift_type, expected, actual, and scan_timestamp per finding". Post-Phase 36
the response is a 2-bucket interim with no `drift_type` / `expected` / `actual` fields. If the
description isn't updated, MCP clients consuming the schema will see a mismatch between
description and live response.
**Why it happens:** CONTEXT.md D-04 says "schema description gains a one-line note" — easy to
read as "append" when "rewrite" is what's needed.
**How to avoid:** Replace (not append to) the description so it accurately reflects the 2-bucket
shape AND notes filter inertness. Suggested phrasing per D-04: "Scan for infrastructure drift
against the sitemap. Returns 2-bucket coverage report (probed-OK, unreachable) per resolved
Proxmox host. Filter semantics under Phase 37 redesign — node/vm_type currently inert."

### Pitfall 5: Resource Cache Reader Shape Compatibility
**What goes wrong:** `test_drift_resource.py:test_drift_resource_after_scan` constructs a sample
report `{"drift_detected": True, "drifted_vms": [], "scanned_at": "..."}` — neither key
("drifted_vms", "drift_detected") matches the new 2-bucket shape (`probed_ok`, `unreachable`,
`scan_timestamp`). The test is a pure pass-through assertion (`set → read → assert equal`) so it
will keep passing after Phase 36 because it sets and reads its own arbitrary dict, but it no
longer exercises the actual scan output shape.
**Why it happens:** The resource layer is shape-agnostic — it just caches and returns whatever
`scan_drift` produces.
**How to avoid:** Update the sample fixture in `test_drift_resource_after_scan` to use the new
shape (`{"status": "success", "scan_timestamp": "...", "scanned": 0, "probed_ok": [], "unreachable": []}`)
even though the test logic doesn't change. Keeps fixtures honest. CONTEXT.md D-16 last bullet
already calls this out: "tests/test_drift_resource.py — keep but verify the cached payload shape
change (D-18) doesn't break the test; rewrite the fixtures if so."

## Code Examples

### `scan_drift` 2-bucket implementation skeleton (D-01/D-02/D-09 informed)

```python
# Source: synthesized from CONTEXT.md D-01/D-02/D-09 + verified live signatures
import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import aiohttp

from .database import DatabaseAdapter
from .log_filter import sanitize_error
from .proxmox_api import CredentialNotFoundError, get_proxmox_client

logger = logging.getLogger(__name__)


async def scan_drift(
    session: aiohttp.ClientSession | None,
    db_adapter: DatabaseAdapter,
    node: str | None = None,           # D-04: inert passthrough
    vm_type: str = "all",              # D-04: inert passthrough
) -> dict[str, Any]:
    scan_timestamp = datetime.now(UTC).isoformat()
    probed_ok: list[dict[str, Any]] = []
    unreachable: list[dict[str, Any]] = []

    rows = db_adapter.get_all_devices()  # D-09 entry point
    for row in rows:
        hostname = row.get("hostname")
        # D-10a: skip degenerate Phase-35 fallback rows
        if hostname in ("", "unknown", None) or row.get("status") == "error":
            continue

        try:
            # get_proxmox_client internally calls resolve_proxmox_credentials when host
            # is set and no explicit auth (proxmox_api.py:370-378). The resolver tuple
            # surfaces via the get_proxmox_client log line at proxmox_api.py:373-378.
            client = await get_proxmox_client(host=hostname, session=session)
        except CredentialNotFoundError:
            # D-10: row is not a registered Proxmox host → silently skip
            continue
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
            # Resolver itself raised on probe-during-cluster-walk
            unreachable.append({
                "hostname": hostname,
                "connection_ip": row.get("connection_ip", ""),
                "scope": "unknown",
                "cluster_name": None,
                "status": "unreachable",
                "error": sanitize_error(exc),
                "scan_timestamp": scan_timestamp,
            })
            continue

        # NOTE: capturing scope/cluster_name requires either:
        #  (a) calling resolve_proxmox_credentials directly (allowed — pubic API)
        #  (b) reading from a new attribute on ProxmoxAPIClient (would require client change)
        # Recommend (a): one extra call per row, returns the same tuple already cached
        # in _HOST_CLUSTER_CACHE. Trades a microseconds-scale lookup for clean telemetry.
        # Or planner may push (b) as an optimization in D-09's "Claude's discretion" space.
        from .proxmox_api import resolve_proxmox_credentials  # noqa: PLC0415
        try:
            _token, scope, cluster_name = await resolve_proxmox_credentials(hostname, session=session)
        except CredentialNotFoundError:
            # Should not happen — get_proxmox_client just succeeded — but defensive.
            continue

        try:
            status = await client.get("/cluster/status")
            if not isinstance(status, list):
                raise ValueError(f"unexpected /cluster/status payload type: {type(status).__name__}")
            probed_ok.append({
                "hostname": hostname,
                "connection_ip": row.get("connection_ip", ""),
                "scope": scope,
                "cluster_name": cluster_name,
                "status": "probed-ok",
                "error": None,
                "scan_timestamp": scan_timestamp,
            })
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
            unreachable.append({
                "hostname": hostname,
                "connection_ip": row.get("connection_ip", ""),
                "scope": scope,
                "cluster_name": cluster_name,
                "status": "unreachable",
                "error": sanitize_error(exc),
                "scan_timestamp": scan_timestamp,
            })

    return {
        "status": "success",
        "scan_timestamp": scan_timestamp,
        "scanned": len(probed_ok) + len(unreachable),
        "probed_ok": probed_ok,
        "unreachable": unreachable,
    }
```

**Note on the double resolver call:** the recommended approach has `get_proxmox_client` call
`resolve_proxmox_credentials` internally, then `scan_drift` calls it again to capture telemetry.
This is wasteful in CPU terms but trivial in real time (second call hits the
`_HOST_CLUSTER_CACHE` per `proxmox_api.py:243-265`). The alternative is to surface the resolver
tuple via a new attribute on `ProxmoxAPIClient`, which is a wider blast radius. Planner may pick
either; the cache-hit path makes the double-call effectively free.

### Migration drop step (D-05) for SQLite

```python
# Source: synthesized from migration.py:37-62 ssh_credentials precedent
# Place AFTER the existing Phase 35 stale-UNIQUE rebuild (line ~222),
# REPLACING the existing CREATE block at lines 224-247.

# Drop legacy drift_baselines table if it still exists (v1.7 cleanup).
# Sitemap is now the single source of truth for drift detection (DRFT-11).
cursor.execute(
    """
    SELECT name FROM sqlite_master
    WHERE type='table' AND name='drift_baselines'
    """
)
if cursor.fetchone():
    cursor.execute("DROP INDEX IF EXISTS idx_drift_baselines_node_vmid")
    cursor.execute("DROP TABLE IF EXISTS drift_baselines")
    conn.commit()
    applied_migrations.append("drop_drift_baselines_table")
    import sys  # noqa: PLC0415
    print(
        "Dropped legacy drift_baselines table (v1.7: sitemap is now the single source of truth for drift)",
        file=sys.stderr,
    )
    print(
        "NOTE: Pre-existing baseline rows are not preserved (per DRFT-21 architectural decision).\n"
        "      Drift now reports against the live sitemap; no manual baseline registration is needed.",
        file=sys.stderr,
    )
```

### Migration drop step (D-05) for Postgres

```python
# Source: synthesized from migration.py:281-305 ssh_credentials Postgres precedent
# Place AFTER the existing Phase 35 Postgres stale-UNIQUE drop (line ~389).

cursor.execute(
    """
    SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_name = 'drift_baselines'
    )
    """
)
if cursor.fetchone()[0]:
    cursor.execute("DROP INDEX IF EXISTS idx_drift_baselines_node_vmid")
    cursor.execute("DROP TABLE IF EXISTS drift_baselines")
    conn.commit()
    applied_migrations.append("drop_drift_baselines_table")
    import sys  # noqa: PLC0415
    print(
        "Dropped legacy drift_baselines table from Postgres (v1.7: sitemap is now the single source of truth for drift)",
        file=sys.stderr,
    )
    print(
        "NOTE: Pre-existing baseline rows are not preserved (per DRFT-21 architectural decision).\n"
        "      Drift now reports against the live sitemap; no manual baseline registration is needed.",
        file=sys.stderr,
    )
```

### AST meta-test extension (D-12)

```python
# Source: synthesized from tests/test_ast_regression.py:24-46 + 142-178 pattern.
# ADD to the existing FORBIDDEN_SOURCE_STRINGS list:

FORBIDDEN_SOURCE_STRINGS: list[str] = [
    # ... existing Phase 33 / 33.1 entries ...
    "drift_baselines",          # Phase 36 D-12: dropped table name
    "upsert_drift_baseline",    # Phase 36 D-12: removed adapter method
    "get_drift_baseline",       # Phase 36 D-12: removed adapter method
    "get_all_drift_baselines",  # Phase 36 D-12: removed adapter method
]

# ADD to ALLOWED_EXCEPTIONS:
ALLOWED_EXCEPTIONS: dict[str, set[str]] = {
    "ssh_credentials": {"migration.py"},
    "drift_baselines": {"migration.py"},  # D-05 drop step needs the literal string
}
# Note: the three method names are NOT added to ALLOWED_EXCEPTIONS — they should
# never appear after D-07 deletes the methods. migration.py only references the
# table name (in DROP TABLE / SELECT FROM sqlite_master), not the method names.

# Existing test_no_forbidden_strings_in_source() picks up the new entries automatically.
# No new function needed for D-12 — it's a list extension.
```

### AST meta-test for D-13 (drift_detection.py-specific)

```python
# Source: synthesized from tests/test_ast_regression.py:438-493 (Phase 35 D-15 single-file pattern)
def test_drift_detection_no_baseline_references_phase36() -> None:
    """Phase 36 D-13: drift_detection.py must contain no reference to the
    parallel baseline data layer — singular OR plural, in any AST node form
    (string literal, identifier, attribute access)."""
    src_root = Path(__file__).parent.parent / "src" / "homelab_mcp"
    source = (src_root / "drift_detection.py").read_text(encoding="utf-8")

    forbidden = [
        "drift_baseline",          # singular — covers e.g. db_adapter.upsert_drift_baseline()
        "drift_baselines",         # plural — covers table name + db_adapter.get_all_drift_baselines()
    ]
    violations = [s for s in forbidden if s in source]
    assert not violations, (
        f"Phase 36 D-13 regression — drift_detection.py contains forbidden baseline references: {violations}. "
        f"scan_drift must read from sitemap rows (db_adapter.get_all_devices()) only."
    )
```

## State of the Art

| Old Approach | Current Approach (post-Phase 36) | When Changed | Impact |
|--------------|------------------------------------|--------------|--------|
| `drift_baselines` SQLite table as parallel baseline storage; `upsert_drift_baseline` writes after every mutation | Sitemap rows (`get_all_devices()`) ARE the baseline; no parallel layer | Phase 36 (v1.7) | Removes Bug J at root; eliminates dual-data-layer integration debt |
| `scan_drift` reads `db_adapter.get_all_drift_baselines()` then probes each baseline's VM | `scan_drift` iterates `db_adapter.get_all_devices()` and probes each candidate Proxmox host's `/cluster/status` | Phase 36 (v1.7) | Drift coverage transparency simplified to 2 buckets (probed-OK / unreachable); 4-bucket arrives in Phase 37 |
| Drift handler returns precondition error on `baselines_available == 0` | Drift handler returns successful empty result on zero candidate rows | Phase 36 D-03 | DRFT-12 SC-2 (no env vars set → successful scan) becomes satisfiable |
| Proxmox cred resolution implicit via `PROXMOX_HOST` env var on drift path | `resolve_proxmox_credentials(hostname)` per row via `get_proxmox_client` funnel | Phase 36 D-09/D-09b | Drift inherits Phase 34 cluster-scope keyring story |
| `update_baseline_after_mutation` hook on `create_proxmox_vm` / `create_proxmox_lxc` / `clone_proxmox_vm` success | No hook; sitemap-update lifecycle hooks deferred to v1.7.1 LIFE-01..04 | Phase 36 D-11 | Cleaner separation of concerns; mutation tools don't write to a baseline data layer |

**Deprecated/outdated:**
- `drift_baselines` SQLite table — table dropped post-Phase 36; only the migration step retains the literal string for the drop SQL.
- `_diff_vm_config(baseline, live)` helper — deleted (D-11a). Phase 39's changed-detection (DRFT-19) will introduce a different helper that compares sitemap fingerprint fields against live probes — different shape, different field set.
- `CONFIG_DRIFT_FIELDS = ["cores", "memory", "sockets", "net0", "net1", "net2"]` constant — deleted (no callers after `_diff_vm_config` removed).
- `update_baseline_after_mutation` async function — deleted (D-11). Lifecycle hooks land in v1.7.1.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Postgres `init_schema` does not create `drift_baselines` | Code Examples / Standard Stack | LOW — verified by reading `database.py:595-665`. CONTEXT.md says the same. [VERIFIED] |
| A2 | The four `update_baseline_after_mutation` mock patches in `test_proxmox_api.py` (lines 1784, 1825, 1854, 1893) will fail with `AttributeError` after D-11 | Pitfall 1 | LOW — this is `unittest.mock.patch` standard behavior; `target` resolution happens at patch-application via `_get_target` on the module attribute lookup [VERIFIED via `unittest.mock` docs and Python 3.12 source] |
| A3 | `tests/test_proxmox_baseline_hooks.py` is fully orphaned by D-11 (no other test imports from it) | Pitfall 2 | LOW — verified by reading the entire 170-line file; no helpers, no fixtures shared with other tests [VERIFIED] |
| A4 | `_HOST_CLUSTER_CACHE` makes the second `resolve_proxmox_credentials` call effectively free | Code Examples / scan_drift skeleton | MEDIUM — verified by reading `proxmox_api.py:243-265` (cache lookup) and `proxmox_api.py:315` (cache write on cluster MATCH). The cache only fires on cluster-scope hits; per-node hits at tier 1 (lines 222-240) don't go through the cache but they're already a single-pass operation [VERIFIED] |
| A5 | Tagging by symbol-name (rather than by line number) handles CONTEXT.md's ±2 line drift cleanly | Pitfall 3 | LOW — Python class/function deletion by AST identifier is unambiguous; line numbers are advisory |

**No `[ASSUMED]` claims remain** — all factual claims about the codebase are tagged `[VERIFIED]` via direct code reads.

## Open Questions

1. **Should the AST guards land in `tests/test_ast_regression.py` or a new `tests/test_drift_baselines_removed.py`?**
   - What we know: CONTEXT.md D-12 recommends a new file (Claude's discretion). Existing project convention is to consolidate in `test_ast_regression.py` (extended through Phase 33/33.1/35).
   - What's unclear: planner preference; both are CONTEXT-acceptable.
   - Recommendation: extend `test_ast_regression.py`. Single-file consolidation gives one discovery point for "all AST guards in this project" and matches the established Phase 35 convention (`test_store_device_matches_on_hostname_alone_phase35` etc. live there).

2. **How should `scan_drift` capture `(scope, cluster_name)` for D-02 telemetry — second resolver call, or new attribute on `ProxmoxAPIClient`?**
   - What we know: `get_proxmox_client` calls the resolver internally and logs the tuple but does not return it. Calling `resolve_proxmox_credentials` again from `scan_drift` is cache-fast (microseconds) but architecturally redundant.
   - What's unclear: Whether the planner is comfortable with the redundant call or wants to thread the tuple through `ProxmoxAPIClient`.
   - Recommendation: second-call approach. It's clean, isolated, and avoids cross-cutting changes to `ProxmoxAPIClient`. The cache hit path makes the cost negligible.

3. **Does `tests/test_drift_wiring.py` survive in any form, or is it fully redundant after the rewrite?**
   - What we know: 124 lines, three test classes (`TestDriftSchemaRegistration`, `TestDriftHandlerRegistration`, `TestDriftAnnotations`). The schema/annotations classes still hold (DRFT-04 inert passthrough preserves `node`/`vm_type`); only the handler-registration test (`test_handler_returns_content_wrapped_dict`) mocks `get_all_drift_baselines.return_value = []` (line 62) which becomes obsolete.
   - What's unclear: Whether the planner prefers full delete-and-rewrite vs surgical update.
   - Recommendation: surgical update. Keep schema + annotation tests verbatim; rewrite only the handler test to mock `get_all_devices` instead of `get_all_drift_baselines`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | runtime | ✓ | 3.12+ (project requirement per CLAUDE.md) | — |
| pytest | unit tests (D-14, D-15 SQLite path) | ✓ | 8.4.1 | — |
| pytest-asyncio | async test support | ✓ | 1.0.0 | — |
| aiohttp | scan_drift probe + ClientError | ✓ | 3.12.13 | — |
| asyncssh | drift_detection.py imports (cleanup may remove this if unused post-rewrite) | ✓ | 2.21.0 | — |
| psycopg2 | D-15 Postgres migration test | optional (POSTGRESQL_AVAILABLE flag in `database.py:15-21`) | psycopg2-binary | Skip Postgres test branch with `pytest.mark.integration` + Docker compose pattern (existing `tests/integration/conftest.py`) |
| Docker | D-15 Postgres integration test | unverified on the dev box (this researcher's session) | — | Test marked `@pytest.mark.integration`; CI runs full integration on GitHub Actions per `.github/workflows/main.yml` |
| ruff | quality gate (per CLAUDE.md) | ✓ | declared in pyproject | — |
| mypy | type check gate | ✓ | declared in pyproject | — |
| bandit | security scan | ✓ | declared in pyproject | — |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** Docker for D-15 Postgres integration test — falls back to CI execution. Local SQLite `:memory:` test of D-15 covers the SQLite migration path without external deps.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.4.1 + pytest-asyncio 1.0.0 [VERIFIED via `uv pip list`] |
| Config file | `pyproject.toml` (project-standard) — no separate pytest.ini |
| Quick run command | `uv run pytest tests/ -m "not integration" -x` [from CLAUDE.md] |
| Full suite command | `uv run pytest` [from CLAUDE.md] |
| Integration command | `uv run pytest tests/integration/ -m integration -v` [from CLAUDE.md] |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DRFT-11 | scan_drift iterates sitemap rows, no parallel-table read | unit | `uv run pytest tests/test_drift_detection.py::TestScanDrift2Bucket -x` | ❌ Wave 0 (rewrite) |
| DRFT-11 | AST guard — no source file outside migration.py references drift_baselines | meta | `uv run pytest tests/test_ast_regression.py::test_no_forbidden_strings_in_source -x` | ✅ extend existing list |
| DRFT-11 | AST guard — drift_detection.py specifically has zero baseline references | meta | `uv run pytest tests/test_ast_regression.py::test_drift_detection_no_baseline_references_phase36 -x` | ❌ Wave 0 |
| DRFT-12 | scan_drift uses resolve_proxmox_credentials (via get_proxmox_client) per row | unit | `uv run pytest tests/test_drift_detection.py::TestScanDrift2Bucket::test_resolves_credentials_per_row -x` | ❌ Wave 0 |
| DRFT-12 | scan_drift never calls os.getenv("PROXMOX_HOST") | meta+manual | covered by D-13 AST guard (drift_detection.py forbids any `PROXMOX_HOST` token); also visible via `scan_drift` log telemetry from `get_proxmox_client.proxmox_api.py:373-378` | ✅ extend D-13 to also forbid "PROXMOX_HOST" string |
| DRFT-12 | scan_drift returns probed-ok bucket with scope and cluster_name from resolver | unit | `uv run pytest tests/test_drift_detection.py::TestScanDrift2Bucket::test_probed_ok_record_shape -x` | ❌ Wave 0 |
| DRFT-12 | scan_drift returns unreachable bucket on aiohttp.ClientError with sanitized error | unit | `uv run pytest tests/test_drift_detection.py::TestScanDrift2Bucket::test_unreachable_on_clienterror -x` | ❌ Wave 0 |
| DRFT-12 | scan_drift silently skips rows that raise CredentialNotFoundError | unit | `uv run pytest tests/test_drift_detection.py::TestScanDrift2Bucket::test_silent_skip_on_credential_not_found -x` | ❌ Wave 0 |
| DRFT-21 | drift_baselines table dropped on SQLite startup migration (idempotent) | unit | `uv run pytest tests/test_migration.py::TestDriftBaselinesDrop::test_sqlite_drop_idempotent -x` | ❌ Wave 0 |
| DRFT-21 | drift_baselines table dropped on Postgres startup migration (idempotent) | integration | `uv run pytest tests/test_migration.py::TestDriftBaselinesDrop::test_postgres_drop_idempotent -m integration -v` | ❌ Wave 0 |
| DRFT-21 | DatabaseAdapter ABC has no upsert_drift_baseline / get_drift_baseline / get_all_drift_baselines | unit | `uv run pytest tests/test_database.py::TestDriftBaselinesRemoved -x` (negative-shape test) OR delete TestDriftBaselines entirely + rely on D-12 AST guard | ❌ Wave 0 |
| SC-3 | grep `drift_baselines` reads/writes — only migration.py | meta | covered by D-12 AST guard | ✅ same as DRFT-11 first row |
| SC-4 | AST meta-test fails CI if any future code path on drift-scan call chain reads from a parallel baseline table | meta | covered by D-12 + D-13 AST guards | ✅ extend `test_ast_regression.py` |
| Empty-sitemap success path (D-03 leak from DRFT-13) | unit | `uv run pytest tests/test_drift_detection.py::TestScanDrift2Bucket::test_empty_sitemap_returns_success -x` | ❌ Wave 0 |
| Filter inertness (D-04) | unit | `uv run pytest tests/test_drift_wiring.py::TestDriftSchemaRegistration::test_drift_tool_schema_properties -x` | ✅ existing test still passes |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/ -m "not integration" -x` (~30s, no Docker)
- **Per wave merge:** `uv run pytest` (full unit suite + integration if Docker available)
- **Phase gate:** Full suite green + manual MCP-client verification of `scan_infrastructure_drift` against a real Proxmox host (per CLAUDE.md DRFT-12 SC-2 — "user calling scan_infrastructure_drift with no Proxmox env vars set sees a successful scan"). Manual step documented in 36-VALIDATION.md.

### Wave 0 Gaps

- [ ] `tests/test_drift_detection.py` — full rewrite for 2-bucket scan; new `TestScanDrift2Bucket` class with mocked `get_all_devices`, `resolve_proxmox_credentials`, and `ProxmoxAPIClient.get` (D-14)
- [ ] `tests/test_drift_wiring.py` — surgical update of `TestDriftHandlerRegistration::test_handler_returns_content_wrapped_dict` to mock `get_all_devices` instead of `get_all_drift_baselines`
- [ ] `tests/test_ast_regression.py` — extend `FORBIDDEN_SOURCE_STRINGS` and `ALLOWED_EXCEPTIONS`; add `test_drift_detection_no_baseline_references_phase36()` (D-12 + D-13)
- [ ] `tests/test_migration.py` — add `TestDriftBaselinesDrop` class with SQLite `:memory:` idempotency test + Postgres `pytest.mark.integration` test (D-15)
- [ ] `tests/test_drift_resource.py` — update sample fixture to 2-bucket shape (Pitfall 5)
- [ ] `tests/test_database.py` — delete `TestDriftBaselines` class (lines 357-468) (D-16)
- [ ] `tests/test_proxmox_baseline_hooks.py` — DELETE entire file (Pitfall 2; not in CONTEXT.md but required)
- [ ] `tests/test_proxmox_api.py` — remove four `patch("...update_baseline_after_mutation")` lines (1784, 1825, 1854, 1893) (Pitfall 1)
- [ ] No framework install needed — pytest 8.4.1 + pytest-asyncio 1.0.0 already declared.

## Project Constraints (from CLAUDE.md)

- **Python 3.12+** with strict typing (mypy enforced)
- **uv** as package manager (`uv run pytest`, `uv sync`)
- **pytest + pytest-asyncio** for tests; `@pytest.mark.asyncio` on async test functions
- **ruff / mypy / bandit** quality gates (`./scripts/quality-check.sh`)
- **Type hints required** on all functions
- **Async-first** for I/O (SSH, network, Proxmox API)
- **`error_handling.py` patterns** for consistent error responses (Phase 36 uses `sanitize_error` from `log_filter.py` re-imported via `error_handling.py:14`)
- **Tool registration** via `tool_schemas/` + `tool_handlers/` + `tool_annotations.py` — Phase 36 modifies existing entries, no new tools (D-17)
- **DO NOT run TestSprite** as part of phase verification (project rule)
- **MCP server communicates via stdio** — handlers must remain thin pass-throughs returning `{"content": [{"type": "text", "text": json.dumps(...)}]}`
- **Pre-commit hooks configured** in `.pre-commit-config.yaml` — quality gates fire on commit

**Memory-derived constraints:**
- Phase 36 is footgun-removal (Bug J dissolution) → AST meta-tests apply (per `feedback_regression_test_scope.md`)
- Keyring is sole source of truth → no `PROXMOX_HOST` env-var fallback on `scan_drift`'s success path (per `project_credential_architecture.md`, codifies CONTEXT D-09b)
- TestSprite credits are limited → Phase 36 verification stays in pytest land (per `feedback_testsprite_runs.md`)

## Sources

### Primary (HIGH confidence)
- `src/homelab_mcp/drift_detection.py` (entire file, 280 lines) — verified scan_drift signature, _diff_vm_config impl, update_baseline_after_mutation impl, CONFIG_DRIFT_FIELDS constant
- `src/homelab_mcp/database.py` (entire file, 1009 lines) — verified DatabaseAdapter ABC drift methods at 69-94, SQLiteAdapter init_schema CREATE block at 205-222, SQLiteAdapter drift methods at 451-527, PostgreSQLAdapter init_schema (no drift_baselines CREATE) at 595-665, PostgreSQLAdapter NotImplementedError stubs at 917-939
- `src/homelab_mcp/migration.py` (entire file, 738 lines) — verified Phase 33 ssh_credentials drop pattern (37-62 SQLite, 281-305 Postgres), Phase 35 zombie-dedup (88-132), Phase 35 stale-UNIQUE rebuild (134-222), drift_baselines auto-create CREATE block at 224-247
- `src/homelab_mcp/tool_handlers/drift_handlers.py` (entire file, 41 lines) — verified handle_scan_infrastructure_drift precondition at 24-37
- `src/homelab_mcp/tool_handlers/proxmox_handlers.py` (entire file, 279 lines) — verified update_baseline_after_mutation imports + try/except at handle_create_proxmox_lxc (116-153), handle_create_proxmox_vm (156-192), handle_clone_proxmox_vm (195-224)
- `src/homelab_mcp/tool_schemas/drift_tools_schema.py` (entire file, 28 lines) — verified DRIFT_TOOLS schema description at 5-9
- `src/homelab_mcp/proxmox_api.py:194-396` — verified resolve_proxmox_credentials signature (`tuple[str, Literal["node", "cluster"], str | None]`), the per-node→cluster→error tier order, _HOST_CLUSTER_CACHE behavior at 243-265 + 315, get_proxmox_client resolver call at 370-378
- `src/homelab_mcp/log_filter.py` (entire file, 77 lines) — verified sanitize_error implementation at 64-76, _SENSITIVE_PATTERNS at 16-33
- `src/homelab_mcp/error_handling.py:14` — verified sanitize_error re-import from log_filter
- `src/homelab_mcp/resource_readers.py:127-138` — verified read_drift_resource shape
- `src/homelab_mcp/server.py:78-83, 171, 445` — verified set_latest_drift_report / get_latest_drift_report / DRIFT_SCAN_TOOLS
- `tests/test_ast_regression.py` (entire file, 553 lines) — verified canonical AST meta-test pattern, FORBIDDEN_SOURCE_STRINGS list, ALLOWED_EXCEPTIONS dict, _collect_string_literals + _collect_name_and_attr_ids helpers
- `tests/test_drift_detection.py` (entire file, 248 lines) — verified existing TestScanDriftReport / TestConfigDrift / TestStateDrift / TestBaselineUpdate test classes; full rewrite needed
- `tests/test_drift_wiring.py` (entire file, 124 lines) — verified TestDriftSchemaRegistration / TestDriftHandlerRegistration / TestDriftAnnotations
- `tests/test_drift_resource.py` (entire file, 90 lines) — verified sample-payload shape mismatch (Pitfall 5)
- `tests/test_proxmox_baseline_hooks.py` (entire file, 170 lines) — verified DRFT-05 hook test scope; full deletion required (Pitfall 2)
- `tests/test_proxmox_api.py:1770-1905` — verified four `update_baseline_after_mutation` patch lines at 1784/1825/1854/1893 (Pitfall 1)
- `tests/test_database.py:340-468` — verified TestDriftBaselines class scope (D-16 deletion)
- `tests/test_migration.py` (entire file, 668 lines) — verified migration test infrastructure for D-15
- `.planning/phases/36-drift-sitemap-foundation/36-CONTEXT.md` (entire file, 295 lines) — locked design
- `.planning/REQUIREMENTS.md` — DRFT-11/12/21 + Out-of-Scope coverage
- `.planning/STATE.md` — Phase 36 ordering + carry-forward constraints
- `.planning/ROADMAP.md` — SC-1..SC-4

### Secondary (MEDIUM confidence)
- `.planning/milestones/v1.6-phases/33-keyring-single-source-of-truth/33-CONTEXT.md` §Regression Guards (read references-only; not re-verified for this research)
- `.planning/milestones/v1.6-phases/34-cluster-scoped-proxmox-credentials/34-CONTEXT.md` §D-09 (read references-only)
- `.planning/milestones/v1.6-phases/35-sitemap-discovery-reliability-fix-discover-and-map-field-los/35-CONTEXT.md` §D-01 (read references-only)

### Tertiary (LOW confidence)
- None — all factual claims verified directly against the codebase.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified at exact versions via `uv pip list`
- Architecture: HIGH — every CONTEXT.md-cited code location was opened and verified
- Pitfalls: HIGH — Pitfalls 1, 2, 5 surfaced during verification (not from training); Pitfalls 3, 4 are mechanical observations from reading the code
- Test inventory: HIGH — every test file in `tests/` enumerated; drift-related coverage scoped exhaustively via grep + targeted file reads
- Migration shape: HIGH — Phase 33 + Phase 35 precedents read end-to-end; D-05 reuse is mechanical

**Research date:** 2026-04-25
**Valid until:** 2026-05-25 (30-day window — codebase is stable; only the line numbers may drift slightly as other phases land. Symbol-name resolution makes the research robust to minor line shifts.)
