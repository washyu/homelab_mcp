# Configuration Reference

This document covers every configuration option for the Homelab MCP Server. Variables can be set in a `.env` file in the project root or exported as environment variables. CLI arguments override environment variables when both are set.

## Environment Variables

### Server

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_DEBUG` | `false` | Enable debug mode (verbose logging) |
| `MCP_LOG_LEVEL` | `INFO` | Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL |

### SSH

| Variable | Default | Description |
|----------|---------|-------------|
| `SSH_TIMEOUT` | `10` | Timeout in seconds for SSH connection attempts |
| `SSH_RETRIES` | `3` | Number of retry attempts for failed SSH connections |

### Discovery

| Variable | Default | Description |
|----------|---------|-------------|
| `DISCOVERY_BATCH_SIZE` | `10` | Number of hosts to scan concurrently during network discovery |
| `DISCOVERY_TIMEOUT` | `300` | Overall timeout in seconds for discovery operations (5 minutes) |

### Proxmox Connection

| Variable | Default | Description |
|----------|---------|-------------|
| `PROXMOX_HOST` | *(required)* | IP address or hostname of your Proxmox server |
| `PROXMOX_USER` | *(required)* | Proxmox user in `user@realm` format (e.g., `root@pam`) |
| `PROXMOX_PASSWORD` | *(none)* | Password for Proxmox authentication. Use either this or `PROXMOX_API_TOKEN` |
| `PROXMOX_API_TOKEN` | *(none)* | API token in `user@realm!tokenid=uuid` format. Recommended over password authentication as tokens do not expire |
| `PROXMOX_VERIFY_SSL` | `true` | Verify SSL certificates when connecting to Proxmox. Set to `false` for self-signed certificates |
| `PROXMOX_CA_CERT` | *(none)* | Path to a custom CA certificate file for Proxmox SSL verification |

### HTTP Transport

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_HTTP_ENABLED` | `false` | Enable HTTP transport mode |
| `MCP_HTTP_HOST` | `0.0.0.0` (env) / `127.0.0.1` (CLI) | Host address to bind the HTTP server. See note below |
| `MCP_HTTP_PORT` | `8080` | Port for the HTTP server |
| `MCP_API_KEY` | *(none)* | API key for HTTP authentication. Required when auth is enabled. Must be at least 16 characters |
| `MCP_AUTH_ENABLED` | `true` | Enable API key authentication for HTTP transport |
| `MCP_SSL_CERT` | *(none)* | Path to SSL certificate file to enable HTTPS |
| `MCP_SSL_KEY` | *(none)* | Path to SSL private key file |

> **Host default discrepancy:** When using the `MCP_HTTP_HOST` environment variable, the default is `0.0.0.0` (all interfaces). When using the `--host` CLI flag, the default is `127.0.0.1` (localhost only). The CLI default is more secure -- set `MCP_HTTP_HOST` explicitly if you need network access via env vars.

### Database

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_TYPE` | `sqlite` | Database backend: `sqlite` or `postgresql` |
| `SQLITE_PATH` | `~/.mcp/sitemap.db` | File path for the SQLite database |
| `POSTGRES_HOST` | `localhost` | PostgreSQL server hostname |
| `POSTGRES_PORT` | `5432` | PostgreSQL server port |
| `POSTGRES_DB` | `homelab_mcp` | PostgreSQL database name |
| `POSTGRES_USER` | `postgres` | PostgreSQL username |
| `POSTGRES_PASSWORD` | `password` | PostgreSQL password |

### Feature Flags

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_POSTGRESQL` | `false` | Enable PostgreSQL support (requires `psycopg2-binary` package) |
| `ENABLE_RESOURCE_POOLS` | `false` | Enable Proxmox resource pool management features |

## CLI Arguments

The `run_server.py` entry point accepts the following arguments. CLI arguments take precedence over environment variables.

| Argument | Environment Variable | Default | Description |
|----------|---------------------|---------|-------------|
| `--http` | `MCP_HTTP_ENABLED` | `false` | Run in HTTP mode instead of stdio mode |
| `--host` | `MCP_HTTP_HOST` | `127.0.0.1` | HTTP server bind address |
| `--port` | `MCP_HTTP_PORT` | `8080` | HTTP server port |
| `--no-auth` | `MCP_AUTH_ENABLED` | auth enabled | Disable API key authentication |
| `--api-key` | `MCP_API_KEY` | *(none)* | API key for authentication |
| `--ssl-cert` | `MCP_SSL_CERT` | *(none)* | Path to SSL certificate file (enables HTTPS) |
| `--ssl-key` | `MCP_SSL_KEY` | *(none)* | Path to SSL private key file |

### Examples

```bash
# stdio mode (default, for Claude Desktop / Claude Code)
uv run python run_server.py

# HTTP mode on localhost
uv run python run_server.py --http

# HTTP mode with network access and custom port
uv run python run_server.py --http --host 0.0.0.0 --port 9000

# HTTP mode with SSL
uv run python run_server.py --http --ssl-cert /path/to/cert.pem --ssl-key /path/to/key.pem

# HTTP mode without authentication (local development only)
uv run python run_server.py --http --no-auth
```

## SSL Configuration

### Proxmox SSL

The server verifies Proxmox API SSL certificates by default. For common scenarios:

**Self-signed certificate (quickest):**

```bash
PROXMOX_VERIFY_SSL=false
```

**Custom CA certificate (recommended for production):**

```bash
PROXMOX_VERIFY_SSL=true
PROXMOX_CA_CERT=/path/to/proxmox-ca.crt
```

When `PROXMOX_VERIFY_SSL=true` (the default) and no `PROXMOX_CA_CERT` is set, the system's default CA bundle is used.

### HTTP Server SSL

To serve the MCP HTTP endpoint over HTTPS:

```bash
uv run python run_server.py --http --ssl-cert /path/to/cert.pem --ssl-key /path/to/key.pem
```

Or via environment variables:

```bash
MCP_SSL_CERT=/path/to/cert.pem
MCP_SSL_KEY=/path/to/key.pem
```

## Database Configuration

### SQLite (default)

SQLite is used by default with no additional setup. The database file is created automatically at `~/.mcp/sitemap.db`.

To use a custom path:

```bash
SQLITE_PATH=/custom/path/to/sitemap.db
```

### PostgreSQL

To use PostgreSQL instead of SQLite:

1. Install the PostgreSQL driver:
   ```bash
   uv add psycopg2-binary
   ```

2. Enable PostgreSQL and configure the connection:
   ```bash
   ENABLE_POSTGRESQL=true
   DATABASE_TYPE=postgresql
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   POSTGRES_DB=homelab_mcp
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=your_secure_password
   ```

3. Ensure the database exists before starting the server:
   ```bash
   createdb homelab_mcp
   ```

The server will create all required tables automatically on first run.

## Credentials CLI

The `credentials` subcommand manages stored credentials in the OS keyring. These are separate from environment variables and take precedence when the server connects to a host.

```bash
homelab-mcp credentials <subcommand> [options]
```

| Subcommand | Arguments | Description |
|------------|-----------|-------------|
| `add` | `<hostname> <username> [--type ssh\|proxmox]` | Prompt for password/token and store in OS keyring |
| `list` | `[--type ssh\|proxmox]` | List hostnames with stored credentials |
| `remove` | `<hostname> [--type ssh\|proxmox]` | Delete stored credential for a host |

**--type flag:**

| Value | Default | Use For |
|-------|---------|---------|
| `ssh` | yes | SSH password authentication |
| `proxmox` | no | Proxmox API token or password |

**Examples:**

```bash
# Add SSH credential (prompts for password)
homelab-mcp credentials add 192.168.1.10 admin

# Add Proxmox credential (prompts for API token or password)
homelab-mcp credentials add 192.168.1.200 root@pam --type proxmox

# List all SSH credentials
homelab-mcp credentials list

# List Proxmox credentials only
homelab-mcp credentials list --type proxmox

# Remove SSH credential for a host
homelab-mcp credentials remove 192.168.1.10

# Remove Proxmox credential for a host
homelab-mcp credentials remove 192.168.1.200 --type proxmox
```

> **Headless servers:** If the OS keyring is unavailable (no D-Bus session), `credentials add` will warn that the credential was not persisted. In that case, use environment variables (`PROXMOX_PASSWORD`, `PROXMOX_API_TOKEN`) as a fallback.
