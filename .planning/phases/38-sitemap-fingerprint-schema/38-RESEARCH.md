# Phase 38: Sitemap Fingerprint Schema - Research

**Researched:** 2026-04-25
**Domain:** SQLite + Postgres schema extension, asyncssh probe wiring, MCP tool + prompt registry extension
**Confidence:** HIGH (CONTEXT.md is locked; this research verifies file references and surfaces implementation gotchas only)

## Summary

Phase 38 ships exactly one requirement (DRFT-20) plus the SC-4 reliability discipline carried forward from Phase 35. The user has already locked all 13 architectural decisions (D-01..D-13) in `38-CONTEXT.md`. This research verifies CONTEXT.md's file references against the live codebase, surfaces five implementation gotchas the planner needs (most critically: **CONTEXT.md missed two registry files — `tool_annotations.py` and the `MUTATING_TOOLS` set in `server.py`**), maps each new artifact to its closest existing analog, and builds the Nyquist Validation Architecture so plan-check can wire validation per Dimension 8.

**Primary recommendation:** Plan a 5-task implementation following CONTEXT.md's locked decisions verbatim — but add explicit tasks for the two CONTEXT.md gaps surfaced here (tool annotations, MUTATING_TOOLS / resource notification wiring), update the brittle `test_ssh_discover_success` mock that uses fixed-order list lookup, and treat D-05b's "schema-level validation" as handler-side Python validation (the MCP framework does not validate against `inputSchema` automatically in this codebase).

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DRFT-20 | Sitemap schema captures fields necessary for meaningful drift detection — kernel version, package fingerprint, capability probes (e.g., GPU passthrough state, ML library availability such as Vulkan support) | Verified live: `ssh_discover_system` (lines 225-487), `_run_with_timeout` helper (lines 490-516), `parse_discovery_output` (lines 75-146), `NetworkDevice` dataclass (lines 34-60), `SQLiteAdapter.store_device` (lines 188-300), `SQLiteAdapter.init_schema` CREATE TABLE (lines 121-149), `PostgreSQLAdapter.store_device` `system_info` dict (lines 557-583), `PostgreSQLAdapter.get_all_devices` flattening (lines 686-708), `_maybe_json_load` (lines 839-857), Phase 35 D-09c migration block (`migration.py` lines 65-79), schema-rebuild branch (`migration.py` lines 149-220 — extends to line 220, not 178 as CONTEXT.md noted), Phase 35 D-15 AST guard at `tests/test_ast_regression.py:447` (verified — this guard auto-enforces SC-4 for any new `conn.run` inside `ssh_discover_system`). |
</phase_requirements>

## CONTEXT.md Verification — Live Codebase Audit

CONTEXT.md was written 2026-04-25 (the same day as this research). All file references verified against the live tree. Differences from CONTEXT.md:

| CONTEXT.md claim | Verified location | Drift |
|------------------|-------------------|-------|
| `_run_with_timeout` at `ssh_tools.py:490-516` | Lines 490-516 | None ✓ |
| `ssh_discover_system` at `ssh_tools.py:225-487` | Lines 225-487 | None ✓ |
| `NetworkDevice` at `sitemap.py:34-60` | Lines 34-60 | None ✓ |
| `parse_discovery_output` at `sitemap.py:75-146` | Lines 75-146 | None ✓ |
| `SQLiteAdapter.init_schema()` CREATE TABLE at `database.py:121-149` | Lines 121-149 | None ✓ |
| `SQLiteAdapter.store_device()` at `database.py:188-300` | Lines 188-300 | None ✓ |
| `PostgreSQLAdapter.init_schema()` at `database.py:481-540` | Lines 469-546 | Slight (start line 469, not 481; end 546, not 540) |
| `PostgreSQLAdapter.store_device()` `system_info` dict at `database.py:557-583` | Lines 557-583 | None ✓ |
| `PostgreSQLAdapter.get_all_devices()` flattening at `database.py:686-708` | Lines 686-708 | None ✓ |
| `_maybe_json_load` exists in `database.py` | Lines 839-857 | None ✓ |
| Phase 35 D-09c ALTER TABLE block at `migration.py:65-79` | Lines 65-79 | None ✓ |
| Schema-rebuild branch at `migration.py:149-178` | Lines 149-220 (CREATE TABLE 149-178; column copy logic 179-220) | CONTEXT.md cuts off early — the `target_cols` list ends at line 212, INSERT/RENAME at 215-220 |
| `target_cols` list at `migration.py:185` | Variable assigned at 185, list literal spans 185-212 | OK if planner reads it as "the list literal starting at line 185" |
| AST guard at `tests/test_ast_regression.py:447` | Line 447 (`test_ssh_discover_system_wraps_every_conn_run_phase35`) | None ✓ |
| AST guard at `tests/test_ast_regression.py:392` | Line 392 (`test_store_device_matches_on_hostname_alone_phase35`) | None ✓ |
| Existing `system_info["os"]` field populated from `device_data.get("os_info")` | `database.py:577` | None ✓ |
| `prompt_registry.py` Phase 14 prompts (`connect_to_device`, `decommission_device_workflow`, `deploy_service_workflow`, `homelab_health_check`) | All four present in `HOMELAB_PROMPTS` dict (lines 19-63), with builders 84-171 and dispatcher 179-208 | None ✓ |
| `tools.py` is the tool-registration surface for `update_device_fingerprint` | **WRONG.** `tools.py` is now a 42-line router. Schemas live in `tool_schemas/network_tools_schema.py` (or a new file); handlers in `tool_handlers/network_handlers.py`; routing in `tool_handlers/__init__.py` (the `TOOL_HANDLERS` dict at lines 77-138). | **MAJOR — CONTEXT.md describes the pre-Phase-21 monolithic `tools.py`. The current registry is split across `tool_schemas/` and `tool_handlers/` directories.** |
| `discover_and_map` description in `tools.py` | Description in `tool_schemas/network_tools_schema.py` line 7 | Same correction as above |
| `ssh_discover_system` description in `tools.py` | Description in `tool_schemas/ssh_tools_schema.py` line 7 (tool name is `ssh_discover`, not `ssh_discover_system`) | Same correction; also note tool name is `ssh_discover` (function is `ssh_discover_system`) |

[VERIFIED: codebase grep across all referenced files]

## Items CONTEXT.md Missed

These are real artifacts the planner MUST address; they're not in CONTEXT.md's `## Source Files Affected` list. Listed in priority order.

### 1. `tool_annotations.py` — readOnlyHint / destructiveHint registration

**File:** `src/homelab_mcp/tool_annotations.py` (197 lines, registers all 57 tools today)

The MCP spec requires `ToolAnnotations` (`readOnlyHint`, `destructiveHint`, `idempotentHint`) for every tool. This is registered in a separate file from the `inputSchema` and is wired into `server.py`'s `list_tools` handler.

**Required additions:**
- `update_device_fingerprint` → add to `_MUTATING_ANNOTATIONS` dict with `readOnlyHint=False, destructiveHint=False, idempotentHint=True` (idempotent because identical input produces identical merge result).
- `update_device_fingerprint_preview` (if D-05c ships) → add to `_READ_ONLY_TOOLS` list at line 23 (alongside the existing `decommission_device_preview`, `delete_proxmox_vm_preview`, etc.).

**If this step is skipped:** `get_tool_annotations("update_device_fingerprint")` returns `None` → `server.py`'s `list_tools` emits the tool without annotations → MCP clients can't show appropriate safety hints. Not a fatal bug; degrades UX consistency.

[VERIFIED: read `src/homelab_mcp/tool_annotations.py` end-to-end]

### 2. `MUTATING_TOOLS` set in `server.py` — resource-notification wiring

**File:** `src/homelab_mcp/server.py` lines 168-173 (`MUTATING_TOOLS: frozenset[str]`)

Today this set contains only `discover_and_map` and `bulk_discover_and_map`. When `handle_call_tool` (line 442) detects a tool in `MUTATING_TOOLS` and the call succeeded (non-dry-run), it sends `notifications/resources/list_changed` so subscribed MCP clients refresh `homelab://devices`.

**Required addition:** Add `update_device_fingerprint` to `MUTATING_TOOLS`. A successful capability merge changes the `homelab://devices` resource payload (the `fingerprint` key on a device row gets new content), so subscribed clients should re-fetch.

`update_device_fingerprint_preview` should NOT be added — it's read-only, no DB write happens.

**If this step is skipped:** Subscribed MCP clients won't see the updated fingerprint until the next time they manually re-read `homelab://devices`. Mostly cosmetic for the homelab single-user scope, but inconsistent with how `discover_and_map` behaves.

[VERIFIED: read `src/homelab_mcp/server.py` lines 165-178, 414-458]

### 3. `homelab://devices` resource — auto-surfaces `fingerprint` (no extra wiring)

**File:** `src/homelab_mcp/resource_readers.py` `read_devices_resource()` at line 75

This resource calls `db.get_all_devices()` and returns each device's full row dict. After Phase 38's D-10 changes (Postgres `get_all_devices` flattens `fingerprint` into top-level keys), the resource automatically surfaces `fingerprint` to MCP clients reading `homelab://devices`. **No code changes needed.** Listed here for awareness — the planner should NOT add an explicit task for this.

[VERIFIED: read `src/homelab_mcp/resource_readers.py` lines 75-115]

### 4. Brittle test mock at `tests/test_ssh_tools.py:78-95`

**File:** `tests/test_ssh_tools.py` `test_ssh_discover_success` (lines 16-152)

This test mocks SSH command results in **fixed-order list lookup** with 8 entries (hostname, nproc, cpu_model, mem, disk, network, uptime, os-release). After Phase 38 adds 3 new probes (uname -s, uname -r, dpkg-fingerprint), the test breaks: the 9th `mock_run` call falls through to `default_result` (exit_status=1, empty stdout), so the new probe results never populate. Worse, depending on probe ORDER inside `ssh_discover_system`, the 9th probe might be one of the OLD probes (lsusb, lspci, lsblk are AFTER os-release — see `ssh_tools.py` lines 386-447), causing previously-passing assertions to fail.

**Required fix:** Refactor `test_ssh_discover_success` to use the `STDOUT_BY_CMD` lookup pattern that the Phase 35 tests at lines 467-686 already use. Map by `cmd_name` (not call-order index). New probes can then be added without breakage. Or: extend the list to include all NEW probes in the right order. The lookup-by-name pattern is more resilient and matches Phase 35's existing convention.

**If this step is skipped:** `test_ssh_discover_success` fails after the new probes land, plus the existing `lsusb`/`lspci`/`lsblk` assertions in surrounding tests may break depending on call-order shifts.

[VERIFIED: read `tests/test_ssh_tools.py` lines 1-152, 460-686 — confirmed 8 results in `mock_run` closure, vs Phase 35 `STDOUT_BY_CMD` pattern]

### 5. MCP framework does NOT auto-validate `inputSchema`

**File:** `src/homelab_mcp/server.py` `handle_call_tool` (lines 418-458) → `tool_handlers/__init__.py` `get_tool_handler` → handler

The dispatch path is: SDK calls `handle_call_tool(name, arguments)` → `get_tool_handler(name)` returns the handler → `await handler(arguments or {})`. **No JSON Schema validation runs between dispatch and handler invocation.** A grep of `src/homelab_mcp/` for `additionalProperties` or `jsonschema` returns zero matches — the codebase does NOT use jsonschema validation; it relies on Python-side `validate_hostname()` calls inside handlers.

**Implication for D-05b:** "Only the recognized top-level keys are validated by the schema; unknown top-level keys are silently dropped" — this MUST be implemented inside the handler, not relied on as MCP framework behavior. Recommended pattern in the handler:

```python
RECOGNIZED_TOP_LEVEL = {"kernel_name", "kernel_version", "os_name", "os_version", "package_fingerprint", "capabilities"}

async def handle_update_device_fingerprint(arguments: dict[str, Any]) -> dict[str, Any]:
    validate_hostname(arguments["hostname"])
    fp = arguments.get("fingerprint", {})
    if not isinstance(fp, dict):
        return _error_result("`fingerprint` must be an object")
    cleaned = {k: v for k, v in fp.items() if k in RECOGNIZED_TOP_LEVEL}
    # ... merge, persist, return
```

[VERIFIED: read `src/homelab_mcp/server.py` lines 414-458; grep for `additionalProperties` and `jsonschema` returned no matches in `src/`]

## Standard Stack

This phase reuses everything already in the codebase. No new dependencies.

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `asyncssh` | already pinned | Per-probe SSH command execution | The codebase has used asyncssh since Phase 1; `ssh_discover_system` (the function Phase 38 extends) is built on it [VERIFIED: `src/homelab_mcp/ssh_tools.py` line 10 `import asyncssh`] |
| `mcp[cli]` | already pinned | MCP tool + prompt registration | Phase 14 prompts and all 57 existing tools use this; `mcp.types.Prompt`, `mcp.types.PromptArgument`, `mcp.types.GetPromptResult`, `mcp.types.ToolAnnotations` are the relevant types [VERIFIED: `src/homelab_mcp/prompt_registry.py` line 10, `src/homelab_mcp/tool_annotations.py` line 10] |
| `sqlite3` (stdlib) | Python 3.12 | Local sitemap DB | Already used; `ALTER TABLE ADD COLUMN fingerprint TEXT` is the exact mirror of Phase 35 D-09c [CITED: SQLite docs — `ALTER TABLE` supports `ADD COLUMN` with NULL default for existing rows] |
| `psycopg2` | already pinned, optional | Postgres adapter | JSONB column accommodates new `fingerprint` sub-key without DDL [VERIFIED: `src/homelab_mcp/database.py` lines 17-21] |
| `hashlib` (stdlib) | Python 3.12 | sha256 of dpkg output | Used elsewhere for `calculate_data_hash`; [VERIFIED: `src/homelab_mcp/database.py` line 3, `database.py:834-836`] |

**No new packages.** `uv sync` already installs everything.

## Architecture Patterns

### System Architecture Diagram

```
                    ┌─────────────────────────────────┐
                    │ Agent (Claude in MCP client)    │
                    └────────┬──────────────────────┬─┘
                             │                      │
       ┌─────────────────────┘                      │
       │ discover_and_map(hostname)                 │ configure_host_fingerprint(hostname)
       │ (existing tool)                            │ (new MCP prompt — agent reads, follows steps)
       │                                            │
       ▼                                            ▼
┌──────────────────────────┐         ┌──────────────────────────────────┐
│ handle_discover_and_map  │         │ Agent reads sitemap row,          │
│ → discover_and_store     │         │ infers role hints from os/pci,    │
│ → ssh_discover_system    │         │ asks user, runs ssh_execute_      │
│                          │         │ command for capability probes,    │
│ Wraps every conn.run     │         │ assembles capabilities dict,      │
│ in _run_with_timeout(10s)│         │ then calls:                       │
│                          │         │                                   │
│ NEW probes (3):          │         │ update_device_fingerprint(        │
│   uname -s   → kernel_name         │   hostname,                       │
│   uname -r   → kernel_version      │   {capabilities: {...}})          │
│   /etc/os-release → os_name/os_ver │                                   │
│   dpkg -l|sort|sha256sum →         │                                   │
│     package_fingerprint            │                                   │
└──────────┬───────────────┘         └──────────────┬───────────────────┘
           │                                        │
           │ Discovery payload JSON                 │ Update fingerprint
           │ {data: {...,                           │ (deep-merge on capabilities,
           │   fingerprint: {                       │  overwrite on top-level)
           │     kernel_name, kernel_version,       │
           │     os_name, os_version,               │
           │     package_fingerprint              }}│
           │ partial: True (if any probe missed)    │
           ▼                                        ▼
┌──────────────────────────┐         ┌──────────────────────────────────┐
│ parse_discovery_output   │         │ handle_update_device_fingerprint │
│ → NetworkDevice          │         │ → validate_hostname,             │
│   .fingerprint =         │         │   filter top-level keys,          │
│     json.dumps(          │         │   db_adapter.update_              │
│       data["fingerprint"])         │   device_fingerprint(             │
└──────────┬───────────────┘         │     hostname, merged_dict)        │
           │                         └──────────────┬───────────────────┘
           ▼                                        ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    SQLiteAdapter / PostgreSQLAdapter                  │
│                                                                       │
│  store_device:                       update_device_fingerprint:       │
│  ─────────────                       ────────────────────────         │
│  SQLite: write `fingerprint TEXT`    SQLite: read existing JSON,      │
│    column (JSON-string)                deep-merge per D-05, write     │
│  Postgres: store inside system_info    back. Update last_seen.        │
│    JSONB sub-key                     Postgres: jsonb merge or         │
│                                        read+merge+write in Python.    │
│                                                                       │
│  get_all_devices:                                                     │
│  ────────────                                                         │
│  SQLite: SELECT * picks up new column automatically; parse JSON       │
│    string back to dict in flatten loop (mirror Phase 35 D-09b).      │
│  Postgres: flatten system_info.fingerprint → top-level `fingerprint` │
│    key (mirror Phase 35 D-09b).                                      │
└─────────────────────────────────┬────────────────────────────────────┘
                                  │
                                  ▼
                    ┌──────────────────────────┐
                    │ homelab://devices        │
                    │ MCP resource (auto-      │
                    │ surfaces `fingerprint`   │
                    │ via get_all_devices)     │
                    │                          │
                    │ Phase 39 (DRFT-19) reads │
                    │ this for `changed`       │
                    │ bucket detection.        │
                    └──────────────────────────┘
```

### Component Responsibilities

| Component | File:Lines | Phase 38 Responsibility |
|-----------|------------|-------------------------|
| `ssh_discover_system` | `ssh_tools.py:225-487` | Add 3 new probes (uname -s, uname -r, dpkg fingerprint) + `/etc/os-release` parse upgrade; assemble `system_info["fingerprint"]` sub-dict; all wrapped in `_run_with_timeout` |
| `_run_with_timeout` helper | `ssh_tools.py:490-516` | Reused unchanged. AST guard at `tests/test_ast_regression.py:447` enforces every new probe wraps. |
| `NetworkDevice` dataclass | `sitemap.py:34-60` | Add `fingerprint: str \| None = None` field (JSON string per Phase 35 D-09b convention) |
| `parse_discovery_output` | `sitemap.py:75-146` | New branch: when `data["fingerprint"]` exists, `device.fingerprint = json.dumps(data["fingerprint"])` |
| `SQLiteAdapter.init_schema` | `database.py:111-186` | Add `fingerprint TEXT` column to `CREATE TABLE devices` (lines 121-149) |
| `SQLiteAdapter.store_device` | `database.py:188-300` | UPDATE branch (218-255) and INSERT branch (256-294) both add `fingerprint` (param + row) |
| `SQLiteAdapter.get_all_devices` | `database.py:302-331` | `SELECT *` already covers; add JSON parse in the flatten loop (lines 322-327) for `fingerprint` alongside usb/pci/block |
| `PostgreSQLAdapter.store_device` | `database.py:548-662` | Add `"fingerprint": _maybe_json_load(device_data.get("fingerprint"))` to `system_info` dict at line 580-583 |
| `PostgreSQLAdapter.get_all_devices` | `database.py:664-713` | Add `"fingerprint": system_info.get("fingerprint")` to flattening dict at lines 686-708 |
| New adapter method `update_device_fingerprint` (D-11 Option A — recommended) | new method on `DatabaseAdapter` ABC + both concrete adapters | Read existing `fingerprint`, deep-merge per D-05 (top-level overwrite, `capabilities` deep-merge), write back, refresh `last_seen` |
| `run_sqlite_migrations` | `migration.py:15-252` | Add `ALTER TABLE devices ADD COLUMN fingerprint TEXT` step (mirror Phase 35 D-09c block at lines 65-79) |
| Schema-rebuild branch | `migration.py:149-220` | Add `fingerprint TEXT` to the `devices_new` CREATE TABLE (line ~170 area); add `"fingerprint"` to `target_cols` list (within lines 185-212) |
| `tool_schemas/network_tools_schema.py` | currently 102 lines | Register `update_device_fingerprint` schema; optionally `update_device_fingerprint_preview`; update `discover_and_map` description (line 7) to reference `configure_host_fingerprint` |
| `tool_schemas/ssh_tools_schema.py` line 7 | currently `ssh_discover` description | Update description to reference `configure_host_fingerprint` |
| `tool_handlers/network_handlers.py` | currently 85 lines | Add `handle_update_device_fingerprint` (and preview variant if shipped); use `validate_hostname` (existing pattern at line 12) |
| `tool_handlers/__init__.py` `TOOL_HANDLERS` dict | lines 77-138 | Register new handler(s) — under `# Network tools` section (lines 82-89) |
| `tool_annotations.py` | currently 197 lines | Add `update_device_fingerprint` to `_MUTATING_ANNOTATIONS` dict; `update_device_fingerprint_preview` to `_READ_ONLY_TOOLS` list |
| `server.py` `MUTATING_TOOLS` | lines 168-173 | Add `update_device_fingerprint` so resource notifications fire |
| `prompt_registry.py` | currently 209 lines | Add `configure_host_fingerprint` entry to `HOMELAB_PROMPTS` (lines 19-63); add `_build_configure_host_fingerprint_result` builder (mirror `_build_connect_to_device_result` at lines 125-154); add dispatcher case in `get_prompt_result` (lines 192-208) |

### Anti-Patterns to Avoid

- **Bare `await conn.run(...)` for new probes** — Phase 35 D-15 AST guard at `tests/test_ast_regression.py:447` will FAIL the test suite. Every new probe must call `_run_with_timeout(conn, "<cmd>", cmd_name="<name>", timed_out=timed_out_commands)`.
- **Cross-OS branching in probe code** — User's locked decision (D-04 + free-text in DISCUSSION-LOG): probe code does Debian happy path; agent gap-fills via `ssh_execute_command`. Do NOT add `if os_release.contains("Ubuntu") then ... else if RHEL then ...`.
- **Distinct `unsupported` sentinel** — User's locked decision: missing tool = field absent + `partial: True` (Phase 35 inheritance). Don't add a new sentinel string.
- **Strict additionalProperties: false** on the `update_device_fingerprint` inputSchema — D-05b says `additionalProperties: true` inside `capabilities`. Even at the top level, the codebase pattern is to filter unknown keys in the handler (since MCP framework doesn't enforce). Don't try to make jsonschema validate.
- **Composite `(hostname, connection_ip)` lookup in the new `update_device_fingerprint` adapter method** — Phase 35 D-01 / D-14 (AST-guarded at line 392) requires hostname-alone lookup with degenerate-hostname fallback to composite. Mirror the existing `store_device` lookup pattern (`database.py:200-211`).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-probe SSH timeout | New timeout loop | `_run_with_timeout(conn, cmd, cmd_name=..., timed_out=...)` (`ssh_tools.py:490-516`) | Phase 35 D-05; AST-guarded at `test_ast_regression.py:447` |
| Hostname-natural-key lookup | New SELECT query | Mirror existing `store_device` lookup pattern (`database.py:200-211`) | Phase 35 D-01; AST-guarded at `test_ast_regression.py:392` |
| JSON-string round-trip for Postgres adapter | New helper | `_maybe_json_load` helper (`database.py:839-857`) | Phase 35 D-09b; handles None/empty/non-string passthrough |
| MCP prompt registration | New mechanism | `prompt_registry.py` — add to `HOMELAB_PROMPTS` dict + add `_build_*_result` function + dispatcher case | Phase 14 PRMT-01..04; the existing 4 prompts cover the entire pattern |
| Tool annotation registration | New mechanism | `tool_annotations.py` — add to `_MUTATING_ANNOTATIONS` dict | The codebase has 57 tools all going through this single registry |
| Tool registration (new MCP tool) | New mechanism | Add inputSchema to `tool_schemas/network_tools_schema.py`, handler to `tool_handlers/network_handlers.py`, register in `tool_handlers/__init__.py` `TOOL_HANDLERS` dict | The split-registry pattern (schemas vs handlers) is established for all 57 tools |
| Hostname validation | Custom regex | `validate_hostname()` from `validation.py` | Used by every existing handler that takes a hostname |
| sha256 hashing | New code | `hashlib.sha256(...).hexdigest()` (Python stdlib) | Already imported in `database.py` for `calculate_data_hash` |

**Key insight:** Phase 38 is almost entirely "extend an existing pattern by one row/key/registration." There are no new mechanisms to invent — every artifact has 1-3 existing analogs in the codebase to mirror exactly. The risk is forgetting one of the registration sites (per CONTEXT.md gaps surfaced above).

## Runtime State Inventory

This is a NEW-FEATURE phase, not a rename/refactor/migration phase, so the rename inventory does not apply. However, since Phase 38 ALSO ships a SQLite ALTER TABLE migration, the relevant runtime-state question is: *what existing data in the sitemap DB needs to know about the new column?*

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Existing SQLite `~/.mcp/sitemap.db` rows: `fingerprint` column gets NULL on first migration run | None — re-discovery populates them. SC-3 explicitly accepts NULL for old rows. |
| Stored data | Existing Postgres `devices.system_info` JSONB rows: no `fingerprint` sub-key on first migration run | None — new sub-key just doesn't exist; `system_info.get("fingerprint")` returns `None`. Re-discovery adds it. |
| Live service config | None — no n8n / external workflows | None — verified by absence of any external orchestration in the codebase |
| OS-registered state | None — no Windows Task Scheduler, systemd, or pm2 entries reference the schema | None — verified by `Glob("**/*.plist")`, `Glob("**/*.service")` returning nothing project-related |
| Secrets / env vars | None — no env vars reference field names | None — verified by absence of fingerprint-related env vars |
| Build artifacts | `pyproject.toml` version unaffected by Phase 38 (no public API surface changes); test snapshot files don't exist for sitemap rows | None — verified by `Grep("snapshot", path="tests/")` returning no matches |

**The canonical question:** *After every code change ships, what runtime systems still have stale state?* Answer: **only existing SQLite `devices` rows with NULL `fingerprint` and existing Postgres rows missing the `system_info.fingerprint` sub-key. Both are explicitly accepted as "re-discovery populates them" per SC-3.**

## Common Pitfalls

### Pitfall 1: `dpkg -l` output is locale-sensitive

**What goes wrong:** Two runs of `dpkg -l | sort | sha256sum` against the SAME package set produce DIFFERENT digests if the locale (LANG / LC_COLLATE / LC_ALL) changes between runs — the sort order shifts because `sort` honors locale collation, and the dpkg output column widths can shift if the user's locale produces wider package descriptions.
**Why it happens:** glibc `strcoll()` / `qsort()` honors `LC_COLLATE`. Most Debian/Proxmox hosts default to `en_US.UTF-8` or `C.UTF-8` so this is rare in practice — but a host with `de_DE.UTF-8` or `fr_FR.UTF-8` will sort differently.
**How to avoid:** Pin locale at probe time. Recommended command: `LC_ALL=C dpkg -l 2>/dev/null | sort | sha256sum`. The `LC_ALL=C` prefix forces byte-wise sort, locale-independent. Mention this in the new probe code as an inline comment so it's not "fixed" later.
**Warning signs:** Two consecutive `discover_and_map` runs against the same host produce different `package_fingerprint` values without any package change.

[CITED: https://reproducible-builds.org/docs/stable-outputs/ — "When machine parsing dpkg output, it is customary to set the locale to C.UTF-8 to get reproducible results"]

### Pitfall 2: `dpkg -l` includes a header line that timestamps may vary

**What goes wrong:** `dpkg -l` output includes a 5-line header (column titles + separator) that's stable across hosts but does NOT include any timestamp. **However**, `dpkg -l` shows the package "ii" status (installed, half-installed, etc.) — a package whose status flips from "ii" to "rc" (config-files-only after `apt remove` without `--purge`) changes the digest without changing what's truly installed in the user-meaningful sense.
**Why it happens:** dpkg tracks more states than just installed/removed.
**How to avoid:** Either accept the broader "any state change" semantics (recommended for Phase 38; matches DRFT-20's "package fingerprint changes when packages change") OR use `dpkg-query -W -f='${Package} ${Version}\n'` which lists only currently-installed packages and excludes `rc` entries. **Recommended:** start with `dpkg -l` per CONTEXT.md D-04 and document the "rc state changes also count" semantics in the prompt body so the agent can explain it; switch to `dpkg-query -W` later if false-positive drift is reported.
**Warning signs:** Drift report says "package fingerprint changed" but `apt list --upgradable` is empty — likely a state-flip not a real upgrade.

[CITED: https://manpages.debian.org/unstable/dpkg/dpkg-query.1.en.html — `-W --show` lists installed packages; format-string controls fields]

### Pitfall 3: `/etc/os-release` `PRETTY_NAME` quoting inconsistency

**What goes wrong:** Different distros quote `PRETTY_NAME` differently — Debian uses `PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"`, Proxmox uses `PRETTY_NAME="Proxmox VE 8.2.4"`, but some homemade derivatives (and old Alpine builds) use `PRETTY_NAME=Alpine Linux 3.18` (no quotes). The existing code at `ssh_tools.py:380-383` uses `os_line.split("=", 1)[1].strip('"')` — that strips quotes only if present, OK for most cases but breaks on values that legitimately contain quote chars.
**Why it happens:** `/etc/os-release` is a shell-fragment format; quoting is recommended but not required.
**How to avoid:** Either reuse the existing parser at line 374-383 (handles current real-world distros) or use `shlex.split()` to do proper shell-quoting parse. Recommended: stay with the existing parser, and ALSO parse `NAME` and `VERSION_ID` independently as fallbacks (CONTEXT.md D-04 already specifies this fallback). For `os_version`, prefer `VERSION_ID` (a clean machine-parseable field like `8.2.4` or `12`) over parsing version out of `PRETTY_NAME`. Don't try to be clever about parsing the full string.
**Warning signs:** Drift report says `os_name` changed but the host is the same release.

[CITED: https://www.freedesktop.org/software/systemd/man/os-release.html — `VERSION_ID` is the recommended machine-parseable version field]

### Pitfall 4: Postgres JSONB null vs missing sub-key semantics

**What goes wrong:** When Phase 38's Postgres adapter writes `system_info` with `"fingerprint": null` (because `device_data.get("fingerprint")` returned None), `get_all_devices` flattening `system_info.get("fingerprint")` returns `None`. So far so good. But when the agent later calls `update_device_fingerprint` and the Postgres adapter does the JSONB merge — if it uses the `||` operator with the new dict, it will OVERWRITE `system_info` entirely if not careful. The recommended pattern is read-merge-write in Python (Option B-style for the merge), not `jsonb_set` SQL operations, to keep the merge logic identical between SQLite and Postgres.
**Why it happens:** JSONB merge semantics are subtle; `||` is shallow merge; `jsonb_set` requires exact path strings.
**How to avoid:** Implement `update_device_fingerprint` adapter method as: (1) `SELECT system_info FROM devices WHERE hostname = ?`, (2) merge in Python, (3) `UPDATE devices SET system_info = ? WHERE hostname = ?`. Identical structure to the SQLite path, just with `%s` placeholders and `json.dumps`. Document this as a deliberate choice — "merge in Python for path parity with SQLite" — so a future optimizer doesn't try to push it into SQL.
**Warning signs:** A second `update_device_fingerprint(...)` call wipes out the kernel/os fields that were populated by the prior `discover_and_map`.

[CITED: https://www.postgresql.org/docs/current/functions-json.html — JSONB `||` is shallow merge; `jsonb_set` is path-based replacement]

### Pitfall 5: Test-fixture brittleness in `test_ssh_discover_success` (already mentioned above)

See "Items CONTEXT.md Missed" item 4. The fixed-order `mock_run` lookup in `tests/test_ssh_tools.py:78-95` will break when 3 new probes are added between `os-release` (call 8) and `lsusb` (call 9 today, call 12 after Phase 38). Mitigation: refactor to `STDOUT_BY_CMD` lookup pattern.

### Pitfall 6: `discovery_history` JSON shape change is a breaking change for `homelab://devices`'s `last_discovery_data` consumers

**What goes wrong:** The `read_devices_resource` function (`resource_readers.py:75`) attaches `last_discovery_data = changes[0]["data"]` — and the discovery JSON gets a new top-level `data.fingerprint` sub-dict in Phase 38. If any downstream MCP-resource-reading test asserts the EXACT shape of `data` (e.g., asserts only specific keys exist), it breaks. Likely no such test exists, but worth a grep.
**Why it happens:** Discovery payload is the public shape of the resource.
**How to avoid:** `Grep('"data".*"cpu".*"memory"', tests/)` and `Grep('"data".keys()', tests/)` before merging. If found, widen the assertion to "at least these keys exist" rather than "only these keys exist."
**Warning signs:** Resource-related test fails with "unexpected key 'fingerprint' in data".

[VERIFIED via Grep: `Grep('discovery_data.*keys\\(\\)', tests/)` returned no matches; the existing tests check specific keys present, not absent — Phase 38 is safe]

## Code Examples

Verified patterns from the live codebase.

### New probe inside `ssh_discover_system` (mirror existing CPU/memory blocks)

```python
# Source: ssh_tools.py:265-269 (nproc probe — exact mirror pattern)
# Phase 38 NEW probe, to be added inside ssh_discover_system after the os-release block (around line 384):

# Get kernel and OS fingerprint info (Phase 38 D-04)
fingerprint_info: dict[str, Any] = {}

uname_s_result = await _run_with_timeout(
    conn, "uname -s", cmd_name="uname-s", timed_out=timed_out_commands
)
if uname_s_result and uname_s_result.exit_status == 0 and uname_s_result.stdout:
    fingerprint_info["kernel_name"] = cast(str, uname_s_result.stdout).strip()

uname_r_result = await _run_with_timeout(
    conn, "uname -r", cmd_name="uname-r", timed_out=timed_out_commands
)
if uname_r_result and uname_r_result.exit_status == 0 and uname_r_result.stdout:
    fingerprint_info["kernel_version"] = cast(str, uname_r_result.stdout).strip()

# /etc/os-release — re-read full file (the existing PRETTY_NAME-only line at 374-383 stays
# for the legacy `system_info["os"]` field; this NEW parse extracts os_name + os_version
# for the fingerprint sub-dict per D-04 + D-07 back-compat).
os_release_result = await _run_with_timeout(
    conn, "cat /etc/os-release 2>/dev/null", cmd_name="os-release-full",
    timed_out=timed_out_commands,
)
if os_release_result and os_release_result.exit_status == 0 and os_release_result.stdout:
    parsed: dict[str, str] = {}
    for line in cast(str, os_release_result.stdout).splitlines():
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        parsed[key.strip()] = value.strip().strip('"').strip("'")
    if parsed.get("PRETTY_NAME"):
        fingerprint_info["os_name"] = parsed["PRETTY_NAME"]
    elif parsed.get("NAME"):
        fingerprint_info["os_name"] = parsed["NAME"]
    if parsed.get("VERSION_ID"):
        fingerprint_info["os_version"] = parsed["VERSION_ID"]

# dpkg fingerprint — locale-pinned for reproducibility (see Pitfall 1)
dpkg_result = await _run_with_timeout(
    conn,
    "LC_ALL=C dpkg -l 2>/dev/null | sort | sha256sum",
    cmd_name="dpkg-fingerprint",
    timed_out=timed_out_commands,
)
if dpkg_result and dpkg_result.exit_status == 0 and dpkg_result.stdout:
    digest_field = cast(str, dpkg_result.stdout).strip().split()[0]
    if digest_field and digest_field != "d41d8cd98f00b204e9800998ecf8427e":  # not empty/sha-of-empty
        fingerprint_info["package_fingerprint"] = f"sha256:{digest_field}"

if fingerprint_info:
    system_info["fingerprint"] = fingerprint_info
```
[ASSUMED: exact placement inside ssh_discover_system — the planner picks; immediately after the existing os-release block at line 383 is the natural location]

### `parse_discovery_output` extension (mirror Phase 35 D-09b usb/pci/block branch)

```python
# Source: sitemap.py:121-127 (Phase 35 D-09b pattern)
# Phase 38 addition, to be added inside parse_discovery_output after the block_devices branch:

# Fingerprint sub-dict (Phase 38 D-04c: store as JSON string per Phase 35 D-09b convention)
if "fingerprint" in discovery_data:
    device.fingerprint = json.dumps(discovery_data["fingerprint"])
```

### `NetworkDevice` field addition (mirror Phase 35 D-09b)

```python
# Source: sitemap.py:55-57 (Phase 35 D-09b additions)
# Phase 38 addition, to be added in the dataclass field block:

fingerprint: str | None = None  # JSON string (Phase 38 D-04c, D-09b convention)
```

### `update_device_fingerprint` deep-merge logic (D-05)

```python
# To be added as a method on the new adapter ABC method or inside the handler.
# This is the merge contract D-05 mandates:

def merge_fingerprint(stored: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Phase 38 D-05 merge: top-level overwrite, capabilities deep-merge.

    `stored` is the existing fingerprint dict (parsed from JSON column).
    `incoming` is the dict the agent sent via update_device_fingerprint.
    Returns the merged dict to write back.
    """
    merged = dict(stored)  # start from stored
    for key, value in incoming.items():
        if key == "capabilities" and isinstance(value, dict):
            existing_caps = dict(merged.get("capabilities", {}))
            existing_caps.update(value)  # incoming sub-keys overwrite, others preserved
            merged["capabilities"] = existing_caps
        else:
            merged[key] = value  # top-level keys overwrite (D-05 step 3a)
    return merged
```
[ASSUMED: exact function placement — recommended in `database.py` as a module-level helper if D-11 Option A; otherwise inside the handler if D-11 Option B]

### `configure_host_fingerprint` MCP prompt (mirror Phase 14 `connect_to_device`)

```python
# Source: prompt_registry.py:52-62 (HOMELAB_PROMPTS entry) and 125-154 (builder)
# Phase 38 addition to HOMELAB_PROMPTS dict:

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

```python
# Phase 38 addition — builder mirroring _build_connect_to_device_result (lines 125-154):

def _build_configure_host_fingerprint_result(args: dict[str, str]) -> types.GetPromptResult:
    """Build the configure_host_fingerprint prompt result (Phase 38 D-06)."""
    hostname = args.get("hostname", "<hostname>")
    text = f"""Follow these steps to configure capability-fingerprint tracking for {hostname}:

1. Call get_network_sitemap and find the entry whose hostname matches "{hostname}". \
If not found, redirect the user: "Run discover_and_map first so {hostname} is in the sitemap."

2. Read the entry's fingerprint.os_name and pci_devices fields to infer role hints:
   - If os_name contains "Proxmox VE": likely a Proxmox host. Suggest tracking gpu_passthrough \
(IOMMU groups, vfio modules, kernel cmdline) and ZFS module version if pools exist.
   - If pci_devices contains "NVIDIA": likely a GPU host. Suggest tracking CUDA driver and runtime versions.
   - If pci_devices contains "AMD" + "VGA" or "Display": likely a graphics-capable host. \
Suggest tracking Vulkan loader version and Mesa/ROCm library versions.
   - If os_name contains "TrueNAS" or block_devices show ZFS pool members: likely a NAS. \
Suggest tracking ZFS module version and expected-running services.

3. Present the suggestions to the user (free-form): "Based on what I see on {hostname}, \
here are signals I'd suggest tracking as drift indicators: [list]. Should I track these? \
Anything else to add?" — let the user accept, modify, or extend the list.

4. For each agreed signal, call ssh_execute_command(hostname="{hostname}", command="<probe>") \
to capture the current value. Examples:
   - vulkaninfo: command="vulkaninfo --summary 2>/dev/null | head -20"
   - nvidia-smi: command="nvidia-smi --query-gpu=driver_version,name --format=csv,noheader"
   - IOMMU groups: command="ls /sys/kernel/iommu_groups/ 2>/dev/null | wc -l"
   - vfio modules: command="lsmod | grep -E '^vfio'"
   - ZFS module: command="modinfo zfs 2>/dev/null | grep ^version"
   - kernel cmdline: command="cat /proc/cmdline"

5. Build a capabilities dict from the captured values and call \
update_device_fingerprint(hostname="{hostname}", fingerprint={{"capabilities": {{...}}}}). \
Use update_device_fingerprint_preview first if you want to confirm the merge before persisting.

6. Confirm the persisted fingerprint to the user, summarising what is now being tracked.

Phase 39's drift detection will use these signals to detect changed infrastructure on \
subsequent discover_and_map runs."""
    return types.GetPromptResult(
        description="Per-host capability fingerprint configuration workflow",
        messages=[_make_user_message(text)],
    )
```

```python
# Phase 38 addition to get_prompt_result dispatcher (lines 192-208):

elif name == "configure_host_fingerprint":
    return _build_configure_host_fingerprint_result(args)
```

### Closest existing analogs (D-06 prompt + D-05 tool + D-12 tests)

| New artifact | Closest existing analog | Why it's the cleanest mirror |
|--------------|------------------------|------------------------------|
| `update_device_fingerprint` MCP tool handler | `handle_discover_and_map` (`tool_handlers/network_handlers.py:10-15`) | Same module, same `validate_hostname` opening pattern, same return shape (`{"content": [{"type": "text", "text": result}]}`). The handler that should NOT be mirrored is `handle_purge_failed_discoveries` (lines 69-84) — that one has a `dry_run` param baked in; `update_device_fingerprint_preview` (D-05c) is a SEPARATE tool, not a `dry_run=True` param. |
| `update_device_fingerprint_preview` (if D-05c ships) | `decommission_device_preview` (`tool_handlers/infrastructure_handlers.py` + tool_schemas line 275-315) | Existing `*_preview` thin-delegation pattern: same handler shape minus the write step. Returns the merge result without persisting. |
| `configure_host_fingerprint` MCP prompt body | `_build_connect_to_device_result` (`prompt_registry.py:125-154`) | Same hostname argument, same multi-step instruction format, same "if X then Y" branching style. Mirror exactly. |
| Test file for fingerprint round-trip | Extension of `tests/test_sitemap.py` (existing fixtures `sample_ssh_discovery_success` at line 28-57 + `TestNetworkSiteMap` class) | Add a `fingerprint` key to the fixture; add `assert device.fingerprint == json.dumps({...})`; mirror the `test_parse_discovery_output_success` pattern at line 104. **Don't create a new file** — the existing one already has the right helpers and the right `temp_db` fixture. |
| Test for `update_device_fingerprint` adapter method | Extension of `tests/test_database.py` (`TestSQLiteAdapter` class at line 20+) | Mirror `test_store_and_retrieve_device` at line 53 — store, then call new method, then read back. |
| Test for new MCP tool routing | Extension of `tests/test_tools.py` (`test_execute_unknown_tool` at line 69 + the existing `execute_tool("discover_and_map", ...)` call patterns at line 103) | Same `await execute_tool(name, args)` pattern. |
| Test for new MCP prompt | Extension of `tests/test_mcp_prompts.py` (`test_connect_to_device_prompt` at line 96-129) | Mirror exactly — assert prompt registered, assert builder returns interpolated text containing required tool names. |

## State of the Art

| Old approach (pre-Phase 38) | New approach (Phase 38) | When changed | Impact |
|------|------|--------------|--------|
| Discovery payload's `data.os` is a single PRETTY_NAME string | Discovery payload also has `data.fingerprint.{kernel_name, kernel_version, os_name, os_version, package_fingerprint}` | Phase 38 D-04 | `os_info` field stays for back-compat; new fields enable Phase 39's per-field diff |
| Sitemap rows have flat per-field columns (cpu, memory, disk, etc.) plus 3 JSON-string columns (usb/pci/block from Phase 35) | Same flat columns + 3 Phase-35 JSONs + 1 new JSON column `fingerprint` | Phase 38 D-01 | First "freeform per-host" column on the sitemap; capabilities sub-dict is genuinely freeform per host |
| MCP prompts cover onboarding, decommission, deploy, health-check (4 prompts) | + `configure_host_fingerprint` (5 prompts) | Phase 38 D-06 | Each prompt is plain narrative; agent compliance is the contract |
| MCP tools are 57 (per `tool_annotations.py` comment line 3) | + `update_device_fingerprint` and optionally `update_device_fingerprint_preview` (58 or 59) | Phase 38 D-05, D-05c | Tool count published in README must increment if D-13 docs sweep updates that file |

**Deprecated/outdated:** Nothing deprecated in Phase 38. CONTEXT.md D-07 explicitly keeps `os_info` indefinitely. Future deprecation is a separate phase.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `LC_ALL=C dpkg -l \| sort \| sha256sum` is locale-stable across consecutive runs on the same Debian/Proxmox host | Pitfall 1, Code Examples | Low — well-documented practice; if wrong, two consecutive discoveries produce different fingerprints, surfacing as false-positive drift in Phase 39 |
| A2 | `dpkg-query -W -f='${Package} ${Version}\n'` is the cleaner alternative if `dpkg -l` proves too noisy (rc state changes triggering false drift) | Pitfall 2 | Low — both are well-documented dpkg interfaces; if wrong, agent-driven `tracked_packages` capability captures the precise packages instead |
| A3 | Postgres JSONB merge via Python read-merge-write is the right path-parity choice (avoids `jsonb_set` SQL complexity) | Pitfall 4 | Low — the codebase already does this pattern for `system_info` writes today (`database.py:629-631` calls `json.dumps(system_info)`); same pattern works for the new merge step |
| A4 | The existing `read_devices_resource` (`resource_readers.py:75`) auto-surfaces the new `fingerprint` field via `db.get_all_devices()` flattening, with no extra wiring | Items CONTEXT.md Missed §3 | Low — verified by reading the function end-to-end; the `dict(device)` at line 97 includes whatever keys `get_all_devices` returns |
| A5 | The MCP framework does NOT validate `inputSchema` automatically; the handler must do dict-shape validation in Python | Items CONTEXT.md Missed §5 | Low — verified by reading `server.py:418-458` and grepping for `additionalProperties` / `jsonschema` (no matches); confirmed by `validate_hostname()` being called explicitly inside every handler that takes a hostname |
| A6 | Phase 38 should add `update_device_fingerprint` to `MUTATING_TOOLS` so resource notifications fire | Items CONTEXT.md Missed §2 | Low — only impact if missed is "subscribed clients don't auto-refresh `homelab://devices`" — single-user homelab UX nicety |
| A7 | The existing `test_ssh_discover_success` test at `tests/test_ssh_tools.py:16-152` will break when 3 new probes are added (fixed-order list lookup hits 9th call falling through to default) | Items CONTEXT.md Missed §4 | Medium — verified by reading the mock_run closure lines 76-95; certain to break unless refactored |
| A8 | The Phase 35 STDOUT_BY_CMD pattern at `tests/test_ssh_tools.py:507-525` is the recommended pattern to refactor `test_ssh_discover_success` to | Items CONTEXT.md Missed §4 | Low — already in use elsewhere in the same file; planner can mirror exactly |

## Open Questions (RESOLVED)

> **Status (Phase 38 plan-checker iteration 1):** All four open-question recommendations are materially honored by the plan set. Specifically:
> - Q1 (LC_ALL=C on dpkg probe) → incorporated into Plan 01's probe definition (recommendation accepted).
> - Q2 (update_device_fingerprint_preview ship-or-defer) → DEFERRED per D-11 Option A scoping; the preview wrapper is out of Phase 38 scope, captured for follow-up.
> - Q3 (D-11 adapter strategy) → Option A chosen; Plan 04 implements the dedicated adapter method.
> - Q4 (test file naming) → Extend existing files; Plans 01-06 all extend `tests/test_*.py` rather than creating `tests/test_sitemap_fingerprint.py`.

1. **Should `LC_ALL=C` go into the `dpkg -l` probe command?** (Pitfall 1)
   - What we know: Locale affects sort order; pinning to C is the documented best practice.
   - What's unclear: User didn't specifically address this in CONTEXT.md.
   - Recommendation: Plan adds `LC_ALL=C` and documents the rationale in an inline code comment. Fully Claude's Discretion (D-04 specifies `dpkg -l 2>/dev/null | sort | sha256sum` without locale prefix; adding `LC_ALL=C` is a refinement, not a contradiction).

2. **`update_device_fingerprint_preview` (D-05c) — ship in Phase 38 or follow-up?**
   - What we know: CONTEXT.md says "recommended to ship in Phase 38; planner may defer if scope balloons."
   - What's unclear: Scope size depends on D-11 choice (Option A is heavier).
   - Recommendation: Ship in Phase 38 if D-11 Option A is chosen (the adapter method is doing the work; preview is a thin wrapper). Defer if D-11 Option B is chosen (preview becomes more involved without a dedicated adapter method).

3. **D-11 adapter strategy — Option A (dedicated method) or Option B (piggyback on store_device)?**
   - What we know: CONTEXT.md prefers Option A; both are workable.
   - What's unclear: Plan-checker may reject Option B as a coupling violation if `store_device` becomes overloaded with merge logic.
   - Recommendation: Option A. The merge logic is non-trivial (deep-merge on `capabilities`, overwrite on top-level), it has its own test surface, and it lives cleanly as a separate adapter method. Option B forces test cases for "fingerprint-merge through store_device" which mixes two concerns.

4. **Test file naming — `tests/test_sitemap_fingerprint.py` (new) or extend `tests/test_sitemap.py`?**
   - What we know: CONTEXT.md says "planner picks." The codebase pattern is to extend existing files when the new code is part of the same module/concept.
   - Recommendation: Extend existing files. `tests/test_sitemap.py` for `parse_discovery_output` + dataclass changes; `tests/test_database.py` for adapter method; `tests/test_tools.py` or `tests/test_tool_handlers.py` for handler routing; `tests/test_mcp_prompts.py` for prompt registration. This matches the established "extend, don't create" convention seen in Phase 35.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12+ | Entire codebase | ✓ | matches CLAUDE.md | — |
| `uv` | Build/test/lint | ✓ | matches CLAUDE.md | `pip` works for installs |
| `asyncssh` | New probes | ✓ | already pinned in `pyproject.toml` | — |
| `mcp[cli]` | Tool + prompt registration | ✓ | already pinned | — |
| `psycopg2` | Postgres adapter (optional) | ✓ optional | already pinned | Tests skip if unavailable; SQLite path always works |
| `pytest`, `pytest-asyncio` | Test framework | ✓ | matches CLAUDE.md | — |
| `ruff`, `mypy`, `bandit` | Quality checks | ✓ | matches CLAUDE.md | — |
| Docker | Integration tests in `tests/integration/` | unknown | runs in CI; local optional | Skip integration tests with `-m "not integration"` |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None — all installed.

## Validation Architecture

`workflow.nyquist_validation` is `true` in `.planning/config.json`, so Validation Architecture is required.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 7.x + pytest-asyncio (versions pinned by `uv sync`) [VERIFIED: `tests/test_*.py` use `@pytest.mark.asyncio`, conftest.py imports `asyncio`] |
| Config file | `pyproject.toml` (no separate `pytest.ini` / `conftest.py` at root level for pytest config) [VERIFIED: `Glob("pyproject.toml")`, `Glob("pytest.ini")`] |
| Quick run command | `uv run pytest tests/ -m "not integration" -x` (existing CLAUDE.md command) |
| Full suite command | `uv run pytest` (runs unit + integration; integration only if Docker available) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| DRFT-20 | New `fingerprint` sub-dict in discovery payload after `ssh_discover_system` | unit | `uv run pytest tests/test_ssh_tools.py -k fingerprint -x` | ❌ Wave 0 (new test methods extend existing file) |
| DRFT-20 | `parse_discovery_output` populates `NetworkDevice.fingerprint` from `data["fingerprint"]` | unit | `uv run pytest tests/test_sitemap.py -k fingerprint -x` | ❌ Wave 0 (new test methods extend existing file) |
| DRFT-20 | SQLite `ALTER TABLE ADD COLUMN fingerprint TEXT` migration is idempotent + non-destructive | unit | `uv run pytest tests/test_migration.py -k fingerprint -x` | ❌ Wave 0 |
| DRFT-20 | SQLite `store_device` round-trips `fingerprint` (UPDATE + INSERT branches) | unit | `uv run pytest tests/test_database.py -k fingerprint -x` | ❌ Wave 0 |
| DRFT-20 | Postgres `store_device` lands `fingerprint` inside `system_info` JSONB | integration (psycopg2 mocked or live) | `uv run pytest tests/test_database.py -k "postgres and fingerprint" -x` | ❌ Wave 0 |
| DRFT-20 | Postgres `get_all_devices` flattens `fingerprint` to top-level key | unit | `uv run pytest tests/test_database.py -k "postgres and flatten" -x` | ❌ Wave 0 |
| DRFT-20 | `update_device_fingerprint` adapter method does deep-merge on `capabilities` | unit | `uv run pytest tests/test_database.py -k update_device_fingerprint -x` | ❌ Wave 0 |
| DRFT-20 | `update_device_fingerprint` adapter method overwrites top-level keys (kernel, os) | unit | `uv run pytest tests/test_database.py -k update_device_fingerprint_overwrite -x` | ❌ Wave 0 |
| DRFT-20 | `update_device_fingerprint` MCP tool routes through `execute_tool` and merges via adapter | unit | `uv run pytest tests/test_tools.py -k update_device_fingerprint -x` | ❌ Wave 0 |
| DRFT-20 | `update_device_fingerprint` filters unknown top-level keys (D-05b in handler) | unit | `uv run pytest tests/test_tools.py -k unknown_keys -x` | ❌ Wave 0 |
| DRFT-20 | `update_device_fingerprint` returns structured error on missing hostname (pointer to `discover_and_map`) | unit | `uv run pytest tests/test_tools.py -k missing_hostname -x` | ❌ Wave 0 |
| DRFT-20 | `configure_host_fingerprint` prompt registered, accepts `hostname`, body interpolates correctly | unit | `uv run pytest tests/test_mcp_prompts.py -k configure_host_fingerprint -x` | ❌ Wave 0 |
| DRFT-20 | `update_device_fingerprint` registered in `tool_annotations.py` `_MUTATING_ANNOTATIONS` | unit | `uv run pytest tests/test_tools.py -k annotations -x` (or new test) | ❌ Wave 0 |
| DRFT-20 | `update_device_fingerprint` added to `server.py` `MUTATING_TOOLS` so resource notifications fire | unit | `uv run pytest tests/test_logging_notifications.py -k update_device_fingerprint -x` (existing file pattern) | ❌ Wave 0 |
| SC-4 | New probes inside `ssh_discover_system` are wrapped in `_run_with_timeout` | AST regression (already exists) | `uv run pytest tests/test_ast_regression.py::test_ssh_discover_system_wraps_every_conn_run_phase35 -x` | ✅ EXISTING (line 447) |
| SC-3 | Migration is idempotent (running twice is a no-op; old rows get NULL) | unit | `uv run pytest tests/test_migration.py -k fingerprint_idempotent -x` | ❌ Wave 0 |
| SC-1 / SC-2 | Discovery against a real Debian Docker container populates `fingerprint` sub-dict; before/after re-discovery shows kernel_version field as comparable | integration | `uv run pytest tests/integration/test_sitemap_integration.py -k fingerprint -m integration -v` | ❌ Wave 0 (new integration test extending existing file; the existing Docker harness in `tests/integration/conftest.py` provides an Ubuntu container with SSH on localhost:2222) |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/ -m "not integration" -x` (the standard unit suite — runs in <30 seconds in current 732-test state)
- **Per wave merge:** `uv run pytest` (full suite including integration if Docker available locally; CI always runs both)
- **Phase gate:** Full suite green + `./scripts/quality-check.sh` green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_ssh_tools.py` — refactor brittle `test_ssh_discover_success` (lines 16-152) to use `STDOUT_BY_CMD` lookup pattern (mirror lines 507-525); then add new test methods asserting `fingerprint` sub-dict population and `partial: True` firing on probe miss.
- [ ] `tests/test_sitemap.py` — extend existing `sample_ssh_discovery_success` fixture (line 28) to include a `fingerprint` block; add `test_parse_discovery_output_fingerprint`, `test_store_and_retrieve_fingerprint`.
- [ ] `tests/test_database.py` — extend `TestSQLiteAdapter` and `TestPostgreSQLAdapter` classes with fingerprint round-trip tests + `update_device_fingerprint` adapter method tests (deep-merge, overwrite-on-top-level, missing-hostname error).
- [ ] `tests/test_migration.py` — add migration test for the new ALTER TABLE step (idempotency, NULL on old rows).
- [ ] `tests/test_tools.py` — add MCP tool routing tests for `update_device_fingerprint` (success, missing hostname, malformed dict, unknown top-level key filter).
- [ ] `tests/test_mcp_prompts.py` — add `configure_host_fingerprint` registration test + builder text-content test (mirror `test_connect_to_device_prompt` at line 96).
- [ ] `tests/integration/test_sitemap_integration.py` — extend with a Docker-container discovery test that asserts `fingerprint.kernel_name == "Linux"`, `fingerprint.kernel_version` matches `/proc/version`, `fingerprint.package_fingerprint` is non-null and starts with `sha256:`. The existing `test_container` fixture in `tests/integration/conftest.py:19-78` provides Ubuntu on localhost:2222; the test container is Debian-family so `dpkg -l` will work natively.

*(No new framework install or config-file gap — pytest-asyncio is already installed and conftest is in place.)*

## Project Constraints (from CLAUDE.md)

| Directive | How Phase 38 complies |
|-----------|----------------------|
| Python 3.12+ with strict typing (mypy) | All new code (probes, adapter methods, handlers, prompt builder) needs full type annotations |
| `uv` package manager | No new dependencies; existing `uv sync` covers everything |
| Async-first I/O | All probes use `await _run_with_timeout(...)`; new MCP handlers are `async def`; adapter methods can be sync (DB access is sync today) |
| Type hints required on all functions | Apply to all new code |
| `ruff check` + `ruff format` clean | Run `./scripts/quality-check.sh` per CLAUDE.md before commit |
| `mypy` clean | Apply to all new code |
| `bandit -r src/` clean | New probes execute SSH commands; use `_run_with_timeout` (already audited); avoid string interpolation of user input into shell commands |
| Pytest + pytest-asyncio | Match existing test conventions (`@pytest.mark.asyncio` for async tests, `@pytest.mark.integration` for integration tests) |
| Tools defined in `tools.py` TOOLS dict | **OUTDATED in CLAUDE.md** — actual pattern is split across `tool_schemas/` and `tool_handlers/`. Phase 38 follows the actual current pattern; consider opening a backlog quick-task to update CLAUDE.md if it's stale across other phases too. |
| TestSprite rules: don't run/modify | Phase 38 doesn't touch TestSprite |
| MCP server stdio communication | Unchanged |
| Pre-commit hooks + GitHub Actions CI | Phase 38 must pass both |

## Sources

### Primary (HIGH confidence)
- `src/homelab_mcp/ssh_tools.py` — read end-to-end (693 lines)
- `src/homelab_mcp/sitemap.py` — read end-to-end (519 lines)
- `src/homelab_mcp/database.py` — read end-to-end (858 lines)
- `src/homelab_mcp/migration.py` — read end-to-end (766 lines)
- `src/homelab_mcp/prompt_registry.py` — read end-to-end (209 lines)
- `src/homelab_mcp/tool_annotations.py` — read end-to-end (197 lines)
- `src/homelab_mcp/tool_schemas/network_tools_schema.py` — read end-to-end (102 lines)
- `src/homelab_mcp/tool_schemas/ssh_tools_schema.py` — read (96 lines)
- `src/homelab_mcp/tool_schemas/__init__.py` — read end-to-end (30 lines)
- `src/homelab_mcp/tool_schemas/infrastructure_tools_schema.py` — preview-tool pattern at lines 275-348
- `src/homelab_mcp/tool_handlers/network_handlers.py` — read end-to-end (85 lines)
- `src/homelab_mcp/tool_handlers/__init__.py` — read end-to-end (149 lines)
- `src/homelab_mcp/server.py` — read MUTATING_TOOLS section (lines 165-178), call_tool dispatch (lines 414-458)
- `src/homelab_mcp/resource_readers.py` — read `read_devices_resource` (lines 75-115)
- `src/homelab_mcp/validation.py` — read `validate_hostname` (lines 22-61)
- `src/homelab_mcp/tools.py` — read end-to-end (42-line router)
- `tests/test_ast_regression.py` — read Phase 35 D-15 guard (lines 380-503)
- `tests/test_ssh_tools.py` — read structure (lines 1-200, 460-686)
- `tests/test_sitemap.py` — read structure (lines 20-150)
- `tests/test_database.py` — read structure (lines 1-100)
- `tests/test_mcp_prompts.py` — read end-to-end (221 lines)
- `tests/integration/conftest.py` — read end-to-end (111 lines)
- `tests/integration/test_sitemap_integration.py` — read header section (lines 1-120)
- `tests/integration/test_ssh_integration.py` — read end-to-end (60 lines)
- `.planning/phases/38-sitemap-fingerprint-schema/38-CONTEXT.md` — read end-to-end (348 lines)
- `.planning/phases/38-sitemap-fingerprint-schema/38-DISCUSSION-LOG.md` — read tail decisions
- `.planning/REQUIREMENTS.md` — read end-to-end (146 lines)
- `.planning/ROADMAP.md` — read Phase 38 § (lines 144-153)
- `.planning/STATE.md` — read top section (lines 1-120)
- `CLAUDE.md` — instructions in initial context

### Secondary (MEDIUM confidence)
- [reproducible-builds.org docs](https://reproducible-builds.org/docs/stable-outputs/) — locale-pinning for dpkg machine parsing
- [systemd os-release manpage](https://www.freedesktop.org/software/systemd/man/os-release.html) — VERSION_ID is the recommended machine-parseable version field
- [PostgreSQL JSONB functions](https://www.postgresql.org/docs/current/functions-json.html) — `||` is shallow merge, not deep merge
- [dpkg-query manpage](https://manpages.debian.org/unstable/dpkg/dpkg-query.1.en.html) — `-W --show` for installed-only listing

### Tertiary (LOW confidence)
None — all critical claims either verified against the live codebase or cited from authoritative sources.

## Metadata

**Confidence breakdown:**
- File reference verification: HIGH — read every file CONTEXT.md cited and verified line numbers
- Pattern identification (closest existing analogs): HIGH — patterns already established by Phases 14, 15, 33, 35
- Pitfall identification: HIGH for dpkg locale (cited reproducible-builds.org), MEDIUM for /etc/os-release quoting (verified against current Debian/Proxmox real-world output but no comprehensive cross-distro audit), HIGH for Postgres JSONB merge (verified against existing `database.py:629` pattern)
- Items CONTEXT.md missed (tool_annotations, MUTATING_TOOLS, brittle test mock): HIGH — verified by direct file reads
- Validation Architecture: HIGH — every test path maps to an existing file, every command runs against existing infrastructure

**Research date:** 2026-04-25
**Valid until:** 2026-05-25 (30 days for stable feature work; codebase Phase 35-37 patterns are locked)

## RESEARCH COMPLETE
