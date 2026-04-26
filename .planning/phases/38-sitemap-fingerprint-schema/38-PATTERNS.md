# Phase 38: Sitemap Fingerprint Schema - Pattern Map

**Mapped:** 2026-04-25
**Files analyzed:** 20 (12 source/docs + 8 tests)
**Analogs found:** 20 / 20 (every artifact has a verified in-tree mirror)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/homelab_mcp/ssh_tools.py` (extend `ssh_discover_system`) | probe / SSH transformer | request-response | self — existing usb/pci/block probe blocks at `ssh_tools.py:386-476` | exact (same function) |
| `src/homelab_mcp/sitemap.py` (extend `NetworkDevice` + `parse_discovery_output`) | dataclass + parser | transform | Phase 35 D-09b usb/pci/block branches (`sitemap.py:55-57, 121-127`) | exact |
| `src/homelab_mcp/database.py` (SQLiteAdapter + PostgreSQLAdapter `store_device` / `get_all_devices`) | adapter (CRUD) | CRUD | Phase 35 D-09b usb/pci/block additions (`database.py:140-142, 224-294, 580-582, 705-707`) | exact |
| `src/homelab_mcp/database.py` (new `update_device_fingerprint` adapter method on ABC + both concretes) | adapter (CRUD) | CRUD | `SQLiteAdapter.store_device` (`database.py:188-300`) hostname-natural-key lookup pattern | role-match (new method, established lookup) |
| `src/homelab_mcp/migration.py` (ALTER TABLE + schema-rebuild branch) | migration | batch | Phase 35 D-09c block (`migration.py:64-79`) + schema-rebuild (`migration.py:149-220`) | exact |
| `src/homelab_mcp/tool_schemas/network_tools_schema.py` (new `update_device_fingerprint` schema) | tool schema | config | self — existing tools in `network_tools_schema.py:5-101` | exact |
| `src/homelab_mcp/tool_schemas/network_tools_schema.py` (new `update_device_fingerprint_preview`) | tool schema | config | `decommission_device_preview` (`infrastructure_tools_schema.py:275-315`) | exact (preview convention) |
| `src/homelab_mcp/tool_schemas/network_tools_schema.py` + `ssh_tools_schema.py` (description tweak) | tool schema | config | line 7 of each file | exact (string edit) |
| `src/homelab_mcp/tool_handlers/network_handlers.py` (new `handle_update_device_fingerprint`) | handler | request-response | `handle_discover_and_map` (`network_handlers.py:10-15`) | exact (same module) |
| `src/homelab_mcp/tool_handlers/__init__.py` (registry registration) | router | config | existing `# Network tools` block (`__init__.py:82-89`) | exact |
| `src/homelab_mcp/tool_annotations.py` (`_MUTATING_ANNOTATIONS` + `_READ_ONLY_TOOLS`) | annotations registry | config | `_MUTATING_ANNOTATIONS["discover_and_map"]` (`tool_annotations.py:80-84`); `_READ_ONLY_TOOLS` list (`tool_annotations.py:23-52`) | exact |
| `src/homelab_mcp/server.py` (`MUTATING_TOOLS` frozenset) | router | config | `MUTATING_TOOLS` literal at `server.py:168-173` | exact |
| `src/homelab_mcp/prompt_registry.py` (new `configure_host_fingerprint`) | prompt registry | config | `connect_to_device` entry (`prompt_registry.py:52-62`) + `_build_connect_to_device_result` (`prompt_registry.py:125-154`) + dispatcher case (`prompt_registry.py:199-200`) | exact |
| `docs/tool-reference.md` (entries for new tool + prompt) | docs | n/a | existing entries in same file | role-match |
| `tests/test_ssh_tools.py` (refactor + new probe tests) | unit test | n/a | `STDOUT_BY_CMD` dict pattern (`tests/test_ssh_tools.py:507-525`) | exact |
| `tests/test_sitemap.py` (extend fixture + new tests) | unit test | n/a | `sample_ssh_discovery_success` fixture (`tests/test_sitemap.py:28-57`) + `test_parse_discovery_output_success` (`tests/test_sitemap.py:104-124`) | exact |
| `tests/test_database.py` (round-trip + adapter method tests) | unit test | n/a | `test_store_and_retrieve_device` (`tests/test_database.py:53-81`) | exact |
| `tests/test_migration.py` (ALTER TABLE idempotent test) | unit test | n/a | existing `add_column_` assertions (`tests/test_database.py:580-613` — note: ALTER TABLE migrations are tested in `test_database.py`, not `test_migration.py`) | partial (correct test file) |
| `tests/test_tools.py` (MCP routing + annotations tests) | unit test | n/a | `test_execute_discover_and_map` (`tests/test_tools.py:116-130`) | exact |
| `tests/test_mcp_prompts.py` (`configure_host_fingerprint` registration test) | unit test | n/a | `test_connect_to_device_prompt` (`tests/test_mcp_prompts.py:96-129`) | exact |
| `tests/test_mcp_resources.py` (resource notification test — NOT `test_logging_notifications.py`) | unit test | n/a | `test_discover_and_map_sends_list_changed` (`tests/test_mcp_resources.py:260-271`) | exact |
| `tests/integration/test_sitemap_integration.py` (Docker fingerprint assertion) | integration test | n/a | `TestSitemapIntegration.test_sitemap_workflow_with_mock_discovery` (`tests/integration/test_sitemap_integration.py:36-106`) + `test_container` fixture (`tests/integration/conftest.py:19-78`) | role-match |

> Note on routing correction: CONTEXT.md mentions `tests/test_logging_notifications.py` for the resource-notification test. **Use `tests/test_mcp_resources.py` instead** — that's where `test_discover_and_map_sends_list_changed` lives (line 260) and the `_make_mock_session` helper is already defined (line 247). `test_logging_notifications.py` is for `set_logging_level` / `emit_progress` only.

## Pattern Assignments

### `src/homelab_mcp/ssh_tools.py` — three new fingerprint probes inside `ssh_discover_system`

**Analog:** existing usb/pci/block probe blocks in the same function.

**Probe wrapping pattern** (mirror lines 386-405 — `lsusb` block — and lines 374-383 — `os-release`):
```python
# Source: ssh_tools.py:386-405 (existing lsusb probe — exact mirror for shape)
usb_devices: list[dict[str, str]] = []
lsusb_result = await _run_with_timeout(
    conn, "lsusb 2>/dev/null", cmd_name="lsusb", timed_out=timed_out_commands
)
if lsusb_result and lsusb_result.exit_status == 0 and lsusb_result.stdout:
    for line in cast(str, lsusb_result.stdout).strip().split("\n"):
        if line:
            ...
if usb_devices:
    system_info["usb_devices"] = usb_devices
```

**New code to add** — add a `fingerprint_info: dict[str, Any] = {}` accumulator immediately after the existing `os-release` block (line 384), then three `_run_with_timeout` calls, and finally `if fingerprint_info: system_info["fingerprint"] = fingerprint_info`. The full code excerpt is in RESEARCH.md "Code Examples" §New probe inside `ssh_discover_system` (lines 336-390 of RESEARCH.md). Critical refinements:

1. **Use `LC_ALL=C` for the dpkg command** to ensure locale-stable digests (RESEARCH.md Pitfall 1):
   ```python
   "LC_ALL=C dpkg -l 2>/dev/null | sort | sha256sum"
   ```
2. **Strip the trailing filename from `sha256sum` output** (it appends `  -` for stdin):
   ```python
   digest_field = cast(str, dpkg_result.stdout).strip().split()[0]
   ```
3. **All three probes MUST go through `_run_with_timeout`** — Phase 35 D-15 AST guard at `tests/test_ast_regression.py:447` will fail the suite if any new `conn.run` slips through.

**`_run_with_timeout` contract** (`ssh_tools.py:490-516`):
```python
async def _run_with_timeout(
    conn: asyncssh.SSHClientConnection,
    command: str,
    *,
    cmd_name: str,
    timed_out: list[str],
    timeout: float = 10.0,
) -> "asyncssh.SSHCompletedProcess | None":
    try:
        return await asyncio.wait_for(conn.run(command, check=False), timeout=timeout)
    except TimeoutError:
        timed_out.append(cmd_name)
        return None
```

---

### `src/homelab_mcp/sitemap.py` — `NetworkDevice` field + `parse_discovery_output` branch

**Analog:** Phase 35 D-09b usb/pci/block additions in the same module.

**Dataclass field pattern** (lines 55-57):
```python
network_interfaces: str | None = None  # JSON string
usb_devices: str | None = None  # JSON string (Phase 35 D-09b)
pci_devices: str | None = None  # JSON string (Phase 35 D-09b)
block_devices: str | None = None  # JSON string (Phase 35 D-09b)
```

**Add after `block_devices`:**
```python
fingerprint: str | None = None  # JSON string (Phase 38 D-04c)
```

**Parse branch pattern** (`sitemap.py:121-127`):
```python
# USB / PCI / block devices (Phase 35 D-09b: store as JSON)
if "usb_devices" in discovery_data:
    device.usb_devices = json.dumps(discovery_data["usb_devices"])
if "pci_devices" in discovery_data:
    device.pci_devices = json.dumps(discovery_data["pci_devices"])
if "block_devices" in discovery_data:
    device.block_devices = json.dumps(discovery_data["block_devices"])
```

**Add immediately after** (Phase 38 D-04c):
```python
if "fingerprint" in discovery_data:
    device.fingerprint = json.dumps(discovery_data["fingerprint"])
```

---

### `src/homelab_mcp/database.py` — SQLite schema + store_device + get_all_devices

**Analog:** Phase 35 D-09b `usb_devices` / `pci_devices` / `block_devices` column additions.

**SQLite CREATE TABLE pattern** (`database.py:140-145`):
```python
network_interfaces TEXT,
usb_devices TEXT,
pci_devices TEXT,
block_devices TEXT,
uptime TEXT,
os_info TEXT,
```

**Add `fingerprint TEXT`** (place after `block_devices TEXT,` to mirror the JSON-column grouping):
```python
network_interfaces TEXT,
usb_devices TEXT,
pci_devices TEXT,
block_devices TEXT,
fingerprint TEXT,        # Phase 38 D-08
uptime TEXT,
os_info TEXT,
```

**SQLite UPDATE branch pattern** (`database.py:217-255` — UPDATE columns + parameter tuple):
```python
cursor.execute(
    """
    UPDATE devices SET
        ..., network_interfaces = ?,
        usb_devices = ?, pci_devices = ?, block_devices = ?,
        uptime = ?, os_info = ?, error_message = ?, updated_at = ?,
        connection_ip = ?
    WHERE id = ?
""",
    (
        ...,
        device_data.get("network_interfaces"),
        device_data.get("usb_devices"),
        device_data.get("pci_devices"),
        device_data.get("block_devices"),
        device_data.get("uptime"),
        ...
    ),
)
```
Add `fingerprint = ?` to the SET clause (between `block_devices = ?` and `uptime = ?`) and `device_data.get("fingerprint")` to the parameter tuple at the matching position. Same insertion in the INSERT branch (`database.py:256-294`).

**SQLite get_all_devices JSON-decode loop** (`database.py:321-327`):
```python
# Phase 35 D-09b: parse usb_devices / pci_devices / block_devices JSON
for _json_col in ("usb_devices", "pci_devices", "block_devices"):
    if device_dict.get(_json_col):
        try:
            device_dict[_json_col] = json.loads(device_dict[_json_col])
        except json.JSONDecodeError:
            device_dict[_json_col] = []
```

**Add `fingerprint` to the tuple** — but use `{}` as the JSONDecodeError default (fingerprint is a dict, not a list):
```python
for _json_col in ("usb_devices", "pci_devices", "block_devices"):
    ...
if device_dict.get("fingerprint"):
    try:
        device_dict["fingerprint"] = json.loads(device_dict["fingerprint"])
    except json.JSONDecodeError:
        device_dict["fingerprint"] = {}
```

**Postgres `system_info` dict pattern** (`database.py:557-583`):
```python
system_info = {
    "cpu": {...},
    ...
    "uptime": device_data.get("uptime"),
    "os": device_data.get("os_info"),
    # Phase 35 D-09b: usb/pci/block device inventories land inside the
    # existing system_info JSONB column (no schema change on Postgres).
    "usb_devices": _maybe_json_load(device_data.get("usb_devices")),
    "pci_devices": _maybe_json_load(device_data.get("pci_devices")),
    "block_devices": _maybe_json_load(device_data.get("block_devices")),
}
```

**Add inside the dict literal** (after `block_devices` key):
```python
"block_devices": _maybe_json_load(device_data.get("block_devices")),
"fingerprint": _maybe_json_load(device_data.get("fingerprint")),  # Phase 38 D-09a
```

**Postgres `get_all_devices` flatten pattern** (`database.py:702-707`):
```python
# Phase 35 D-09b: flatten usb/pci/block device inventories
# so downstream consumers see the same top-level keys as
# the SQLite path.
"usb_devices": system_info.get("usb_devices"),
"pci_devices": system_info.get("pci_devices"),
"block_devices": system_info.get("block_devices"),
```

**Add:**
```python
"fingerprint": system_info.get("fingerprint"),  # Phase 38 D-10
```

---

### `src/homelab_mcp/database.py` — new `update_device_fingerprint` adapter method (D-11 Option A)

**Analog:** `SQLiteAdapter.store_device` hostname-natural-key lookup pattern (`database.py:200-211`).

**Hostname-natural-key lookup pattern** (Phase 35 D-01 — AST-guarded at `tests/test_ast_regression.py:392`):
```python
hostname_key = device_data["hostname"]
if hostname_key in (None, "", "unknown"):
    cursor.execute(
        "SELECT id FROM devices WHERE hostname = ? AND connection_ip = ?",
        (hostname_key, device_data["connection_ip"]),
    )
else:
    cursor.execute(
        "SELECT id FROM devices WHERE hostname = ?",
        (hostname_key,),
    )
existing = cursor.fetchone()
```

**Deep-merge contract** (Phase 38 D-05 — recommended placement: module-level helper in `database.py` so both adapters call it identically):
```python
def merge_fingerprint(stored: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Phase 38 D-05 merge: top-level overwrite, capabilities deep-merge."""
    merged = dict(stored)
    for key, value in incoming.items():
        if key == "capabilities" and isinstance(value, dict):
            existing_caps = dict(merged.get("capabilities", {}))
            existing_caps.update(value)  # incoming sub-keys overwrite, others preserved
            merged["capabilities"] = existing_caps
        else:
            merged[key] = value  # top-level keys overwrite (D-05 step 3a)
    return merged
```

**ABC declaration pattern** (`database.py:24-76`):
```python
class DatabaseAdapter(ABC):
    @abstractmethod
    def store_device(self, device_data: dict[str, Any]) -> int:
        """Store or update a device record."""
        pass
```

**Add to ABC:**
```python
@abstractmethod
def update_device_fingerprint(
    self, hostname: str, fingerprint: dict[str, Any]
) -> dict[str, Any]:
    """Phase 38 D-05/D-11: deep-merge fingerprint dict into the device row.

    Returns the merged fingerprint dict. Raises ValueError if hostname is
    not found in the sitemap.
    """
    pass
```

**SQLite implementation outline** (read-merge-write — same path-parity choice for Postgres per RESEARCH.md Pitfall 4):
```python
def update_device_fingerprint(
    self, hostname: str, fingerprint: dict[str, Any]
) -> dict[str, Any]:
    if not self.connection:
        self.connect()
    assert self.connection is not None
    cursor = self.connection.cursor()

    # Hostname-natural-key lookup (Phase 35 D-01 — AST guard tests/test_ast_regression.py:392)
    if hostname in (None, "", "unknown"):
        raise ValueError(f"Cannot fingerprint degenerate hostname: {hostname!r}")
    cursor.execute("SELECT fingerprint FROM devices WHERE hostname = ?", (hostname,))
    row = cursor.fetchone()
    if row is None:
        raise ValueError(
            f"Hostname not in sitemap: {hostname!r}. "
            "Run discover_and_map first to add the device."
        )

    stored = json.loads(row[0]) if row[0] else {}
    merged = merge_fingerprint(stored, fingerprint)
    cursor.execute(
        "UPDATE devices SET fingerprint = ?, last_seen = ?, updated_at = ? WHERE hostname = ?",
        (json.dumps(merged), datetime.now().isoformat(), datetime.now().isoformat(), hostname),
    )
    self.connection.commit()
    return merged
```

**Postgres implementation:** same shape, `%s` placeholders, `RETURNING system_info`, parse JSONB → call `merge_fingerprint` on the `system_info["fingerprint"]` sub-key → write entire updated `system_info` back via `UPDATE devices SET system_info = %s, last_seen = %s, updated_at = NOW() WHERE hostname = %s`. RESEARCH.md Pitfall 4 explicitly warns against `jsonb_set` / `||` SQL operators.

---

### `src/homelab_mcp/migration.py` — ALTER TABLE step + schema-rebuild update

**Analog:** Phase 35 D-09c block at `migration.py:64-79`.

**ALTER TABLE pattern** (verbatim mirror — same loop, just one column):
```python
# ─────────────────────────────────────────────────────────────────
# Phase 35 D-09c: ADD COLUMN for usb_devices / pci_devices / block_devices.
# Legacy rows get NULL defaults; get_all_devices returns None for these on
# pre-existing devices until re-discovered.
# ─────────────────────────────────────────────────────────────────
cursor.execute("PRAGMA table_info(devices)")
existing_columns = {row[1] for row in cursor.fetchall()}
newly_added: list[str] = []
for new_col in ("usb_devices", "pci_devices", "block_devices"):
    if new_col not in existing_columns:
        cursor.execute(f"ALTER TABLE devices ADD COLUMN {new_col} TEXT")  # noqa: S608
        newly_added.append(new_col)
if newly_added:
    conn.commit()
    for col in newly_added:
        applied_migrations.append(f"add_column_{col}")
```

**Add new block immediately after** (Phase 38 D-08):
```python
# ─────────────────────────────────────────────────────────────────
# Phase 38 D-08: ADD COLUMN fingerprint for sitemap drift detection.
# Mirrors Phase 35 D-09c. Legacy rows get NULL until re-discovered.
# ─────────────────────────────────────────────────────────────────
cursor.execute("PRAGMA table_info(devices)")
existing_columns = {row[1] for row in cursor.fetchall()}
if "fingerprint" not in existing_columns:
    cursor.execute("ALTER TABLE devices ADD COLUMN fingerprint TEXT")
    conn.commit()
    applied_migrations.append("add_column_fingerprint")
```

**Schema-rebuild branch pattern** (`migration.py:149-220`):
```python
cursor.execute("""
    CREATE TABLE devices_new (
        ...,
        usb_devices TEXT,
        pci_devices TEXT,
        block_devices TEXT,
        uptime TEXT,
        os_info TEXT,
        ...
    )
""")
...
target_cols = [
    ...
    "usb_devices",
    "pci_devices",
    "block_devices",
    "uptime",
    "os_info",
    ...
]
```

**Add `fingerprint TEXT` to the `devices_new` CREATE TABLE** (after `block_devices TEXT,` at line ~171) AND add `"fingerprint",` to the `target_cols` list (after `"block_devices",` at line ~206). Failure to update either spot means a pre-Phase-35 DB upgrading through Phase 38's path loses the column on rebuild (D-08b).

---

### `src/homelab_mcp/tool_schemas/network_tools_schema.py` — new `update_device_fingerprint` schema

**Analog:** existing entries in the same dict (`network_tools_schema.py:5-101`).

**Schema shape** (mirror of `discover_and_map`'s schema at lines 6-28):
```python
"discover_and_map": {
    "description": "Discover a device via SSH and store it in the network site map database",
    "inputSchema": {
        "type": "object",
        "properties": {
            "hostname": {"type": "string", "description": "Hostname or IP address"},
            ...
        },
        "required": ["hostname"],
    },
},
```

**Add new entries** (per D-05b — `additionalProperties` must be filtered in handler since MCP framework doesn't validate; schema documents intent only):
```python
"update_device_fingerprint": {
    "description": (
        "Merge fingerprint data (kernel, OS, package digest, capabilities) into a "
        "device's sitemap row. Top-level keys overwrite; capabilities sub-keys deep-merge. "
        "Run discover_and_map first to populate the device. See the "
        "configure_host_fingerprint prompt for the conversational workflow."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "hostname": {"type": "string", "description": "Hostname of the device to fingerprint"},
            "fingerprint": {
                "type": "object",
                "description": (
                    "Fingerprint dict. Recognized top-level keys: kernel_name, kernel_version, "
                    "os_name, os_version, package_fingerprint, capabilities. Unknown top-level "
                    "keys are dropped server-side. capabilities is a freeform sub-dict."
                ),
                "properties": {
                    "kernel_name": {"type": "string"},
                    "kernel_version": {"type": "string"},
                    "os_name": {"type": "string"},
                    "os_version": {"type": "string"},
                    "package_fingerprint": {"type": "string"},
                    "capabilities": {"type": "object", "additionalProperties": True},
                },
                "additionalProperties": False,
            },
        },
        "required": ["hostname", "fingerprint"],
    },
},
```

**Description-only edit for `discover_and_map`** (D-06c — append to current line 7):
```python
"description": (
    "Discover a device via SSH and store it in the network site map database. "
    "Recommended follow-up: run the configure_host_fingerprint prompt to capture "
    "per-host capability signals for drift detection."
),
```

**Preview-tool pattern** (`infrastructure_tools_schema.py:275-315`):
```python
INFRASTRUCTURE_TOOLS["decommission_device_preview"] = {
    "description": (
        "Preview what decommission_device would affect without executing. "
        "Returns a structured dry-run report. No infrastructure is modified."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "device_id": {"type": "integer", ...},
            ...
        },
        "required": ["device_id"],
    },
}
```

**Add `update_device_fingerprint_preview`** with identical inputSchema to `update_device_fingerprint` and a preview-flavored description. Implementation: thin wrapper that calls `merge_fingerprint(stored, incoming)` without persisting and returns the would-be result.

---

### `src/homelab_mcp/tool_schemas/ssh_tools_schema.py` — description tweak

**Analog:** line 7 description string.

**Edit to existing description** (current text at line 7):
```python
"ssh_discover": {
    "description": "SSH into a system and gather hardware/system information. If credentials were stored with `credentials add`, ...",
```

Append one sentence (per D-06c): `"... Recommended follow-up after onboarding: run the configure_host_fingerprint prompt to capture per-host capability signals for drift detection."`

---

### `src/homelab_mcp/tool_handlers/network_handlers.py` — new `handle_update_device_fingerprint`

**Analog:** `handle_discover_and_map` (`network_handlers.py:10-15`) — same module, same hostname validation, same return shape.

**Handler pattern:**
```python
async def handle_discover_and_map(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle discover_and_map tool."""
    validate_hostname(arguments["hostname"])
    sitemap = NetworkSiteMap()
    result = await discover_and_store(sitemap, **arguments)
    return {"content": [{"type": "text", "text": result}]}
```

**New handler shape** (place after `handle_purge_failed_discoveries` at line 84):
```python
async def handle_update_device_fingerprint(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle update_device_fingerprint tool (Phase 38 D-05).

    Filters unknown top-level keys (D-05b) since MCP framework does not
    validate inputSchema (RESEARCH.md Items CONTEXT.md Missed §5).
    """
    RECOGNIZED_TOP_LEVEL = {
        "kernel_name", "kernel_version", "os_name", "os_version",
        "package_fingerprint", "capabilities",
    }
    validate_hostname(arguments["hostname"])
    fp_in = arguments.get("fingerprint", {})
    if not isinstance(fp_in, dict):
        result = json.dumps({
            "status": "error",
            "error": "`fingerprint` must be an object (got {type(fp_in).__name__})",
        })
        return {"content": [{"type": "text", "text": result}]}
    cleaned = {k: v for k, v in fp_in.items() if k in RECOGNIZED_TOP_LEVEL}

    sitemap = NetworkSiteMap()
    try:
        merged = sitemap.db_adapter.update_device_fingerprint(arguments["hostname"], cleaned)
    except ValueError as e:
        result = json.dumps({
            "status": "error",
            "error": str(e),
            "hint": "Run discover_and_map for this hostname first.",
        })
        return {"content": [{"type": "text", "text": result}]}

    result = json.dumps({"status": "success", "hostname": arguments["hostname"], "fingerprint": merged}, indent=2)
    return {"content": [{"type": "text", "text": result}]}
```

(Add a sibling `handle_update_device_fingerprint_preview` if D-05c ships — same code minus the `update_device_fingerprint` call; instead read existing fingerprint via `db_adapter.get_all_devices()` filter, call `merge_fingerprint(stored, cleaned)` directly, and return without writing.)

---

### `src/homelab_mcp/tool_handlers/__init__.py` — register new handler

**Analog:** existing `# Network tools` block (`__init__.py:82-89`).

**Pattern:**
```python
# Network tools
"discover_and_map": handle_discover_and_map,
"bulk_discover_and_map": handle_bulk_discover_and_map,
"get_network_sitemap": handle_get_network_sitemap,
"analyze_network_topology": handle_analyze_network_topology,
"suggest_deployments": handle_suggest_deployments,
"get_device_changes": handle_get_device_changes,
"purge_failed_discoveries": handle_purge_failed_discoveries,
```

**Add to import block at top (lines 23-31):**
```python
from .network_handlers import (
    handle_analyze_network_topology,
    handle_bulk_discover_and_map,
    handle_discover_and_map,
    handle_get_device_changes,
    handle_get_network_sitemap,
    handle_purge_failed_discoveries,
    handle_suggest_deployments,
    handle_update_device_fingerprint,           # Phase 38
    handle_update_device_fingerprint_preview,    # Phase 38 D-05c (if shipped)
)
```

**Add to TOOL_HANDLERS dict** (after `purge_failed_discoveries` at line 89):
```python
    "purge_failed_discoveries": handle_purge_failed_discoveries,
    "update_device_fingerprint": handle_update_device_fingerprint,                  # Phase 38
    "update_device_fingerprint_preview": handle_update_device_fingerprint_preview,  # Phase 38 D-05c
```

---

### `src/homelab_mcp/tool_annotations.py` — annotations for the new tool(s)

**Analog (mutating non-destructive):** `_MUTATING_ANNOTATIONS["discover_and_map"]` (`tool_annotations.py:80-84`).

**Pattern:**
```python
"discover_and_map": ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=True,
),
```

**Add inside `_MUTATING_ANNOTATIONS` dict** (Phase 38 — `idempotentHint=True` because identical fingerprint input produces identical merged output):
```python
"update_device_fingerprint": ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=True,
),
```

**Analog (read-only / preview):** `_READ_ONLY_TOOLS` list at `tool_annotations.py:23-52`.

**Add `update_device_fingerprint_preview`** to `_READ_ONLY_TOOLS` (D-05c — preview reads but doesn't write):
```python
_READ_ONLY_TOOLS = [
    ...
    "decommission_device_preview",
    "delete_proxmox_vm_preview",
    "remove_vm_preview",
    "destroy_terraform_service_preview",
    "rollback_infrastructure_changes_preview",
    "update_device_fingerprint_preview",  # Phase 38 D-05c
]
```

---

### `src/homelab_mcp/server.py` — `MUTATING_TOOLS` frozenset

**Analog:** `MUTATING_TOOLS` literal at `server.py:168-173`.

**Pattern:**
```python
#: Tools that write new device rows to the database.
#: A successful (non-error, non-dry-run) call to any of these tools triggers
#: a notifications/resources/list_changed push to subscribed clients.
MUTATING_TOOLS: frozenset[str] = frozenset(
    {
        "discover_and_map",
        "bulk_discover_and_map",
    }
)
```

**Update to include `update_device_fingerprint`** (Phase 38 — RESEARCH.md Items CONTEXT.md Missed §2):
```python
MUTATING_TOOLS: frozenset[str] = frozenset(
    {
        "discover_and_map",
        "bulk_discover_and_map",
        "update_device_fingerprint",  # Phase 38: merge writes new fingerprint into device row
    }
)
```

`update_device_fingerprint_preview` is NOT added — it's read-only.

---

### `src/homelab_mcp/prompt_registry.py` — `configure_host_fingerprint` prompt

**Analog:** `connect_to_device` (`prompt_registry.py:52-62, 125-154, 199-200`).

**Registry entry pattern** (`prompt_registry.py:52-62`):
```python
"connect_to_device": types.Prompt(
    name="connect_to_device",
    description="Step-by-step onboarding workflow for connecting a new device to the homelab",
    arguments=[
        types.PromptArgument(
            name="hostname",
            description="Hostname or IP address of the new device to onboard",
            required=True,
        )
    ],
),
```

**Add to `HOMELAB_PROMPTS` dict** (after `connect_to_device`, around line 62):
```python
"configure_host_fingerprint": types.Prompt(
    name="configure_host_fingerprint",
    description=(
        "Conversational workflow for capturing per-host capability fingerprints "
        "(GPU passthrough state, Vulkan/CUDA versions, ZFS pool config, etc.) "
        "to enable Phase 39 changed-infrastructure drift detection."
    ),
    arguments=[
        types.PromptArgument(
            name="hostname",
            description="Hostname or IP of the device to configure fingerprint tracking for",
            required=True,
        )
    ],
),
```

**Builder pattern** (`prompt_registry.py:125-154`):
```python
def _build_connect_to_device_result(args: dict[str, str]) -> types.GetPromptResult:
    """Build the connect_to_device prompt result (TOFU-03, Phase 33 D-13/D-18/D-22)."""
    hostname = args.get("hostname", "<hostname>")
    text = f"""Follow these steps to onboard {hostname} into your homelab:

1. Ensure you have an SSH-accessible user on {hostname} with sudo privileges. ...
...
If any step fails, fix the issue before proceeding to the next step."""
    return types.GetPromptResult(
        description="Full device onboarding workflow",
        messages=[_make_user_message(text)],
    )
```

**Add `_build_configure_host_fingerprint_result`** — full text excerpt is in RESEARCH.md "Code Examples" §`configure_host_fingerprint` MCP prompt (lines 461-505 of RESEARCH.md). Keep the role-hint inference rules (Proxmox VE, NVIDIA, AMD, TrueNAS) per D-06b.

**Dispatcher pattern** (`prompt_registry.py:192-208`):
```python
def get_prompt_result(name: str, arguments: dict[str, str] | None) -> types.GetPromptResult:
    args = arguments or {}
    if name == "decommission_device_workflow":
        return _build_decommission_result(args)
    elif name == "deploy_service_workflow":
        return _build_deploy_service_result(args)
    elif name == "homelab_health_check":
        return _build_health_check_result(args)
    elif name == "connect_to_device":
        return _build_connect_to_device_result(args)
    else:
        raise McpError(...)
```

**Add dispatcher case before the `else`:**
```python
elif name == "configure_host_fingerprint":
    return _build_configure_host_fingerprint_result(args)
```

---

### `tests/test_ssh_tools.py` — refactor brittle mock + new fingerprint tests

**Analog:** `STDOUT_BY_CMD` lookup pattern (`tests/test_ssh_tools.py:507-525`).

**Pattern to MIRROR for the refactor of `test_ssh_discover_success` (lines 16-152):**
```python
STDOUT_BY_CMD = {
    "hostname": "pve1\n",
    "nproc": "4\n",
    "cpuinfo": "model name : CPU Model Z9\n",
    "free": "              total        used        free      shared  buff/cache   available\nMem:    8589934592  2147483648  4294967296           0  2147483648  5368709120\n",
    "df": "Filesystem     Type  1B-blocks       Used   Available Use% Mounted on\n/dev/sda1      ext4  100000000000  40000000000  60000000000  40% /\n",
    "ip": '[{"ifname":"eth0","operstate":"UP","addr_info":[{"family":"inet","local":"10.0.0.5"}]}]\n',
    "uptime": "up 2 days, 3 hours\n",
    "os-release": 'PRETTY_NAME="Debian 12"\n',
    "lsusb": "Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub\n",
    "lspci": "00:00.0 Host bridge: Intel Corporation Device 4660 (rev 02)\n",
    "lsblk": "",
}

async def _mock_run_with_timeout(conn, command, *, cmd_name, timed_out, timeout=10.0):
    if cmd_name == "lsblk":
        timed_out.append("lsblk")
        return None
    return _fake_cp(STDOUT_BY_CMD.get(cmd_name, ""))

monkeypatch.setattr(ssh_tools, "_run_with_timeout", _mock_run_with_timeout)
```

**Refactor approach:** rewrite the existing `test_ssh_discover_success` (lines 16-152) to use the same `monkeypatch.setattr(ssh_tools, "_run_with_timeout", _mock_run_with_timeout)` pattern instead of the fixed-order list mock at lines 76-100. Then add new probe entries:
```python
STDOUT_BY_CMD = {
    ...,
    "uname-s": "Linux\n",
    "uname-r": "6.5.13-1-pve\n",
    "os-release-full": (
        'NAME="Proxmox VE"\n'
        'PRETTY_NAME="Proxmox VE 8.2.4"\n'
        'VERSION_ID="8.2.4"\n'
    ),
    "dpkg-fingerprint": "abc123def456789  -\n",
}
```

**New test methods** (mirror Phase 35 D-17c `test_ssh_discover_system_partial_phase35` pattern):
- `test_ssh_discover_populates_fingerprint_phase38` — assert `result["data"]["fingerprint"]["kernel_name"] == "Linux"` etc.
- `test_ssh_discover_partial_when_dpkg_missing_phase38` — `dpkg-fingerprint` returns exit_status=1, assert `partial: True` AND `package_fingerprint` key absent from `fingerprint` dict.

---

### `tests/test_sitemap.py` — extend fixture + add fingerprint tests

**Analog:** `sample_ssh_discovery_success` (`tests/test_sitemap.py:28-57`) + `test_parse_discovery_output_success` (lines 104-124).

**Fixture pattern:**
```python
@pytest.fixture
def sample_ssh_discovery_success():
    return json.dumps({
        "status": "success",
        "hostname": "test-server",
        "connection_ip": "192.168.1.100",
        "data": {
            "cpu": {"model": "Intel Core i7-9700K", "cores": "8"},
            ...
            "uptime": "up 5 days, 2 hours, 30 minutes",
            "os": "Ubuntu 22.04.3 LTS",
        },
    })
```

**Extend fixture by adding a `fingerprint` block** under `data`:
```python
"data": {
    ...
    "os": "Ubuntu 22.04.3 LTS",
    "fingerprint": {
        "kernel_name": "Linux",
        "kernel_version": "6.5.13-1-pve",
        "os_name": "Proxmox VE 8.2.4",
        "os_version": "8.2.4",
        "package_fingerprint": "sha256:abc123",
    },
},
```

**Test pattern** (`test_parse_discovery_output_success` at lines 104-124):
```python
def test_parse_discovery_output_success(self, sitemap, sample_ssh_discovery_success):
    device = sitemap.parse_discovery_output(sample_ssh_discovery_success)
    assert device.hostname == "test-server"
    ...
    network_data = json.loads(device.network_interfaces)
    assert network_data[0]["name"] == "eth0"
```

**Add new tests:**
- `test_parse_discovery_output_fingerprint_phase38` — assert `device.fingerprint` is a JSON string, `json.loads(device.fingerprint)["kernel_name"] == "Linux"`.
- `test_store_and_retrieve_fingerprint_phase38` — round-trip via `store_device` → `get_all_devices` and assert `devices[0]["fingerprint"]["kernel_name"] == "Linux"` (note: parsed back to dict by SQLite get_all_devices flatten loop).

---

### `tests/test_database.py` — round-trip + adapter method tests

**Analog:** `test_store_and_retrieve_device` (`tests/test_database.py:53-81`).

**Pattern:**
```python
def test_store_and_retrieve_device(self, adapter):
    device_data = {
        "hostname": "test-server",
        "connection_ip": "192.168.1.10",
        "last_seen": datetime.now().isoformat(),
        "status": "success",
        "cpu_model": "Intel Core i7",
        ...
    }
    device_id = adapter.store_device(device_data)
    devices = adapter.get_all_devices()
    assert devices[0]["hostname"] == "test-server"
    assert devices[0]["cpu_cores"] == 8
```

**Add to `TestSQLiteAdapter`:**
- `test_store_and_retrieve_fingerprint` — store with `"fingerprint": json.dumps({"kernel_name": "Linux", ...})`, read back, assert `devices[0]["fingerprint"]["kernel_name"] == "Linux"`.
- `test_update_device_fingerprint_deep_merge_capabilities` — store fingerprint with `capabilities.vulkan`, call `adapter.update_device_fingerprint(hostname, {"capabilities": {"cuda": {...}}})`, read back, assert BOTH `vulkan` and `cuda` present.
- `test_update_device_fingerprint_overwrites_top_level` — store with `kernel_version="6.0.0"`, update with `kernel_version="6.5.13"`, assert overwritten.
- `test_update_device_fingerprint_missing_hostname_raises` — call against unknown hostname, assert `ValueError` with message containing `"discover_and_map"`.

**Repeat the same four tests inside `TestPostgreSQLAdapter`** (per the existing skip-if-postgres-unavailable pattern in the file).

---

### `tests/test_migration.py` (or `tests/test_database.py`) — ALTER TABLE idempotency test

**Analog:** existing `add_column_` assertions live in `tests/test_database.py:580-613` (NOT in `test_migration.py`, which covers `DatabaseMigrator` cross-DB transfer).

**Pattern** (`tests/test_database.py:578-613`):
```python
applied1 = run_sqlite_migrations(db_path=db_path)
assert "dedupe_zombie_device_rows" in applied1, applied1
assert any(a.startswith("add_column_") for a in applied1), applied1
assert "drop_stale_hostname_ip_unique" in applied1, applied1

# ... assertions about migrated state ...

applied2 = run_sqlite_migrations(db_path=db_path)
assert "dedupe_zombie_device_rows" not in applied2, applied2
assert not any(a.startswith("add_column_") for a in applied2), applied2
assert "drop_stale_hostname_ip_unique" not in applied2, applied2
```

**Add new test in `tests/test_database.py`** (mirror exactly):
```python
def test_run_sqlite_migrations_adds_fingerprint_column_idempotently_phase38(tmp_path):
    db_path = str(tmp_path / "legacy.db")
    # Build a pre-Phase-38 schema (with usb/pci/block but no fingerprint).
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hostname TEXT NOT NULL,
            connection_ip TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            status TEXT NOT NULL,
            usb_devices TEXT, pci_devices TEXT, block_devices TEXT
        )
    """)
    conn.commit()
    conn.close()

    applied1 = run_sqlite_migrations(db_path=db_path)
    assert "add_column_fingerprint" in applied1

    # Verify column exists.
    conn = sqlite3.connect(db_path)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(devices)").fetchall()}
    assert "fingerprint" in cols
    conn.close()

    # Re-run is idempotent.
    applied2 = run_sqlite_migrations(db_path=db_path)
    assert "add_column_fingerprint" not in applied2
```

---

### `tests/test_tools.py` — MCP routing test

**Analog:** `test_execute_discover_and_map` (`tests/test_tools.py:116-130`).

**Pattern:**
```python
@pytest.mark.asyncio
@patch("src.homelab_mcp.tool_handlers.network_handlers.discover_and_store")
async def test_execute_discover_and_map(mock_discover_and_store):
    mock_response = json.dumps({"status": "success", ...})
    mock_discover_and_store.return_value = mock_response
    result = await execute_tool("discover_and_map", {"hostname": "test-host", ...})
    assert "content" in result
```

**Add tests:**
- `test_execute_update_device_fingerprint_success_phase38` — patch `NetworkSiteMap`/`db_adapter.update_device_fingerprint`, call `execute_tool("update_device_fingerprint", {"hostname": ..., "fingerprint": {...}})`, assert returned merged dict.
- `test_update_device_fingerprint_filters_unknown_top_level_phase38` — pass `{"fingerprint": {"kernel_name": "X", "bogus_key": "Y"}}`, assert merged result excludes `bogus_key`.
- `test_update_device_fingerprint_missing_hostname_phase38` — patch adapter to raise `ValueError`, assert response contains `status=error` and a hint to run `discover_and_map`.
- `test_update_device_fingerprint_malformed_dict_phase38` — pass `{"fingerprint": "not a dict"}`, assert structured error.
- `test_update_device_fingerprint_annotations_phase38` — `from src.homelab_mcp.tool_annotations import get_tool_annotations`, assert non-None and `idempotentHint is True`.

Also update the `test_get_available_tools` count assertion at `tests/test_tools.py:16` (from `len(tools) == 52` to `53` or `54` depending on whether preview ships).

---

### `tests/test_mcp_prompts.py` — `configure_host_fingerprint` registration

**Analog:** `test_connect_to_device_prompt` (`tests/test_mcp_prompts.py:96-129`).

**Pattern:**
```python
def test_connect_to_device_prompt() -> None:
    from mcp.types import GetPromptResult
    from homelab_mcp.prompt_registry import get_prompt_result

    result = get_prompt_result("connect_to_device", {"hostname": "test-host"})
    assert isinstance(result, GetPromptResult)
    assert len(result.messages) >= 1
    combined_text = " ".join(msg.content.text for msg in result.messages if hasattr(msg.content, "text")).lower()
    assert "credentials add" in combined_text
    assert "register_server" in combined_text
    assert "ssh_discover" in combined_text
    assert "discover_and_map" in combined_text
    assert "test-host" in combined_text
```

**Add `test_configure_host_fingerprint_prompt_phase38`:**
- Assert prompt is registered in `HOMELAB_PROMPTS`.
- Assert `get_prompt_result("configure_host_fingerprint", {"hostname": "test.local"})` returns `GetPromptResult`.
- Assert combined text mentions: `get_network_sitemap`, `ssh_execute_command`, `update_device_fingerprint`, `capabilities`, `test.local` (hostname interpolated).

---

### `tests/test_mcp_resources.py` — resource notification test (NOT `test_logging_notifications.py`)

**Analog:** `test_discover_and_map_sends_list_changed` (`tests/test_mcp_resources.py:260-271`).

**Pattern:**
```python
@pytest.mark.asyncio
async def test_discover_and_map_sends_list_changed(mocker: MockerFixture) -> None:
    """handle_call_tool for discover_and_map sends resource list changed notification on success."""
    mock_handler = AsyncMock(return_value={"content": [{"type": "text", "text": '{"status": "ok"}'}]})
    mocker.patch("src.homelab_mcp.server.get_tool_handler", return_value=mock_handler)

    mock_session, mock_ctx = _make_mock_session()
    mocker.patch.object(type(server), "request_context", new_callable=PropertyMock, return_value=mock_ctx)

    await handle_call_tool("discover_and_map", {})

    mock_session.send_resource_list_changed.assert_awaited_once()
```

**Add new test** (verbatim mirror with tool name swapped):
```python
@pytest.mark.asyncio
async def test_update_device_fingerprint_sends_list_changed_phase38(mocker: MockerFixture) -> None:
    """Phase 38: handle_call_tool for update_device_fingerprint fires notifications/resources/list_changed."""
    mock_handler = AsyncMock(return_value={"content": [{"type": "text", "text": '{"status": "success"}'}]})
    mocker.patch("src.homelab_mcp.server.get_tool_handler", return_value=mock_handler)

    mock_session, mock_ctx = _make_mock_session()
    mocker.patch.object(type(server), "request_context", new_callable=PropertyMock, return_value=mock_ctx)

    await handle_call_tool("update_device_fingerprint", {"hostname": "x", "fingerprint": {}})

    mock_session.send_resource_list_changed.assert_awaited_once()
```

Also add `test_update_device_fingerprint_preview_no_notification_phase38` (preview should NOT fire — read-only).

---

### `tests/integration/test_sitemap_integration.py` — Docker fingerprint assertion

**Analog:** `TestSitemapIntegration.test_sitemap_workflow_with_mock_discovery` (`tests/integration/test_sitemap_integration.py:36-106`) + `test_container` fixture (`tests/integration/conftest.py:19-78`).

**Container fixture provides** (`conftest.py:70-78`):
```python
yield {
    "container": container,
    "hostname": "localhost",
    "port": 2222,
    "admin_user": "testadmin",
    "admin_pass": "testpass123",
    ...
}
```

**Add new integration test** (Debian-family Ubuntu container so `dpkg -l` works natively):
```python
@pytest.mark.asyncio
async def test_discover_populates_fingerprint_against_docker_phase38(self, test_container, temp_db):
    """Phase 38: live SSH discovery against Docker container populates fingerprint sub-dict."""
    sitemap = NetworkSiteMap(db_path=temp_db, db_type="sqlite")
    result = await discover_and_store(
        sitemap,
        hostname=test_container["hostname"],
        username=test_container["admin_user"],
        password=test_container["admin_pass"],
        port=test_container["port"],
    )
    devices = sitemap.get_all_devices()
    assert len(devices) == 1
    fp = devices[0].get("fingerprint")
    assert fp is not None
    assert fp.get("kernel_name") == "Linux"
    assert fp.get("kernel_version"), "kernel_version should be populated from uname -r"
    assert fp.get("package_fingerprint", "").startswith("sha256:")
```

---

## Shared Patterns

### Hostname-natural-key lookup (Phase 35 D-01)

**Source:** `src/homelab_mcp/database.py:200-211` (SQLite) + `database.py:599-609` (Postgres).
**Apply to:** new `update_device_fingerprint` adapter method on both SQLite + Postgres adapters.
**AST guard:** `tests/test_ast_regression.py:392 test_store_device_matches_on_hostname_alone_phase35` — ANY new query against the `devices` table that uses hostname as a key must use this pattern.
```python
hostname_key = device_data["hostname"]
if hostname_key in (None, "", "unknown"):
    cursor.execute(
        "SELECT id FROM devices WHERE hostname = ? AND connection_ip = ?",
        (hostname_key, device_data["connection_ip"]),
    )
else:
    cursor.execute(
        "SELECT id FROM devices WHERE hostname = ?",
        (hostname_key,),
    )
```

### Per-probe SSH timeout wrapping (Phase 35 D-05)

**Source:** `src/homelab_mcp/ssh_tools.py:490-516` (`_run_with_timeout`).
**Apply to:** every new probe in `ssh_discover_system` (uname-s, uname-r, os-release-full, dpkg-fingerprint).
**AST guard:** `tests/test_ast_regression.py:447 test_ssh_discover_system_wraps_every_conn_run_phase35` — auto-fails if any new `conn.run(...)` slips in without going through `_run_with_timeout`.
```python
result = await _run_with_timeout(
    conn, "<command>", cmd_name="<short-name>", timed_out=timed_out_commands
)
if result and result.exit_status == 0 and result.stdout:
    ...  # populate fingerprint_info
```

### Hostname validation in handlers (SEC-03)

**Source:** `src/homelab_mcp/validation.py:22-61` + every existing handler that takes a hostname (e.g., `network_handlers.py:12`).
**Apply to:** `handle_update_device_fingerprint` and (if shipped) `handle_update_device_fingerprint_preview`.
```python
from ..validation import validate_hostname

async def handle_update_device_fingerprint(arguments: dict[str, Any]) -> dict[str, Any]:
    validate_hostname(arguments["hostname"])
    ...
```

### Handler return shape

**Source:** every handler in `tool_handlers/network_handlers.py` (e.g., line 15).
**Apply to:** new fingerprint handler(s).
```python
return {"content": [{"type": "text", "text": result_str}]}
```

### Structured error envelope inside handlers

**Source:** `tool_handlers/network_handlers.py:74-83` (purge_failed_discoveries) + `tools.py` execute_tool error path.
**Apply to:** all error returns from `handle_update_device_fingerprint` (missing hostname, malformed dict).
```python
result = json.dumps({"status": "error", "error": "...", "hint": "..."})
return {"content": [{"type": "text", "text": result}]}
```

### JSON-string-in-dataclass + decode-on-read convention (Phase 35 D-09b)

**Source:** `src/homelab_mcp/sitemap.py:55-57` (declare as `str | None`) + `sitemap.py:121-127` (`json.dumps` at parse time) + `database.py:321-327` (`json.loads` at read time) + `database.py:580-582` Postgres path uses `_maybe_json_load` helper.
**Apply to:** `NetworkDevice.fingerprint`, `parse_discovery_output` branch, `SQLiteAdapter.get_all_devices` JSON-decode loop, `PostgreSQLAdapter.store_device` `_maybe_json_load` call, `PostgreSQLAdapter.get_all_devices` flatten dict.

### Tool registration trio

**Source:** every existing tool (e.g., `discover_and_map`).
**Apply to:** every new tool (`update_device_fingerprint` and optionally `update_device_fingerprint_preview`).
**The three sites:**
1. `tool_schemas/<area>_schema.py` — `inputSchema` definition.
2. `tool_handlers/<area>_handlers.py` — async handler function.
3. `tool_handlers/__init__.py` `TOOL_HANDLERS` dict — name → handler mapping.
4. `tool_annotations.py` — `_MUTATING_ANNOTATIONS` or `_READ_ONLY_TOOLS` (CONTEXT.md missed this; RESEARCH.md §1).
5. `server.py` `MUTATING_TOOLS` — only if the tool writes to the device DB (CONTEXT.md missed this; RESEARCH.md §2).

Forgetting any of these five sites is the most likely defect for Phase 38.

### MCP prompt registration trio

**Source:** all four Phase 14 prompts (`prompt_registry.py:19-208`).
**Apply to:** `configure_host_fingerprint`.
**The three sites:**
1. `HOMELAB_PROMPTS` dict (lines 19-63) — `types.Prompt(name=..., description=..., arguments=[...])`.
2. `_build_<name>_result` function (mirror lines 125-154) — return `types.GetPromptResult(messages=[_make_user_message(text)])`.
3. `get_prompt_result` dispatcher `elif` clause (mirror line 199-200).

### MCP framework does NOT auto-validate inputSchema

**Source:** RESEARCH.md Items CONTEXT.md Missed §5 — verified by reading `server.py:418-458` and grepping for `additionalProperties` / `jsonschema` (zero matches).
**Apply to:** `handle_update_device_fingerprint` MUST do its own dict-shape validation in Python and filter unknown top-level keys.
```python
RECOGNIZED_TOP_LEVEL = {
    "kernel_name", "kernel_version", "os_name", "os_version",
    "package_fingerprint", "capabilities",
}
cleaned = {k: v for k, v in fp_in.items() if k in RECOGNIZED_TOP_LEVEL}
```

### Locale-stable dpkg digest (RESEARCH.md Pitfall 1)

**Source:** RESEARCH.md Pitfall 1 + reproducible-builds.org guidance.
**Apply to:** the new dpkg-fingerprint probe in `ssh_discover_system`.
```python
"LC_ALL=C dpkg -l 2>/dev/null | sort | sha256sum"
```

### Read-merge-write for both SQLite and Postgres adapter methods (RESEARCH.md Pitfall 4)

**Source:** RESEARCH.md Pitfall 4 — explicitly avoid `jsonb_set` / `||` for path-parity with SQLite.
**Apply to:** Postgres `update_device_fingerprint` adapter method.
**Pattern:** SELECT existing row → parse JSON in Python → `merge_fingerprint(stored, incoming)` → UPDATE with full new value. Identical structure to SQLite path; only placeholder syntax differs.

---

## No Analog Found

None — every artifact in scope has a verified mirror in the existing codebase. Every pattern Phase 38 needs has been established by Phases 14, 15, 33, 35, or 36.

---

## Metadata

**Analog search scope:**
- `src/homelab_mcp/ssh_tools.py` (probe pattern + `_run_with_timeout`)
- `src/homelab_mcp/sitemap.py` (NetworkDevice + parse_discovery_output)
- `src/homelab_mcp/database.py` (SQLite + Postgres adapter patterns + `_maybe_json_load`)
- `src/homelab_mcp/migration.py` (Phase 35 D-09c ALTER TABLE block + schema rebuild branch)
- `src/homelab_mcp/tool_schemas/network_tools_schema.py` + `ssh_tools_schema.py` + `infrastructure_tools_schema.py` (preview pattern)
- `src/homelab_mcp/tool_handlers/network_handlers.py` + `__init__.py`
- `src/homelab_mcp/tool_annotations.py` (mutating + read-only registries)
- `src/homelab_mcp/server.py` (`MUTATING_TOOLS`)
- `src/homelab_mcp/prompt_registry.py` (Phase 14 prompts)
- `src/homelab_mcp/validation.py` (`validate_hostname`)
- `tests/test_ssh_tools.py` (`STDOUT_BY_CMD` lookup pattern lines 507-525 vs. brittle list-mock at 16-152)
- `tests/test_sitemap.py` (fixture + `test_parse_discovery_output_success`)
- `tests/test_database.py` (round-trip test + `add_column_` migration assertions at 580-613)
- `tests/test_mcp_prompts.py` (`test_connect_to_device_prompt` at line 96)
- `tests/test_mcp_resources.py` (`test_discover_and_map_sends_list_changed` at line 260)
- `tests/test_tools.py` (`test_execute_discover_and_map`)
- `tests/integration/conftest.py` (`test_container` fixture)
- `tests/integration/test_sitemap_integration.py` (`TestSitemapIntegration` class)

**Files scanned:** 18 source/test files end-to-end or in targeted ranges; 4 RESEARCH.md sections re-verified (Code Examples, Items CONTEXT.md Missed, Common Pitfalls, Validation Architecture).

**Pattern extraction date:** 2026-04-25

## PATTERN MAPPING COMPLETE
