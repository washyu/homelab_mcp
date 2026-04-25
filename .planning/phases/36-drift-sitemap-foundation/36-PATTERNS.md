# Phase 36: Drift Sitemap Foundation - Pattern Map

**Mapped:** 2026-04-25
**Files analyzed:** 19 (8 source modules + 7 test files + 1 doc + 3 cross-cutting concerns)
**Analogs found:** 19 / 19 (100% — all in-tree precedents from Phase 33 / 34 / 35)

---

## File Classification

| New/Modified File | Action | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|--------|------|-----------|----------------|---------------|
| `src/homelab_mcp/drift_detection.py` | rewrite | service (scan orchestrator) | request-response (async iterate + probe) | `src/homelab_mcp/sitemap.py` `analyze_network_topology` (lines 176-225) — same `db_adapter.get_all_devices()` consumer idiom | exact (role + data flow) |
| `src/homelab_mcp/database.py` | delete-symbols | model (DB adapter) | CRUD removal | Phase 33 `ssh_credentials` adapter-method removal (same file, prior commits) | exact |
| `src/homelab_mcp/migration.py` | extend | migration (idempotent startup) | batch | `migration.py:37-62` (SQLite ssh_credentials drop) + `migration.py:281-305` (Postgres ssh_credentials drop) | exact (verbatim shape reuse) |
| `src/homelab_mcp/tool_handlers/drift_handlers.py` | simplify | controller (MCP tool handler) | request-response | `src/homelab_mcp/tool_handlers/network_handlers.py` (thin pass-through) | exact |
| `src/homelab_mcp/tool_handlers/proxmox_handlers.py` | delete-callsites | controller (MCP tool handler) | request-response | self (3 sibling handlers in same file with identical 3-block shape) | exact |
| `src/homelab_mcp/tool_schemas/drift_tools_schema.py` | rewrite description | config (schema) | static | self (current schema; description string only) | exact |
| `src/homelab_mcp/server.py` | rewrite description (research-corrected) | config (resource registry) | static | self — `HOMELAB_RESOURCES["homelab://drift/latest"]` at lines 149-152 | exact |
| `src/homelab_mcp/resource_readers.py` | no-op confirmed | utility (resource reader) | request-response | self — reader is shape-agnostic at lines 127-138 | exact |
| `docs/tool-reference.md` | add entry | documentation | static | other tool entries (e.g., `### refresh_terraform_service` at line 956 — drift-adjacent precedent) | partial (no existing drift entry) |
| `tests/test_drift_detection.py` | full rewrite | test (unit) | mocked async | `tests/test_drift_detection.py:8-77` (existing harness) + `tests/test_drift_resource.py` AsyncMock idiom | exact |
| `tests/test_drift_wiring.py` | surgical update | test (unit, schema/handler wiring) | mocked async | self — keep schema + annotation tests, rewrite only `TestDriftHandlerRegistration` | exact |
| `tests/test_database.py` | delete-class | test (unit, adapter CRUD) | n/a | self — `TestDriftBaselines` class at lines 357-468 | exact |
| `tests/test_drift_resource.py` | fixture rewrite only | test (unit, resource pass-through) | mocked async | self — sample fixture at lines 52-56 | exact |
| `tests/test_proxmox_baseline_hooks.py` | **DELETE FILE** | test (unit, baseline hooks) | n/a | n/a — entire file orphaned by D-11 (research finding) | n/a |
| `tests/test_proxmox_api.py` | surgical line-removal (4 lines) | test (unit, schema-passthrough) | n/a | self — patches at lines 1784/1825/1854/1893 | exact |
| `tests/test_ast_regression.py` | extend (consolidate) | test (meta, AST guard) | static | self — Phase 33/35 idiom at lines 24-46 + 142-178 | exact |
| `tests/test_migration.py` (or new file) | add idempotency tests | test (unit + integration) | mocked + Docker | `tests/test_database.py:642-727` (Phase 35 D-17b SQLite migration test) | exact (only changes `dedupe_zombie_device_rows` → `drop_drift_baselines_table`) |

---

## Pattern Assignments

### `src/homelab_mcp/drift_detection.py` (service, request-response, full rewrite)

**Analog 1 (consumer pattern):** `src/homelab_mcp/sitemap.py:176-225` `analyze_network_topology`

**Analog 2 (resolver-funnel pattern):** `src/homelab_mcp/proxmox_api.py:340-396` `get_proxmox_client` — already calls `resolve_proxmox_credentials` internally when `host` is set and no explicit auth.

**Imports pattern** (existing `drift_detection.py:1-13`, simplify):
```python
"""Infrastructure drift detection for homelab MCP server."""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import aiohttp

from .database import DatabaseAdapter
from .log_filter import sanitize_error
from .proxmox_api import CredentialNotFoundError, get_proxmox_client, resolve_proxmox_credentials

logger = logging.getLogger(__name__)
```

**Iteration pattern** — copy from `src/homelab_mcp/sitemap.py:176-200`:
```python
def analyze_network_topology(self) -> dict[str, Any]:
    """Analyze the network topology and provide insights."""
    devices = self.get_all_devices()                                 # ← entry point

    analysis = {
        "total_devices": len(devices),
        ...
    }

    for device in devices:
        if device["status"] != "success":                            # ← D-10a degenerate skip (status)
            continue
        # Skip degenerate rows that slipped past the status filter (defense
        # in depth for legacy/zombie rows with empty hostname).
        if not device.get("hostname"):                               # ← D-10a degenerate skip (hostname)
            continue
        ...
```

**Apply to scan_drift:** copy this exact `for device in devices: if status/hostname degenerate: continue` shape, then layer in the per-row `get_proxmox_client` + `resolve_proxmox_credentials` + `client.get("/cluster/status")` probe per the synthesized skeleton in RESEARCH.md §"Code Examples / scan_drift 2-bucket implementation skeleton" (lines 462-559).

**Resolver-call pattern** — copy from `proxmox_api.py:370-378`:
```python
# D-10: resolver fires only when host is known AND no explicit auth was provided.
if host and not api_token and not (username and password):
    resolved_token, scope, cluster_name = await resolve_proxmox_credentials(host, session=session)
    api_token = resolved_token
    logger.debug(
        "Proxmox credential resolved for host=%s via source=%s cluster=%s",
        host, scope, cluster_name,
    )
```
Apply: `scan_drift` calls `get_proxmox_client(host=row["hostname"], session=session)` first (which fires this internal resolver call). To capture `(scope, cluster_name)` for the per-row record (D-02), call `await resolve_proxmox_credentials(hostname, session=session)` again — the second call hits `_HOST_CLUSTER_CACHE` (`proxmox_api.py:243-265`, A4 in RESEARCH §Assumptions Log) and is effectively free.

**Symbols to DELETE:**
- `CONFIG_DRIFT_FIELDS` constant (line 16)
- `_diff_vm_config` function (lines 19-54)
- `update_baseline_after_mutation` function (lines 228-279)
- The current `scan_drift` body in its entirety (lines 57-225)

**Imports to DROP:** `asyncssh` (no SSH probe in 2-bucket interim), `from .proxmox_api import get_proxmox_vm_config, get_proxmox_vm_status` (replaced by `get_proxmox_client` + direct `client.get`).

---

### `src/homelab_mcp/database.py` (model, CRUD, delete-symbols)

**Analog:** Phase 33 `ssh_credentials` removal — same module, identical pattern (5 ABC methods + 5 SQLite impls + 5 Postgres stubs deleted in one go).

**Symbols to delete (resolve by symbol name, not line number — RESEARCH Pitfall 3):**
- `DatabaseAdapter.upsert_drift_baseline` ABC (lines 67-78)
- `DatabaseAdapter.get_drift_baseline` ABC (lines 80-88)
- `DatabaseAdapter.get_all_drift_baselines` ABC (lines 90-93)
- The `# Drift baseline CRUD methods` comment block above them (line 67)
- `SQLiteAdapter.upsert_drift_baseline` (lines 449-480 — note: the `# Drift baseline CRUD methods` comment at line 449 also goes)
- `SQLiteAdapter.get_drift_baseline` (lines 482-507)
- `SQLiteAdapter.get_all_drift_baselines` (lines 509-527)
- `PostgreSQLAdapter.upsert_drift_baseline` (lines 916-926)
- `PostgreSQLAdapter.get_drift_baseline` (lines 928-935)
- `PostgreSQLAdapter.get_all_drift_baselines` (lines 937-939)
- The `# Drift baseline CRUD methods (Phase 11 scope: SQLite only — stubs for ABC compliance)` comment at line 916
- `SQLiteAdapter.init_schema` `CREATE TABLE drift_baselines` block at lines 205-222 (also delete the `# Create drift_baselines table for VM configuration baseline storage` comment at line 205 + the `cursor.execute` for the index at lines 219-222)

**Verification after deletion:** `database.py` should have ZERO occurrences of the strings `drift_baseline` or `drift_baselines` (the AST guard in D-12 will enforce this).

---

### `src/homelab_mcp/migration.py` (migration, batch, extend)

**Analog (SQLite branch):** `migration.py:37-62` — Phase 33 D-01 `ssh_credentials` drop. **Verbatim shape reuse.**

**Concrete excerpt to copy and adapt** (from `migration.py:37-62`):
```python
# D-01: Drop legacy ssh_credentials table if it still exists (v1.6 cleanup).
# Keyring is now the single source of truth for remote credentials (CRED-04).
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

    print(
        "Dropped legacy ssh_credentials table (v1.6: keyring is now the sole credential store)",
        file=sys.stderr,
    )
    print(
        "NOTE: Any credentials previously stored in the database have been removed.\n"
        "Re-add them with: homelab-mcp credentials add <hostname> <username>",
        file=sys.stderr,
    )
```

**Adaptations for D-05 SQLite:**
- swap `name='ssh_credentials'` → `name='drift_baselines'`
- swap `DROP INDEX IF EXISTS idx_ssh_credentials_hostname` + `idx_ssh_credentials_device_id` → single `DROP INDEX IF EXISTS idx_drift_baselines_node_vmid` (only one index — verified at `database.py:219-222`)
- swap `DROP TABLE IF EXISTS ssh_credentials` → `DROP TABLE IF EXISTS drift_baselines`
- swap `applied_migrations.append("drop_ssh_credentials_table")` → `applied_migrations.append("drop_drift_baselines_table")`
- replace banner text with the D-08 phrasing:
  ```
  "Dropped legacy drift_baselines table (v1.7: sitemap is now the single source of truth for drift)"
  ```
  and:
  ```
  "NOTE: Pre-existing baseline rows are not preserved (per DRFT-21 architectural decision).\n"
  "      Drift now reports against the live sitemap; no manual baseline registration is needed."
  ```

**Placement:** after the existing Phase 35 stale-UNIQUE rebuild at line 222, replacing the existing CREATE block at lines 224-247.

**Analog (Postgres branch):** `migration.py:281-305` — Phase 33 D-01 ssh_credentials Postgres drop.

**Concrete excerpt to copy and adapt** (from `migration.py:281-305`):
```python
# D-01: Drop legacy ssh_credentials table if it still exists (v1.6 cleanup — Postgres path).
# Keyring is now the single source of truth for remote credentials (CRED-04).
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
    import sys  # noqa: PLC0415

    print(
        "Dropped legacy ssh_credentials table from Postgres (v1.6: keyring is now the sole credential store)",
        file=sys.stderr,
    )
    print(
        "NOTE: Any credentials previously stored in the database have been removed.\n"
        "Re-add them with: homelab-mcp credentials add <hostname> <username>",
        file=sys.stderr,
    )
```

**Adaptations for D-05 Postgres:**
- swap `'ssh_credentials'` table-name string → `'drift_baselines'`
- swap two `DROP INDEX` calls → single `DROP INDEX IF EXISTS idx_drift_baselines_node_vmid`
- swap `DROP TABLE` target → `drift_baselines`
- swap `applied_migrations.append("drop_ssh_credentials_table")` → `applied_migrations.append("drop_drift_baselines_table")`
- swap banner text matching SQLite (above) but with `from Postgres` prefix:
  ```
  "Dropped legacy drift_baselines table from Postgres (v1.7: sitemap is now the single source of truth for drift)"
  ```

**Placement:** after the existing Phase 35 Postgres stale-UNIQUE drop (around line 389 — verify by grep for `idx_devices_hostname_ip_unique` Postgres branch).

**Auto-create block to delete:** `migration.py:224-247`:
```python
# Check if drift_baselines table exists
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
    conn.commit()
    applied_migrations.append("create_drift_baselines_table")
```
This entire block disappears — replaced by the DROP step above.

---

### `src/homelab_mcp/tool_handlers/drift_handlers.py` (controller, request-response, simplify)

**Analog (current shape):** the file itself, lines 9-40.

**Imports pattern** (existing — keep as-is):
```python
import json
from typing import Any
from ..drift_detection import scan_drift
```

**Current handler (post-D-03 simplification target):**
```python
async def handle_scan_infrastructure_drift(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle scan_infrastructure_drift tool."""
    from ..server import get_resource_manager, set_latest_drift_report  # deferred

    rm = get_resource_manager()
    result = await scan_drift(
        session=rm.proxmox_session,
        db_adapter=rm.db_adapter,
        node=arguments.get("node"),
        vm_type=arguments.get("vm_type", "all"),
    )

    set_latest_drift_report(result)  # cache for homelab://drift/latest (DRFT-09)
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
```

**Block to DELETE (current lines 21-37):** the `if result.get("summary", {}).get("baselines_available", 0) == 0:` precondition early-return, including the entire `return {"content": [...]}` block with the `"no baseline available"` message.

**Why this is safe:** Phase 36's `scan_drift` returns `{"status": "success", ..., "scanned": 0, "probed_ok": [], "unreachable": []}` for the empty-sitemap case (D-03). No `summary.baselines_available` key exists in the new shape; the precondition would always evaluate to `0 == 0` and short-circuit, defeating D-03's purpose.

---

### `src/homelab_mcp/tool_handlers/proxmox_handlers.py` (controller, request-response, delete-callsites)

**Analog (callsite shape — appears 3× verbatim, lines 116-153, 156-192, 195-224):**

The exact 6-10 line block to remove from each handler:
```python
    from ..drift_detection import update_baseline_after_mutation       # ← deferred import
    from ..server import get_resource_manager
    ...
    if result.get("status") == "success":                              # ← guard block
        try:
            await update_baseline_after_mutation(
                node=arguments["node"],
                vmid=arguments["vmid"],
                vm_type="lxc",                                          # or "qemu" / arguments.get("vm_type", "qemu")
                tool_name="create_proxmox_lxc",                         # tool name varies per handler
                session=get_resource_manager().proxmox_session,
                db_adapter=get_resource_manager().db_adapter,
            )
        except Exception:
            logger.debug("Baseline update skipped for create_proxmox_lxc vmid=%s", arguments["vmid"])
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
```

**After Phase 36, each handler's tail becomes simply:**
```python
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
```

**Three identical surgical removals required:**

| Handler | Line range to remove | Comment |
|---------|----------------------|---------|
| `handle_create_proxmox_lxc` | line 118 (deferred import) + lines 141-152 (try/except block) | Keep `from ..server import get_resource_manager` (still needed) |
| `handle_create_proxmox_vm` | line 158 (deferred import) + lines 180-191 (try/except block) | Keep `from ..server import get_resource_manager` |
| `handle_clone_proxmox_vm` | line 197 (deferred import) + lines 212-223 (try/except block) | Keep `from ..server import get_resource_manager` |

**Verification after edit:** `grep -n "update_baseline_after_mutation" src/homelab_mcp/tool_handlers/proxmox_handlers.py` → zero matches.

---

### `src/homelab_mcp/tool_schemas/drift_tools_schema.py` (config, static, rewrite description)

**Analog (current shape):** the file itself, lines 1-28.

**Excerpt — current description (lines 5-9):**
```python
"description": (
    "Scan for infrastructure drift: config drift (CPU/memory/network changed outside MCP) "
    "and state drift (VMs offline that should be running). "
    "Returns structured report with drift_type, expected, actual, and scan_timestamp per finding."
),
```

**Phase 36 D-04 + RESEARCH Pitfall 4 — REPLACE (not append) with:**
```python
"description": (
    "Scan for infrastructure drift against the sitemap. Returns 2-bucket coverage report "
    "(probed_ok, unreachable) per resolved Proxmox host. "
    "Filter semantics under Phase 37 redesign — node/vm_type currently inert."
),
```

**`inputSchema.properties` (lines 11-25) — keep verbatim.** `node` and `vm_type` props stay; only the description changes.

**Critical correction from RESEARCH:** the current description references `drift_type`, `expected`, `actual` fields that do NOT exist in the 2-bucket shape. CONTEXT.md D-04 says "gains a one-line note" but RESEARCH Pitfall 4 confirms the description must be REWRITTEN, not appended.

---

### `src/homelab_mcp/server.py` (config, static, research-corrected)

**Analog:** self — `HOMELAB_RESOURCES["homelab://drift/latest"]` at lines 149-152.

**Important correction:** CONTEXT.md D-18 references `resource_readers.py:131` for the description tweak, but the actual description literal lives in **`server.py:151`**, not in `resource_readers.py`. The reader (`resource_readers.py:127-138`) is shape-agnostic — it just calls `get_latest_drift_report()` and returns whatever's cached.

**Excerpt — current description (server.py:149-152):**
```python
"homelab://drift/latest": {
    "name": "Drift Report",
    "description": "Latest infrastructure drift scan result from scan_infrastructure_drift",
},
```

**Phase 36 D-18 — optional one-line tweak:**
```python
"homelab://drift/latest": {
    "name": "Drift Report",
    "description": "Latest infrastructure drift scan result (2-bucket interim — shape stabilizes in Phase 37)",
},
```

**`resource_readers.py:127-138`:** no change needed (shape-agnostic).

---

### `docs/tool-reference.md` (documentation, static, add entry)

**Analog (sibling tool entry shape — `### refresh_terraform_service` at line 956):**

```markdown
### refresh_terraform_service

**Description:** Refresh Terraform state and detect configuration drift.

**Annotations:** `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| ... | ... | ... | ... | ... |

**Example:**

```json
{
  ...
}
```

**Returns:** A dict with the refreshed state and any detected drift.
```

**Phase 36 D-19 — add new entry (no existing `scan_infrastructure_drift` section):**

The tool-reference.md does NOT currently have a `scan_infrastructure_drift` entry (verified via grep — only `refresh_terraform_service` mentions drift). Phase 36 needs to ADD one in a new section (likely under a new `## Drift Tools` heading at end of file, or under `## Infrastructure Tools`). Use the sibling-entry shape above as the template.

**Phrasing guidance from CONTEXT D-19:**
- Description must mention "iterates the sitemap"
- No "register a drift baseline" language
- No `PROXMOX_HOST` mention
- 2-bucket return shape (`probed_ok`, `unreachable`)

**Sweep step:** `grep -n "register_drift_baseline\|list_drift_baselines\|delete_drift_baseline\|drift baseline" docs/` → remove any speculative mentions (none expected per CONTEXT D-19, but verify).

---

### `tests/test_drift_detection.py` (test, mocked async, full rewrite)

**Analog (mock harness pattern):** existing `tests/test_drift_detection.py:8-77` (drop the assertions but keep the `MagicMock + AsyncMock + patch` idiom).

**Imports pattern** (drop existing line 8 import; rewrite):
```python
"""Tests for drift detection — Phase 36 (sitemap-as-baseline 2-bucket interim)."""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from homelab_mcp.drift_detection import scan_drift
from homelab_mcp.proxmox_api import CredentialNotFoundError
```

**Mock fixture pattern** — extend the existing AsyncMock harness from `tests/test_drift_detection.py:8-30`:
```python
class TestScanDrift2Bucket:
    """Phase 36 D-01/D-02/D-09: scan_drift 2-bucket sitemap-iteration shape."""

    @pytest.mark.asyncio
    async def test_three_row_classification(self):
        """3-row sitemap: pve1 → probed_ok, truenas1 → silently skipped, pi-lab → unreachable."""
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {"hostname": "pve1", "connection_ip": "10.0.0.10", "status": "success"},
            {"hostname": "truenas1", "connection_ip": "10.0.0.11", "status": "success"},
            {"hostname": "pi-lab", "connection_ip": "10.0.0.12", "status": "success"},
        ]
        session = AsyncMock(spec=aiohttp.ClientSession)

        # Mock get_proxmox_client + resolve_proxmox_credentials per CONTEXT.md D-14
        ...
```

**Patch-target pattern (RESEARCH Pattern 3):** patch `homelab_mcp.drift_detection.get_proxmox_client` directly — matches the existing idiom at `tests/test_drift_detection.py:195`:
```python
with patch("homelab_mcp.drift_detection.get_proxmox_client") as mock_client:
    ...
```

**Test classes to DELETE (entire):**
- `TestScanDriftReport` (lines 11-77) — uses obsolete `get_all_drift_baselines.return_value`
- `TestConfigDrift` (lines 80-110) — tests deleted `_diff_vm_config`
- `TestStateDrift` (lines 113+) — tests obsolete state_drift bucket
- `TestUpdateBaselineAfterMutation` (per CONTEXT D-11b) — tests deleted function

**Test classes to ADD (per CONTEXT D-14 + RESEARCH §Phase Requirements → Test Map):**
- `TestScanDrift2Bucket::test_resolves_credentials_per_row`
- `TestScanDrift2Bucket::test_probed_ok_record_shape`
- `TestScanDrift2Bucket::test_unreachable_on_clienterror`
- `TestScanDrift2Bucket::test_silent_skip_on_credential_not_found`
- `TestScanDrift2Bucket::test_empty_sitemap_returns_success`
- `TestScanDrift2Bucket::test_degenerate_rows_excluded` (D-10a)

---

### `tests/test_drift_wiring.py` (test, mocked async, surgical update)

**Analog:** the file itself.

**Keep verbatim:** `TestDriftSchemaRegistration` (lines 8-34), `TestDriftAnnotations` (lines 102-123) — DRFT-04 inert passthrough preserves `node`/`vm_type` schema; annotations unchanged.

**Surgical change to `TestDriftHandlerRegistration::test_handler_returns_content_wrapped_dict` (lines 52-71):**

Current (line 62):
```python
mock_rm.db_adapter.get_all_drift_baselines.return_value = []
mock_rm.db_adapter.get_all_devices.return_value = []
```

Change to:
```python
mock_rm.db_adapter.get_all_devices.return_value = []
```
(Drop `get_all_drift_baselines` mock — method no longer exists.)

**Update `test_handler_passes_node_and_vm_type` (lines 73-99) mock_scan return value:**

Current (lines 86-92):
```python
mock_scan.return_value = {
    "status": "success",
    "scan_timestamp": "2026-01-01T00:00:00Z",
    "config_drift": [],
    "state_drift": [],
    "summary": {},
}
```

Change to:
```python
mock_scan.return_value = {
    "status": "success",
    "scan_timestamp": "2026-01-01T00:00:00Z",
    "scanned": 0,
    "probed_ok": [],
    "unreachable": [],
}
```

---

### `tests/test_database.py` (test, delete-class)

**Analog:** Phase 33 `TestSqliteAdapterCredentialsRemoved` shape — was likely deleted in Phase 33 (similar removal). Current vestige to delete: `TestDriftBaselines` class.

**Class to DELETE (entire):** `TestDriftBaselines` at lines 357-468 (verified at line 357 `class TestDriftBaselines:` and ends at line 468 `assert result["baseline_config"]["net0"] == "virtio,bridge=vmbr0"`).

The five test methods being deleted:
- `test_upsert_and_get_baseline` (lines 372-390)
- `test_upsert_replaces_existing` (lines 392-418)
- `test_get_returns_none_when_absent` (lines 420-424)
- `test_get_all_drift_baselines` (lines 426-449)
- `test_baseline_config_is_full_dict` (lines 451-468)

---

### `tests/test_drift_resource.py` (test, fixture rewrite only)

**Analog:** the file itself, lines 42-65.

**Surgical fixture update only — `test_drift_resource_after_scan` (lines 52-56):**

Current:
```python
sample_report = {
    "drift_detected": True,
    "drifted_vms": [],
    "scanned_at": "2026-01-01T00:00:00",
}
```

Change to:
```python
sample_report = {
    "status": "success",
    "scan_timestamp": "2026-01-01T00:00:00",
    "scanned": 0,
    "probed_ok": [],
    "unreachable": [],
}
```

The test logic (set → read → assert equal) is shape-agnostic and passes regardless. The fixture update keeps the test honest. Other tests in this file (`test_drift_resource_registered`, `test_drift_resource_empty_state`, `test_drift_resource_notification`, `test_drift_resource_uri_roundtrip`) are unaffected.

---

### `tests/test_proxmox_baseline_hooks.py` (test, **DELETE FILE ENTIRELY** — research finding)

**Analog:** none — file is fully orphaned by D-11.

**Action:** `git rm tests/test_proxmox_baseline_hooks.py` (170 lines, 4 test classes).

**Justification:** the entire file tests `update_baseline_after_mutation` hook callsites in 3 Proxmox handlers. After D-11 removes the function and D-11 removes the callsites, every test fails at `patch("...update_baseline_after_mutation")` resolve time with `AttributeError`. RESEARCH Pitfall 2 confirms self-contained: no other test imports from it.

---

### `tests/test_proxmox_api.py` (test, surgical 4-line removal)

**Analog:** the file itself.

**Lines to DELETE (just the patch-line within each `with` block, keep test bodies):**
- Line 1784: `patch("src.homelab_mcp.drift_detection.update_baseline_after_mutation", mock_baseline),`
- Line 1825: same patch line
- Line 1854: same patch line
- Line 1893: same patch line

**Concrete excerpt (line 1781-1785):**
```python
with (
    patch("src.homelab_mcp.server.get_resource_manager", return_value=mock_rm),
    patch.object(_ph_mod, "create_proxmox_vm", mock_fn),
    patch("src.homelab_mcp.drift_detection.update_baseline_after_mutation", mock_baseline),  # ← REMOVE THIS LINE
):
```

**Also remove the now-unused mock setup (one line above each):**
- `mock_baseline = AsyncMock()` (lines 1779, 1820, 1849, 1888) — remove if `mock_baseline` has no other reference in the test body.

**Why tests stay green:** RESEARCH Pitfall 1 confirms the now-missing `try/except update_baseline_after_mutation` block in handlers (deleted by D-11) means there's no side effect to suppress. The tests verify schema-passing kwargs (`call_kwargs.get("sockets") == 2`, etc.) which is unaffected.

---

### `tests/test_ast_regression.py` (test, meta-AST guard, EXTEND consolidation — RESEARCH recommendation)

**Analog:** the file itself, lines 24-46 + 142-178 + 383-435 + 438-493 (Phase 35 D-15 single-file pattern at 438).

**RESEARCH recommendation override:** consolidate Phase 36 D-12/D-13 guards into existing `tests/test_ast_regression.py` rather than creating new `tests/test_drift_baselines_removed.py`. Matches Phase 33/35 convention (CONTEXT.md D-12 lists this as Claude's discretion).

**Extension pattern 1 — list addition (lines 24-37):**
```python
FORBIDDEN_SOURCE_STRINGS: list[str] = [
    "ssh_credentials",  # D-15: DB table name
    "add_credential",
    # ... existing entries ...
    "verify_mcp_admin_access",  # D-10: removed by Plan 33.1-03
    # ─── Phase 36 D-12 additions ───
    "drift_baselines",          # Phase 36 D-12: dropped table name
    "upsert_drift_baseline",    # Phase 36 D-12: removed adapter method
    "get_drift_baseline",       # Phase 36 D-12: removed adapter method
    "get_all_drift_baselines",  # Phase 36 D-12: removed adapter method
]
```

**Extension pattern 2 — exception dict (lines 41-45):**
```python
ALLOWED_EXCEPTIONS: dict[str, set[str]] = {
    "ssh_credentials": {"migration.py"},
    # ─── Phase 36 D-12 addition ───
    "drift_baselines": {"migration.py"},  # D-05 drop step needs the literal string
}
```
**NOTE:** the three method names (`upsert_drift_baseline`, `get_drift_baseline`, `get_all_drift_baselines`) are NOT added to `ALLOWED_EXCEPTIONS` — they should never appear in any source file post-D-07.

**Extension pattern 3 — new single-file test (analog: `test_ssh_discover_system_wraps_every_conn_run_phase35` at lines 438-493 — same shape but for substring matching, not AST walk):**

```python
def test_drift_detection_no_baseline_references_phase36() -> None:
    """Phase 36 D-13: drift_detection.py must contain no reference to the
    parallel baseline data layer — singular OR plural, in any AST node form
    (string literal, identifier, attribute access).

    Belt-and-braces guard: the broader test_no_forbidden_strings_in_source()
    catches reintroduction in any source file; this test pins drift_detection.py
    specifically as the only module on the drift-scan call chain.
    """
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

**Existing helper functions** (lines 126-139, copy verbatim — already present):
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

**Existing test that picks up the new strings automatically** (lines 142-178, no change needed):
```python
def test_no_forbidden_strings_in_source() -> None:
    """D-15 + D-25: No source file contains removed credential DB names or deleted tool references."""
    src_root = Path(__file__).parent.parent / "src" / "homelab_mcp"
    assert src_root.exists(), f"Source root not found: {src_root}"

    violations: list[str] = []

    for py_file in sorted(src_root.rglob("*.py")):
        source = py_file.read_text(encoding="utf-8")

        # Fast pre-check: skip files that don't contain any forbidden string
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
                violations.append(
                    f"{py_file.relative_to(src_root.parent.parent)}: contains forbidden identifier/string {forbidden!r}"
                )

    assert not violations, (
        "Phase 33 regression: found removed DB/tool references in source files.\n"
        "These strings must not appear outside test files:\n" + "\n".join(f"  - {v}" for v in violations)
    )
```

The test assertion message currently says "Phase 33 regression"; consider updating the docstring to reflect Phase 33 + 36 (cosmetic; no behavioral change). The `assert not violations` text remains accurate since the test now covers both phases of strings.

---

### `tests/test_migration.py` (test, add idempotency tests — D-15)

**Analog:** `tests/test_database.py:642-727` `test_migration_dedup_collapses_duplicates_and_is_idempotent_phase35` — Phase 35 D-17b SQLite migration test.

**Concrete excerpt to copy and adapt** (from `test_database.py:642-727`):
```python
def test_migration_dedup_collapses_duplicates_and_is_idempotent_phase35(tmp_path):
    """Phase 35 D-17b: ... first migration run collapses them into one ...; second run is a no-op."""
    import sqlite3

    from src.homelab_mcp.migration import run_sqlite_migrations

    db_path = str(tmp_path / "phase35_d17b.db")

    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE devices (...)""")
    # ... seed pre-existing rows ...
    conn.commit()
    conn.close()

    applied1 = run_sqlite_migrations(db_path=db_path)
    assert "dedupe_zombie_device_rows" in applied1, applied1
    # ... assert post-migration state ...

    applied2 = run_sqlite_migrations(db_path=db_path)
    assert "dedupe_zombie_device_rows" not in applied2, applied2
    # ... assert no-op on second run ...
```

**Adaptations for D-15:**

```python
def test_drift_baselines_drop_idempotent_phase36(tmp_path):
    """Phase 36 D-15: pre-populated DB with drift_baselines drops on first run; second run no-op."""
    import sqlite3
    from src.homelab_mcp.migration import run_sqlite_migrations

    db_path = str(tmp_path / "phase36_d15.db")

    # Seed: create drift_baselines table with rows + index, mirroring the legacy schema
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE drift_baselines (
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
    conn.execute("CREATE INDEX idx_drift_baselines_node_vmid ON drift_baselines (node, vmid, vm_type)")
    conn.execute("INSERT INTO drift_baselines (node, vmid, vm_type, baseline_config, recorded_at, recorded_by) "
                 "VALUES (?, ?, ?, ?, ?, ?)", ("pve", 100, "qemu", "{}", "2026-01-01", "test"))
    # Also seed devices table so the rest of run_sqlite_migrations completes cleanly
    conn.execute("""CREATE TABLE devices (... per Phase 35 schema ...)""")
    conn.commit()
    conn.close()

    applied1 = run_sqlite_migrations(db_path=db_path)
    assert "drop_drift_baselines_table" in applied1, applied1

    # Verify table is gone
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='drift_baselines'"
    ).fetchall()
    assert len(rows) == 0, f"Phase 36 D-15: drift_baselines table still exists after migration: {rows}"
    conn.close()

    # Second run: no banner, no migration applied
    applied2 = run_sqlite_migrations(db_path=db_path)
    assert "drop_drift_baselines_table" not in applied2, applied2


def test_drift_baselines_drop_fresh_db_phase36(tmp_path):
    """Phase 36 D-15: fresh DB (no drift_baselines table) — migration runs cleanly, no-op for the drop step."""
    # ... seed only devices table (no drift_baselines) ...
    applied1 = run_sqlite_migrations(db_path=db_path)
    assert "drop_drift_baselines_table" not in applied1, applied1


@pytest.mark.integration
def test_drift_baselines_drop_idempotent_postgres_phase36():
    """Phase 36 D-15: Postgres path — uses Docker postgres per existing integration pattern."""
    # ... use tests/integration/conftest.py fixtures + run_postgres_migrations ...
```

**Placement consideration:** the file `tests/test_migration.py` is currently scoped to SQLite→Postgres data migration (different concept). The Phase 35 D-17b test lives in `tests/test_database.py:642-727`. Planner choice: place D-15 tests in `tests/test_database.py` (matches Phase 35 precedent) OR create a new `tests/test_drift_baseline_drop.py`. RESEARCH Wave 0 Gaps suggests `tests/test_migration.py`; either location is acceptable.

---

## Shared Patterns

### Pattern A: Idempotent Startup Migration (cross-cutting, applies to D-05 SQLite + Postgres)

**Source:** `src/homelab_mcp/migration.py:37-62` (SQLite) + `migration.py:281-305` (Postgres)
**Apply to:** `src/homelab_mcp/migration.py` D-05 drop step (both adapters)
**Why standard:** Phase 33 D-01 (`ssh_credentials`) and Phase 35 D-02 (zombie dedup) both use this exact shape. The `IF EXISTS` guard makes every run idempotent — fresh installs and second-run-after-drop both no-op without error.

**Concrete excerpt — SQLite header pattern:**
```python
cursor.execute(
    """
    SELECT name FROM sqlite_master
    WHERE type='table' AND name='<TABLE_NAME>'
    """
)
if cursor.fetchone():
    cursor.execute("DROP INDEX IF EXISTS <INDEX_NAME>")
    cursor.execute("DROP TABLE IF EXISTS <TABLE_NAME>")
    conn.commit()
    applied_migrations.append("drop_<TABLE_NAME>_table")
    import sys  # noqa: PLC0415
    print("<BANNER LINE 1>", file=sys.stderr)
    print("<BANNER LINE 2>", file=sys.stderr)
```

**Concrete excerpt — Postgres header pattern:**
```python
cursor.execute(
    """
    SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_name = '<TABLE_NAME>'
    )
    """
)
if cursor.fetchone()[0]:
    cursor.execute("DROP INDEX IF EXISTS <INDEX_NAME>")
    cursor.execute("DROP TABLE IF EXISTS <TABLE_NAME>")
    conn.commit()
    applied_migrations.append("drop_<TABLE_NAME>_table")
    # ... banner print ...
```

---

### Pattern B: Sanitized Per-Row Error Message (cross-cutting, applies to scan_drift)

**Source:** `src/homelab_mcp/log_filter.py:64-76` `sanitize_error()` (re-imported via `error_handling.py:14`)
**Apply to:** `drift_detection.scan_drift` per-row `error` field on `unreachable` entries (D-09a)
**Why standard:** Phase 33/34 convention. `_SENSITIVE_PATTERNS` at `log_filter.py:16-33` redacts `PVEAPIToken=...`, `password=...`, etc.

**Concrete usage pattern:**
```python
from .log_filter import sanitize_error
# ... or via:
from .error_handling import sanitize_error  # re-exported

try:
    status = await client.get("/cluster/status")
except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
    unreachable.append({
        ...
        "error": sanitize_error(exc),     # ← scrub before placing in user-visible payload
        ...
    })
```

**Anti-pattern (forbidden):** placing raw `str(exc)` or `exc.args[0]` directly into JSON payload — RESEARCH §"Don't Hand-Roll" row 3.

---

### Pattern C: Resolver-Funnel Pass-Through (cross-cutting, applies to scan_drift D-09)

**Source:** `src/homelab_mcp/proxmox_api.py:340-396` `get_proxmox_client`
**Apply to:** every Phase 36 per-row Proxmox call site
**Why standard:** Phase 34 D-09 locked the resolver shape. `scan_drift` consumes it via `get_proxmox_client(host=..., session=...)` — the resolver fires internally at lines 370-378.

**Concrete usage pattern in scan_drift:**
```python
try:
    client = await get_proxmox_client(host=row["hostname"], session=session)
except CredentialNotFoundError:
    continue                                 # D-10: silent skip — row is not a Proxmox host
```

**Anti-pattern (forbidden):** calling `os.getenv("PROXMOX_HOST")` directly inside `scan_drift` (RESEARCH §"Anti-Patterns to Avoid") — D-09b enforces; D-13 AST guard catches reintroduction.

---

### Pattern D: AST Meta-Test Consolidation (cross-cutting, applies to D-12 + D-13)

**Source:** `tests/test_ast_regression.py:24-178` (Phase 33/33.1/35 idiom)
**Apply to:** Phase 36 footgun-removal regression guards
**Why standard:** RESEARCH §Open Questions Q1 — established convention is single-file consolidation; `test_ast_regression.py` already extended by Phase 33 / 33.1 / 35 (functions named `_phase{N}` at lines 383, 438, 505).

**Two extension points** (already detailed above under `tests/test_ast_regression.py` section):
1. Append to `FORBIDDEN_SOURCE_STRINGS` list + extend `ALLOWED_EXCEPTIONS` dict (D-12)
2. Add `test_drift_detection_no_baseline_references_phase36()` function modeled on `test_ssh_discover_system_wraps_every_conn_run_phase35()` at lines 438-493 (D-13)

---

### Pattern E: Sitemap Iteration Entry Point (cross-cutting, single-funnel rule)

**Source:** `src/homelab_mcp/database.py:48` (ABC), `database.py:349` (SQLite impl), `database.py:790` (Postgres impl)
**Consumers:** `sitemap.py:158-160`, `resource_readers.py:93+164`, `infrastructure_crud.py:25+463+1132`, `vm_operations.py:20`, `tool_handlers/network_handlers.py:30`
**Apply to:** `drift_detection.scan_drift` (Phase 36 adds itself to this list)
**Why standard:** Phase 35 D-01 made `db_adapter.get_all_devices()` the single funnel for sitemap reads. Every "iterate the sitemap" path uses this entry point. Phase 36 inherits — no new adapter method, no new entry point.

**Concrete iteration shape** (most representative — `sitemap.py:194-200`):
```python
for device in devices:
    if device["status"] != "success":
        continue
    if not device.get("hostname"):
        continue
    # ... per-device processing ...
```

Phase 36 `scan_drift` extends with the additional D-10a guard `if hostname in ("", "unknown", None) or row.get("status") == "error"`.

---

## No Analog Found

All Phase 36 files have an in-tree analog. Zero greenfield patterns.

| Item | Status |
|------|--------|
| (none) | All patterns sourced from existing v1.6 codebase |

This reflects RESEARCH §State of the Art — Phase 36 is "100% deletion + redirection. Every facility it needs already exists in the v1.6 codebase."

---

## Research-Surfaced Corrections to CONTEXT.md

The PATTERNS.md mapping incorporates two RESEARCH-flagged corrections:

1. **D-04 description must be REWRITE not append** (RESEARCH Pitfall 4) — current schema description references obsolete fields (`drift_type`, `expected`, `actual`).
2. **D-18 description location is `server.py:151`, not `resource_readers.py:131`** — verified via grep on `homelab://drift/latest`. The reader is shape-agnostic.

Two RESEARCH-added scope items:

3. **`tests/test_proxmox_baseline_hooks.py` — DELETE FILE** (RESEARCH Pitfall 2) — orphaned by D-11.
4. **`tests/test_proxmox_api.py` — 4 surgical patch-line removals** (RESEARCH Pitfall 1) — at lines 1784/1825/1854/1893.

One scope-consolidation choice:

5. **D-12/D-13 land in existing `tests/test_ast_regression.py`** — RESEARCH §Open Questions Q1 recommendation. CONTEXT.md D-12 lists this as Claude's discretion; consolidation matches Phase 33/35 convention.

---

## Metadata

**Analog search scope:**
- `src/homelab_mcp/` (entire directory)
- `tests/` (entire directory)
- `docs/tool-reference.md` and `docs/PRD.md`
- `.planning/milestones/v1.6-phases/33-*/`, `34-*/`, `35-*/` (referenced via CONTEXT canonical_refs only — not re-read; line-numbers verified in current code)

**Files scanned:**
- 11 source files read in full or in targeted ranges
- 8 test files read in targeted ranges
- 2 doc files greppped

**Pattern extraction date:** 2026-04-25

**Confidence:** HIGH — every analog excerpt is verbatim from the live tree (verified via Read tool 2026-04-25). Line numbers are advisory; symbol-name resolution handles the ±2-line drift RESEARCH flagged.
