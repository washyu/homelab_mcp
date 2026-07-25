# AGENTS.md - Operating Guide for This Repo

## Tech Stack

- **Python 3.12+**, strict typing (mypy), managed with `uv`
- **MCP Framework**: `mcp[cli]` — server is stdio-based, communicates via JSON-RPC over stdio
- **SSH**: `asyncssh` for all SSH operations
- **Database**: SQLite by default (`~/.homelab_mcp/homelab.db`), optional PostgreSQL (set `ENABLE_POSTGRESQL=true`)

## Key Commands

```bash
uv sync                        # install all deps (dev group auto-installed)
uv run python run_server.py    # start the MCP server
uv run pytest tests/ -m "not integration"   # fast unit tests only
uv run pytest tests/integration/ -m integration  # requires Docker running
uv run ruff check src/         # lint
uv run ruff format src/        # format
uv run mypy src/               # typecheck
```

## Adding a New Tool

1. Define schema in `src/homelab_mcp/tool_schemas/{category}.py` (8 files cover each domain)
2. Annotate with read/write/mutation intent via `src/homelab_mcp/tool_annotations.py`
3. Add an entry to the `TOOLS` dict in `src/homelab_mcp/tools.py` referencing that schema file
4. Register in `src/homelab_mcp/server.py` under the matching category handler
5. Write tests in `tests/test_*.py`

## TestSprite (Hackathon Branch) — CRITICAL RULES

- **Never run TestSprite unless told to** — it can autonomously loop and burn credits.
- **Never modify anything under `testsprite_tests/`** — it's auto-generated.
- If code review finds agent-created files in `testsprite_tests/`, delete/revert them before proceeding.

## SSH / Proxmox Prerequisites

Before running the server, ensure `.env.example` is copied to `.env`. Required vars:

| Var | Purpose |
|-----|---------|
| `PROXMOX_HOST` | (required) IP/FQDN of Proxmox host |
| `PROXMOX_USER` / `PROXMOX_PASSWORD` | Password auth |
| `PROXMOX_API_TOKEN` | API token auth — preferred; no 2h timeout |

Optional: MCP_HTTP transport, SSL certs, PostgreSQL settings.

## Database Behavior

- Device records are tracked in-memory for a session and persisted to the SQLite DB on changes (`database.py`)
- New device types auto-create tables via migration logic
- Integration tests spin up Docker containers; unit tests skip anything that touches the network (decorated `not integration`)

## Environment / Config Quirks

- **Credentials CLI**: `homelab-mcp credentials add/remove/list` — OS keyring, falls back to env vars.
- **Service templates** (`src/homelab_mcp/service_templates/*.yaml`, 10 files: jellyfin, pihole, ollama, homeassistant, truenas, etc.) drive the service installer; new services follow existing template structure.
- **Runtime config**: `config.yaml` is also loaded at startup on top of env vars.

## Testing Quirks

- Integration tests require Docker — they are marked `@pytest.mark.integration`.
- Unit tests use mocks for SSH connections and database calls.
- `~/.homelab_mcp/` (SQLite DB dir) does NOT exist by default — server creates it on first device write.
- New Proxmox API tools auto-import from `community-scripts/ProxmoxVE`; check that source if a tool's behavior looks wrong.

## Adding a Tool to the Codebase

1. Schema → `src/homelab_mcp/tool_schemas/*.py` (one file per domain: ssh, service, vm, proxmox, network, infrastructure, drift, credential)
2. Annotation → add entry in `tool_annotations.py` with read/write/mutation intent (`read`, `write`, `mutation`)
3. Tools dict → add to `src/homelab_mcp/tools.py:TOOLS` referencing the schema module
4. Server registration → register handler category in `src/homelab_mcp/server.py` (dispatches via tool group)
5. Tests → write unit tests under `tests/`, mock SSH with `asyncssh.connect` mocks; integration tests go in `tests/integration/`

## Environment / Config Gotchas

- **Credential CLI**: `uv run python -m homelab_mcp credentials add|remove|list` — stores in OS keyring (libsecret/macOS Keychain), falls back to env vars when unavailable.
- **Proxmox SSL verify default changes** based on hostname: internal IPs (192.168.x/10.x) or loopback auto-disable `VERIFY_SSL`; external FQDNs enforce it unless `PROXMOX_VERIFY_SSL=false`.
- **Two-phase SSH key lifecycle**: server generates `~/.ssh/mcp_admin_rsa` (or user-provided), copies public key to target during `setup_mcp_admin`, then all subsequent tools use this existing connection. Never re-invoke credential prompt for the same host after first setup.
