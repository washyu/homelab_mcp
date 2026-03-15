# Setup Guide

This guide walks you through installing and running the Homelab MCP Server from scratch. By the end, you will have an AI-powered interface to your homelab infrastructure.

## 1. Prerequisites

Before you begin, ensure you have:

- **Python 3.12+** -- Check with `python3 --version`
- **uv** -- A fast Python package manager. Install it with:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  source ~/.local/bin/env
  ```
- **A Proxmox server** or any SSH-accessible Linux host that you want to manage

## 2. Install

### Option A: Install from PyPI (recommended)

If you have `uv` installed, run the server directly from PyPI with no clone needed:

```bash
uvx homelab-mcp
```

`uvx` downloads and caches the package on first run. Subsequent runs start immediately.

For MCP client configuration with uvx, see section 5.

### Option B: Clone and run from source

```bash
git clone https://github.com/washyu/homelab_mcp.git
cd homelab_mcp
uv sync
```

`uv sync` installs all dependencies and creates a virtual environment automatically. This typically takes 2-3 seconds.

## 3. Configure

Copy the example environment file and edit it with your values:

```bash
cp .env.example .env
```

At minimum, set your Proxmox connection details in `.env`:

```bash
# Required: Your Proxmox host IP or hostname
PROXMOX_HOST=192.168.10.200

# Option 1: Password authentication (2-hour ticket timeout)
PROXMOX_USER=root@pam
PROXMOX_PASSWORD=your_password_here

# Option 2: API token authentication (no timeout, recommended)
# Create a token in Proxmox UI: Datacenter -> Permissions -> API Tokens
# Format: user@realm!tokenid=uuid
# PROXMOX_API_TOKEN=root@pam!mcp-server=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

If your Proxmox instance uses a self-signed certificate, you may also want:

```bash
PROXMOX_VERIFY_SSL=false
```

For a complete list of all configuration options, see [Configuration Reference](configuration.md).

## 4. Choose Transport Mode

The server supports two transport modes depending on how your MCP client connects.

### stdio mode (default)

Use stdio mode for clients that launch the server as a subprocess, such as Claude Desktop and Claude Code.

```bash
uv run python run_server.py
```

No additional configuration is needed -- the client manages the server lifecycle.

### HTTP mode

Use HTTP mode for network-based clients like OpenWebUI, or when the server runs on a different machine than the client.

```bash
uv run python run_server.py --http
```

By default, HTTP mode binds to `127.0.0.1:8080` (localhost only). To expose it on the network:

```bash
uv run python run_server.py --http --host 0.0.0.0 --port 8080
```

When running HTTP mode with network access, enable authentication by setting an API key:

```bash
# Generate a secure API key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Add to your .env file
MCP_API_KEY=your_generated_key_here
```

See [Configuration Reference](configuration.md) for all HTTP and SSL options.

## 5. Connect to MCP Client

### Claude Desktop

Add the server to your Claude Desktop configuration file.

**Configuration file location:**

| OS      | Path                                                                 |
|---------|----------------------------------------------------------------------|
| macOS   | `~/Library/Application Support/Claude/claude_desktop_config.json`    |
| Linux   | `~/.config/Claude/claude_desktop_config.json`                        |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json`                        |

Add the following to the `mcpServers` section.

**Using PyPI (uvx) — recommended:**

```json
{
  "mcpServers": {
    "homelab": {
      "command": "uvx",
      "args": ["homelab-mcp"]
    }
  }
}
```

**Using source clone** (replace `/path/to/homelab_mcp` with your actual clone path):

```json
{
  "mcpServers": {
    "homelab": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/homelab_mcp", "python", "run_server.py"],
      "cwd": "/path/to/homelab_mcp"
    }
  }
}
```

Restart Claude Desktop after saving the file.

> **Tip:** If Claude Desktop cannot find `uv`, use the full path to the binary (e.g., `/Users/yourname/.local/bin/uv` on macOS or `/home/yourname/.local/bin/uv` on Linux).

### Claude Code

Create a `.mcp.json` file in your project root.

**Using PyPI (uvx) — recommended:**

```json
{
  "mcpServers": {
    "homelab": {
      "command": "uvx",
      "args": ["homelab-mcp"]
    }
  }
}
```

**Using source clone** (replace `/path/to/homelab_mcp` with your actual clone path):

```json
{
  "mcpServers": {
    "homelab": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/homelab_mcp", "python", "run_server.py"],
      "cwd": "/path/to/homelab_mcp"
    }
  }
}
```

Claude Code will detect the file automatically and connect to the server.

### HTTP clients (OpenWebUI)

When using HTTP mode, clients connect via the base URL:

```
http://localhost:8080/mcp/
```

If authentication is enabled, include the API key in requests:

```
Authorization: Bearer your_api_key_here
```

Consult your MCP client's documentation for where to configure the endpoint URL and authentication header.

## 6. Verify Installation

Once connected, ask your AI assistant to run a simple tool to confirm everything is working:

> "List available services" or "Show me the network sitemap"

These invoke the `list_available_services` and `get_network_sitemap` tools respectively.

A successful response from `list_available_services` looks like:

```
Available services: jellyfin, k3s, prometheus, grafana, pihole, ...
```

If you see a list of service names, the server is running correctly and connected to your MCP client.

See [Tool Reference](tool-reference.md) for the complete list of available tools.

## Troubleshooting

### "uv: command not found"

Ensure uv is on your PATH:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### "Connection refused" or Proxmox errors

1. Verify `PROXMOX_HOST` is correct and reachable: `ping $PROXMOX_HOST`
2. Check credentials: try logging into the Proxmox web UI with the same user/password
3. If using a self-signed certificate, set `PROXMOX_VERIFY_SSL=false` in your `.env`

### Claude Desktop does not show the server

1. Ensure the config JSON is valid (no trailing commas)
2. Verify the `cwd` path exists and contains `run_server.py`
3. Restart Claude Desktop completely (quit and reopen)
4. Check Claude Desktop logs for error messages
