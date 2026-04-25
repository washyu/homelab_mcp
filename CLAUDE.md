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

## Release & Tagging Workflow

**PyPI publishing is auto-triggered by `git tag v*` push** via OIDC trusted publishing. The workflow runs test-and-quality + cross-platform + security + release jobs and only publishes if all pass — but the trigger fires on the **tag commit**, regardless of which branch it's on.

**Standard release flow — always follow this order:**

1. Work on a feature/milestone branch (e.g. `credential-cleanup`, `feature/foo`)
2. Bump `pyproject.toml` version in a dedicated commit on the branch
3. Push branch + open PR against `main` (`gh pr create --base main`)
4. Let CI run on the PR; address any failures
5. Merge PR to `main` via GitHub UI (squash or merge-commit per project preference)
6. **Tag from `main`, not from the feature branch:**
   ```bash
   git checkout main && git pull origin main
   git tag -a v1.X -m "<release notes>"
   git push origin v1.X
   ```
7. Tag push triggers the publish workflow → PyPI

**Why this matters:**
- Tagging from a non-main branch publishes code that doesn't match what `main` shows on GitHub — confusing for anyone reading the repo
- The PR creates a discoverable review point for "what shipped in vX.Y"
- Skipping the merge step leaves `main` stale while PyPI is current

**Never:**
- Tag a non-main branch and push the tag (publishes code that isn't in main)
- Force-push tags or push tags before the underlying commits are pushed
- Skip the PR step "to save time" — the PyPI publish is irreversible (PyPI rejects re-uploads of the same version)

## TestSprite Rules
- DO NOT run TestSprite unless explicitly told to do so
- DO NOT modify any files in `testsprite_tests/`
- DO NOT modify `testsprite_backend_test_plan.json`
- DO NOT modify any TestSprite configuration files
- Fix failures by correcting the SERVER code only, never the test code
