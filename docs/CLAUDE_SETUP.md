# Connecting Your Homelab MCP Server to Claude

This guide explains how to connect your Homelab MCP Server to Claude AI for managing your infrastructure through natural language.

## What You Can Do

Once connected, you can ask Claude to:

### Infrastructure Management
- **"Deploy a new nginx container on device 1"**
- **"List all VMs running on my Pi server"**
- **"Scale up the web service to 3 replicas"**
- **"Create a backup of my infrastructure"**
- **"Show me the status of all Docker containers"**

### Network Discovery
- **"Scan my network and show me all devices"**
- **"What's the CPU usage on my home server?"**
- **"Set up SSH access on my new Pi"**
- **"Analyze my network topology"**

### VM/Container Operations
- **"Start the database container on device 2"**
- **"Get logs from the nginx container"**
- **"Deploy an Ubuntu VM using LXD"**
- **"Remove the test containers"**

## Setup Methods

### Option 1: Claude Desktop App (Recommended)

1. **Install Claude Desktop** from [claude.ai](https://claude.ai/download)

2. **Copy the configuration file** to Claude's config directory:

   **On macOS:**
   ```bash
   cp claude_desktop_config.json ~/Library/Application\ Support/Claude/claude_desktop_config.json
   ```

   **On Windows:**
   ```cmd
   copy claude_desktop_config.json %APPDATA%\Claude\claude_desktop_config.json
   ```

   **On Linux:**
   ```bash
   cp claude_desktop_config.json ~/.config/Claude/claude_desktop_config.json
   ```

3. **Update the path** in the config file to match your installation:
   ```json
   {
     "mcpServers": {
       "homelab": {
         "command": "python3",
         "args": ["/YOUR/ACTUAL/PATH/homelab_mcp/run_server.py"],
         "env": {
           "PYTHONPATH": "/YOUR/ACTUAL/PATH/homelab_mcp/src"
         }
       }
     }
   }
   ```

4. **Restart Claude Desktop**

5. **Verify Connection**: You should see an MCP icon in Claude's interface indicating the server is connected

### Option 2: Claude Web with Local Bridge (Advanced)

For Claude web interface, you'll need a local bridge:

1. **Install the Claude MCP Bridge** (if available) or use a WebSocket bridge
2. **Configure the bridge** to connect to your MCP server
3. **Start both** the MCP server and bridge

## Initial Setup Workflow

### 1. Prepare Your Infrastructure

First, make sure your homelab devices are accessible:

```bash
# Test SSH access to your devices
ssh user@192.168.1.100
```

### 2. Set Up MCP Admin Access

Ask Claude to set up passwordless access:

> "Set up MCP admin access on my Pi server at 192.168.1.100 using username 'pi' and password 'raspberry'"

This will:
- Create the `mcp_admin` user
- Install SSH keys for passwordless access
- Grant sudo privileges

### 3. Discover Your Network

> "Scan and discover all devices on my network starting with 192.168.1.100"

### 4. Start Managing Infrastructure

> "Show me all the devices you've discovered"
> "Deploy a nginx container on device 1 with port 80 exposed"
> "List all running containers across my infrastructure"

## Available Tools (23 Total)

### SSH & Admin Tools (4)
- `hello_world` - Test connection
- `ssh_discover` - Discover system information
- `setup_mcp_admin` - Set up passwordless SSH access
- `verify_mcp_admin` - Verify SSH access

### Network Discovery Tools (6)
- `discover_and_map` - Discover and catalog devices
- `bulk_discover_and_map` - Discover multiple devices
- `get_network_sitemap` - Get all discovered devices
- `analyze_network_topology` - Analyze network structure
- `suggest_deployments` - Get deployment recommendations
- `get_device_changes` - Track device changes

### Infrastructure CRUD Tools (7)
- `deploy_infrastructure` - Deploy new services
- `update_device_config` - Modify device configurations
- `decommission_device` - Safely remove devices
- `scale_services` - Scale services up/down
- `validate_infrastructure_changes` - Validate before applying
- `create_infrastructure_backup` - Create backups
- `rollback_infrastructure_changes` - Rollback changes

### VM Management Tools (6)
- `deploy_vm` - Deploy new VMs/containers
- `control_vm` - Start/stop/restart VMs
- `get_vm_status` - Get VM status details
- `list_vms` - List all VMs on devices
- `get_vm_logs` - Get VM/container logs
- `remove_vm` - Remove VMs/containers

## Example Conversations

### Deploy a Web Server
```
You: "Deploy a nginx web server on my main server"

Claude: I'll deploy an nginx container for you. First, let me check your available devices.

[Claude calls list_devices and shows your infrastructure]

I'll deploy nginx on device 1.

[Claude calls deploy_vm with nginx configuration]

✅ Successfully deployed nginx container 'web-server' on device 1
- Container ID: abc123def456
- Image: nginx:latest
- Ports: 80:80 (accessible at http://192.168.1.100)
- Status: Running
```

### Scale Services
```
You: "I need to scale up my web service to handle more traffic"

Claude: I'll help you scale up your web service. Let me check the current setup first.

[Claude calls get_vm_status and list_vms]

I can see you have nginx running. I'll scale it up by deploying additional instances with load balancing.

[Claude calls deploy_infrastructure with scaling plan]

✅ Scaled web service to 3 replicas:
- web-server-1: Running on device 1 (port 8001)
- web-server-2: Running on device 2 (port 8002)
- web-server-3: Running on device 1 (port 8003)
- Load balancer: Configured automatically
```

### Infrastructure Backup
```
You: "Create a backup of my entire infrastructure"

Claude: I'll create a comprehensive backup of your infrastructure.

[Claude calls create_infrastructure_backup]

✅ Infrastructure backup created successfully
- Backup ID: backup_20240125_143022_abc12345
- Scope: Full infrastructure
- Devices backed up: 3
- Services included: 7 containers, 2 VMs
- Size: 2.3 MB
- Location: /tmp/infrastructure_backup_20240125_143022_abc12345.json

Your backup includes:
- All device configurations
- Container/VM definitions
- Network settings
- Service states
```

## Troubleshooting

### MCP Server Not Connecting
1. **Check the path** in claude_desktop_config.json
2. **Verify Python dependencies** are installed
3. **Test the server manually**:
   ```bash
   cd /path/to/homelab_mcp
   python3 run_server.py
   # Should start without errors
   ```

### SSH Access Issues
1. **Verify network connectivity**:
   ```bash
   ping 192.168.1.100
   ```
2. **Test SSH manually**:
   ```bash
   ssh mcp_admin@192.168.1.100
   ```
3. **Re-run setup** if needed:
   > "Set up MCP admin access again on device 192.168.1.100"

### Permission Errors
1. **Check sudo access** for mcp_admin user
2. **Verify SSH key** is properly installed
3. **Check file permissions** on the MCP server

## Security Notes

- The MCP server uses SSH keys for authentication
- All operations are logged for audit purposes
- The `mcp_admin` user has sudo privileges but uses key-based auth only
- Network communications are encrypted via SSH
- Consider firewall rules for additional security

## Advanced Usage

### Custom VM Configurations
```
You: "Deploy a development environment with Ubuntu 22.04, 4GB RAM, and Docker pre-installed"

Claude: [Deploys LXD VM with custom configuration]
```

### Multi-Device Deployments
```
You: "Deploy a 3-tier application across my devices - database on device 1, API on device 2, and frontend on device 3"

Claude: [Orchestrates multi-device deployment with networking]
```

### Monitoring and Alerts
```
You: "Show me the health status of all my services and alert me if anything is down"

Claude: [Checks all services and provides comprehensive status report]
```

## Next Steps

1. **Connect Claude** using the setup instructions above
2. **Test basic functionality** with "hello world"
3. **Set up MCP admin** on your first device
4. **Start managing** your infrastructure with natural language!

The MCP server provides a powerful interface for managing your homelab through AI. You can deploy services, manage VMs, monitor infrastructure, and perform complex operations just by asking Claude in natural language.
