# Quick Start Guide - Homelab MCP Server

## 🚀 Ready to Connect to Claude!

Your Homelab MCP Server is now fully built and ready to connect to Claude AI. You now have **23 powerful tools** for managing your homelab infrastructure through natural language.

## ✅ What's Built

### Infrastructure Management System
- **Complete CRUD operations** for infrastructure
- **VM/Container management** (Docker & LXD)
- **Network discovery and mapping**
- **Backup and rollback capabilities**
- **Real SSH automation** with passwordless access

### 23 MCP Tools Available
- 🔐 **4 SSH & Admin tools** - Device access and setup
- 🌐 **6 Network Discovery tools** - Scan and map your network
- 🏗️ **7 Infrastructure CRUD tools** - Deploy, update, scale services
- 🖥️ **6 VM Management tools** - Full container/VM lifecycle

## 🔧 Connect to Claude (2 Minutes)

### Step 1: Copy Configuration
```bash
# On macOS
cp claude_desktop_config.json ~/Library/Application\ Support/Claude/claude_desktop_config.json

# On Windows
copy claude_desktop_config.json %APPDATA%\Claude\claude_desktop_config.json

# On Linux
cp claude_desktop_config.json ~/.config/Claude/claude_desktop_config.json
```

### Step 2: Update Paths
Edit the config file and update the path to match your system:
```json
{
  "mcpServers": {
    "homelab": {
      "command": "python3",
      "args": ["/Users/shaun/workspace/mcp_python_server/run_server.py"],
      "env": {
        "PYTHONPATH": "/Users/shaun/workspace/mcp_python_server/src"
      }
    }
  }
}
```

### Step 3: Restart Claude Desktop
- Close Claude Desktop completely
- Reopen Claude Desktop
- Look for MCP connection indicator

## 🎯 Test Your Setup

Ask Claude:
> **"Hello! Can you test the MCP connection and show me what tools you have available?"**

You should see Claude respond with information about the 23 available tools.

## 🏠 Start Managing Your Homelab

### First Setup
> **"Set up MCP admin access on my Pi server at 192.168.1.100 using username 'pi' and password 'raspberry'"**

### Discover Your Network
> **"Scan and discover all devices on my network starting with my Pi server"**

### Deploy Something
> **"Deploy a nginx web server container on device 1 with port 80 exposed"**

### Monitor Infrastructure
> **"Show me all running containers and VMs across my infrastructure"**

### Create Backups
> **"Create a full backup of my infrastructure configuration"**

## 📚 Documentation

- **[CLAUDE_SETUP.md](CLAUDE_SETUP.md)** - Detailed Claude setup and usage examples
- **[README.md](README.md)** - Complete documentation of all 23 tools
- **Test your server**: Run `python3 test_mcp_connection.py`

## 🎉 What You Can Do Now

With your MCP server connected to Claude, you can:

### Infrastructure as Code
- **"Deploy a 3-tier web application across my devices"**
- **"Scale my web service to handle more traffic"**
- **"Migrate the database service to a more powerful device"**

### DevOps Operations
- **"Show me resource usage across all my devices"**
- **"Deploy a monitoring stack with Prometheus and Grafana"**
- **"Create automated backups of my critical services"**

### Network Management
- **"Analyze my network topology and suggest optimizations"**
- **"Set up a new device and add it to my infrastructure"**
- **"Show me the health status of all my services"**

## 🔒 Security Features

- SSH key-based authentication (no passwords stored)
- `mcp_admin` user with controlled sudo access
- Encrypted SSH communications
- Audit logging of all operations
- Backup and rollback capabilities for safety

## 🆘 Troubleshooting

**MCP not connecting?**
1. Check file paths in config
2. Run `python3 test_mcp_connection.py`
3. Restart Claude Desktop

**SSH access issues?**
> "Set up MCP admin access again on my device"

**Need help?**
> "Show me the status of the MCP connection and available tools"

---

**🎊 Congratulations! You now have a fully functional AI-powered homelab management system!**

Your infrastructure can now be managed through natural language conversations with Claude. Deploy services, scale applications, manage VMs, and monitor your entire homelab just by asking Claude what you want to do.
