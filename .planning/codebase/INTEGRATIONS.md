# External Integrations

**Analysis Date:** 2026-03-08

## APIs & External Services

**Proxmox VE:**
- Full REST API integration for VM/container lifecycle management
- SDK/Client: Custom `ProxmoxAPIClient` in `src/homelab_mcp/proxmox_api.py`
- HTTP client: `aiohttp` for async requests
- Auth: Password-based (env vars `PROXMOX_USER`, `PROXMOX_PASSWORD`) or API token (`PROXMOX_API_TOKEN`)
- Base URL: `https://{PROXMOX_HOST}:8006/api2/json`
- SSL verification configurable via `PROXMOX_VERIFY_SSL` (default: false)
- Operations: list resources, node status, VM status, start/stop/reboot VMs, create/clone/delete VMs and LXC containers
- Handler: `src/homelab_mcp/tool_handlers/proxmox_handlers.py`
- Schema: `src/homelab_mcp/tool_schemas/proxmox_tools_schema.py`

**Ollama (Local LLM):**
- Optional AI integration for homelab management assistance
- SDK/Client: `ollama` Python package (optional dependency under `[ai]` extra)
- Auth: None (local service)
- Connection: `OLLAMA_HOST` env var (default: `http://localhost:11434`)
- Model: `OLLAMA_MODEL` env var (default: `llama3.2:1b`)

**Ansible:**
- Optional automation framework for service installation
- SDK/Client: `ansible` package (optional dependency under `[automation]` extra)
- Runner: `AnsibleRunner` class in `src/homelab_mcp/service_installer.py`
- Inventory: `ANSIBLE_INVENTORY_PATH` env var
- Executes playbooks via subprocess

## Data Storage

**Databases:**
- SQLite (default/primary)
  - Connection: Auto-created at `~/.mcp/sitemap.db`
  - Path configurable via `SQLITE_PATH` env var
  - Client: Python stdlib `sqlite3`
  - Adapter: `SQLiteAdapter` in `src/homelab_mcp/database.py`
  - Tables: `devices`, `discovery_history`, `ssh_credentials`

- PostgreSQL (optional, feature-flagged)
  - Connection: `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
  - Client: `psycopg2` (optional import, graceful fallback)
  - Adapter: `PostgreSQLAdapter` in `src/homelab_mcp/database.py`
  - Enhanced with JSONB columns and GIN indexes for system_info and network_interfaces
  - Feature flag: `ENABLE_POSTGRESQL` env var

- Factory: `get_database_adapter()` in `src/homelab_mcp/database.py` auto-detects from `DATABASE_TYPE` env var
- Abstract base: `DatabaseAdapter` ABC defines the interface contract

**File Storage:**
- Local filesystem only
- Service templates: YAML files in `src/homelab_mcp/service_templates/`
- SSH keys: `~/.ssh/mcp/` directory
- Database files: `~/.mcp/` directory

**Caching:**
- None (no caching layer)

## Authentication & Identity

**MCP HTTP API Auth:**
- Custom Bearer token middleware in `src/homelab_mcp/auth.py`
- Class: `APIKeyAuth` (Starlette ASGI middleware)
- Token source: `MCP_API_KEY` env var
- Excludes `/health` endpoint from auth
- Uses `secrets.compare_digest` for timing-safe comparison
- Minimum key length: 16 characters enforced

**SSH Auth:**
- Key-based authentication (primary): Auto-generated RSA keys at `~/.ssh/mcp/`
- Credential storage: `ssh_credentials` table in database
- Resolution priority (in `src/homelab_mcp/ssh_tools.py` `resolve_ssh_credentials()`):
  1. Explicit credentials passed to function
  2. Stored credentials from database
  3. Default `mcp_admin` key
- CRUD operations: `src/homelab_mcp/tool_handlers/credential_handlers.py`

**Proxmox Auth:**
- Password auth: Creates session ticket with 2-hour timeout
- API token auth: No timeout (recommended)
- Credentials from env vars, see Proxmox section above

## Monitoring & Observability

**Error Tracking:**
- Custom `HealthChecker` class in `src/homelab_mcp/error_handling.py`
- Tracks request counts and error types in memory
- Health endpoint: `GET /health` (HTTP mode) or `health/status` method (stdio mode)

**Logs:**
- Python stdlib `logging` module
- Configurable level via `LOG_LEVEL` env var (default: INFO)
- All modules use `logging.getLogger(__name__)` pattern

## CI/CD & Deployment

**Hosting:**
- Docker container (HTTP mode) - `Dockerfile` with multi-stage build
- Direct Python execution (stdio mode for Claude Desktop)
- `docker-compose.yml` for single-service deployment with volume persistence

**CI Pipeline:**
- GitHub Actions (`.github/workflows/main.yml`)
- Jobs:
  1. `test-and-quality` (always): ruff lint/format, mypy, pytest with coverage, Codecov upload
  2. `integration-tests` (manual/scheduled/commit tag): Docker-based integration tests
  3. `cross-platform` (manual/tags): Windows + macOS matrix
  4. `security` (weekly/tags): bandit + safety scans
  5. `release` (tags only): GitHub Release creation via `softprops/action-gh-release@v2`
- Trigger: push to main/develop, PRs, weekly schedule, manual dispatch

**Additional CI:**
- `.github/workflows/claude.yml` - Claude Code integration
- `.github/workflows/claude-code-review.yml` - Claude code review

## Environment Configuration

**Required env vars (minimum viable):**
- None for stdio mode with SQLite defaults

**Required for HTTP mode:**
- `MCP_API_KEY` - API key for authentication (when auth enabled)

**Required for Proxmox integration:**
- `PROXMOX_HOST` - Proxmox server IP/hostname
- Either `PROXMOX_API_TOKEN` or both `PROXMOX_USER` + `PROXMOX_PASSWORD`

**Optional env vars:**
- `PROXMOX_VERIFY_SSL` - SSL verification (default: false)
- `MCP_HTTP_HOST` - HTTP bind address (default: 0.0.0.0)
- `MCP_HTTP_PORT` - HTTP port (default: 8080)
- `MCP_AUTH_ENABLED` - Enable/disable auth (default: true)
- `DATABASE_TYPE` - sqlite or postgresql (default: sqlite)
- `SQLITE_PATH` - Custom SQLite path
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `SSH_TIMEOUT` - SSH operation timeout in seconds (default: 10)
- `SSH_RETRIES` - SSH retry count (default: 3)
- `DISCOVERY_BATCH_SIZE` - Concurrent discovery batch size (default: 10)
- `DISCOVERY_TIMEOUT` - Discovery timeout in seconds (default: 300)
- `OLLAMA_HOST`, `OLLAMA_MODEL` - Ollama LLM configuration
- `ANSIBLE_HOST_KEY_CHECKING`, `ANSIBLE_INVENTORY_PATH`
- `MCP_SSL_CERT`, `MCP_SSL_KEY` - SSL certificate paths for HTTPS
- `MCP_DEBUG`, `MCP_LOG_LEVEL`

**Secrets location:**
- `.env` file (gitignored)
- `.env.development` file (gitignored)
- Docker environment variables in `docker-compose.yml`

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## Network Protocols

**SSH (port 22):**
- Client: `asyncssh` library
- Used for: device discovery, hardware detection, command execution, service installation
- Interactive shell sessions via WebSocket in HTTP mode (`src/homelab_mcp/shell_session.py`)

**HTTPS (port 8006):**
- Proxmox VE API communication via `aiohttp`

**HTTP/HTTPS (port 8080):**
- MCP server HTTP transport (Starlette/uvicorn)
- SSE (Server-Sent Events) for streaming notifications
- WebSocket for interactive shell terminal

**MCP Protocol (stdio):**
- JSON-RPC 2.0 over stdin/stdout
- Protocol version: 2024-11-05

## VM/Container Providers

**Provider abstraction:** `src/homelab_mcp/vm_providers/base.py` defines `VMProvider` ABC

**Implementations:**
- Docker provider: `src/homelab_mcp/vm_providers/docker_provider.py`
- LXD provider: `src/homelab_mcp/vm_providers/lxd_provider.py`
- Proxmox (separate): `src/homelab_mcp/proxmox_api.py` (direct API, not using VMProvider abstraction)

## Service Templates

**Location:** `src/homelab_mcp/service_templates/`

**Available templates:**
- `ollama.yaml`, `ollama_ansible.yaml` - Ollama LLM server
- `pihole.yaml`, `pihole_terraform.yaml` - Pi-hole DNS
- `homeassistant.yaml` - Home Assistant
- `jellyfin.yaml` - Jellyfin media server
- `k3s.yaml` - K3s Kubernetes
- `truenas.yaml` - TrueNAS storage
- `docker_terraform.yaml` - Docker with Terraform
- `ai_homelab_stack_ansible.yaml` - Full AI homelab stack

---

*Integration audit: 2026-03-08*
