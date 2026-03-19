# Phase 27: Update Tests to Cover All Tool Parameters - Research

**Researched:** 2026-03-19
**Domain:** pytest unit testing, schema validation, handler parameter wiring
**Confidence:** HIGH

## Summary

Phase 26 fixed schema-to-function mismatches across all tool categories — removing phantom parameters, adding missing ones, and aligning defaults. Phase 27's job is to write tests that prove those parameters flow correctly from MCP schema declaration through to the underlying function call. Without these tests, future schema edits can silently break parameter wiring again (which is exactly how the Phase 26 bugs accumulated in the first place).

The test gap is narrow but specific: handler-layer wiring tests for the 7 parameters newly added to Proxmox creation tools (`sockets`, `cdrom`, `net0`, `ostype`, `swap`, `ssh_public_keys`, `unprivileged`), schema presence tests for those same parameters, and regression guards on the SSH schema parameters that were aligned in Phase 26 (`timeout` on `setup_mcp_admin`/`verify_mcp_admin`, no-timeout on `ssh_execute_command`, `force_update_key`, `key_path`). A broader structural audit is also needed to identify any remaining gaps across all 57 tools.

Existing test infrastructure is solid: 668 passing unit tests, pytest with pytest-asyncio, and a well-established pattern for handler wiring tests (see `TestHandlerSessionThreading` in `test_proxmox_api.py`). No new frameworks, libraries, or architectural changes are needed.

**Primary recommendation:** Write schema property existence tests and handler wiring tests for all parameters that were added or fixed in Phase 26. Then run a programmatic audit to confirm all schema properties for all 57 tools have at least one test referencing them.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | current (pyproject) | test runner | project standard |
| pytest-asyncio | current | async test support | required for handler tests |
| pytest-mock | current | mock/patch helpers | used throughout test suite |
| unittest.mock | stdlib | patch, MagicMock, AsyncMock | established in all test files |

### No New Dependencies
No new packages needed. All testing infrastructure already exists.

**Version verification:** All packages pinned in `uv.lock`. Run `uv run pytest` for execution.

## Architecture Patterns

### Existing Test Structure
```
tests/
├── test_tools.py          # Schema presence and execute_tool integration tests
├── test_proxmox_api.py    # Proxmox API function + handler wiring tests
├── test_ssh_tools.py      # SSH function tests (function-level)
└── ...
```

### Pattern 1: Schema Property Presence Test
**What:** Assert a specific property key exists in a tool's inputSchema properties dict, and verify its default value if applicable.
**When to use:** Every schema property that was added or changed in Phase 26.
**Example:**
```python
def test_create_proxmox_vm_schema_exposes_phase26_parameters():
    """create_proxmox_vm schema must expose sockets, cdrom, net0, ostype (Phase 26-03)."""
    tools = get_available_tools()
    schema = tools["create_proxmox_vm"]["inputSchema"]["properties"]
    assert "sockets" in schema
    assert schema["sockets"]["default"] == 1
    assert "cdrom" in schema
    assert "net0" in schema
    assert schema["net0"]["default"] == "virtio,bridge=vmbr0"
    assert "ostype" in schema
    assert schema["ostype"]["default"] == "l26"
```

### Pattern 2: Handler Wiring Test (established in TestHandlerSessionThreading)
**What:** Patch the underlying API function and assert the handler calls it with the expected kwargs when specific schema arguments are supplied.
**When to use:** Every optional parameter that has a default — test both default path and explicit override.
**Example:**
```python
@pytest.mark.asyncio
async def test_handle_create_proxmox_vm_passes_sockets(self):
    """handle_create_proxmox_vm passes sockets from arguments to create_proxmox_vm."""
    import src.homelab_mcp.tool_handlers.proxmox_handlers as _ph_mod
    from src.homelab_mcp.tool_handlers.proxmox_handlers import handle_create_proxmox_vm

    mock_rm = MagicMock()
    mock_rm.proxmox_session = MagicMock()
    mock_fn = AsyncMock(return_value={"status": "success", "node": "pve", "vmid": 100, "message": "created"})

    with (
        patch("src.homelab_mcp.server.get_resource_manager", return_value=mock_rm),
        patch.object(_ph_mod, "create_proxmox_vm", mock_fn),
        patch.object(_ph_mod, "update_baseline_after_mutation", AsyncMock()),
    ):
        await handle_create_proxmox_vm({"node": "pve", "vmid": 100, "name": "vm", "sockets": 2})

    call_kwargs = mock_fn.call_args.kwargs
    assert call_kwargs.get("sockets") == 2
```

### Pattern 3: Default Value Wiring Test
**What:** Call handler with minimal arguments (no optional params) and verify the underlying function receives the correct default value.
**When to use:** For each parameter that has an explicit default in the handler's `arguments.get(param, default)` call.

### Pattern 4: Comprehensive Schema Audit Function
**What:** A single parametrized test or audit function that iterates all 57 tools and verifies every property in the schema has a corresponding key (prevents future phantom/missing parameter bugs).
**When to use:** As a regression guard, not a per-parameter test.

### Anti-Patterns to Avoid
- **Testing only happy-path execution:** Schema tests must also check defaults match expectations, not just presence.
- **Testing at the wrong layer:** `test_proxmox_api.py` already covers `create_proxmox_vm` function behavior — Phase 27 tests go in handler wiring layer.
- **Over-testing stable code:** Tools like `get_network_sitemap` (no parameters) don't need new tests.
- **Reimplementing schema with hardcoded expected values:** Import schema constants from the tool schema modules rather than hardcoding strings.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Schema validation | Custom JSON Schema validator | Direct dict key assertions | Already established pattern in test_tools.py |
| Mock session injection | Custom fixture | patch + MagicMock | TestHandlerSessionThreading pattern works |
| Async handler execution | Sync wrapper | @pytest.mark.asyncio | Already in use throughout |

## Common Pitfalls

### Pitfall 1: Testing Function Behavior Instead of Wiring
**What goes wrong:** Writing tests that verify what `create_proxmox_vm` does with `sockets=2`, when `test_proxmox_api.py` already has that coverage.
**Why it happens:** Confusing "test the function" with "test the handler passes the parameter through."
**How to avoid:** Handler wiring tests mock the underlying function and assert it was called with the right kwargs — they don't run the real function.
**Warning signs:** Test needs `aioresponses` or HTTP mocking — that means you're testing the API function, not the handler wiring.

### Pitfall 2: Missing the `update_baseline_after_mutation` Patch
**What goes wrong:** `handle_create_proxmox_vm` and `handle_create_proxmox_lxc` call `update_baseline_after_mutation` after success. Without patching it, the handler test fails because `get_resource_manager` isn't properly set up.
**Why it happens:** The baseline update call is easy to miss when reading the handler.
**How to avoid:** Patch `update_baseline_after_mutation` alongside the main API function in any handler wiring test for `create_proxmox_vm` and `create_proxmox_lxc`.

### Pitfall 3: Wrong Dict Key for `ssh_public_keys`
**What goes wrong:** The schema parameter is named `ssh_public_keys` but the Proxmox API sends it as `ssh-public-keys` (hyphenated). The handler translates between the two. Test the handler extracts `ssh_public_keys` from arguments — not the API payload key.
**Why it happens:** The translation happens inside `create_proxmox_lxc` (proxmox_api.py), not in the handler.
**How to avoid:** In handler wiring tests, assert `create_proxmox_lxc` was called with `ssh_public_keys=...` (underscore), not `ssh-public-keys`.

### Pitfall 4: `cdrom` Parameter is `None` by Default
**What goes wrong:** Testing that `cdrom` is passed when not provided — it defaults to `None` and is correctly omitted from the API payload.
**Why it happens:** The handler calls `arguments.get("cdrom")` with no default (returns `None`). `create_proxmox_vm` only adds `cdrom` to the payload when it's not `None`.
**How to avoid:** Test two cases: (1) no `cdrom` argument → verify `create_proxmox_vm` receives `cdrom=None`, (2) `cdrom` provided → verify it's passed through.

### Pitfall 5: Schema Default vs Handler Default Mismatch
**What goes wrong:** Schema says `"default": 512` for `swap`, handler uses `arguments.get("swap", 512)`. If someone changes one but not the other, they silently diverge.
**Why it happens:** Two separate sources of truth.
**How to avoid:** Write a test that asserts the schema default equals what the handler uses when no argument is supplied. This is what the handler wiring test with minimal args accomplishes.

## Code Examples

Verified patterns from existing tests:

### Handler Wiring Test Setup (from TestHandlerSessionThreading)
```python
# Source: tests/test_proxmox_api.py lines 1547-1576
import src.homelab_mcp.tool_handlers.proxmox_handlers as _ph_mod
from src.homelab_mcp.tool_handlers.proxmox_handlers import handle_list_proxmox_resources

mock_rm = MagicMock()
mock_session = MagicMock()
mock_rm.proxmox_session = mock_session
mock_list = AsyncMock(return_value={"status": "success", "resources": [], "total": 0})

with (
    patch("src.homelab_mcp.server.get_resource_manager", return_value=mock_rm),
    patch.object(_ph_mod, "list_proxmox_resources", mock_list),
):
    await handle_list_proxmox_resources({})

call_kwargs = mock_list.call_args
assert call_kwargs.kwargs.get("session") is mock_session
```

### Schema Property Test (from test_tools.py)
```python
# Source: tests/test_tools.py line 285-316
def test_sitemap_tool_schemas():
    tools = get_available_tools()
    discover_tool = tools["discover_and_map"]
    assert "hostname" in discover_tool["inputSchema"]["properties"]
    assert "username" in discover_tool["inputSchema"]["properties"]
    assert discover_tool["inputSchema"]["required"] == ["hostname"]
    assert discover_tool["inputSchema"]["properties"]["username"].get("default") == "mcp_admin"
```

### Audit Guard Test (from test_tools.py)
```python
# Source: tests/test_tools.py lines 763-777
def test_no_tool_has_password_required():
    tools = get_available_tools()
    for tool_name, tool_def in tools.items():
        schema = tool_def.get("inputSchema", {})
        required = schema.get("required", [])
        assert "password" not in required, f"Tool '{tool_name}' has 'password' in required"
```

## Parameter Coverage Audit: What Exists vs. What's Missing

### Parameters Added/Fixed in Phase 26 — Test Coverage Status

#### Phase 26-01: Service Tool Port Removal
| Parameter | Schema | Function | Handler Test | Schema Test |
|-----------|--------|----------|-------------|------------|
| `port` removed from service tools | Done | Done | No explicit test needed (removal) | test_tools.py line 31 (verified via Phase 26 verification) |

**Gap:** No regression test that verifies `port` is NOT in any service tool schema. Adding one would prevent re-introduction.

#### Phase 26-02: SSH Schema Alignment
| Parameter | Schema | Function | Handler Test Exists? | Schema Test Exists? |
|-----------|--------|----------|---------------------|---------------------|
| `setup_mcp_admin` `timeout` | ssh_tools_schema.py | ssh_tools.py:246 | No | No |
| `setup_mcp_admin` `force_update_key` | ssh_tools_schema.py | ssh_tools.py | test_ssh_tools.py:604 (function-level) | No schema test |
| `verify_mcp_admin` `timeout` | ssh_tools_schema.py | ssh_tools.py:454 | No | No |
| `ssh_execute_command` no `timeout` | ssh_tools_schema.py | ssh_tools.py | No | No explicit "not in schema" test |
| `discover_and_map` `username` default `mcp_admin` | network_tools_schema.py | sitemap.py:315 | No handler test | test_tools.py:296 EXISTS |
| `update_mcp_admin_groups` `key_path` | ssh_tools_schema.py | ssh_tools.py | No | No schema test |

#### Phase 26-03: Proxmox Schema Gap Closure
| Parameter | Handler Extracts? | Handler Test Exists? | Schema Test Exists? |
|-----------|------------------|---------------------|---------------------|
| `create_proxmox_vm` `sockets` | Yes (proxmox_handlers.py:170) | No handler wiring test | No |
| `create_proxmox_vm` `cdrom` | Yes | No | No |
| `create_proxmox_vm` `net0` | Yes | No | No |
| `create_proxmox_vm` `ostype` | Yes | No | No |
| `create_proxmox_lxc` `swap` | Yes | No | No |
| `create_proxmox_lxc` `ssh_public_keys` | Yes | No | No |
| `create_proxmox_lxc` `unprivileged` | Yes | No | No |

Note: `test_proxmox_api.py` has API-function-level tests for `swap`, `ssh_public_keys`, `unprivileged` — but NO handler wiring tests proving the handler extracts and passes these from the arguments dict.

### Full Schema Audit — Properties With No Tests
The following tool properties appear to have no property-level test in any test file:

**SSH tools:**
- `ssh_discover`: `key_path`, `port`
- `setup_mcp_admin`: `timeout`, `force_update_key`, `port`
- `verify_mcp_admin`: `timeout`, `port`
- `ssh_execute_command`: `port`, `sudo`
- `start_interactive_shell`: `username`, `password`, `port`, `initial_command`
- `update_mcp_admin_groups`: `key_path`, `port`

**Proxmox tools (newly added in Phase 26-03):**
- `create_proxmox_vm`: `sockets`, `cdrom`, `net0`, `ostype`
- `create_proxmox_lxc`: `swap`, `ssh_public_keys`, `unprivileged`

**Credential tools:**
- `register_server`: `key_path`, `port`, `display_name`, `verify_connection`, `username`
- `list_registered_servers`: `active_only`
- `update_server_credentials`: all properties (no schema test exists)
- `remove_server`: `credential_id`, `hostname`, `dry_run`

## Recommended Test Scope for Phase 27

Phase 27 should focus on the highest-value gaps — parameters that were recently changed and those that wire through to business logic:

**Priority 1 (Phase 26 regressions — must test):**
1. `create_proxmox_vm` schema: `sockets`, `cdrom`, `net0`, `ostype` present with correct defaults
2. `create_proxmox_lxc` schema: `swap`, `ssh_public_keys`, `unprivileged` present with correct defaults
3. `handle_create_proxmox_vm` wiring: `sockets`, `cdrom`, `net0`, `ostype` passed through from arguments
4. `handle_create_proxmox_lxc` wiring: `swap`, `ssh_public_keys`, `unprivileged` passed through from arguments
5. `setup_mcp_admin` schema: `timeout` property present with default 90
6. `verify_mcp_admin` schema: `timeout` property present with default 30
7. `ssh_execute_command` schema: `timeout` NOT in properties (regression guard for Phase 26-02)
8. Service tools: `port` NOT in any service tool schema (regression guard for Phase 26-01)

**Priority 2 (broader coverage):**
9. `update_mcp_admin_groups` schema: `key_path` present
10. `start_interactive_shell` schema: `initial_command` property present

**Priority 3 (existing pattern extension):**
11. A programmatic audit test that collects all tool names and verifies each property key is a string (smoke test for schema structural integrity)

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest tests/test_tools.py tests/test_proxmox_api.py -x -q` |
| Full suite command | `uv run pytest tests/ -m "not integration" -x -q` |

### Phase Requirements → Test Map

No formal requirement IDs exist for Phase 27 yet. The natural requirements are:

| Behavior | Test Type | Automated Command |
|----------|-----------|-------------------|
| `create_proxmox_vm` schema has `sockets/cdrom/net0/ostype` | schema | `uv run pytest tests/test_tools.py -k proxmox -x` |
| `create_proxmox_lxc` schema has `swap/ssh_public_keys/unprivileged` | schema | same |
| `handle_create_proxmox_vm` passes `sockets` through | handler wiring | `uv run pytest tests/test_proxmox_api.py -k create_vm -x` |
| `handle_create_proxmox_lxc` passes `swap/ssh_public_keys/unprivileged` through | handler wiring | `uv run pytest tests/test_proxmox_api.py -k create_lxc -x` |
| `setup_mcp_admin` schema has `timeout=90` | schema | `uv run pytest tests/test_tools.py -k setup_mcp_admin -x` |
| `verify_mcp_admin` schema has `timeout=30` | schema | `uv run pytest tests/test_tools.py -k verify_mcp_admin -x` |
| `ssh_execute_command` schema has no `timeout` | schema (negative) | `uv run pytest tests/test_tools.py -k ssh_execute -x` |
| No service tool has `port` property | schema (negative audit) | `uv run pytest tests/test_tools.py -k service_schema -x` |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_tools.py tests/test_proxmox_api.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -m "not integration" -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
None — existing test infrastructure (pytest, pytest-asyncio, unittest.mock) covers all needs. No new test files required; new tests go in existing files:
- Schema tests → `tests/test_tools.py` (existing file, follows established pattern)
- Handler wiring tests → `tests/test_proxmox_api.py` `TestHandlerSessionThreading` class (existing class, established pattern)

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual inspection for schema-function alignment | Schema tests as regression guards | Phase 27 establishes | Future schema edits that break wiring fail in CI |
| No handler wiring tests for optional parameters | Handler wiring tests for all non-trivial optional params | Phase 27 establishes | Catches arguments.get() default mismatches |

## Open Questions

1. **Should Phase 27 add a parametrized test scanning ALL 57 tool schemas?**
   - What we know: Such a test would catch any future schema-function mismatches structurally
   - What's unclear: Whether it's worth the parametrization complexity vs. targeted tests
   - Recommendation: Add a lightweight structural audit (all tools have `description` and `inputSchema`) but keep per-parameter assertions targeted to the Phase 26 changes

2. **Should we test handler wiring for SSH tool parameters (force_update_key, port, etc.)?**
   - What we know: SSH handlers use `**arguments` pass-through — so any schema param automatically reaches the underlying function
   - What's unclear: Whether the `**arguments` pattern gives enough coverage on its own
   - Recommendation: For `**arguments` handlers, schema presence test is sufficient; no handler wiring test needed because there's no `.get()` extraction to get wrong. Focus handler wiring tests on Proxmox handlers where extraction is explicit.

## Sources

### Primary (HIGH confidence)
- Direct code inspection: `src/homelab_mcp/tool_schemas/*.py` — all 8 schema files read in full
- Direct code inspection: `src/homelab_mcp/tool_handlers/*.py` — all handler files read
- Direct test inspection: `tests/test_tools.py`, `tests/test_proxmox_api.py` — full coverage audit
- Phase 26 verification report: `.planning/phases/26-sync-tool-schema-file-to-match-current-tool-parameters/26-VERIFICATION.md`

### Secondary (MEDIUM confidence)
- `uv run pytest tests/ -m "not integration" -q` baseline: 668 passed, 7 skipped

## Metadata

**Confidence breakdown:**
- Parameter gaps identified: HIGH — direct code inspection, cross-referenced with test files
- Test patterns: HIGH — patterns copied from existing working tests
- Scope recommendation: HIGH — follows direct chain from Phase 26 summary and verification report

**Research date:** 2026-03-19
**Valid until:** 60 days — test infrastructure is stable, no fast-moving dependencies
