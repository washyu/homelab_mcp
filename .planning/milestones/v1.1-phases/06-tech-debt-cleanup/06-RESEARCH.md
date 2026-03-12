# Phase 6: Tech Debt Cleanup - Research

**Researched:** 2026-03-11
**Domain:** Python async session management, ASGI authentication middleware, structured error handling
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DEBT-01 | ResourceManager.proxmox_session is consumed by handler chain when Proxmox operations are invoked | Session threading analysis: proxmox_handlers.py calls module-level functions that call `get_proxmox_client()` without a session — the shared session is never threaded in. Fix path identified. |
| DEBT-02 | API key authentication is enforced on HTTP transport endpoints | Auth analysis: `create_http_app()` in http_app.py omits `APIKeyAuth` middleware entirely. `APIKeyAuth` exists and works in the deprecated http_transport.py — it just was never wired into the new app. Fix path is a one-function change. |
| DEBT-03 | vm_providers error paths return structured error dicts instead of raw str(e) strings | Code audit: `_format_error()` in base.py correctly structures errors, but `list_vms` fallback paths in docker_provider.py and lxd_provider.py return `{"error": str(e)}` without `error_type` or `detail`. Pattern is consistent and correctable. |

</phase_requirements>

---

## Summary

This phase fixes three discrete v1.0 bugs. None requires new libraries, schema migrations, or new abstractions — each is a targeted repair of existing code. The bugs are independent of each other and can be implemented in any order (or in parallel waves).

**DEBT-01** is the highest-priority fix because the STATE.md notes it as a load-bearing prerequisite for Phases 9 and 11. The `ResourceManager` creates a shared `aiohttp.ClientSession` at startup, but `proxmox_handlers.py` calls bare module-level functions (e.g. `list_proxmox_resources()`, `get_proxmox_node_status()`) that internally call `get_proxmox_client()` with no `session=` argument. The client's `request()` method has a branch that falls back to creating a new per-request `aiohttp.ClientSession` — so every Proxmox tool call silently opens and closes a fresh session. The fix requires `get_resource_manager().proxmox_session` to flow down into every Proxmox handler call.

**DEBT-02** is a missing middleware wiring. `auth.py` contains a fully functional `APIKeyAuth` ASGI middleware class. The deprecated `http_transport.py` wired it correctly. The new `http_app.py` (which replaced it) never applied `APIKeyAuth`, so HTTP transport endpoints accept all requests. The fix adds the middleware wrap inside `create_http_app()`.

**DEBT-03** is an error format inconsistency in `vm_providers`. `VMProvider.base._format_error()` returns `{"status": "error", "operation": ..., "vm_name": ..., "error": ...}` — which lacks `error_type` and `detail` as required by the success criteria. Additionally, `DockerProvider.list_vms()` and `LXDProvider.list_vms()` have bare exception handlers that return `{"status": "error", "platform": ..., "error": str(e)}` directly, bypassing `_format_error()` entirely. The fix upgrades `_format_error()` in `base.py` to include `error_type` and `detail`, then either fixes the bypassing callsites or ensures they route through the updated helper.

**Primary recommendation:** Fix DEBT-01 first (session threading), then DEBT-02 (auth wiring), then DEBT-03 (error format). All three are small, surgical changes with well-defined test surfaces.

---

## Standard Stack

### Core (already present — no new dependencies)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| aiohttp | installed | Shared ClientSession management | Already used; ResourceManager owns its lifecycle |
| starlette | installed | ASGI middleware chain | APIKeyAuth already implemented as Starlette ASGI middleware |
| mcp (lowlevel SDK) | installed | Server lifespan / request context | `get_resource_manager()` accesses the lifespan-bound RM |
| pytest + pytest-asyncio | installed | Unit test execution | Project standard |

No new packages required for this phase.

---

## Architecture Patterns

### Pattern 1: Threading session through handler chain (DEBT-01)

**What:** Proxmox handler functions in `proxmox_handlers.py` call module-level functions in `proxmox_api.py`. Those functions currently call `get_proxmox_client()` with no `session=` argument. Adding `session=get_resource_manager().proxmox_session` at the handler call-sites threads the shared session all the way down.

**Chain:**
```
proxmox_handlers.handle_list_proxmox_resources()
  -> list_proxmox_resources(session=get_resource_manager().proxmox_session)  # add session arg
    -> get_proxmox_client(session=session)
      -> ProxmoxAPIClient(session=session)
        -> request() -> _do_request(self._shared_session, ...)  # already correct
```

**All affected module-level functions in proxmox_api.py:**
- `list_proxmox_resources(host, resource_type)` — needs `session` param
- `get_proxmox_node_status(node, host)` — needs `session` param
- `get_proxmox_vm_status(node, vmid, host, vm_type)` — needs `session` param
- `manage_proxmox_vm(node, vmid, action, host, vm_type)` — needs `session` param
- `create_proxmox_lxc(...)` — needs `session` param
- `create_proxmox_vm(...)` — needs `session` param
- `clone_proxmox_vm(...)` — needs `session` param
- `delete_proxmox_vm(...)` — needs `session` param (also calls `manage_proxmox_vm` internally)

**Import required in proxmox_handlers.py:**
```python
from ..server import get_resource_manager
```

**Example fix for one function (others follow same pattern):**
```python
# proxmox_api.py — add session param
async def list_proxmox_resources(
    host: str | None = None,
    resource_type: str | None = None,
    session: aiohttp.ClientSession | None = None,
) -> dict[str, Any]:
    client = get_proxmox_client(host=host, session=session)
    ...

# proxmox_handlers.py — pass session from ResourceManager
async def handle_list_proxmox_resources(arguments: dict[str, Any]) -> dict[str, Any]:
    if host := arguments.get("host"):
        validate_hostname(host)
    result = await list_proxmox_resources(
        host=arguments.get("host"),
        resource_type=arguments.get("resource_type"),
        session=get_resource_manager().proxmox_session,
    )
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
```

**Important edge case in delete_proxmox_vm:** It calls `manage_proxmox_vm()` internally without passing a session. That internal call must also pass the session:
```python
# Inside delete_proxmox_vm, the internal manage call:
await manage_proxmox_vm(node, vmid, "stop", host, vm_type, session=session)
```

### Pattern 2: Wiring APIKeyAuth into create_http_app (DEBT-02)

**What:** `APIKeyAuth` is an ASGI middleware that wraps any ASGI app. `create_http_app()` builds a `Starlette` instance and returns it. The fix wraps the return value with `APIKeyAuth` conditionally based on whether `MCP_API_KEY` is configured.

**Existing APIKeyAuth behavior (from auth.py):**
- Checks `Authorization: Bearer <key>` header
- Excludes `/health` and `/` paths by default
- Returns 401 for missing/invalid key, 500 if no key configured
- Shell paths (`/shell/`, `/ws/shell/`) also need exclusion (same pattern as deprecated transport)

**Key design decision for exclusion paths:** The deprecated `http_transport.py` excluded `["/health", "/", "/shell/", "/ws/shell/"]`. The new app should exclude the same set. The trailing-slash check in `APIKeyAuth.__call__` uses `path.startswith(exclude_path)` for paths ending with `/`.

```python
# At the bottom of create_http_app(), before the return:
api_key = os.getenv("MCP_API_KEY")
if api_key:
    from .auth import APIKeyAuth
    return APIKeyAuth(
        starlette_app,
        api_key=api_key,
        enabled=True,
        exclude_paths=["/health", "/", "/shell/", "/ws/shell/"],
    )
return starlette_app
```

**Note:** The `create_http_app` return type annotation must change from `Starlette` to `Starlette | APIKeyAuth`. This is consistent with how `http_transport.py` typed it.

### Pattern 3: Structured error dict in vm_providers (DEBT-03)

**What:** The success criteria requires all error paths to return dicts with `error`, `error_type`, and `detail` fields. The existing `_format_error()` in `base.py` only has `error`. The three-field standard must be codified in `_format_error()` and all callsites using bare `{"error": str(e)}` must be updated.

**Required error dict structure:**
```python
{
    "status": "error",
    "operation": operation,   # e.g. "list_vms", "deploy"
    "vm_name": vm_name,        # empty string "" where not applicable
    "error": str(error),       # short human-readable message
    "error_type": type(error).__name__,  # e.g. "TimeoutError", "ValueError", "Exception"
    "detail": repr(error),     # full detail including args
}
```

**Updated `_format_error` in base.py:**
```python
def _format_error(
    self, operation: str, vm_name: str, error: str | Exception
) -> dict[str, Any]:
    """Format error response with structured fields."""
    if isinstance(error, Exception):
        return {
            "status": "error",
            "operation": operation,
            "vm_name": vm_name,
            "error": str(error),
            "error_type": type(error).__name__,
            "detail": repr(error),
        }
    # error is already a string (legacy callers)
    return {
        "status": "error",
        "operation": operation,
        "vm_name": vm_name,
        "error": error,
        "error_type": "Error",
        "detail": error,
    }
```

**Callsites that bypass _format_error and return raw str(e) (require separate fixes):**

In `docker_provider.py`:
```python
# list_vms() — line ~207
except Exception as e:
    return {"status": "error", "platform": "docker", "error": str(e)}
```

In `lxd_provider.py`:
```python
# list_vms() — line ~209
except Exception as e:
    return {"status": "error", "platform": "lxd", "error": str(e)}
```

These `list_vms` paths use `platform` instead of `vm_name` (there's no single VM). The fix should add `error_type` and `detail` fields to align with the contract, while keeping `platform`:
```python
except Exception as e:
    return {
        "status": "error",
        "platform": "docker",
        "error": str(e),
        "error_type": type(e).__name__,
        "detail": repr(e),
    }
```

### Anti-Patterns to Avoid

- **Adding session as a global variable:** Don't stash the session in a module-level global in `proxmox_api.py`. Use `get_resource_manager()` in the handler layer, pass it down as a parameter.
- **Creating a new ClientSession inside individual handler functions:** Defeats the purpose of ResourceManager connection pooling.
- **Making APIKeyAuth mandatory when MCP_API_KEY is absent:** The existing `APIKeyAuth` already handles this (returns 500 with misconfiguration message), but the wiring should only wrap when a key is actually set — otherwise stdio-only deployments without an API key configured are not blocked.
- **Changing the error dict shape in ways that break existing consumers:** `_format_error()` callers that pass string `error` args (not exceptions) exist in the codebase — the updated function must remain compatible with string inputs.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| ASGI auth middleware | Custom request interception | `APIKeyAuth` already in auth.py | Already implemented, tested, uses `secrets.compare_digest` |
| Session access in handlers | New session singleton | `get_resource_manager().proxmox_session` | Already wired through server lifespan |
| Error type introspection | Custom exception hierarchy | `type(e).__name__` + `repr(e)` | Standard Python, no extra deps |

---

## Common Pitfalls

### Pitfall 1: Forgetting the internal manage_proxmox_vm call in delete_proxmox_vm
**What goes wrong:** `delete_proxmox_vm()` calls `manage_proxmox_vm()` internally to stop the VM before deletion. If the outer function receives a `session` but doesn't pass it to this inner call, one per-request session gets created just for the stop step.
**Why it happens:** Internal function calls are easy to miss when adding a new parameter.
**How to avoid:** Search for all calls to `manage_proxmox_vm` within `proxmox_api.py` itself and update them.
**Warning signs:** Test for DEBT-01 passes for most Proxmox ops but delete still creates extra sessions.

### Pitfall 2: create_http_app return type annotation mismatch
**What goes wrong:** If `create_http_app` is annotated to return `Starlette` but conditionally returns `APIKeyAuth`, mypy will fail.
**Why it happens:** `APIKeyAuth` is a plain ASGI class, not a Starlette subclass.
**How to avoid:** Update the return annotation to `Starlette | APIKeyAuth` and the `from __future__ import annotations` import already handles forward references.
**Warning signs:** `uv run mypy src/` reports a return type incompatibility.

### Pitfall 3: error_type field reveals sensitive exception internals
**What goes wrong:** `repr(e)` on some exceptions includes connection strings, passwords, or hostnames in the detail field.
**Why it happens:** Python exception `repr` includes all args verbatim.
**How to avoid:** The project already has `sanitize_error()` in `log_filter.py`. Use it for the `detail` field: `"detail": sanitize_error(e)`.
**Warning signs:** Bandit scan flags string interpolation of exceptions in error responses.

### Pitfall 4: APIKeyAuth path exclusion with Mount prefix
**What goes wrong:** The MCP endpoint is mounted at `/mcp` via `Mount("/mcp", ...)`, which means request paths seen by middleware include `/mcp`, `/mcp/`, etc. The `/mcp` path must NOT be in the exclude list.
**Why it happens:** It's tempting to exclude `/mcp` during development to avoid constant auth headers.
**How to avoid:** Only exclude `/health`, `/`, `/shell/`, `/ws/shell/` — the same set used in the deprecated transport.
**Warning signs:** DEBT-02 test passes for curl but MCP clients skip auth.

### Pitfall 5: ResourceManager not initialized when handler runs in test
**What goes wrong:** Unit tests for DEBT-01 that call `get_resource_manager()` will raise `RuntimeError` because no lifespan has been started.
**Why it happens:** `_resource_manager` is `None` outside of server lifespan.
**How to avoid:** Mock `get_resource_manager()` in unit tests: `patch("homelab_mcp.tool_handlers.proxmox_handlers.get_resource_manager")`.
**Warning signs:** Tests raise `RuntimeError: ResourceManager not available`.

---

## Code Examples

### Verifying session is used (test pattern for DEBT-01)
```python
# Source: pattern from existing test_proxmox_api.py
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_handler_uses_shared_session():
    """DEBT-01: Proxmox handler must pass shared session to client."""
    mock_session = AsyncMock()
    mock_rm = MagicMock()
    mock_rm.proxmox_session = mock_session

    with patch("homelab_mcp.tool_handlers.proxmox_handlers.get_resource_manager", return_value=mock_rm):
        with patch("homelab_mcp.proxmox_api.ProxmoxAPIClient.request") as mock_req:
            mock_req.return_value = []
            await handle_list_proxmox_resources({"resource_type": "vm"})
            # Verify the client was constructed with our shared session
            # (inspect ProxmoxAPIClient._shared_session)
```

### APIKeyAuth wiring test pattern for DEBT-02
```python
# Source: pattern from existing test_http_transport.py
from starlette.testclient import TestClient
from homelab_mcp.http_app import create_http_app

def test_mcp_endpoint_requires_api_key(monkeypatch):
    """DEBT-02: POST /mcp without auth header must return 401."""
    monkeypatch.setenv("MCP_API_KEY", "test-secret-key-32chars-longxxxx")
    app = create_http_app()
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post("/mcp", json={"jsonrpc": "2.0", "method": "tools/list", "id": 1})
    assert response.status_code == 401

def test_health_excluded_from_auth(monkeypatch):
    """DEBT-02: /health must be reachable without API key."""
    monkeypatch.setenv("MCP_API_KEY", "test-secret-key-32chars-longxxxx")
    app = create_http_app()
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/health")
    assert response.status_code != 401
```

### Structured error dict test pattern for DEBT-03
```python
# Source: pattern from existing test_vm_providers.py
@pytest.mark.asyncio
async def test_error_result_has_required_fields():
    """DEBT-03: vm_provider error results must have error, error_type, detail."""
    provider = DockerProvider()
    mock_conn = AsyncMock()
    # Force exception path
    mock_conn.run = AsyncMock(side_effect=Exception("connection refused"))

    result = await provider.deploy_vm(mock_conn, "test-vm", {})

    assert result["status"] == "error"
    assert "error" in result
    assert "error_type" in result
    assert "detail" in result
    assert result["error_type"] == "Exception"
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Per-request `aiohttp.ClientSession` (fallback in proxmox_api.py) | Shared `ClientSession` via `ResourceManager` (already exists, not wired) | Connection pool reuse, no descriptor leak |
| `APIKeyAuth` wired in deprecated `http_transport.py` | Must be wired into `http_app.py` (replacement) | HTTP endpoints currently unauthenticated |
| `_format_error()` returns 4-field dict | Must return 6-field dict with `error_type` and `detail` | Callers can classify and log errors programmatically |

---

## Open Questions

1. **Should MCP_API_KEY be required or optional for HTTP mode?**
   - What we know: `APIKeyAuth` warns (not errors) when key is absent; `http_transport.py` made it opt-out via `auth_enabled` flag.
   - What's unclear: Should stdio deployments (no HTTP) be affected at all? They should not — `create_http_app()` is only called for HTTP mode.
   - Recommendation: Only wrap with `APIKeyAuth` when `MCP_API_KEY` is set in environment. When not set, don't apply the wrapper (pass-through). Log a warning at startup so admins know HTTP is unauthenticated.

2. **Should `detail` field use `sanitize_error()` or raw `repr()`?**
   - What we know: `sanitize_error()` strips known credential patterns. `repr(e)` may include connection strings in some aiohttp exceptions.
   - What's unclear: What exceptions can reach `_format_error()` in practice?
   - Recommendation: Use `sanitize_error(e)` for `detail` to be consistent with the rest of the codebase's error handling philosophy. Import from `log_filter`.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8+ with pytest-asyncio |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_proxmox_api.py tests/test_http_app.py tests/test_vm_providers.py -x` |
| Full suite command | `uv run pytest tests/ -m "not integration"` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEBT-01 | Proxmox handler passes shared session to client | unit | `uv run pytest tests/test_proxmox_api.py -x -k "session"` | Partial - test_proxmox_api.py exists, needs new session-threading tests |
| DEBT-01 | No extra sessions opened per request | unit | `uv run pytest tests/test_proxmox_api.py -x -k "shared_session"` | Wave 0 gap |
| DEBT-02 | POST /mcp without API key returns 401 | unit | `uv run pytest tests/test_http_app.py -x -k "api_key"` | Wave 0 gap |
| DEBT-02 | /health reachable without API key | unit | `uv run pytest tests/test_http_app.py -x -k "health"` | Wave 0 gap |
| DEBT-02 | Valid API key allows request through | unit | `uv run pytest tests/test_http_app.py -x -k "valid_key"` | Wave 0 gap |
| DEBT-03 | Provider error dicts contain error_type field | unit | `uv run pytest tests/test_vm_providers.py -x -k "error_type"` | Wave 0 gap |
| DEBT-03 | Provider error dicts contain detail field | unit | `uv run pytest tests/test_vm_providers.py -x -k "detail"` | Wave 0 gap |
| DEBT-03 | list_vms exception path returns structured dict | unit | `uv run pytest tests/test_vm_providers.py -x -k "list_vms_error"` | Wave 0 gap |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_proxmox_api.py tests/test_http_app.py tests/test_vm_providers.py -x`
- **Per wave merge:** `uv run pytest tests/ -m "not integration"`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_proxmox_api.py` — add session-threading tests: verify `ProxmoxAPIClient._shared_session` is set when `session=` arg provided to module-level functions
- [ ] `tests/test_http_app.py` — add DEBT-02 auth tests: 401 without key, 200 with valid key, health excluded
- [ ] `tests/test_vm_providers.py` — add DEBT-03 structural tests: error dicts from exception paths contain `error_type` and `detail`

*(Existing test files cover the happy paths — Wave 0 only needs new test functions in existing files, no new files.)*

---

## Sources

### Primary (HIGH confidence)
- Direct code read: `src/homelab_mcp/proxmox_api.py` — session fallback branch at line 123-127 confirmed
- Direct code read: `src/homelab_mcp/resource_manager.py` — `proxmox_session` property confirmed, fully initialized
- Direct code read: `src/homelab_mcp/server.py` — `get_resource_manager()` confirmed, lifespan-bound
- Direct code read: `src/homelab_mcp/http_app.py` — `create_http_app()` confirmed: no `APIKeyAuth` applied
- Direct code read: `src/homelab_mcp/auth.py` — `APIKeyAuth` confirmed: functional, exclude_paths supported
- Direct code read: `src/homelab_mcp/tool_handlers/proxmox_handlers.py` — all 9 Proxmox handlers confirmed to call module-level functions without `session=`
- Direct code read: `src/homelab_mcp/vm_providers/base.py` — `_format_error()` confirmed: missing `error_type`, `detail`
- Direct code read: `src/homelab_mcp/vm_providers/docker_provider.py` — `list_vms` bare exception confirmed at line ~207
- Direct code read: `src/homelab_mcp/vm_providers/lxd_provider.py` — `list_vms` bare exception confirmed at line ~209
- Direct code read: `src/homelab_mcp/log_filter.py` — `sanitize_error()` confirmed available

### Secondary (MEDIUM confidence)
- Pattern reference: `src/homelab_mcp/http_transport.py` (deprecated) — shows correct `APIKeyAuth` wiring pattern including exclude_paths

---

## Metadata

**Confidence breakdown:**
- Bug identification: HIGH — all three bugs confirmed by direct code inspection, no ambiguity
- Fix paths: HIGH — all fix patterns are straightforward one-location changes with clear before/after
- Test gaps: HIGH — existing test files identified, new test functions scoped precisely
- Edge cases: MEDIUM — the `delete_proxmox_vm` internal call and `sanitize_error` for `detail` require attention during implementation

**Research date:** 2026-03-11
**Valid until:** 2026-04-11 (stable codebase, no fast-moving dependencies)
