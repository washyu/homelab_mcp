# CLAUDE.md - Project Guidelines for Claude Code

## Project Overview

Homelab MCP Server - A Python Model Context Protocol (MCP) server for AI-powered homelab infrastructure management. Provides 34+ tools for VM management, SSH discovery, service installation, and network topology mapping.

## Tech Stack

- **Python**: 3.12+ (strict typing with mypy)
- **Package Manager**: uv (preferred) - ultrafast Python package manager
- **MCP Framework**: mcp[cli] for Model Context Protocol support
- **Testing**: pytest with pytest-asyncio for async tests
- **Code Quality**: ruff (linting/formatting), mypy (type checking), bandit (security)
- **SSH**: asyncssh for async SSH operations
- **Database**: SQLite for device tracking

## Key Commands

```bash
# Install dependencies
uv sync

# Run the MCP server
uv run python run_server.py

# Run all tests
uv run pytest

# Run unit tests only (fast, no Docker)
uv run pytest tests/ -m "not integration"

# Run integration tests (requires Docker)
uv run pytest tests/integration/ -m integration -v

# Run specific test file
uv run pytest tests/test_server.py -v

# Code quality checks
uv run ruff check src/ tests/       # Linting
uv run ruff format src/ tests/      # Formatting
uv run mypy src/                    # Type checking
uv run bandit -r src/               # Security scan

# Run full quality check
./scripts/quality-check.sh
```

## Project Structure

```
src/homelab_mcp/           # Main package
├── server.py              # MCP server with JSON-RPC protocol
├── tools.py               # Tool registry (34 tools defined here)
├── ssh_tools.py           # SSH discovery & hardware detection
├── service_installer.py   # Service installation framework
├── infrastructure_crud.py # Infrastructure lifecycle management
├── vm_operations.py       # VM/container operations
├── sitemap.py             # Network topology mapping
├── database.py            # SQLite database operations
├── config.py              # Configuration management
├── error_handling.py      # Centralized error handling
├── migration.py           # Database migrations
└── service_templates/     # YAML service definitions

tests/                     # Test suite
├── integration/           # Integration tests (require Docker)
└── test_*.py             # Unit tests
```

## Code Style & Patterns

- **Type hints required**: All functions must have complete type annotations
- **Async-first**: Use async/await for I/O operations (SSH, network, file)
- **Error handling**: Use `error_handling.py` patterns for consistent error responses
- **Tool definitions**: Add new tools in `tools.py` TOOLS dict with proper JSON schema

### Adding New Tools

1. Define schema in `src/homelab_mcp/tools.py`:
```python
TOOLS["new_tool"] = {
    "description": "Tool description",
    "inputSchema": {
        "type": "object",
        "properties": { ... },
        "required": []
    }
}
```

2. Implement logic in appropriate module (ssh_tools.py, vm_operations.py, etc.)
3. Add execution case in `execute_tool()` function
4. Write tests in `tests/test_*.py`

## Testing Guidelines

- Unit tests: `tests/test_*.py` - fast, no external dependencies
- Integration tests: `tests/integration/` - require Docker
- Use `@pytest.mark.asyncio` for async test functions
- Mock SSH connections in unit tests using pytest-mock

## Configuration

- Environment variables: See `.env.example`
- Database: Auto-created at `~/.homelab_mcp/homelab.db`
- SSH keys: Auto-generated at `~/.ssh/mcp_admin_rsa`

## Important Notes

- MCP server communicates via stdio (stdin/stdout)
- Pre-commit hooks configured in `.pre-commit-config.yaml`
- CI runs on GitHub Actions (`.github/workflows/main.yml`)
