# Coding Conventions

**Analysis Date:** 2026-03-08

## Naming Patterns

**Files:**
- Use `snake_case.py` for all Python modules: `ssh_tools.py`, `vm_operations.py`, `error_handling.py`
- Test files prefix with `test_`: `test_server.py`, `test_ssh_tools.py`
- Schema files suffix with `_schema.py`: `ssh_tools_schema.py`, `vm_tools_schema.py`
- Handler files suffix with `_handlers.py`: `ssh_handlers.py`, `vm_handlers.py`

**Functions:**
- Use `snake_case` for all functions: `ssh_discover_system()`, `get_all_devices()`
- Async functions use same naming, no prefix: `async def execute_tool()`
- Handler functions prefix with `handle_`: `handle_ssh_discover()`, `handle_deploy_vm()`
- Factory functions prefix with `get_` or `create_`: `get_database_adapter()`, `create_database_from_config()`
- Boolean check functions prefix with `is_`: `is_postgresql_configured()`

**Variables:**
- Use `snake_case` for all variables: `device_data`, `tool_name`, `request_id`
- Constants use `UPPER_SNAKE_CASE`: `SSH_KEY_DIR`, `POSTGRESQL_AVAILABLE`, `TOOL_HANDLERS`
- Module-level loggers named `logger`: `logger = logging.getLogger(__name__)`

**Types/Classes:**
- Use `PascalCase`: `HomelabMCPServer`, `SQLiteAdapter`, `DatabaseAdapter`
- Custom exceptions suffix with specific error type: `MCPTimeout`, `MCPConnectionError`
- TypeVars use single uppercase letters: `F = TypeVar("F", bound=Callable[..., Any])`

**Tool names:**
- Use `snake_case` strings: `"ssh_discover"`, `"setup_mcp_admin"`, `"deploy_vm"`
- Grouped by domain in schema/handler registries

## Code Style

**Formatting:**
- Tool: ruff format
- Line length: 120 characters (configured in `pyproject.toml` `[tool.ruff]`)
- Target Python: 3.12

**Linting:**
- Tool: ruff check
- Rule sets enabled: E (pycodestyle errors), W (pycodestyle warnings), F (pyflakes), I (isort), B (flake8-bugbear), C4 (flake8-comprehensions), UP (pyupgrade)
- Ignored rules: E501 (line length handled by formatter), B008 (function calls in defaults), C901 (complexity)
- Test-specific ignores in `pyproject.toml`: B018, S101, S105, S106

**Type Checking:**
- Tool: mypy with strict settings
- `disallow_untyped_defs = true` for source code
- `disallow_incomplete_defs = true`
- `warn_return_any = true`
- Tests are exempt from `disallow_untyped_defs` (see `[[tool.mypy.overrides]]` in `pyproject.toml`)
- Use `from typing import Any` for flexible dict types: `dict[str, Any]`
- Use `str | None` syntax (Python 3.10+ union syntax), not `Optional[str]`

**Security:**
- Tool: bandit
- Excludes tests directory
- Skips B101 (assert_used) and B601 (shell=True)

## Import Organization

**Order:**
1. Standard library imports (`import asyncio`, `import json`, `import logging`)
2. Third-party imports (`import asyncssh`, `import pytest`)
3. Local/relative imports (`from .error_handling import timeout_wrapper`)

**Style:**
- Use `from` imports for specific items: `from typing import Any, TypeVar`
- Use relative imports within the package: `from .database import get_database_adapter`
- Use absolute imports in tests: `from src.homelab_mcp.server import HomelabMCPServer`
- Group related imports on separate lines
- isort is enforced via ruff (rule set "I")

**Path Aliases:**
- No path aliases configured. Use `src.homelab_mcp` prefix in tests.

## Error Handling

**MCP Response Pattern:**
All tool results return a structured dict with `content` key containing a list of text items:
```python
return {"content": [{"type": "text", "text": result_string}]}
```

**JSON Error Responses:**
Use structured JSON strings for error data in `src/homelab_mcp/error_handling.py`:
```python
{
    "status": "error",
    "error": "description of what went wrong",
    "error_type": "timeout|ssh_timeout|ssh_connection_error|ssh_auth_error|retry_exhausted|unexpected",
    "timestamp": datetime.now(UTC).isoformat(),
}
```

**Decorator-based Error Handling:**
Use decorators from `src/homelab_mcp/error_handling.py` for cross-cutting error concerns:
- `@timeout_wrapper(timeout_seconds=N)` - wraps async functions with timeout protection
- `@retry_on_failure(max_retries=N, delay_seconds=N)` - retries on `ConnectionError`, `MCPConnectionError`, `OSError`
- `@ssh_connection_wrapper(timeout_seconds=N)` - specialized SSH error handling with connection-specific messages

**Stacking decorators** (outer to inner):
```python
@ssh_connection_wrapper(timeout_seconds=15.0)
@retry_on_failure(max_retries=2, delay_seconds=0.01)
async def ssh_operation(hostname="test"):
    ...
```

**Custom Exceptions:**
- `MCPTimeout` - for timeout operations (defined in `src/homelab_mcp/error_handling.py`)
- `MCPConnectionError` - for connection failures (defined in `src/homelab_mcp/error_handling.py`)

**JSON-RPC Error Pattern (server level):**
Use `_error_response()` in `src/homelab_mcp/server.py`:
```python
{"jsonrpc": "2.0", "id": request_id, "error": {"code": -32603, "message": message}}
```

## Logging

**Framework:** Python standard `logging` module

**Setup pattern (per module):**
```python
import logging
logger = logging.getLogger(__name__)
```

**Log levels used:**
- `logger.info()` - tool execution, server lifecycle events
- `logger.warning()` - timeouts that are non-fatal, retryable failures
- `logger.error()` - failed operations, with `exc_info=True` for unexpected errors
- `logger.debug()` - credential resolution details

**Pattern:** Use f-strings in log messages (ruff does not enforce lazy logging):
```python
logger.info(f"Executing tool: {tool_name}")
logger.error(f"SSH connection failed: {str(e)}", exc_info=True)
```

## Comments

**When to Comment:**
- Module-level docstrings required for every file: `"""Module description."""`
- Class docstrings required: `"""Class description."""`
- Function docstrings use Google-style with Args/Returns/Raises sections
- Inline comments for non-obvious logic (e.g., command sequences in SSH operations)

**Docstring Style:**
```python
def timeout_wrapper(timeout_seconds: float = 30.0, default_response: dict[str, Any] | None = None) -> Callable[[F], F]:
    """
    Decorator to wrap async functions with timeout protection.

    Args:
        timeout_seconds: Maximum time to wait before timing out
        default_response: Default response to return on timeout
    """
```

## Function Design

**Size:** No strict limit, but most functions are under 50 lines. Longer functions exist in database adapters and SSH tools.

**Parameters:**
- Use keyword arguments with defaults for optional params
- Use `**kwargs: Any` for dynamic field updates (e.g., `update_credential()`)
- Spread dict arguments with `**arguments` when delegating to implementations

**Return Values:**
- Tool handlers return `dict[str, Any]` with `content` key
- Low-level functions return JSON strings (parsed by callers)
- Database operations return `int` (IDs), `bool` (success), `list[dict]` (records), or `dict | None`

## Module Design

**Exports:**
- Use `__all__` lists in `__init__.py` files for public API: `__all__ = ["TOOL_HANDLERS", "get_tool_handler", "ToolHandler"]`

**Barrel Files:**
- `src/homelab_mcp/tool_schemas/__init__.py` aggregates all schema modules into `get_all_tool_schemas()`
- `src/homelab_mcp/tool_handlers/__init__.py` aggregates all handler modules into `TOOL_HANDLERS` dict

**Handler Pattern:**
Tool handlers in `src/homelab_mcp/tool_handlers/` follow a thin wrapper pattern:
```python
async def handle_ssh_discover(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle ssh_discover tool."""
    result = await ssh_discover_system(**arguments)
    return {"content": [{"type": "text", "text": result}]}
```

**Schema Pattern:**
Tool schemas in `src/homelab_mcp/tool_schemas/` define JSON Schema dicts:
```python
SSH_TOOLS: dict[str, dict[str, Any]] = {
    "ssh_discover": {
        "description": "...",
        "inputSchema": {
            "type": "object",
            "properties": { ... },
            "required": ["hostname", "username"],
        },
    },
}
```

**Abstract Base Classes:**
Use ABC pattern for database adapters in `src/homelab_mcp/database.py`:
```python
class DatabaseAdapter(ABC):
    @abstractmethod
    def connect(self) -> None: ...
    @abstractmethod
    def store_device(self, device_data: dict[str, Any]) -> int: ...
```

**Configuration Classes:**
Use class-based config with `os.getenv()` defaults in `src/homelab_mcp/config.py`:
```python
class MCPConfig:
    def __init__(self) -> None:
        self.debug = os.getenv("MCP_DEBUG", "false").lower() == "true"
        self.ssh_timeout = int(os.getenv("SSH_TIMEOUT", "10"))
```

**Dataclasses:**
Use `@dataclass` for simple data containers:
```python
@dataclass
class SSHCredentials:
    hostname: str
    username: str
    port: int = 22
    key_path: str | None = None
```

## Pre-commit Hooks

Configured in `.pre-commit-config.yaml`:
- ruff lint (with `--fix` and `--exit-non-zero-on-fix`)
- ruff format
- check-case-conflict, check-merge-conflict, check-yaml, check-json, check-toml
- end-of-file-fixer, trailing-whitespace
- debug-statements, check-ast

Run manually: `uv run pre-commit run --all-files`

---

*Convention analysis: 2026-03-08*
