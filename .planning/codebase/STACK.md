# Technology Stack

**Analysis Date:** 2026-03-08

## Languages

**Primary:**
- Python 3.12+ - All application code, strict typing enforced via mypy

**Secondary:**
- YAML - Service template definitions in `src/homelab_mcp/service_templates/`
- HTML - Shell terminal UI in `src/homelab_mcp/shell_terminal.html`

## Runtime

**Environment:**
- Python 3.12 (pinned in `.python-version`)
- CPython on Linux (primary target), cross-platform tested on macOS and Windows

**Package Manager:**
- uv (Astral) - ultrafast Python package manager and resolver
- Lockfile: `uv.lock` present
- Build backend: hatchling

## Frameworks

**Core:**
- mcp[cli] >=1.9.1 - Model Context Protocol framework for AI tool integration
- Starlette >=0.30.0 - ASGI web framework for HTTP transport layer
- uvicorn >=0.24.0 - ASGI server for HTTP mode

**Testing:**
- pytest >=8.3.5 - Test runner with strict markers and strict config
- pytest-asyncio >=0.23.0 - Async test support
- pytest-cov >=6.1.1 - Coverage reporting (minimum 40% enforced in CI)
- pytest-mock >=3.14.0 - Mock fixtures
- aioresponses >=0.7.6 - Mocking aiohttp requests

**Code Quality:**
- ruff >=0.8.0 - Linting and formatting (target: py312, line-length: 120)
- mypy >=1.13.0 - Static type checking (strict mode: disallow_untyped_defs, warn_return_any, etc.)
- bandit >=1.7.0 - Security linting
- safety >=3.0.0 - Dependency vulnerability scanning
- pre-commit >=4.3.0 - Git hooks

**Build/Dev:**
- hatchling - Build backend (`pyproject.toml` build-system)
- Docker - Multi-stage build for HTTP deployment (`Dockerfile`)
- docker-compose - Container orchestration (`docker-compose.yml`)

## Key Dependencies

**Critical:**
- asyncssh >=2.14.0 - Async SSH client for remote device management (core functionality)
- aiohttp >=3.9.0 - Async HTTP client for Proxmox API integration
- httpx >=0.28.1 - HTTP client (secondary)
- pyyaml >=6.0 - YAML parsing for service templates
- jsonschema >=4.24.0 - JSON Schema validation for tool input schemas
- websockets >=12.0 - WebSocket support for interactive shell sessions

**Infrastructure:**
- rich >=13.10.5 - Terminal output formatting
- aiofiles >=24.1.0 - Async file I/O

**Optional Dependencies (extras):**
- `monitoring`: pandas >=2.2.3, pyarrow >=20.0.0 - Data analysis
- `automation`: ansible >=2.9.0, paramiko >=3.0.0 - Ansible playbook execution
- `ai`: ollama >=0.4.4 - Local LLM integration
- `security`: keyring >=25.0.0, cryptography >=42.0.0 - Enhanced credential management

## Configuration

**Environment:**
- Configuration via environment variables, loaded in `src/homelab_mcp/config.py`
- `.env.example` provides reference for all variables
- `.env` and `.env.development` files present (not committed)
- Key config classes: `MCPConfig`, `DatabaseConfig`, `HTTPConfig` in `src/homelab_mcp/config.py`

**Required env vars (by feature):**
- Proxmox: `PROXMOX_HOST`, `PROXMOX_USER`/`PROXMOX_PASSWORD` or `PROXMOX_API_TOKEN`
- HTTP mode: `MCP_API_KEY` (when auth enabled), `MCP_HTTP_PORT`
- Database: `DATABASE_TYPE` (sqlite default), `SQLITE_PATH` (auto-defaults to `~/.mcp/sitemap.db`)
- Ollama: `OLLAMA_HOST`, `OLLAMA_MODEL`

**Build:**
- `pyproject.toml` - All project metadata, tool configs (ruff, mypy, pytest, bandit, coverage)
- `.pre-commit-config.yaml` - Pre-commit hook definitions
- `Dockerfile` - Multi-stage production build (python:3.12-slim)
- `docker-compose.yml` - Single-service deployment with volume persistence

**Ruff config (in `pyproject.toml`):**
- target-version: py312
- line-length: 120
- Rules: E, W, F, I (isort), B (bugbear), C4 (comprehensions), UP (pyupgrade)
- Ignores: E501, B008, C901

**Mypy config (in `pyproject.toml`):**
- Strict mode with disallow_untyped_defs, disallow_incomplete_defs
- Tests have relaxed typing rules
- warn_return_any, warn_unused_configs, strict_equality enabled

## Platform Requirements

**Development:**
- Python 3.12+
- uv package manager
- SSH client (for testing remote operations)
- Docker (for integration tests)

**Production:**
- Docker with docker-compose (recommended)
- OR Python 3.12+ with uv
- Network access to homelab devices (SSH port 22, Proxmox port 8006)
- SQLite (default) or PostgreSQL (optional) for device tracking

**Entry Points:**
- `run_server.py` - CLI entry point with argparse (stdio or HTTP mode)
- `homelab-mcp` - Installed console script via `pyproject.toml` [project.scripts]

---

*Stack analysis: 2026-03-08*
