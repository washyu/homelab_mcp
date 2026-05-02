# Phase 44: Sitemap CRUD Completion - Pattern Map

**Mapped:** 2026-05-02
**Files analyzed:** 11 new symbols / modified files
**Analogs found:** 10 / 11 (1 stdlib idiom, no codebase analog)

## File Classification

| New/Modified File or Symbol | Role | Data Flow | Closest Analog | Match Quality |
|-----------------------------|------|-----------|----------------|---------------|
| `network_handlers.py::handle_remove_device` (new) | handler | request-response (single-row delete) | `network_handlers.py::handle_purge_failed_discoveries` (lines 69-84) + `handle_update_device_fingerprint` missing-id branch (lines 117-128) | exact (envelope) + exact (error shape) |
| `network_handlers.py::handle_purge_devices` (new) | handler | request-response (bulk filter delete) | `network_handlers.py::handle_purge_failed_discoveries` (lines 69-84) | exact (response shape) |
| `network_handlers.py::handle_remove_device_preview` (new) | handler (thin delegate) | request-response | `infrastructure_handlers.py::handle_decommission_device_preview` (lines 117-123) + `network_handlers.py::handle_update_device_fingerprint_preview` (lines 141-216) | exact (one-line delegate idiom) |
| `network_handlers.py::handle_purge_devices_preview` (new) | handler (thin delegate) | request-response | same as above | exact |
| `database.py::DatabaseAdapter.delete_device_by_id` (new ABC + 2 impls) | DB adapter method | CRUD (single-row delete + cascade) | `database.py::purge_failed_devices` (ABC 147-155, SQLite 624-656, Postgres 1182-1207) | role-match (bulk → single-row variant) |
| `database.py::_purge_devices_by_filter` (new shared helper) | private SQL builder/dispatcher | CRUD (bulk delete) | `database.py::purge_failed_devices` SQLite impl (624-656) — inlined SQL pattern | partial (no helper analog yet, structural copy) |
| `tool_schemas/network_tools_schema.py::remove_device + purge_devices` schema entries (new) | schema | n/a (config) | `tool_schemas/network_tools_schema.py::purge_failed_discoveries` (lines 87-104) | exact |
| `tool_handlers/__init__.py` registry entries (4 new) | registry update | n/a (config) | existing `purge_failed_discoveries` registration at line 91, `decommission_device_preview` at line 98 | exact |
| `tool_annotations.py` annotation flags (4 new) | registry update | n/a (config) | line 46 (`decommission_device_preview` in `_READ_ONLY_TOOLS`), line 66 (`decommission_device` in `_DESTRUCTIVE_TOOLS`), line 71 (`purge_failed_discoveries` in `_DESTRUCTIVE_TOOLS`) | exact |
| `openapi_app.py` tool list updates | registry update | n/a (config) | line 43 (`STANDALONE_TOOLS` set), line 154 (`Network Discovery` category in `TOOL_CATEGORIES`), lines 185-186 (`Infrastructure` category) | exact |
| `tests/test_ast_regression.py::TestPhase44RemoveDeviceCallPath` (new) | test (AST guard) | request-response (static AST scan) | `TestPhase381CredBinding::test_scan_drift_no_continue_in_row_loop_phase38_1` (lines 774-814) — body-level AST walk on a named function | exact |
| CIDR membership scan in `_purge_devices_by_filter` (D-03) | utility (in-handler/helper) | transform (per-row filter) | **No codebase analog** — `ipaddress` stdlib idiom | none — document directly |
| `docs/tool-reference.md` new entries | docs prose | n/a (docs) | `docs/tool-reference.md::decommission_device` (lines 493-521) + `decommission_device_preview` (lines 525-545) | exact |
| `drift_detection.py` + `server.py` SC-4 wording sweep | string literal updates | n/a (text) | `drift_detection.py:56-62` `_EMPTY_SCAN_GUIDANCE` constant + `:225-228` `missing` branch message | exact |

---

## Pattern Assignments

### `handle_remove_device` (new, in `tool_handlers/network_handlers.py`)

**Role:** handler / **Data flow:** request-response (single-row delete with structured-error envelope)

**Analog A (handler shape + response envelope):** `network_handlers.py:69-84` — `handle_purge_failed_discoveries`

```python
async def handle_purge_failed_discoveries(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle purge_failed_discoveries tool."""
    dry_run = bool(arguments.get("dry_run", False))
    sitemap = NetworkSiteMap()
    removed = sitemap.purge_failed_devices(dry_run=dry_run)
    result = json.dumps(
        {
            "status": "success",
            "dry_run": dry_run,
            "purged_count": len(removed),
            "purged_devices": removed,
        },
        indent=2,
        default=str,
    )
    return {"content": [{"type": "text", "text": result}]}
```

**Why this is the right analog:** Same module, same json-envelope return shape, same `default=str` for datetime serialization, same `dry_run` extraction idiom, same instantiation of `NetworkSiteMap()` as the entrypoint. D-06a's `removed_device` is the singular analog of `purged_devices`.

**Analog B (missing-id error envelope, D-06b):** `network_handlers.py:117-128` — `handle_update_device_fingerprint` `try/except ValueError` branch

```python
sitemap = NetworkSiteMap()
try:
    merged = sitemap.db_adapter.update_device_fingerprint(arguments["hostname"], cleaned)
except ValueError as e:
    # NOTE: hint substring is asserted exactly by test_update_device_fingerprint_missing_hostname_phase38.
    result_str = json.dumps(
        {
            "status": "error",
            "error": str(e),
            "hint": "Run discover_and_map for this hostname first to add it to the sitemap.",
        }
    )
    return {"content": [{"type": "text", "text": result_str}]}
```

**Why this is the right analog:** D-06b explicitly cites this as the structural mirror — `{status: "error", error: ..., hint: ...}`, returned as the json text content (NOT raised), pointing the agent at the recovery action.

**Notable differences the planner must call out in PLAN.md:**
- The new `delete_device_by_id` adapter returns `None` for missing-id (D-13), NOT raises `ValueError`. Handler dispatches on the `None` return rather than `try/except`. Branch shape:
  ```python
  removed = sitemap.db_adapter.delete_device_by_id(device_id, dry_run=dry_run)
  if removed is None:
      # structured error envelope; hint per D-06b
      ...
  ```
- Hint text per D-06b: `"Run get_network_sitemap to see current device IDs."` (NOT `discover_and_map ...`).
- Error message per D-06b: `f"Device {device_id} not found in sitemap"`.
- Response key is `removed_device` (singular) NOT `purged_devices` (plural list).

---

### `handle_purge_devices` (new, in `tool_handlers/network_handlers.py`)

**Role:** handler / **Data flow:** request-response (bulk filter delete with handler-side `value` shape validation per D-01b)

**Analog (response shape + dry_run handling):** `network_handlers.py:69-84` — `handle_purge_failed_discoveries` (excerpt above)

**Why this is the right analog:** D-01a explicitly mandates verbatim shape match — `{status, dry_run, purged_count, purged_devices}`. Same `default=str` serialization, same `NetworkSiteMap()` entrypoint.

**Notable differences the planner must call out in PLAN.md:**
- Add handler-side validation of `value` shape before dispatch (D-01b). Mirror the malformed-input branch from `handle_update_device_fingerprint:104-113`:
  ```python
  if filter_type == "last_seen_older_than_days" and not isinstance(value, int):
      result_str = json.dumps(
          {
              "status": "error",
              "error": f"`value` must be int for filter_type={filter_type!r} (got {type(value).__name__})",
              "hint": "Pass an integer day count, e.g., 7.",
          }
      )
      return {"content": [{"type": "text", "text": result_str}]}
  ```
- For `ip_range`, validate via `ipaddress.ip_network(value, strict=False)` in a try/except — invalid CIDR → structured error envelope with hint pointing at the format `"192.168.1.0/24"`.
- Dispatch into the new `_purge_devices_by_filter(filter_type, value, dry_run)` shared helper (D-14); do NOT inline the SQL in the handler (keeps handler body within AST-guard tolerances per D-10a — though `purge_devices` is NOT in the guard's named-function list, the discipline still applies to keep the helper reusable for the alias).
- Zero-match returns success with `purged_count: 0, purged_devices: []` per D-01c — never error.

---

### `handle_remove_device_preview` and `handle_purge_devices_preview` (new, thin delegates)

**Role:** handler (one-line delegate) / **Data flow:** request-response (preview-only)

**Analog:** `infrastructure_handlers.py:117-123` — `handle_decommission_device_preview`

```python
async def handle_decommission_device_preview(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle decommission_device_preview tool.

    Delegates to handle_decommission_device with dry_run=True injected.
    No infrastructure is modified.
    """
    return await handle_decommission_device({**arguments, "dry_run": True})
```

**Why this is the right analog:** D-11 explicitly cites this as the canonical `*_preview` impl. Single-line body. The `{**arguments, "dry_run": True}` spread idiom is the pattern; planner copy-adapts verbatim swapping the underlying handler name.

**Notable differences the planner must call out in PLAN.md:**
- Both new previews land in `network_handlers.py` (NOT `infrastructure_handlers.py`) per D-12 — the file-placement distinction is part of the AST guard's safety story.
- Docstring should follow the same 3-line format: 1-line summary, 1-line "Delegates to handle_X with dry_run=True injected.", 1-line "No infrastructure is modified." Mirror exactly so the convention stays uniform.
- Phase 38 also added a non-thin preview (`handle_update_device_fingerprint_preview` at network_handlers.py:141-216) that re-implements the merge logic without persisting. Phase 44's previews are NOT this shape — they are the simpler `decommission_device_preview` shape because `dry_run=True` already short-circuits writes in the underlying handlers.

---

### `delete_device_by_id` (new, on `DatabaseAdapter` ABC + SQLite + Postgres impls)

**Role:** DB adapter method / **Data flow:** CRUD (single-row delete with manual cascade)

**Analog A (ABC declaration):** `database.py:147-155` — `purge_failed_devices` ABC

```python
@abstractmethod
def purge_failed_devices(self, dry_run: bool = False) -> list[dict[str, Any]]:
    """Remove devices where discovery failed.

    Failed = ``status='error'`` OR ``hostname`` is empty/null/'unknown'.
    Returns the list of removed rows (preview only when ``dry_run=True``).
    Also deletes the corresponding ``discovery_history`` rows to avoid
    orphan foreign keys.
    """
    pass
```

**Analog B (SQLite impl, two-step DELETE):** `database.py:624-656` — `SQLiteAdapter.purge_failed_devices`

```python
def purge_failed_devices(self, dry_run: bool = False) -> list[dict[str, Any]]:
    """SQLite implementation. See ``DatabaseAdapter.purge_failed_devices``."""
    if not self.connection:
        self.connect()
    assert self.connection is not None
    cursor = self.connection.cursor()
    cursor.execute(
        """
        SELECT id, hostname, connection_ip, status, error_message, last_seen
        FROM devices
        WHERE status = 'error'
           OR hostname IS NULL
           OR hostname = ''
           OR hostname = 'unknown'
        ORDER BY id
        """
    )
    candidates = [dict(row) for row in cursor.fetchall()]
    if dry_run or not candidates:
        return candidates
    ids = [row["id"] for row in candidates]
    placeholders = ",".join("?" * len(ids))
    # Delete history first (no ON DELETE CASCADE); then devices.
    cursor.execute(
        f"DELETE FROM discovery_history WHERE device_id IN ({placeholders})",  # noqa: S608
        ids,
    )
    cursor.execute(
        f"DELETE FROM devices WHERE id IN ({placeholders})",  # noqa: S608
        ids,
    )
    self.connection.commit()
    return candidates
```

**Analog C (Postgres impl, parametrized cascade):** `database.py:1182-1207` — `PostgreSQLAdapter.purge_failed_devices`

```python
def purge_failed_devices(self, dry_run: bool = False) -> list[dict[str, Any]]:
    """PostgreSQL implementation. See ``DatabaseAdapter.purge_failed_devices``."""
    if not self.connection:
        self.connect()
    assert self.connection is not None
    cursor = self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(
        """
        SELECT id, hostname, connection_ip::text AS connection_ip,
               status, error_message, last_seen::text AS last_seen
        FROM devices
        WHERE status = 'error'
           OR hostname IS NULL
           OR hostname = ''
           OR hostname = 'unknown'
        ORDER BY id
        """
    )
    candidates = [dict(row) for row in cursor.fetchall()]
    if dry_run or not candidates:
        return candidates
    ids = [row["id"] for row in candidates]
    cursor.execute("DELETE FROM discovery_history WHERE device_id = ANY(%s)", (ids,))
    cursor.execute("DELETE FROM devices WHERE id = ANY(%s)", (ids,))
    self.connection.commit()
    return candidates
```

**Why this is the right analog:** D-13 explicitly mandates the same shape: ABC + 2 concretes, two-step DELETE (`discovery_history` first then `devices`), `dry_run` returns the would-delete payload without writing. SQLite uses `?` placeholders + `# noqa: S608` on the f-string DELETEs; Postgres uses `%s` with `RealDictCursor`. Identical commit semantics.

**Notable differences the planner must call out in PLAN.md:**
- Signature is single-row (`device_id: int, dry_run: bool = False`) returning `dict | None`, NOT a `list[dict]`. Adapter SELECTs by `id = ?` instead of the 4-clause OR.
- Return shape: `None` when no row matches (drives the handler's structured-error branch per D-06b); `dict` of the row when found (or would be deleted on `dry_run=True`).
- DELETE clauses become `WHERE device_id = ?` / `= %s` (single-id) instead of the `IN (...)` / `= ANY(%s)` list form. No `placeholders` variable needed.
- Single-transaction wrap per D-06c — both DELETEs share one `self.connection.commit()` at the end so a partial failure doesn't orphan rows. Same as analog.
- Postgres SELECT must keep the `connection_ip::text AS connection_ip` cast and `last_seen::text AS last_seen` cast (analog line 1190-1191) — these are intentional for serialization compatibility with the SQLite shape.
- Adapter docstring should mirror the analog's "See `DatabaseAdapter.delete_device_by_id`" pointer pattern.

---

### `_purge_devices_by_filter` (new shared helper, D-14, recommended placement: `database.py`)

**Role:** private SQL builder/dispatcher / **Data flow:** CRUD (bulk delete, dispatched by `filter_type`)

**Closest analog:** `database.py:624-656` — the SQLite `purge_failed_devices` impl above (no exact helper analog exists yet — this is the first dispatcher of its kind).

**Why this is the closest:** D-14 explicitly says "no exact analog; closest is the inlined SQL in `purge_failed_devices`." The pattern the helper should follow is: SELECT-then-(dry_run-or-DELETE), two-step cascade, parametrized queries with `?` for SQLite / `%s` for Postgres, `noqa: S608` on f-string DELETEs.

**Recommended helper signature (Claude's Discretion per D-14 — `database.py` placement):**

```python
def _purge_devices_by_filter(
    adapter: DatabaseAdapter,
    filter_type: str,
    value: Any,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Shared filter-dispatch for purge_devices + purge_failed_discoveries alias.

    filter_type: one of {'hostname', 'last_seen_older_than_days', 'status',
        'ip_range', 'failed_discovery'} (last is the alias-internal sentinel
        per D-08; matches status='error' OR hostname IN (NULL,'','unknown')).
    value: per-filter shape (str/int/CIDR-str). Validated by caller.
    dry_run: returns candidates without DELETE.
    """
```

**Notable differences the planner must call out in PLAN.md:**
- Per D-14, the helper does NOT live in `network_handlers.py` — keeps the handler module thin and the AST guard cleaner. `database.py` is the recommended home (Claude's Discretion confirmed in D-14 commentary).
- `purge_failed_discoveries` alias dispatches via the sentinel `filter_type='failed_discovery'` — D-08 lock-in: 4-clause OR matched only by the alias; bare `purge_devices(filter_type='status', value='error')` matches ONLY `status='error'`.
- Recommend per-`filter_type` SQL builder functions (one query per filter) per Claude's Discretion in D-01 commentary — easier to test, no SQL-injection-via-clause-construction surface. Each builder produces `(query, params)` tuple consumed by the SELECT path.
- Two-step DELETE pattern from analog applies verbatim per `filter_type`: SELECT candidates, branch on dry_run, then `DELETE FROM discovery_history WHERE device_id IN (...)` then `DELETE FROM devices WHERE id IN (...)`.
- For `ip_range` (D-03), the helper SELECTs `*` first, applies the Python-side `ipaddress` membership filter, THEN cascades into the two-step DELETE on the resulting id list. SQL CANNOT do CIDR membership reliably across `connection_ip` formats.

---

### CIDR membership scan via `ipaddress` stdlib (D-03)

**Role:** in-helper utility / **Data flow:** transform (per-row filter)

**Analog:** **None in codebase.** Documented stdlib idiom per D-03 + canonical_refs external/library reference.

**Recommended Python idiom (verbatim from D-03):**

```python
import ipaddress

# Parse the CIDR once, outside the loop:
try:
    net = ipaddress.ip_network(value, strict=False)
except ValueError as e:
    # Handler-side validation per D-01b — return structured error envelope.
    raise ValueError(f"Invalid CIDR for ip_range filter: {value!r} ({e})") from e

# Per-row membership test, with D-03a skip on unparseable connection_ip:
def _row_in_net(row: dict[str, Any], net: ipaddress._BaseNetwork) -> bool:
    raw_ip = row.get("connection_ip", "")
    if not raw_ip:
        return False
    try:
        return ipaddress.ip_address(raw_ip) in net
    except ValueError:
        # D-03a: zombie row where connection_ip is hostname-fallback or empty;
        # silently skip — never matches the filter, no error raised.
        return False

candidates = [row for row in all_devices if _row_in_net(row, net)]
```

**Why this is the right idiom:**
- `strict=False` accepts host bits set (e.g., `192.168.1.42/24` doesn't raise) — matches D-03 explicitly.
- `ip_network` + `ip_address` handle IPv4, IPv6, single-IP `/32` and `/128`, non-byte-aligned subnets natively per stdlib.
- Per-row try/except absorbs the D-03a contract: rows whose `connection_ip` doesn't parse are skipped silently, never raise.

**Notable differences the planner must call out in PLAN.md:**
- The base type for the parameter annotation is `ipaddress._BaseNetwork` (the union of `IPv4Network | IPv6Network`); the public stdlib doesn't expose a union alias — `ipaddress.ip_network()` returns `IPv4Network | IPv6Network`. Either annotate as the union or use `Any` if the planner prefers to avoid the underscore prefix.
- The CIDR scan reads via `db_adapter.get_all_devices()` (the Phase 36 D-09 single-funnel convention) per CONTEXT canonical_refs — NOT a fresh raw SELECT. Keeps row shape consistent with what drift sees.
- After the Python-side filter narrows to id list, cascade into the same two-step DELETE pattern from the `purge_failed_devices` analog. Don't write a third DELETE pattern.

---

### Schema entries for `remove_device` and `purge_devices`

**Analog:** `tool_schemas/network_tools_schema.py:87-104` — `purge_failed_discoveries` schema entry

```python
"purge_failed_discoveries": {
    "description": (
        "Remove sitemap rows for devices where discovery failed (status='error' "
        "or empty/null/'unknown' hostname). Pass dry_run=true to preview the "
        "removal candidates without deleting them."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "dry_run": {
                "type": "boolean",
                "description": "If true, return removal candidates without deleting (default: false)",
                "default": False,
            },
        },
        "required": [],
    },
},
```

**Why this is the right analog:** Same module, same dict-of-dicts shape, same parenthesized-multiline description style, same `dry_run` boolean property idiom with `default: False`.

**Notable differences the planner must call out in PLAN.md:**
- `remove_device` schema needs `device_id: integer` in `required` (per D-06): `"required": ["device_id"]`. Mirror the `decommission_device` schema entry at `infrastructure_tools_schema.py:105-147` for the device_id field shape.
- `purge_devices` schema per D-01 + D-01b: `filter_type` is an enum (Claude's Discretion recommends BOTH JSON Schema `enum` and prose description for IDE/agent autocomplete + human readability):
  ```python
  "filter_type": {
      "type": "string",
      "enum": ["hostname", "last_seen_older_than_days", "status", "ip_range"],
      "description": "Filter to apply (exactly one per call). ...",
  },
  "value": {
      # D-01b: handler validates the per-filter_type shape; schema is permissive.
      "oneOf": [{"type": "string"}, {"type": "integer"}],
      "description": "Filter value. Shape varies by filter_type: ...",
  },
  ```
- Description text must include the 3-tool contrast block per D-09 (canonical sentence template — copy verbatim across `remove_device`, `purge_devices`, AND `decommission_device` description updates):
  > "Use `remove_device` for inventory-only deletion of one row; use `purge_devices` for bulk filter-based inventory deletion; use `decommission_device` when host-side cleanup (stop services, remove from clusters) is required before deletion."
- Description for `purge_failed_discoveries` gets a parenthetical "(equivalent to `purge_devices` with the failed-discovery filter)" added per D-07.
- Preview-tool schema entries (`remove_device_preview`, `purge_devices_preview`) follow the `update_device_fingerprint_preview` analog at `network_tools_schema.py:145-180` — same shape as the underlying tool's schema, description starts with "Preview the result of X without persisting."

---

### Tool registry / annotations / openapi_app updates

**Analog A (handler registry):** `tool_handlers/__init__.py:91, 97-98` — existing one-line registrations

```python
"purge_failed_discoveries": handle_purge_failed_discoveries,
...
"decommission_device": handle_decommission_device,
"decommission_device_preview": handle_decommission_device_preview,
```

**Pattern to copy:** Add 4 entries to `TOOL_HANDLERS` dict (lines 79-142):
```python
"remove_device": handle_remove_device,
"remove_device_preview": handle_remove_device_preview,
"purge_devices": handle_purge_devices,
"purge_devices_preview": handle_purge_devices_preview,
```
Add the 4 imports to the existing `from .network_handlers import (...)` block at lines 23-33.

**Analog B (annotations):** `tool_annotations.py:46, 66, 71` — existing flag assignments

```python
# Read-only preview tools land in _READ_ONLY_TOOLS:
"decommission_device_preview",      # line 46
"update_device_fingerprint_preview",# line 51

# Destructive write tools land in _DESTRUCTIVE_TOOLS:
"decommission_device",              # line 66
"purge_failed_discoveries",         # line 71
```

**Pattern to copy:** Append `"remove_device_preview"` and `"purge_devices_preview"` to `_READ_ONLY_TOOLS` (lines 23-52); append `"remove_device"` and `"purge_devices"` to `_DESTRUCTIVE_TOOLS` (lines 65-72). No entry needed in `_MUTATING_ANNOTATIONS` — the destructive flag is sufficient.

**Analog C (OpenAPI app):** `openapi_app.py:43, 154, 185-186` — existing tool list memberships

- Line 43: `STANDALONE_TOOLS` set (tools that don't require external infra). `purge_failed_discoveries` is already there. `purge_devices` and `remove_device` belong here too — both are local-DB-only operations.
- Line 154: `TOOL_CATEGORIES["Network Discovery"]` list. Append `"remove_device"`, `"remove_device_preview"`, `"purge_devices"`, `"purge_devices_preview"` (NOT in Infrastructure category — keep separate from `decommission_device` per D-12 file-placement discipline).
- Lines 185-186: `TOOL_CATEGORIES["Infrastructure"]` — NO additions; `decommission_device` stays here, the new tools go to Network Discovery.

**Notable differences the planner must call out in PLAN.md:**
- All 4 new tools go to the **Network Discovery** category in `TOOL_CATEGORIES`, NOT Infrastructure — matches the file-placement discipline in D-12 (handlers in `network_handlers.py`, schemas in `network_tools_schema.py`).
- `STANDALONE_TOOLS` membership is important per the openapi_app's no-external-infra-required contract — both new tools are pure DB ops.
- No entry needed in `_SSH_TOOLS_WITH_HOSTNAME` (line 69) or `_PROXMOX_TOOLS_WITH_HOST` (line 85) — D-10's whole point is that these handlers do NO host dial.

---

### `TestPhase44RemoveDeviceCallPath` AST guard (new, in `tests/test_ast_regression.py`)

**Role:** test (AST guard, body-level scope on named function) / **Data flow:** static AST scan

**Analog A (body-level walk on a named function):** `tests/test_ast_regression.py:774-814` — `TestPhase381CredBinding::test_scan_drift_no_continue_in_row_loop_phase38_1`

```python
def test_scan_drift_no_continue_in_row_loop_phase38_1(self) -> None:
    """Phase 38.1 D-15: no ``continue`` in scan_drift row loop."""
    src_root = Path(__file__).parent.parent / "src" / "homelab_mcp"
    source = (src_root / "drift_detection.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="drift_detection.py")

    target = next(
        (
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name == "scan_drift"
        ),
        None,
    )
    assert target is not None, (
        "Phase 38.1 D-15: scan_drift not found in drift_detection.py "
        "(if you renamed the function, update this guard)"
    )

    # ... walk target subtree, find violations ...
    violations = [n.lineno for n in ast.walk(row_loops[0]) if isinstance(n, ast.Continue)]
    assert not violations, (
        f"Phase 38.1 D-15 regression — `continue` reappeared in scan_drift row "
        f"loop at line(s): {violations}. ..."
    )
```

**Why this is the right analog:** D-10b explicitly cites `TestPhase37/38.1/40` classes as siblings. The body-level scope idiom (find named function via `ast.walk`, then `ast.walk(target)` to find violations only in that function's subtree) is exactly what D-10a mandates. Per-symbol `test_*` methods so failures pinpoint which symbol regressed.

**Analog B (file-list iteration over symbols):** `tests/test_ast_regression.py:707-734` — `TestPhase37DriftHygiene._FORBIDDEN_BASELINE_TOOL_NAMES` tuple + iteration

```python
_FORBIDDEN_BASELINE_TOOL_NAMES: tuple[str, ...] = (
    "register_drift_baseline",
    # ...
)

def test_no_baseline_tool_names_anywhere_in_src(self) -> None:
    # ...
    for forbidden in self._FORBIDDEN_BASELINE_TOOL_NAMES:
        # check each symbol
```

**Pattern to copy for D-10's forbidden-symbol set:**

```python
class TestPhase44RemoveDeviceCallPath:
    """Phase 44 D-10: handle_remove_device + delete_device_by_id are
    body-level free of SSH/Ansible/Terraform/credential-cleanup symbols.

    Scope per D-10a: walks ONLY the named functions' AST subtrees, NOT the
    transitive call graph. If the planner extracts a helper, the helper's
    name goes into _GUARDED_FUNCTIONS below.
    """

    _GUARDED_FUNCTIONS: tuple[tuple[str, str], ...] = (
        # (relative_path_under_src/homelab_mcp, function_name)
        ("tool_handlers/network_handlers.py", "handle_remove_device"),
        ("database.py", "delete_device_by_id"),  # SQLite + Postgres impls — see test impl
    )

    _FORBIDDEN_NAMES: tuple[str, ...] = (
        "ssh_connect",
        "asyncssh",
        "decommission_network_device",
        "_stop_all_device_services",
        "_remove_from_clusters",
        "_execute_migration_plan",
        "delete_credential",
        "delete_proxmox_credential",
    )

    def test_handle_remove_device_no_ssh_imports(self) -> None:
        # one test per forbidden symbol per D-10b
        ...
```

**Notable differences the planner must call out in PLAN.md:**
- Per D-10, the guard targets MULTIPLE named functions across two files (`network_handlers.py::handle_remove_device` AND `database.py::delete_device_by_id` — both SQLite and Postgres impls; for class methods the AST walk needs to find the method by class+name).
- For the Postgres/SQLite class-method case, scope to the `ClassDef` first, then find the method `FunctionDef` within. Mirrors how Phase 41's `TestPhase41BindingAwareResolver` (line 1317) handles class-method scoping (planner should read that class for the multi-impl pattern).
- `subprocess.*` blanket forbid (per D-10's "most defensive scope" choice): use the per-symbol visitor or `ast.dump` substring `"subprocess."` — Claude's Discretion in D-10 commentary recommends per-visitor for symbol-level checks; substring acceptable for the simpler `"no subprocess. anywhere in body"` check.
- One `test_*` method per forbidden symbol per D-10b — failures pinpoint the regressed symbol.
- `keyring.delete_password` / `keyring.set_password` checks: walk for `ast.Attribute` nodes where `attr` is the forbidden method name AND `value.id == "keyring"`. Mirror the pattern from `TestPhase39_1NoSkipInDriftEnum` (line 853) for attribute-access scanning.

---

### `docs/tool-reference.md` new entries

**Analog:** `docs/tool-reference.md:493-545` — `decommission_device` + `decommission_device_preview` paired entries

```markdown
### decommission_device

**Description:** Safely remove a device from the network infrastructure.

**Annotations:** `[Destructive]` `[Idempotent]`

**Arguments:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| device_id | integer | Yes | -- | Database ID of the device to decommission |
| ... | ... | ... | ... | ... |

**Example:**

```json
{
  "device_id": 3,
  ...
}
```

**Returns:** A dict with the decommission operation results or validation report.

---

### decommission_device_preview

**Description:** Preview what `decommission_device` would affect without executing. ...

**Annotations:** `[Read-Only]` `[Idempotent]`

**Arguments:**

Same shape as [`decommission_device`](#decommission_device).

| Name | Type | ... |
| ... |
```

**Why this is the right analog:** Same prose/markdown structure, same `[Annotation]` badge convention, same Arguments table format, same `Same shape as [...]` cross-reference for preview entries.

**Notable differences the planner must call out in PLAN.md:**
- New entries for `remove_device`, `remove_device_preview`, `purge_devices`, `purge_devices_preview` per D-16.
- Each example block per D-16 must cover happy path + dry_run (and per-`filter_type` for `purge_devices`).
- Update `decommission_device` entry: add the See-also cross-reference per D-09a (`"See also: \`remove_device\` for inventory-only deletion (no host-side cleanup)."`) AND the contrast-block sentence per D-09 (canonical wording quoted above).
- Update existing prose at lines 676 and 752 (the `_EMPTY_SCAN_GUIDANCE` quote in scan_infrastructure_drift's example block) to mention `remove_device` / `purge_devices` per SC-4 wording-parity sweep — read each in context first.

---

### `drift_detection.py` + `server.py` SC-4 wording sweep

**Analog:** `drift_detection.py:56-62` `_EMPTY_SCAN_GUIDANCE` constant + `:225-228` missing-branch error message

```python
_EMPTY_SCAN_GUIDANCE = (
    "No Proxmox hosts in sitemap matched this scan. "
    "Run discover_and_map to populate the sitemap, "
    "get_network_sitemap to inspect what's tracked, or "
    "purge_failed_discoveries to clean stale rows. "
    "If a host is decommissioned, use decommission_device."
)

# ...

message = (
    f"Host last seen {parsed.isoformat()} (>{threshold_days}d ago). "
    f"If decommissioned, run `decommission_device {hostname}` or "
    f"`purge_failed_discoveries` to clean up."
)
```

**Why this is the right analog:** Both messages already enumerate the sitemap-CRUD recovery surface. SC-4 wording-parity sweep extends them to mention `remove_device` / `purge_devices`.

**Notable differences the planner must call out in PLAN.md:**
- Update `_EMPTY_SCAN_GUIDANCE` (drift_detection.py:56-62) to add `remove_device` as the inventory-only option alongside `decommission_device`. Suggested addition: insert "or `remove_device` for inventory-only removal" after the `decommission_device` mention.
- Update the missing-branch message (drift_detection.py:225-228): add `remove_device` as the inventory-only alternative to `decommission_device`. Don't lose the existing pointers.
- `drift_detection.py:120-127` `_classify_credential_failure` "degenerate" branch points at `purge_failed_discoveries` — extend with `purge_devices(filter_type='hostname', value='unknown')` as the new precise-match alternative. Per-message wording is planner's call (planner reads each in context per CONTEXT canonical_refs).
- `server.py:157, 1022` — same SC-4 sweep. Planner reads each occurrence in context and updates wording per D-09's canonical contrast-block template where appropriate.

---

## Shared Patterns

### Structured-error envelope

**Source:** `network_handlers.py:104-113` (malformed input branch) + `:120-128` (missing-row branch)

**Apply to:** `handle_remove_device` (D-06b missing-id), `handle_purge_devices` (D-01b bad-`value`-shape).

```python
result_str = json.dumps(
    {
        "status": "error",
        "error": "<concrete-error-message>",
        "hint": "<actionable-recovery-pointer>",
    }
)
return {"content": [{"type": "text", "text": result_str}]}
```

Hints follow the canonical pattern from `project_credential_architecture.md` (memory): missing thing = hard error with CLI/tool pointer.

### `*_preview` thin-delegation

**Source:** `infrastructure_handlers.py:117-123` — `handle_decommission_device_preview` (one-liner spread idiom)

**Apply to:** `handle_remove_device_preview`, `handle_purge_devices_preview` (per D-11).

```python
return await handle_X({**arguments, "dry_run": True})
```

### Two-step DELETE cascade (no FK CASCADE)

**Source:** `database.py:646-654` (SQLite) + `:1204-1205` (Postgres)

**Apply to:** `delete_device_by_id` SQLite + Postgres impls (per D-06c). `discovery_history` first, `devices` second, single transaction.

### Body-level AST guard on a named function

**Source:** `tests/test_ast_regression.py:774-814` (Phase 38.1 D-15 idiom)

**Apply to:** `TestPhase44RemoveDeviceCallPath` (per D-10a). Walk via `ast.walk(tree) → next(... if FunctionDef and n.name == ...)`, then `ast.walk(target)` for body-level violations only. Per-symbol `test_*` method per D-10b.

### Tool-description contrast block (D-09 canonical wording)

**Source:** D-09 template (NEW canonical, per Phase 37 D-08 / Phase 40 D-04 convention precedent)

**Apply verbatim to:** `remove_device`, `purge_devices`, `decommission_device` schema descriptions AND each tool's `docs/tool-reference.md` entry.

> "Use `remove_device` for inventory-only deletion of one row; use `purge_devices` for bulk filter-based inventory deletion; use `decommission_device` when host-side cleanup (stop services, remove from clusters) is required before deletion."

Planner polishes wording for actionability before locking into all three locations (Claude's Discretion).

---

## No Analog Found

| File / Symbol | Role | Data Flow | Reason |
|---------------|------|-----------|--------|
| CIDR membership scan via `ipaddress` stdlib | utility | transform | No existing CIDR/`ipaddress` usage in the codebase; stdlib idiom documented inline above per D-03. |
| `_purge_devices_by_filter` shared dispatcher helper | private SQL builder | CRUD | No existing helper of this kind in `database.py`; closest is the inlined SQL in `purge_failed_devices`. Pattern documented inline above per D-14. |

---

## Metadata

**Analog search scope:**
- `src/homelab_mcp/tool_handlers/` (network_handlers.py, infrastructure_handlers.py, __init__.py)
- `src/homelab_mcp/tool_schemas/` (network_tools_schema.py, infrastructure_tools_schema.py)
- `src/homelab_mcp/database.py` (ABC + SQLite + Postgres adapter impls)
- `src/homelab_mcp/sitemap.py` (NetworkSiteMap shim)
- `src/homelab_mcp/tool_annotations.py`, `openapi_app.py`
- `src/homelab_mcp/drift_detection.py`, `server.py` (SC-4 wording-sweep targets)
- `tests/test_ast_regression.py` (Phase 37/38.1/40 sibling guard classes)
- `docs/tool-reference.md` (decommission_device entry pattern)

**Files scanned:** 11 source files + 1 test file + 1 docs file
**Pattern extraction date:** 2026-05-02

## PATTERN MAPPING COMPLETE
