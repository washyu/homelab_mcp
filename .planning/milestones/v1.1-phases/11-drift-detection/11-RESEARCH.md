# Phase 11: Drift Detection - Research

**Researched:** 2026-03-12
**Domain:** Infrastructure drift detection, SQLite schema migration, Proxmox API config endpoint, baseline diffing
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DRFT-01 | User can run `scan_infrastructure_drift` to get a report of all detected drift | Tool registration pattern (tool_schemas + tool_handlers), report structure design in Code Examples |
| DRFT-02 | State drift detects when VMs/services are offline that should be running (SSH + Proxmox status) | `get_proxmox_vm_status` returns `.../status/current`; SSH probe via `asyncssh`; labeling pattern described in Architecture Patterns |
| DRFT-03 | Config drift detects when VM/device config changed outside MCP (CPU, memory, network) | Proxmox `GET /nodes/{node}/{vm_type}/{vmid}/config` endpoint must be added to `proxmox_api.py`; field comparison logic described |
| DRFT-04 | Drift baselines stored in SQLite as full config dicts for field-level diffing | New `drift_baselines` table schema designed; migration pattern from `migration.py` documented |
| DRFT-05 | Drift baselines update after successful MCP mutations to avoid false positives | `handle_call_tool` post-mutation hook pattern confirmed; `MUTATING_TOOLS` frozenset model for baseline update triggers |
</phase_requirements>

---

## Summary

Phase 11 implements drift detection for homelab infrastructure: a `scan_infrastructure_drift` tool that compares live Proxmox VM state and config against stored baselines, returning a structured report of what changed outside MCP's control.

The implementation requires four concrete additions to the codebase: (1) a new `drift_baselines` SQLite table with full-config JSON storage and a migration applied at startup; (2) a new `get_proxmox_vm_config` function in `proxmox_api.py` hitting the Proxmox config endpoint (distinct from the existing status endpoint); (3) a `drift_detection.py` module with scan logic; (4) a `scan_infrastructure_drift` tool registered in `tool_schemas` and `tool_handlers`. Baseline updates hook into the existing `handle_call_tool` post-success path using the `MUTATING_TOOLS` frozenset pattern established in Phase 10.

State drift findings are labeled `"observation"` rather than `"confirmed_drift"` per the DRFT-02/success-criteria-5 requirement, preventing false positives from transient VM reboot states. Config drift is HIGH confidence because the Proxmox REST API config endpoint is stable and well-documented.

**Primary recommendation:** Build `drift_detection.py` as a standalone module with a single `async def scan_drift(session, db_adapter)` entry point. Keep database operations synchronous (existing SQLite pattern), keep Proxmox calls async. The tool handler wraps this in the standard content-wrapping pattern.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `sqlite3` (stdlib) | 3.12 stdlib | Baseline storage and retrieval | Already used via `SQLiteAdapter` — no new deps |
| `aiohttp` | existing | Proxmox REST API calls | Already used in `proxmox_api.py` |
| `asyncssh` | existing | SSH probe for state drift | Already used in `ssh_tools.py` |
| `json` (stdlib) | stdlib | Serialize/deserialize full config dicts | Already used throughout |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `datetime` (stdlib) | stdlib | `scan_timestamp` in ISO format | All drift report entries need timestamps |
| `deepdiff` | NOT in project | Deep dict comparison | Do NOT add — hand-roll field-level diff from known fields (CPU, memory, network only per DRFT-03) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled field diff | `deepdiff` PyPI | `deepdiff` is overkill; we only compare 3-4 known Proxmox config fields; avoids new dependency |
| Separate drift DB table | Reusing `discovery_history` | `discovery_history` tracks SSH discovery blobs, not Proxmox VM configs; different schema and semantics |

**Installation:**
No new packages needed. All dependencies already present.

---

## Architecture Patterns

### Recommended Project Structure

New files:
```
src/homelab_mcp/
├── drift_detection.py          # Scan logic, baseline CRUD, diff engine
├── tool_schemas/
│   └── drift_tools_schema.py   # scan_infrastructure_drift schema
└── tool_handlers/
    └── drift_handlers.py       # handle_scan_infrastructure_drift
```

Modified files:
```
src/homelab_mcp/
├── proxmox_api.py              # Add get_proxmox_vm_config()
├── migration.py                # Add run_sqlite_migrations drift_baselines table
├── database.py                 # Add drift baseline CRUD to SQLiteAdapter (and abstract base)
├── tool_schemas/__init__.py    # Import and merge DRIFT_TOOLS
├── tool_handlers/__init__.py   # Import and register handle_scan_infrastructure_drift
└── tool_annotations.py         # Add scan_infrastructure_drift to _READ_ONLY_TOOLS
```

### Pattern 1: Drift Baseline Table Schema

**What:** A new SQLite table `drift_baselines` stores the last-known-good full config dict per VM, keyed by `(node, vmid, vm_type)`. Written by MCP mutations, read by drift scans.

**When to use:** Any time a Proxmox mutation succeeds (create, update, resize).

```sql
-- Applied in run_sqlite_migrations()
CREATE TABLE IF NOT EXISTS drift_baselines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node TEXT NOT NULL,
    vmid INTEGER NOT NULL,
    vm_type TEXT NOT NULL DEFAULT 'qemu',
    baseline_config TEXT NOT NULL,   -- JSON-serialized full Proxmox VM config
    recorded_at TEXT NOT NULL,       -- ISO8601 timestamp
    recorded_by TEXT NOT NULL,       -- tool name that wrote this baseline
    UNIQUE(node, vmid, vm_type)      -- one baseline per VM, REPLACE on update
);
CREATE INDEX IF NOT EXISTS idx_drift_baselines_node_vmid
    ON drift_baselines (node, vmid, vm_type);
```

**Critical detail:** Use `INSERT OR REPLACE` (SQLite upsert) so that every successful mutation overwrites the previous baseline atomically. This satisfies DRFT-05.

### Pattern 2: Proxmox VM Config Endpoint

**What:** The Proxmox REST API exposes `GET /nodes/{node}/{vm_type}/{vmid}/config` for the persistent configuration (CPU sockets/cores, memory, network devices). This is distinct from `.../status/current` (runtime stats).

**Endpoint:** `GET /nodes/{node}/qemu/{vmid}/config` for QEMU VMs, `GET /nodes/{node}/lxc/{vmid}/config` for containers.

**Key fields returned:**
- `cores` — CPU core count (int)
- `memory` — RAM in MB (int)
- `sockets` — CPU socket count (int)
- `net0`, `net1`, ... — network device strings (e.g., `"virtio,bridge=vmbr0,firewall=1"`)
- `name` — VM name

**What to add to `proxmox_api.py`:**
```python
# Source: Proxmox VE API docs — /nodes/{node}/{type}/{vmid}/config
async def get_proxmox_vm_config(
    node: str,
    vmid: int,
    host: str | None = None,
    vm_type: str = "qemu",
    session: aiohttp.ClientSession | None = None,
) -> dict[str, Any]:
    """Get the persistent config of a VM or container."""
    client = get_proxmox_client(host=host, session=session)
    try:
        config = await client.get(f"/nodes/{node}/{vm_type}/{vmid}/config")
        return {"status": "success", "node": node, "vmid": vmid, "type": vm_type, "data": config}
    except (aiohttp.ClientError, ValueError) as e:
        return {"status": "error", "message": f"Failed to get VM config: {sanitize_error(e)}"}
```

### Pattern 3: Drift Report Structure

**What:** The `scan_infrastructure_drift` tool returns a structured report with two sections: `config_drift` and `state_drift`. Each finding has required fields per DRFT-01 success criteria.

```python
# Source: REQUIREMENTS.md success criteria for DRFT-01
{
    "status": "success",
    "scan_timestamp": "2026-03-12T17:00:00+00:00",  # ISO8601 UTC
    "config_drift": [
        {
            "drift_type": "config",
            "resource_type": "proxmox_vm",
            "node": "pve",
            "vmid": 100,
            "vm_type": "qemu",
            "expected": {"cores": 2, "memory": 2048},   # from baseline
            "actual": {"cores": 4, "memory": 4096},     # from live API
            "changed_fields": ["cores", "memory"],
            "scan_timestamp": "2026-03-12T17:00:00+00:00",
        }
    ],
    "state_drift": [
        {
            "drift_type": "state",
            "observation": "vm_offline",   # NOT "confirmed_drift" — point-in-time per DRFT-05 SC-5
            "resource_type": "proxmox_vm",
            "node": "pve",
            "vmid": 101,
            "vm_type": "qemu",
            "expected": "running",
            "actual": "stopped",
            "scan_timestamp": "2026-03-12T17:00:00+00:00",
        }
    ],
    "summary": {
        "config_drift_count": 1,
        "state_drift_count": 1,
        "total_vms_scanned": 5,
        "baselines_available": 3,
    }
}
```

**CRITICAL: State drift label must be `"observation"` not `"confirmed_drift"`** — the success criterion explicitly requires this to prevent false positives during transient reboots.

### Pattern 4: Baseline Update Hook

**What:** After any successful Proxmox VM mutation, the handler fetches live config and writes it to `drift_baselines`. This mirrors Phase 10's notification dispatch hook in `handle_call_tool`.

**Where to put it:** In `drift_detection.py`, expose an `async def update_baseline_after_mutation(node, vmid, vm_type, tool_name, session, db_adapter)`. Call this from tool handlers that mutate VM config (create_proxmox_vm, create_proxmox_lxc, manage_proxmox_vm with resize, etc.) OR hook into `handle_call_tool` for the mutation set.

**Preferred approach:** Direct calls from the relevant mutation handlers (not a generic hook in `handle_call_tool`), because baseline update requires knowing `node` and `vmid` which are tool-specific args. The `handle_call_tool` hook pattern from Phase 10 works for generic notifications but is insufficient here.

**Mutation tools that should update baselines:**
- `create_proxmox_vm` — on success, fetch config and store
- `create_proxmox_lxc` — on success, fetch config and store
- `clone_proxmox_vm` — on success, fetch config and store
- `manage_proxmox_vm` — on `start`/`stop` do NOT update config baseline; but if used for resize it should (Proxmox resize is a separate API call not currently in the codebase)

For Phase 11 scope: baseline writes happen in `create_proxmox_vm`, `create_proxmox_lxc`, `clone_proxmox_vm` handlers. A helper function in `drift_detection.py` is called by each handler after success.

### Pattern 5: Tool Registration

Following the established pattern:

1. Create `src/homelab_mcp/tool_schemas/drift_tools_schema.py` with `DRIFT_TOOLS` dict
2. Import and merge in `tool_schemas/__init__.py`
3. Create `src/homelab_mcp/tool_handlers/drift_handlers.py` with `handle_scan_infrastructure_drift`
4. Import and register in `tool_handlers/__init__.py`
5. Add `"scan_infrastructure_drift"` to `_READ_ONLY_TOOLS` in `tool_annotations.py`

### Anti-Patterns to Avoid

- **Don't reuse `discovery_history` for baselines:** That table stores SSH discovery blobs for network devices. VM config baselines are a different entity with different keys and lifecycle.
- **Don't label state drift as "confirmed_drift":** Per DRFT-02 success criteria 5, state findings are point-in-time observations. Use `"observation"` field, not a definitive drift label.
- **Don't scan all Proxmox resources in one call and block for minutes:** Fetch VMs via `list_proxmox_resources` first, then limit config fetches to VMs that have baselines. Avoids scanning VMs we have no expectations for.
- **Don't raise on missing baseline:** If a VM has no baseline, skip config drift for it — report in `summary.baselines_available` count. Only compare VMs with stored baselines.
- **Don't store `status/current` as the baseline:** The status endpoint returns runtime data (uptime, CPU usage). The config endpoint returns persistent config (cores, memory, network). Baseline must come from `/config`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Proxmox VM list | Custom scraping | `list_proxmox_resources()` already in `proxmox_api.py` | Handles auth, filtering by type, error wrapping |
| Async SSH probe | Raw asyncssh | Existing `ssh_connect` context manager in `ssh_connection.py` | Handles key management, connection pooling |
| DB connection management | Direct sqlite3 | `SQLiteAdapter` via `get_resource_manager().db_adapter` | Handles connect/close lifecycle, row_factory |
| Error sanitization | Custom sanitize | `sanitize_error()` from `log_filter.py` | Credential redaction already wired |
| Session management | New aiohttp.ClientSession | `get_resource_manager().proxmox_session` | Connection pooling, SSL config already handled |

---

## Common Pitfalls

### Pitfall 1: Config vs. Status Endpoint Confusion
**What goes wrong:** Developer calls `get_proxmox_vm_status()` (`.../status/current`) expecting persistent config fields like `cores` and `memory`, but gets runtime data instead.
**Why it happens:** The naming is confusing. The existing codebase only has `get_proxmox_vm_status` — there is no `get_proxmox_vm_config` yet.
**How to avoid:** Add `get_proxmox_vm_config()` to `proxmox_api.py` hitting `GET /nodes/{node}/{vm_type}/{vmid}/config`. Never use status endpoint for baseline comparison.
**Warning signs:** Baseline comparison finds drift on every scan because CPU usage changes between calls.

### Pitfall 2: SQLite UNIQUE Constraint on Baseline Upsert
**What goes wrong:** `INSERT INTO drift_baselines` fails with UNIQUE constraint error on second write for the same VM.
**Why it happens:** The table has `UNIQUE(node, vmid, vm_type)` but plain `INSERT` doesn't handle conflicts.
**How to avoid:** Use `INSERT OR REPLACE INTO drift_baselines` (SQLite upsert) to overwrite the existing row.
**Warning signs:** `IntegrityError: UNIQUE constraint failed` in logs after second VM create/mutation.

### Pitfall 3: False Positive State Drift During Reboots
**What goes wrong:** `scan_infrastructure_drift` reports a VM as drifted offline when it was mid-reboot.
**Why it happens:** VM status is checked once; a reboot causes a brief `stopped` window.
**How to avoid:** Label state findings as `"observation"` (not `"confirmed_drift"`). The success criterion is explicit: "State drift findings are labeled as point-in-time observations." Do NOT add retry logic — just use the correct label.
**Warning signs:** Users complaining about spurious alerts after intentional reboots.

### Pitfall 4: Migration Not Applied on Existing Databases
**What goes wrong:** `drift_baselines` table doesn't exist when the first drift scan runs on an existing installation.
**Why it happens:** The table is new and existing users already have an initialized database without it.
**How to avoid:** Add the migration to `run_sqlite_migrations()` following the exact pattern used for `ssh_credentials` — check `sqlite_master` for table existence, create if absent, append migration name to `applied_migrations`.
**Warning signs:** `OperationalError: no such table: drift_baselines` on scan.

### Pitfall 5: Scanning VMs Without Baselines
**What goes wrong:** Every VM in Proxmox is reported as config drifted because there's no baseline.
**Why it happens:** Initial install has no baselines. Drift scan iterates all VMs.
**How to avoid:** Only compare VMs that have a stored baseline. VMs without baselines should appear in `summary.baselines_available` count, not in `config_drift` list.
**Warning signs:** Every VM shows as drifted on the first scan after install.

### Pitfall 6: Database Access from Async Context
**What goes wrong:** SQLite calls block the event loop, causing slow scans with many VMs.
**Why it happens:** `sqlite3` is synchronous. The existing pattern uses it synchronously throughout the codebase.
**How to avoid:** Follow the existing pattern — synchronous SQLite calls are fine for the data volumes of a homelab (< 100 VMs). Do NOT add `asyncio.to_thread` complexity unless profiling shows a problem.

---

## Code Examples

### Scan Infrastructure Drift Tool Schema
```python
# Source: existing patterns in tool_schemas/proxmox_tools_schema.py
DRIFT_TOOLS: dict[str, dict] = {
    "scan_infrastructure_drift": {
        "description": (
            "Scan for infrastructure drift: config drift (CPU/memory/network changed outside MCP) "
            "and state drift (VMs offline that should be running). "
            "Returns structured report with drift_type, expected, actual, and scan_timestamp per finding."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "node": {
                    "type": "string",
                    "description": "Proxmox node name to scan (optional; scans all nodes if omitted)",
                },
                "vm_type": {
                    "type": "string",
                    "enum": ["qemu", "lxc", "all"],
                    "description": "VM type to scan (default: 'all')",
                    "default": "all",
                },
            },
            "required": [],
        },
    }
}
```

### Baseline CRUD in SQLiteAdapter
```python
# Source: database.py pattern (add these methods to SQLiteAdapter and abstract base)

def upsert_drift_baseline(
    self,
    node: str,
    vmid: int,
    vm_type: str,
    baseline_config: dict[str, Any],
    recorded_by: str,
) -> None:
    """Store or replace a drift baseline for a VM."""
    if not self.connection:
        self.connect()
    assert self.connection is not None
    cursor = self.connection.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO drift_baselines
            (node, vmid, vm_type, baseline_config, recorded_at, recorded_by)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (node, vmid, vm_type, json.dumps(baseline_config),
         datetime.now().isoformat(), recorded_by),
    )
    self.connection.commit()

def get_drift_baseline(
    self, node: str, vmid: int, vm_type: str
) -> dict[str, Any] | None:
    """Retrieve the stored baseline for a VM, or None if absent."""
    if not self.connection:
        self.connect()
    assert self.connection is not None
    cursor = self.connection.cursor()
    cursor.execute(
        "SELECT baseline_config, recorded_at, recorded_by FROM drift_baselines "
        "WHERE node = ? AND vmid = ? AND vm_type = ?",
        (node, vmid, vm_type),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return {
        "baseline_config": json.loads(row[0]),
        "recorded_at": row[1],
        "recorded_by": row[2],
    }

def get_all_drift_baselines(self) -> list[dict[str, Any]]:
    """Return all stored baselines (for scan iteration)."""
    if not self.connection:
        self.connect()
    assert self.connection is not None
    cursor = self.connection.cursor()
    cursor.execute(
        "SELECT node, vmid, vm_type, baseline_config, recorded_at, recorded_by "
        "FROM drift_baselines ORDER BY node, vmid"
    )
    results = []
    for row in cursor.fetchall():
        results.append({
            "node": row[0], "vmid": row[1], "vm_type": row[2],
            "baseline_config": json.loads(row[3]),
            "recorded_at": row[4], "recorded_by": row[5],
        })
    return results
```

### Config Diff Logic
```python
# Source: project pattern — hand-rolled, no external deps
# Fields to compare per DRFT-03 (CPU, memory, network)
CONFIG_DRIFT_FIELDS = ["cores", "memory", "sockets", "net0", "net1", "net2"]

def _diff_vm_config(
    baseline: dict[str, Any],
    live: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    """
    Compare baseline config dict against live config dict.
    Returns (expected_subset, actual_subset, changed_field_names).
    Only reports fields present in CONFIG_DRIFT_FIELDS.
    """
    changed_fields = []
    expected: dict[str, Any] = {}
    actual: dict[str, Any] = {}
    for field in CONFIG_DRIFT_FIELDS:
        b_val = baseline.get(field)
        l_val = live.get(field)
        if b_val != l_val and (b_val is not None or l_val is not None):
            changed_fields.append(field)
            expected[field] = b_val
            actual[field] = l_val
    return expected, actual, changed_fields
```

### Migration Addition
```python
# Source: migration.py pattern — add to run_sqlite_migrations()
cursor.execute("""
    SELECT name FROM sqlite_master
    WHERE type='table' AND name='drift_baselines'
""")
if not cursor.fetchone():
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS drift_baselines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node TEXT NOT NULL,
            vmid INTEGER NOT NULL,
            vm_type TEXT NOT NULL DEFAULT 'qemu',
            baseline_config TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            recorded_by TEXT NOT NULL,
            UNIQUE(node, vmid, vm_type)
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_drift_baselines_node_vmid
        ON drift_baselines (node, vmid, vm_type)
    """)
    adapter.connection.commit()
    applied_migrations.append("create_drift_baselines_table")
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No drift tracking | SQLite baseline table + scan tool | Phase 11 | Enables point-in-time config drift detection |
| No VM config API call | `get_proxmox_vm_config()` added to `proxmox_api.py` | Phase 11 | Config diff against live Proxmox state |
| Phase 10 MUTATING_TOOLS (only SSH discovery tools) | Baseline writes on Proxmox VM creation | Phase 11 | New category of post-mutation side-effect |

**Existing infrastructure that Phase 11 builds on:**
- `ResourceManager.proxmox_session` — wired in Phase 6; passed to all Proxmox API calls
- `ResourceManager.db_adapter` — used in resource readers; drift module follows same access pattern
- `MUTATING_TOOLS` frozenset — Phase 10 pattern; drift extends the concept of "mutations with side effects"
- `run_sqlite_migrations()` — Phase 6/7 pattern; drift adds one migration block

---

## Open Questions

1. **Which Proxmox mutation handlers should write baselines?**
   - What we know: `create_proxmox_vm`, `create_proxmox_lxc`, `clone_proxmox_vm` are clear cases
   - What's unclear: `manage_proxmox_vm` handles start/stop/reboot — these don't change config, so no baseline write needed; but hotplug/resize operations (not currently in the codebase) would need it
   - Recommendation: Scope baseline writes to creation and clone only for Phase 11; document that resize tools (future) must call `upsert_drift_baseline` on success

2. **Should state drift check services (SSH probe) or only Proxmox VM status?**
   - What we know: DRFT-02 says "SSH + Proxmox status"; success criterion 2 says "using both Proxmox API status and SSH probe"
   - What's unclear: SSH probe requires an IP per VM — not all Proxmox VMs have IPs registered in the device table
   - Recommendation: Implement Proxmox API status check first (always available); add SSH probe only for VMs whose IP is found in `db_adapter.get_all_devices()`. If no IP found, Proxmox status alone is sufficient for the finding.

3. **What is the "expected" state for state drift?**
   - What we know: A VM that was `running` when last seen by MCP is "expected" to be running
   - What's unclear: The baseline only stores config, not runtime state. We need a separate mechanism to know expected state.
   - Recommendation: Store `"expected_status": "running"` in the baseline when writing it after a `manage_proxmox_vm` start action, or after create+start. Default assumption: any VM with a stored baseline is expected to be running. Flag in planning to confirm this interpretation.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `pytest.ini` or `pyproject.toml` (existing) |
| Quick run command | `uv run pytest tests/test_drift_detection.py -x -v` |
| Full suite command | `uv run pytest tests/ -m "not integration"` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DRFT-01 | `scan_infrastructure_drift` returns structured report with `drift_type`, `expected`, `actual`, `scan_timestamp` | unit | `uv run pytest tests/test_drift_detection.py::TestScanDriftReport -x` | Wave 0 |
| DRFT-02 | State drift identifies VMs offline that should be running, labeled as `"observation"` | unit | `uv run pytest tests/test_drift_detection.py::TestStateDrift -x` | Wave 0 |
| DRFT-03 | Config drift detects CPU/memory/network changes by comparing live Proxmox config to baseline | unit | `uv run pytest tests/test_drift_detection.py::TestConfigDrift -x` | Wave 0 |
| DRFT-04 | `drift_baselines` table stores full config dicts; `get_drift_baseline`/`upsert_drift_baseline` work correctly | unit | `uv run pytest tests/test_database.py::TestDriftBaselines -x` | Wave 0 |
| DRFT-05 | Baseline updates after successful VM creation/clone mutations | unit | `uv run pytest tests/test_drift_detection.py::TestBaselineUpdate -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_drift_detection.py -x -v`
- **Per wave merge:** `uv run pytest tests/ -m "not integration"`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_drift_detection.py` — covers DRFT-01, DRFT-02, DRFT-03, DRFT-05
- [ ] `tests/test_database.py::TestDriftBaselines` — covers DRFT-04 (add class to existing file)

---

## Sources

### Primary (HIGH confidence)
- Proxmox VE REST API — `GET /nodes/{node}/qemu/{vmid}/config` endpoint structure confirmed from Proxmox API docs; field names (`cores`, `memory`, `sockets`, `net0`) are stable across PVE 7.x/8.x
- Codebase analysis: `database.py` (SQLiteAdapter patterns), `migration.py` (table addition pattern), `server.py` (MUTATING_TOOLS hook), `proxmox_api.py` (client pattern), `dry_run.py` (response builder pattern)
- `tool_handlers/__init__.py` and `tool_schemas/__init__.py` — confirmed tool registration pattern

### Secondary (MEDIUM confidence)
- Proxmox VE API distinction between `/status/current` (runtime) vs `/config` (persistent) — standard API design; confirmed by codebase use of `status/current` endpoint only currently

### Tertiary (LOW confidence)
- SSH probe availability per VM (depends on IP being in device table) — unverified at research time; flagged as Open Question 2

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all dependencies already in project; no new installs
- Architecture: HIGH — patterns directly derived from existing Phase 6/8/10 implementations
- Pitfalls: HIGH — derived from codebase analysis and known SQLite/Proxmox API gotchas
- Validation Architecture: HIGH — follows established pytest patterns

**Research date:** 2026-03-12
**Valid until:** 2026-06-12 (stable APIs; Proxmox config endpoint is not changing)
