# Phase 35: Sitemap + Discovery Reliability - Pattern Map

**Mapped:** 2026-04-23
**Files analyzed:** 7 source + 4 test targets
**Analogs found:** 7 / 7 (all in-tree, same module or sibling)

## File Classification

| File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/homelab_mcp/database.py` (SQLite `store_device`) | schema + writer | CRUD | self — existing `store_device` match/update/insert shape | exact (in-place edit) |
| `src/homelab_mcp/database.py` (Postgres `store_device`) | schema + writer | CRUD | self — existing Postgres branch | exact (in-place edit, mirrors SQLite) |
| `src/homelab_mcp/database.py` (SQLite `init_schema`) | schema | DDL | self — `network_interfaces TEXT` JSON column (line 156) | exact (JSON-col template) |
| `src/homelab_mcp/database.py` (Postgres `init_schema`) | schema | DDL | self — `system_info JSONB` / `network_interfaces JSONB` (line 527–528) | exact (JSONB template) |
| `src/homelab_mcp/ssh_tools.py` (`ssh_discover_system`) | upstream producer | request-response (multi-subprocess) | self — each `conn.run(...)` already uses `check=False` + `exit_status` guard | exact (wrap each call) |
| `src/homelab_mcp/ssh_tools.py` (decorator line 224) | decorator arg | — | self — other `@ssh_connection_wrapper(timeout_seconds=N)` call sites | exact (arg bump) |
| `src/homelab_mcp/sitemap.py` (`parse_discovery_output`) | reader / transformer | transform | self — existing `"network"` → `network_interfaces` JSON write (line 97–98) | exact (add 3 more) |
| `src/homelab_mcp/sitemap.py` (`NetworkDevice`) | dataclass | — | self — existing `network_interfaces: str \| None = None` (line 36) | exact (3 new fields) |
| `src/homelab_mcp/sitemap.py` (`bulk_discover_and_store`) | orchestrator | batch | Phase 34 Proxmox concurrent-probe (pattern from `<code_context>`) | role-match (adapt `gather + Semaphore`) |
| `src/homelab_mcp/sitemap.py` (`analyze_network_topology`, `suggest_deployments`) | analyzer | transform | self — correct guard at line 200–201 is exemplar | exact (replace bad sites) |
| `src/homelab_mcp/migration.py` (new dedup + ALTER TABLE step) | one-time migration | schema + data | self — Phase 33 D-01 `DROP TABLE IF EXISTS ssh_credentials` block (line 27–51) | exact (copy block shape) |
| `tests/test_ast_regression.py` (new D-14/D-15/D-16 cases) | meta-test | AST scan | self — existing `test_no_forbidden_strings_in_source` (line 140–178) + `test_no_username_mcp_admin_default_in_function_signatures` (line 206–277) | exact (copy scanner shape) |
| `tests/test_sitemap.py` / `tests/test_database.py` / `tests/test_ssh_tools.py` (or new `tests/test_discovery_reliability.py`) | functional test | unit + integration | self — existing `sitemap` fixture + JSON sample fixtures | exact (extend with new-field + null-threshold + timeout cases) |

## Pattern Assignments

### `src/homelab_mcp/database.py` — SQLite `store_device` (D-01 upsert-key change)

**Analog:** itself, lines 210–305.

**Current match clause the planner MUST replace** (`database.py:218-225`):
```python
# Check if device exists
cursor.execute(
    """
    SELECT id FROM devices
    WHERE hostname = ? AND connection_ip = ?
""",
    (device_data["hostname"], device_data["connection_ip"]),
)
```

**D-01 target shape** (planner writes this — hostname-only match):
```python
hostname = device_data["hostname"]
# D-01a: degenerate-hostname fallback — keep legacy (hostname, connection_ip)
# match so failed discoveries do not collapse into one poisoned bucket.
if hostname in (None, "", "unknown"):
    cursor.execute(
        "SELECT id FROM devices WHERE hostname = ? AND connection_ip = ?",
        (hostname, device_data["connection_ip"]),
    )
else:
    cursor.execute(
        "SELECT id FROM devices WHERE hostname = ?",
        (hostname,),
    )
```

**Cross-file invariant:** The existing `UNIQUE(hostname, connection_ip)` constraint at `database.py:162` is **incompatible** with hostname-only upsert once a host's IP changes — the UPDATE path is safe (no uniqueness violation on `UPDATE … WHERE id=?`), but the constraint itself is now stale. Planner's call whether to drop the UNIQUE via the Phase 35 migration step (recommended: drop the constraint, drop the `idx_devices_hostname_ip` composite index, add a new non-unique index on `hostname`). Parallel consideration applies to Postgres `UNIQUE(hostname, connection_ip)` at `database.py:532`.

---

### `src/homelab_mcp/database.py` — Postgres `store_device` (D-01 mirror)

**Analog:** itself, lines 580–678.

**Current match clause the planner MUST replace** (`database.py:623-630`):
```python
# Check if device exists
cursor.execute(
    """
    SELECT id FROM devices
    WHERE hostname = %s AND connection_ip = %s
""",
    (device_data["hostname"], device_data["connection_ip"]),
)
```

**D-01 target shape** (same branching, `%s` placeholders instead of `?`):
```python
hostname = device_data["hostname"]
if hostname in (None, "", "unknown"):
    cursor.execute(
        "SELECT id FROM devices WHERE hostname = %s AND connection_ip = %s",
        (hostname, device_data["connection_ip"]),
    )
else:
    cursor.execute(
        "SELECT id FROM devices WHERE hostname = %s",
        (hostname,),
    )
```

**Cross-file invariant:** Both adapters mirror. A Phase 35 PR that touches only the SQLite branch will leave `PostgreSQLAdapter.store_device` re-producing zombie rows on the Postgres path — the D-14 AST meta-test must scan BOTH functions.

---

### `src/homelab_mcp/database.py` — SQLite `init_schema` (D-09c ADD COLUMN)

**Analog:** itself, lines 128–208. The `network_interfaces TEXT` column (line 156) is the **template** for D-09b's three new JSON-TEXT columns.

**Existing JSON-column template** (`database.py:156`):
```python
network_interfaces TEXT,
```

**D-09c target — three new JSON-encoded TEXT columns** (added in the same table):
```python
usb_devices TEXT,
pci_devices TEXT,
block_devices TEXT,
```

**Caveat:** `CREATE TABLE IF NOT EXISTS` in `init_schema` does NOT add columns to a pre-existing table. The D-09c column additions MUST land in `migration.py` as `ALTER TABLE devices ADD COLUMN …` statements wrapped in `sqlite_master`-existence guards (SQLite tolerates no `IF NOT EXISTS` on ADD COLUMN, so the guard has to come from a prior `PRAGMA table_info(devices)` scan).

---

### `src/homelab_mcp/database.py` — Postgres `init_schema` (D-09c mirror)

**Analog:** itself, lines 511–578. The Postgres path already funnels all hardware info through `system_info JSONB DEFAULT '{}'` (line 527) — there are NO discrete `cpu_cores` / `memory_total` columns to mirror.

**Two possible planner moves:**
1. **Keep the JSONB shape** — extend `store_device`'s `system_info` dict (line 589–610) with three new keys (`"usb_devices"`, `"pci_devices"`, `"block_devices"`) and mirror the flattening in `get_all_devices` (line 700–719). No schema change; the JSONB column absorbs the new keys. **Recommended** — matches the existing Postgres pattern.
2. **Add three JSONB columns** parallel to SQLite. Requires `ALTER TABLE` in migration + `RealDictCursor` selection updates. More invasive.

Planner picks; preference for option 1 so the adapter asymmetry does not grow.

---

### `src/homelab_mcp/ssh_tools.py` — `ssh_discover_system` (D-05 per-cmd timeout, D-06 partial, D-08 wrapper bump, D-09 field names)

**Analog:** itself, lines 224–438.

**Current decorator line** (`ssh_tools.py:224` — D-08 changes `30.0` → `120.0`):
```python
@ssh_connection_wrapper(timeout_seconds=30.0)
@retry_on_failure(max_retries=1, delay_seconds=1.0)
async def ssh_discover_system(
```

**Representative `conn.run(...)` pattern D-05 must wrap** (`ssh_tools.py:267-269`, one of ten):
```python
cpu_result = await conn.run("nproc", check=False)
if cpu_result.exit_status == 0 and cpu_result.stdout:
    cpu_info["count"] = int(cast(str, cpu_result.stdout).strip())
```

**D-05 target shape — small helper pattern** (matches `_sudo_run` idiom at `ssh_tools.py:441` and `_resolve_username_from_registry` at `ssh_tools.py:40`):
```python
async def _run_with_timeout(
    conn: asyncssh.SSHClientConnection,
    command: str,
    *,
    cmd_name: str,
    timed_out: list[str],
    timeout: float = 10.0,
) -> "asyncssh.SSHCompletedProcess | None":
    """Run a discovery probe with a per-command timeout.

    Returns the SSHCompletedProcess on success, or None on timeout — caller
    leaves the corresponding field unset so the field lands as None in the
    final JSON. Appends ``cmd_name`` to ``timed_out`` for D-06 reporting.
    """
    try:
        return await asyncio.wait_for(
            conn.run(command, check=False), timeout=timeout
        )
    except TimeoutError:
        logger.debug(
            "SSH discovery probe %r exceeded %.1fs on connection; field skipped",
            cmd_name, timeout,
        )
        timed_out.append(cmd_name)
        return None
```

Call-site shape — each `conn.run(...)` becomes:
```python
timed_out_commands: list[str] = []
cpu_result = await _run_with_timeout(conn, "nproc", cmd_name="nproc", timed_out=timed_out_commands)
if cpu_result and cpu_result.exit_status == 0 and cpu_result.stdout:
    cpu_info["cores"] = int(cast(str, cpu_result.stdout).strip())  # D-09a: "cores" not "count"
```

**Current return shape D-06 extends** (`ssh_tools.py:430-438`):
```python
return json.dumps(
    {
        "status": "success",
        "hostname": actual_hostname,
        "connection_ip": hostname,
        "data": system_info,
    },
    indent=2,
)
```

**D-06 target — conditionally inject `partial` + `timed_out_commands`**:
```python
payload: dict[str, Any] = {
    "status": "success",
    "hostname": actual_hostname,
    "connection_ip": hostname,
    "data": system_info,
}
if timed_out_commands:
    payload["partial"] = True
    payload["timed_out_commands"] = list(timed_out_commands)
return json.dumps(payload, indent=2)
```

**D-09a field-name alignment at producer** (the three anti-patterns producing the schema mismatch):

1. `ssh_tools.py:269` writes `cpu_info["count"]` — must become `cpu_info["cores"]` so `parse_discovery_output` at `sitemap.py:74` (`cpu_info.get("cores", 0)`) actually finds it.

2. `ssh_tools.py:281-292` — `free -b` emits only `total` + `used` as raw ints; reader at `sitemap.py:81-84` expects string-typed `total`/`used`/`free`/`available`. Producer must (a) compute `free = total - used`, (b) parse the `available` column from `free -b` (column 7 of the `Mem:` row), (c) format all four as strings — GiB like `"16Gi"` — to match the reader's `_parse_memory_gb` at `sitemap.py:220`.

3. `ssh_tools.py:295-306` — `df -B1 /` emits only `total`/`used`/`available` ints; reader at `sitemap.py:88-94` expects `filesystem`, `size`, `use_percent`, `mount`. Producer must switch to `df -B1 -T /` (the `-T` exposes filesystem type as col 2, shifting the other indices), compute `use_percent` as `f"{used * 100 // total}%"`, and emit `mount` from the final column. Field names on emit: `filesystem`, `size` (not `total`), `used`, `available`, `use_percent`, `mount`.

4. `usb_devices` / `pci_devices` / `block_devices` (lines 346–428) already emit under the correct names; reader side is the gap.

---

### `src/homelab_mcp/sitemap.py` — `NetworkDevice` (D-09b dataclass extension)

**Analog:** itself, lines 16–39. `network_interfaces: str | None = None` (line 36, "# JSON string" comment) is the template.

**Three new fields to add** (mirroring `network_interfaces`):
```python
usb_devices: str | None = None       # JSON string
pci_devices: str | None = None       # JSON string
block_devices: str | None = None     # JSON string
```

---

### `src/homelab_mcp/sitemap.py` — `parse_discovery_output` (D-09 reader extension)

**Analog:** itself, lines 54–117. The `network_interfaces` JSON write (line 97–98) is the template.

**Existing JSON-write template** (`sitemap.py:97-98`):
```python
# Network interfaces (store as JSON)
if "network" in discovery_data:
    device.network_interfaces = json.dumps(discovery_data["network"])
```

**D-09b target — three parallel writes**, inserted directly after line 98:
```python
# USB devices (store as JSON)
if "usb_devices" in discovery_data:
    device.usb_devices = json.dumps(discovery_data["usb_devices"])

# PCI devices (store as JSON)
if "pci_devices" in discovery_data:
    device.pci_devices = json.dumps(discovery_data["pci_devices"])

# Block devices (store as JSON)
if "block_devices" in discovery_data:
    device.block_devices = json.dumps(discovery_data["block_devices"])
```

**Corresponding reader-side JSON decode** in `get_all_devices` (`database.py:320-324`, SQLite):
```python
# Parse network interfaces JSON
if device_dict.get("network_interfaces"):
    try:
        device_dict["network_interfaces"] = json.loads(device_dict["network_interfaces"])
    except json.JSONDecodeError:
        device_dict["network_interfaces"] = []
```

D-09b adds three parallel decode blocks directly after this one (same try/except shape, same `[]` fallback). The Postgres `get_all_devices` at `database.py:700-719` — under the recommended JSONB-extend option — receives the new keys for free via the `system_info` JSONB flatten.

---

### `src/homelab_mcp/database.py` — SQLite `store_device` UPDATE/INSERT column-list extension (D-09c write path)

**Analog:** itself — the existing `network_interfaces` placement in the UPDATE column list (line 238) and the INSERT column list (line 273).

The three new columns (`usb_devices`, `pci_devices`, `block_devices`) must be threaded into:
- The UPDATE `SET` clause (lines 232–241) — add `usb_devices = ?, pci_devices = ?, block_devices = ?` immediately after `network_interfaces = ?`.
- The UPDATE values tuple (lines 242–263) — add three `device_data.get(...)` calls immediately after `device_data.get("network_interfaces")`.
- The INSERT column list (lines 269–275) — same slot.
- The INSERT values tuple (lines 277–299) — same slot.
- The `VALUES (?, ?, ?, ?, ...)` placeholder count (line 275) goes from 20 to 23 `?`.

**Parallel extension applies to Postgres `store_device`**: the `system_info` dict (line 589–610) gets three new keys (`"usb_devices"`, `"pci_devices"`, `"block_devices"`) — they ride inside the existing JSONB column, no new placeholders.

---

### `src/homelab_mcp/sitemap.py` — `bulk_discover_and_store` (D-07 parallelism)

**Analog:** itself, lines 349–391 (current serial loop).

**Current serial loop the planner MUST replace** (`sitemap.py:354-371`):
```python
for i, target in enumerate(targets):
    await emit_progress(
        "info",
        f"Discovering {target.get('hostname', 'unknown')} ({i + 1}/{total})",
    )
    try:
        result = await discover_and_store(
            sitemap,
            target["hostname"],
            target.get("username"),
            target.get("password"),
            target.get("key_path"),
            target.get("port", 22),
        )
        results.append(json.loads(result))
    except Exception as e:
        results.append(
            {
                "status": "error",
                "hostname": target.get("hostname", "unknown"),
                "error": sanitize_error(e),
            }
        )
```

**D-07 target — `Semaphore(10)` + `gather(return_exceptions=True)`**:
```python
semaphore = asyncio.Semaphore(10)
completed = 0  # increments by completion order, not target order (D-07a)
lock = asyncio.Lock()

async def _discover_one(target: dict[str, Any]) -> dict[str, Any]:
    nonlocal completed
    hostname_label = target.get("hostname", "unknown")
    async with semaphore:
        async with lock:
            completed += 1
            local_i = completed
        await emit_progress("info", f"Discovering {hostname_label} ({local_i}/{total})")
        try:
            result = await discover_and_store(
                sitemap,
                target["hostname"],
                target.get("username"),
                target.get("password"),
                target.get("key_path"),
                target.get("port", 22),
            )
            await emit_progress("info", f"Completed {hostname_label} ({local_i}/{total})")
            return json.loads(result)
        except Exception as e:
            return {
                "status": "error",
                "hostname": hostname_label,
                "error": sanitize_error(e),
            }

results = await asyncio.gather(
    *[_discover_one(t) for t in targets],
    return_exceptions=False,  # _discover_one already catches; no bare exceptions reach gather
)
```

**Caveat on `return_exceptions`:** CONTEXT D-07 specifies `return_exceptions=True`. Because `_discover_one` already converts every exception to an error-dict before returning, `return_exceptions=True` is functionally equivalent here — the belt-and-suspenders guarantee against a surprise raise from inside `emit_progress` or `json.loads`. Planner picks; the AST meta-test D-15 does not constrain this.

**Imports:** `bulk_discover_and_store` currently does not import `asyncio` at module scope (`sitemap.py` imports none of asyncio). Planner must add `import asyncio` at the top of `sitemap.py`.

---

### `src/homelab_mcp/sitemap.py` — `analyze_network_topology` + `suggest_deployments` (D-10..D-13 null-threshold fix)

**Analog:** itself, lines 200–201 — the CORRECT guard shape that planner must replicate at the two bad sites.

**Exemplar — keep as reference** (`sitemap.py:200-201`):
```python
cpu_cores = device.get("cpu_cores")
if cpu_cores is not None and cpu_cores <= 2:
```

**False-negative site to fix** (`sitemap.py:255-256`):
```python
# CURRENT (broken):
cpu_cores = device.get("cpu_cores") or 0
if cpu_cores >= 4:
```
**Target (D-13: no silent coercion):**
```python
cpu_cores = device.get("cpu_cores")
if cpu_cores is not None and cpu_cores >= 4:
```

**False-positive bug site to fix** (`sitemap.py:296-297`):
```python
# CURRENT (broken — None → 0 → classified as "<= 2" upgrade candidate):
cpu_cores = device.get("cpu_cores") or 0
if cpu_cores <= 2:
```
**Target (D-13):**
```python
cpu_cores = device.get("cpu_cores")
if cpu_cores is not None and cpu_cores <= 2:
```

**Existing `logger.debug` skip template** (`sitemap.py:193-197`, reference for D-12 log-level consistency):
```python
except (ValueError, AttributeError):
    logger.debug(
        "Skipping device %s in topology analysis: unable to parse disk usage",
        device.get("hostname", "unknown"),
    )
```

**D-11 optional helper** (small private helper idiom — matches `_parse_memory_gb` at `sitemap.py:220` and the `_sudo_run` / `_resolve_username_from_registry` pattern):
```python
def _has_threshold_data(device: dict[str, Any], *fields: str) -> bool:
    """D-11: gate a threshold comparison on all required fields being non-None/non-empty.

    Truthy-empty-string is treated as missing (consistent with existing
    ``if device.get("disk_use_percent"):`` truthy guards at sitemap.py:179, 269).
    """
    for f in fields:
        value = device.get(f)
        if value is None or value == "":
            return False
    return True
```

Usage at the three sites:
```python
if _has_threshold_data(device, "cpu_cores", "memory_total") and device["cpu_cores"] <= 2:
    ...
```

**D-10 / D-13 invariant:** `cpu_cores or 0` and `memory_total or ""` never reappear on threshold-field reads. The D-16 AST meta-test enforces this.

---

### `src/homelab_mcp/migration.py` — new one-time startup step (D-02 zombie dedup + D-09c ALTER TABLE)

**Analog:** itself, lines 27–51 (Phase 33 D-01 `DROP TABLE IF EXISTS ssh_credentials` block).

**Exemplar block to copy shape from** (`migration.py:27-51`):
```python
# D-01: Drop legacy ssh_credentials table if it still exists (v1.6 cleanup).
# Keyring is now the single source of truth for remote credentials (CRED-04).
cursor = adapter.connection.cursor()
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
    adapter.connection.commit()
    applied_migrations.append("drop_ssh_credentials_table")
    import sys  # noqa: PLC0415
    print(
        "Dropped legacy ssh_credentials table (v1.6: keyring is now the sole credential store)",
        file=sys.stderr,
    )
```

**Key properties the new Phase 35 block MUST preserve from this shape:**
1. **Idempotent:** guard via `SELECT FROM sqlite_master` / Postgres `information_schema.tables` / `PRAGMA table_info(devices)` — a second run observes "nothing to do" and exits silently.
2. **Both adapters:** the same block runs in `run_sqlite_migrations` (line 15) AND `run_postgres_migrations` (line 82). Omitting the Postgres twin is the #1 regression risk — planner MUST update both.
3. **Append to `applied_migrations`:** the list is the audit trail; emit identifiers like `"dedupe_zombie_device_rows"` and `"add_usb_pci_block_columns"` on success.
4. **Ordering:** Phase 33 D-01 drop runs first (already in place, don't touch); Phase 35 dedup + ALTER runs AFTER the Phase 33 drop but BEFORE `drift_baselines` creation (line 54) is irrelevant since the two don't interact. Place the new Phase 35 block immediately before the `drift_baselines` block.

**D-02 dedup block — SQLite shape:**
```python
# D-02 (Phase 35): collapse duplicate (hostname, connection_ip) rows into a
# single row per hostname. Keep the row with the greatest last_seen; merge
# non-null values from siblings into the kept row; delete the siblings.
# Skip degenerate hostnames ('', 'unknown') — those are Phase 33-pre-existing
# distinct-error rows and must NOT be collapsed.
cursor.execute(
    """
    SELECT hostname, COUNT(*) AS n
    FROM devices
    WHERE hostname NOT IN ('', 'unknown') AND hostname IS NOT NULL
    GROUP BY hostname
    HAVING n > 1
    """
)
duplicate_hostnames = [row[0] for row in cursor.fetchall()]
for hostname in duplicate_hostnames:
    cursor.execute(
        "SELECT * FROM devices WHERE hostname = ? ORDER BY last_seen DESC",
        (hostname,),
    )
    rows = cursor.fetchall()  # sqlite3.Row — first row = most-recent (keep)
    # merge non-null values from siblings[1:] into merged dict; UPDATE winner;
    # DELETE siblings by id. (planner writes the merge body.)
if duplicate_hostnames:
    adapter.connection.commit()
    applied_migrations.append("dedupe_zombie_device_rows")
```

**D-09c column-add block — SQLite shape:**
```python
# D-09c (Phase 35): ALTER TABLE to add usb_devices / pci_devices / block_devices
# JSON-TEXT columns on pre-existing devices rows. New rows get these columns
# from init_schema going forward; legacy rows receive NULL until re-discovered.
cursor.execute("PRAGMA table_info(devices)")
existing_columns = {row[1] for row in cursor.fetchall()}  # row[1] = column name
for new_col in ("usb_devices", "pci_devices", "block_devices"):
    if new_col not in existing_columns:
        cursor.execute(f"ALTER TABLE devices ADD COLUMN {new_col} TEXT")
        applied_migrations.append(f"add_column_{new_col}")
if any(col.startswith("add_column_") for col in applied_migrations[-3:]):
    adapter.connection.commit()
```

**Postgres twins:** same two blocks in `run_postgres_migrations`, with:
- `information_schema.tables` / `information_schema.columns` existence checks instead of `sqlite_master` / `PRAGMA`.
- `psycopg2.extras.RealDictCursor` style if planner prefers named access (the existing Phase 33 D-01 Postgres block uses positional `cursor.fetchone()[0]` — keep consistent).
- The JSONB-extension recommendation (see Postgres `init_schema` section above) makes the column-add block a **no-op on Postgres** — the new keys land inside the existing `system_info JSONB` column without schema change. Planner's choice.

---

### `src/homelab_mcp/error_handling.py` — `ssh_connection_wrapper` (unchanged, confirm shape)

**Analog:** itself, lines 229–285.

**Key line the per-call override path already supports** (`error_handling.py:241`):
```python
effective_timeout = kwargs.pop("timeout", None) or timeout_seconds
```

This means D-08's bump from `30.0` → `120.0` on the decorator line (`ssh_tools.py:224`) is a plain argument edit — no machinery change in `error_handling.py`. A test wanting to override to, say, `5.0` in a unit test can pass `timeout=5.0` as a kwarg and `effective_timeout` picks it up. Planner does NOT touch `error_handling.py`.

---

### `src/homelab_mcp/tool_handlers/network_handlers.py` — unchanged (confirm thin-delegation)

**Analog:** itself, lines 10–24. No changes.

**Current shape** (`network_handlers.py:10-15`):
```python
async def handle_discover_and_map(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle discover_and_map tool."""
    validate_hostname(arguments["hostname"])
    sitemap = NetworkSiteMap()
    result = await discover_and_store(sitemap, **arguments)
    return {"content": [{"type": "text", "text": result}]}
```

Because the handler is a thin `await discover_and_store(...)` → `text` envelope, the new `partial` / `timed_out_commands` keys in the D-06 JSON response flow through verbatim — no handler edit needed. Phase 35 preserves `<domain> out-of-scope: no MCP tool surface changes`.

---

### Tests — `tests/test_ast_regression.py` extension (D-14 + D-15 + D-16)

**Analog:** itself, lines 140–178 (`test_no_forbidden_strings_in_source`) and lines 206–277 (`test_no_username_mcp_admin_default_in_function_signatures`).

**D-14 target — AST scan for the forbidden SQL pattern in `store_device`:**

```python
# D-14 (Phase 35): store_device match clause must not re-introduce
# `hostname = ? AND connection_ip = ?` (or %s equivalent) as the primary
# match. The degenerate-hostname fallback is allowed, but the non-degenerate
# branch MUST match on hostname alone.
def test_store_device_matches_on_hostname_alone() -> None:
    src_root = Path(__file__).parent.parent / "src" / "homelab_mcp"
    db_source = (src_root / "database.py").read_text(encoding="utf-8")

    # Find both store_device function bodies (SQLite + Postgres adapters).
    tree = ast.parse(db_source, filename="database.py")
    store_device_funcs = [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "store_device"
    ]
    assert len(store_device_funcs) == 2, (
        "Expected 2 store_device functions (SQLite + Postgres adapters)"
    )

    for func in store_device_funcs:
        # Collect every string constant inside the function body.
        body_strings = [
            node.value
            for node in ast.walk(func)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        ]
        hostname_only_found = any(
            "WHERE hostname = ?" in s or "WHERE hostname = %s" in s
            for s in body_strings
            if "AND connection_ip" not in s
        )
        assert hostname_only_found, (
            f"store_device at {func.lineno}: must contain a hostname-only "
            f"SELECT clause (D-14 — Phase 35 zombie-row fix regressed)"
        )
```

**D-15 target — AST scan for unwrapped `conn.run(...)`:**

```python
# D-15 (Phase 35): every conn.run() call inside ssh_discover_system must
# be wrapped by asyncio.wait_for OR the per-cmd helper (_run_with_timeout).
# A bare `conn.run(cmd, check=False)` outside either wrapper is a regression.
def test_ssh_discover_system_wraps_every_conn_run() -> None:
    src_root = Path(__file__).parent.parent / "src" / "homelab_mcp"
    source = (src_root / "ssh_tools.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="ssh_tools.py")

    target = next(
        (n for n in ast.walk(tree)
         if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
         and n.name == "ssh_discover_system"),
        None,
    )
    assert target is not None, "ssh_discover_system not found"

    # Walk the function body; find every Call to conn.run and verify it is
    # inside either asyncio.wait_for(...) or _run_with_timeout(...).
    violations: list[int] = []
    for node in ast.walk(target):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "run"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "conn"):
            continue
        # Walk up via ast.parent (planner wires up parent pointers) and
        # verify an enclosing Call whose .func resolves to asyncio.wait_for
        # or _run_with_timeout exists. Fail if bare.
        ...  # planner writes the parent-walk

    assert not violations, (
        "Phase 35 D-15 regression: bare conn.run() calls at lines "
        + ", ".join(map(str, violations))
    )
```

**D-16 target — AST scan for forbidden coercion patterns in analyzer bodies:**

```python
# D-16 (Phase 35): cpu_cores / memory_total / disk_use_percent must never
# be coerced with `or 0` / `or ""` in analyze_network_topology or
# suggest_deployments bodies. Phase 35 D-13 removed these; the test
# prevents re-introduction.
FORBIDDEN_COERCION_FIELDS = {"cpu_cores", "memory_total", "disk_use_percent"}

def test_no_threshold_coercion_in_analyzer_bodies() -> None:
    src_root = Path(__file__).parent.parent / "src" / "homelab_mcp"
    source = (src_root / "sitemap.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="sitemap.py")

    analyzers = [
        n for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.name in ("analyze_network_topology", "suggest_deployments")
    ]
    assert len(analyzers) == 2

    violations: list[str] = []
    for func in analyzers:
        # Look for BoolOp(Or, [left, Constant(0 | "")]) where `left` is a
        # reference to one of the threshold fields (device.get("...") or a
        # Name bound to the .get call).
        for node in ast.walk(func):
            if not (isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or)):
                continue
            if len(node.values) != 2:
                continue
            right = node.values[1]
            if not (isinstance(right, ast.Constant) and right.value in (0, "")):
                continue
            # Left side: device.get("cpu_cores") or similar. Extract the
            # string argument if present.
            left = node.values[0]
            if (isinstance(left, ast.Call)
                    and isinstance(left.func, ast.Attribute)
                    and left.func.attr == "get"
                    and left.args
                    and isinstance(left.args[0], ast.Constant)
                    and left.args[0].value in FORBIDDEN_COERCION_FIELDS):
                violations.append(
                    f"{func.name}:{node.lineno} — "
                    f"`{left.args[0].value} or {right.value!r}` coercion forbidden (D-16)"
                )

    assert not violations, (
        "Phase 35 D-16 regression: threshold-field coercion reappeared.\n"
        + "\n".join(f"  - {v}" for v in violations)
    )
```

**Shared AST utility:** the existing `_collect_string_literals` (line 120) and `_collect_name_and_attr_ids` (line 129) helpers stay reusable. Planner extends the file in-place — no new test module required unless the planner prefers separation.

---

### Functional tests (D-17) — pick a host file

**D-17a (hostname-only upsert):** extend `tests/test_database.py` with a parametrized SQLite + Postgres case:
```python
def test_store_device_updates_in_place_on_ip_change():
    """D-17a: same hostname, different connection_ip → same id, overwritten IP."""
    sitemap = NetworkSiteMap(db_path=":memory:", db_type="sqlite")
    dev1 = NetworkDevice(hostname="pve", connection_ip="192.168.1.10",
                         last_seen="2026-01-01T00:00:00", status="success")
    dev2 = NetworkDevice(hostname="pve", connection_ip="192.168.1.11",
                         last_seen="2026-01-02T00:00:00", status="success")
    id1 = sitemap.store_device(dev1)
    id2 = sitemap.store_device(dev2)
    assert id1 == id2
    devices = sitemap.get_all_devices()
    assert len(devices) == 1
    assert devices[0]["connection_ip"] == "192.168.1.11"
```

**D-17b (migration idempotent):** extend `tests/test_database.py` or new `test_discovery_reliability.py`:
- Seed a pre-migration DB with two rows sharing a hostname but different IPs.
- Run the migration step once, assert one row with merged non-null fields.
- Run a second time, assert no change (idempotency).

**D-17c (partial timeout):** extend `tests/test_ssh_tools.py`; mock `asyncssh.SSHClientConnection.run` to raise `TimeoutError` for one command, success for others. Assert response contains `"partial": true` and `timed_out_commands == ["lsblk"]`.

**D-17d (parallelism proof):** extend `tests/test_sitemap.py`; mock `ssh_discover_system` to `asyncio.sleep(2)` then return error JSON. Feed 10 targets; assert total elapsed < 2.5s (vs. 20s serial).

**D-17e (analyzer null skip):** extend `tests/test_sitemap.py`; seed sitemap with a device `{"cpu_cores": None, ...}`, assert `analyze_network_topology()["resource_utilization"]["low_resources"]` does NOT list it, and `suggest_deployments()["upgrade_recommendations"]` does NOT list it.

## Shared Patterns

### One-Time Startup Migration
**Source:** `migration.py:27-51` (Phase 33 D-01 `DROP TABLE IF EXISTS ssh_credentials`)
**Apply to:** Phase 35 D-02 (zombie dedup) and D-09c (ALTER TABLE). Idempotent, both SQLite + Postgres paths, appends to `applied_migrations` on success.

### Small Private Helper (Cross-Site Concern)
**Source:** `ssh_tools.py:40` (`_resolve_username_from_registry`), `ssh_tools.py:441` (`_sudo_run`), `sitemap.py:220` (`_parse_memory_gb`)
**Apply to:** D-05 (`_run_with_timeout`) in `ssh_tools.py`, D-11 (`_has_threshold_data`) in `sitemap.py`. Module-private (leading underscore), takes explicit dependencies as parameters, documented in a docstring.

### JSON-Column Pattern
**Source:** `database.py:156` (SQLite schema), `database.py:320-324` (SQLite reader), `sitemap.py:97-98` (sitemap writer), `sitemap.py:36` (dataclass field)
**Apply to:** D-09b — `usb_devices` / `pci_devices` / `block_devices` each carry all four touchpoints identically.

### Both-Adapters Mirror
**Source:** every SQLite block in `database.py` has a Postgres twin (e.g., `store_device` lines 210-305 ↔ 580-678; `init_schema` lines 128-208 ↔ 511-578).
**Apply to:** D-01 match clause (both adapters), D-09c column adds (both adapters, though Postgres may opt for the JSONB-extend shortcut). Touching one without the other is the canonical regression failure mode.

### AST Meta-Test Regression Guard
**Source:** `tests/test_ast_regression.py:140-178` (scan source for forbidden strings), `tests/test_ast_regression.py:206-277` (scan for forbidden function-arg defaults), `tests/test_ast_regression.py:280+` (scan tool schemas for forbidden properties).
**Apply to:** D-14 (store_device match pattern), D-15 (unwrapped conn.run), D-16 (threshold-field coercion). Same `Path(__file__).parent.parent / "src" / "homelab_mcp"` root, same `ast.walk` shape, same violation-list + assert pattern.

### Truthy-Safe `if device.get(...)` Guard (DO NOT break)
**Source:** `sitemap.py:179` and `sitemap.py:269` — `if device.get("disk_use_percent"):`
**Apply to:** D-10/D-11 explicitly preserves these — `disk_use_percent` uses truthy-safe guard (empty string falsy), `cpu_cores`/`memory_total` use explicit `is not None` since `0` is valid-but-low. Don't collapse the two styles into one.

### asyncio.Semaphore + gather Pattern
**Source:** per CONTEXT `<code_context> ### Reusable Assets` — "Proxmox concurrent-probe pattern from Phase 34". No current in-tree example in `src/homelab_mcp/` imports `asyncio.Semaphore` directly; the pattern lives in Phase 34 planning + `.planning/phases/34-*/` plan files.
**Apply to:** D-07 `bulk_discover_and_store`. `Semaphore(10)` as module-level-adjacent constant OR function-local; `gather(*, return_exceptions=...)` with a per-target coroutine helper that converts exceptions to the existing error-dict shape.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| *(none)* | — | — | Every Phase 35 file has a same-module or sibling-module analog. Phase 35 is pure bug-fix + small extension; no greenfield surfaces. |

## Metadata

- **Analog search scope:** `src/homelab_mcp/**/*.py`, `tests/test_*.py`, `.planning/phases/33*/`, `.planning/phases/34*/`
- **Files scanned:** sitemap.py, database.py, ssh_tools.py, migration.py, error_handling.py, tool_handlers/network_handlers.py, test_ast_regression.py, test_sitemap.py (headers)
- **Pattern extraction date:** 2026-04-23
- **Phase-35 CONTEXT anchor:** `.planning/phases/35-sitemap-discovery-reliability-fix-discover-and-map-field-los/35-CONTEXT.md`
