# HTTP Service Setup Guide

This guide explains how to run the Homelab MCP Server as an HTTP service for use with OpenWebUI and other web-based MCP clients.

## Overview

The MCP server supports two transport modes:

1. **stdio mode** (default) - For Claude Desktop and other stdio-based clients
2. **HTTP mode** - For OpenWebUI and web-based clients using MCP Streamable HTTP transport

## Quick Start

### Generate an API Key

First, generate a secure API key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Save this key securely - you'll need it for configuration.

### Start the HTTP Server

```bash
# Basic HTTP mode with authentication
MCP_API_KEY="your-api-key-here" python run_server.py --http

# Custom host and port
MCP_API_KEY="your-api-key-here" python run_server.py --http --host 127.0.0.1 --port 9000

# Development mode (no authentication - NOT recommended for production)
python run_server.py --http --no-auth
```

### Verify the Server

```bash
# Health check (no auth required)
curl http://localhost:8080/health

# List tools (requires auth)
curl -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key-here" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_HTTP_ENABLED` | `false` | Enable HTTP mode by default |
| `MCP_HTTP_HOST` | `0.0.0.0` | HTTP server bind address |
| `MCP_HTTP_PORT` | `8080` | HTTP server port |
| `MCP_API_KEY` | (none) | API key for authentication |
| `MCP_AUTH_ENABLED` | `true` | Enable/disable authentication |

### Command Line Arguments

| Argument | Description |
|----------|-------------|
| `--http` | Run in HTTP mode |
| `--host HOST` | HTTP server host (default: 0.0.0.0) |
| `--port PORT` | HTTP server port (default: 8080) |
| `--no-auth` | Disable authentication (development only) |
| `--api-key KEY` | API key (alternative to MCP_API_KEY env var) |

## HTTP Endpoints

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/mcp` | POST | JSON-RPC 2.0 requests | Yes |
| `/mcp` | GET | SSE stream for notifications | Yes |
| `/health` | GET | Health check | No |
| `/` | GET | Service discovery info | No |

## OpenWebUI Configuration

1. Go to **Settings** > **Connections** > **MCP Servers** in OpenWebUI
2. Click **Add Server**
3. Configure:
   - **Name**: Homelab MCP
   - **Type**: MCP (Streamable HTTP)
   - **URL**: `http://<your-server-ip>:8080/mcp`
   - **Authorization**: Bearer Token
   - **Token**: Your MCP_API_KEY value

## Running as a Systemd Service

### 1. Create the Service User

```bash
sudo useradd -r -s /bin/false mcp
sudo mkdir -p /home/mcp/.mcp
sudo chown mcp:mcp /home/mcp/.mcp
```

### 2. Install the Application

```bash
sudo mkdir -p /opt/homelab-mcp
sudo cp -r . /opt/homelab-mcp/
cd /opt/homelab-mcp
sudo python -m venv .venv
sudo .venv/bin/pip install -e .
sudo chown -R mcp:mcp /opt/homelab-mcp
```

### 3. Create Environment File

```bash
sudo mkdir -p /etc/homelab-mcp
echo "MCP_API_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')" | sudo tee /etc/homelab-mcp/env
sudo chmod 600 /etc/homelab-mcp/env
```

### 4. Install the Service

```bash
sudo cp systemd/homelab-mcp.service /etc/systemd/system/
# Edit the service file to use EnvironmentFile=/etc/homelab-mcp/env
sudo systemctl daemon-reload
sudo systemctl enable homelab-mcp
sudo systemctl start homelab-mcp
```

### 5. Verify the Service

```bash
sudo systemctl status homelab-mcp
curl http://localhost:8080/health
```

### View Logs

```bash
sudo journalctl -u homelab-mcp -f
```

## Security Considerations

### API Key Security

- **Generate strong keys**: Use `secrets.token_urlsafe(32)` or similar
- **Store securely**: Use environment files with restricted permissions
- **Rotate regularly**: Update API keys periodically
- **Never commit**: Add API keys to `.gitignore`

### Network Security

- **Firewall**: Restrict access to trusted networks
- **HTTPS**: Use a reverse proxy (nginx, Caddy) for TLS in production
- **Local development**: Use `--host 127.0.0.1` to bind only to localhost

### Example Nginx Configuration

```nginx
server {
    listen 443 ssl http2;
    server_name mcp.example.com;

    ssl_certificate /etc/letsencrypt/live/mcp.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mcp.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;

        # SSE support
        proxy_read_timeout 86400;
        proxy_buffering off;
    }
}
```

## Troubleshooting

### Connection Refused

1. Check the server is running: `systemctl status homelab-mcp`
2. Verify the port is open: `ss -tlnp | grep 8080`
3. Check firewall rules: `sudo ufw status`

### Authentication Errors

1. Verify API key is set correctly
2. Check the Authorization header format: `Bearer <key>`
3. Review server logs for detailed error messages

### Tool Execution Fails

1. Check server logs: `journalctl -u homelab-mcp`
2. Verify SSH keys are configured correctly
3. Test the tool via CLI first: `python run_server.py` (stdio mode)

## Testing

Run the HTTP transport tests:

```bash
uv run pytest tests/test_http_transport.py -v
```

## API Reference

### JSON-RPC Methods

#### initialize

Initialize the MCP connection.

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize"
}
```

#### tools/list

List available tools.

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list"
}
```

#### tools/call

Execute a tool.

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "ssh_discover",
    "arguments": {
      "hostname": "192.168.1.100",
      "username": "admin"
    }
  }
}
```

#### health/status

Get server health status.

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "health/status"
}
```
