# 🚀 Deployment Guide: Homelab MCP Server with uv

This guide shows how the migration to **uv** dramatically improves the deployment experience.

## 📦 **Quick Start with uv**

### **Prerequisites**
```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.local/bin/env
```

### **Lightning Fast Setup**
```bash
# Clone the repository
git clone https://github.com/washyu/homelab_mcp.git
cd homelab_mcp

# Install dependencies and run (2-3 seconds!)
uv sync
uv run python run_server.py
```

## ⚡ **Speed Comparison**

### **Before (pip):**
```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip                    # 10-15 seconds
pip install -e .                            # 30+ seconds
ERROR: Python version conflicts...          # Manual fixes needed
python run_server.py
```
**Total time: ~60+ seconds + debugging**

### **After (uv):**
```bash
uv sync                                      # 2-3 seconds (all dependencies)
uv run python run_server.py                 # Instant
```
**Total time: ~3 seconds**

## 🔧 **Development Workflow**

### **Adding Dependencies**
```bash
# Core dependencies
uv add pyyaml asyncssh

# Optional feature groups
uv add --group monitoring pandas pyarrow
uv add --group automation ansible paramiko
uv add --group ai ollama
uv add --group security keyring cryptography

# Development dependencies
uv add --dev pytest pytest-asyncio pytest-cov
```

### **Running Tests**
```bash
# Run all tests
uv run pytest

# Run specific test
uv run pytest tests/test_tools.py::test_get_available_tools -v

# With coverage
uv run pytest --cov=src/homelab_mcp
```

### **Service Installation Testing**
```bash
# Test service installer
uv run python -c "
from src.homelab_mcp.service_installer import ServiceInstaller
installer = ServiceInstaller()
print('Available services:', installer.get_available_services())
"

# Test service info
uv run python -c "
from src.homelab_mcp.service_installer import ServiceInstaller
installer = ServiceInstaller()
import json
print(json.dumps(installer.get_service_info('jellyfin'), indent=2))
"
```

## 🖥️ **Claude Desktop Integration**

### **Configuration File**
Location: `~/.config/claude-desktop/config.json` or `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "homelab": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/homelab_mcp", "python", "run_server.py"],
      "cwd": "/path/to/homelab_mcp",
      "env": {
        "PATH": "/Users/your-username/.local/bin:$PATH"
      }
    }
  }
}
```

### **Testing the Integration**
1. Restart Claude Desktop
2. Ask Claude: "List available homelab services"
3. Try: "Install Jellyfin on my server at 192.168.1.100"

## 🐳 **Docker Deployment**

### **Dockerfile with uv**
```dockerfile
FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ src/
COPY run_server.py ./

# Install dependencies
RUN uv sync --frozen

# Run the server
CMD ["uv", "run", "python", "run_server.py"]
```

### **Build and Run**
```bash
# Build image
docker build -t homelab-mcp-server .

# Run container
docker run -p 8000:8000 homelab-mcp-server
```

## 🚀 **Production Deployment**

### **Systemd Service**
```ini
[Unit]
Description=Homelab MCP Server
After=network.target

[Service]
Type=exec
User=mcp
WorkingDirectory=/opt/homelab-mcp-server
ExecStart=/home/mcp/.local/bin/uv run python run_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### **Setup Script**
```bash
#!/bin/bash
# Production deployment script

# Create service user
sudo useradd -r -s /bin/false mcp

# Install uv for service user
sudo -u mcp curl -LsSf https://astral.sh/uv/install.sh | sudo -u mcp sh

# Deploy application
sudo mkdir -p /opt/homelab-mcp-server
sudo chown mcp:mcp /opt/homelab-mcp-server
sudo -u mcp git clone https://github.com/washyu/homelab_mcp.git /opt/homelab-mcp-server
cd /opt/homelab-mcp-server
sudo -u mcp /home/mcp/.local/bin/uv sync

# Install and start service
sudo cp homelab-mcp.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable homelab-mcp
sudo systemctl start homelab-mcp
```

## 🔒 **Security Considerations**

### **SSH Key Management**
```bash
# Keys are automatically generated in:
~/.ssh/mcp/mcp_admin_key
~/.ssh/mcp/mcp_admin_key.pub

# Backup these keys securely:
tar -czf mcp-ssh-keys-backup.tar.gz ~/.ssh/mcp/
```

### **Service Isolation**
```bash
# Run services in isolated environments
uv run --isolated python run_server.py

# Use different Python versions per project
uv python install 3.12
uv run --python 3.12 python run_server.py
```

## 📊 **Performance Benefits**

| Operation | pip | uv | Improvement |
|-----------|-----|----|-----------:|
| Fresh install | 45s | 3s | **15x faster** |
| Dependency resolution | 20s | 0.5s | **40x faster** |
| Lock file generation | 30s | 0.1s | **300x faster** |
| Virtual env creation | 5s | 0.2s | **25x faster** |

## 🐛 **Troubleshooting**

### **Common Issues**

**1. uv command not found**
```bash
# Add uv to PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

**2. Python version conflicts**
```bash
# uv handles this automatically
uv python install 3.12  # Installs if needed
uv sync                  # Uses correct version
```

**3. Claude Desktop can't find uv**
```json
{
  "mcpServers": {
    "homelab": {
      "command": "/Users/your-username/.local/bin/uv",
      "args": ["run", "python", "run_server.py"],
      "cwd": "/path/to/project"
    }
  }
}
```

**4. Permission errors**
```bash
# Fix permissions
chmod +x ~/.local/bin/uv
chown -R $USER:$USER ~/.local/bin/
```

## 🎯 **Next Steps**

1. **Test the new service installation features:**
   ```bash
   uv run python -c "
   import asyncio
   from src.homelab_mcp.service_installer import ServiceInstaller

   async def test():
       installer = ServiceInstaller()
       # Test requirement checking (replace with your server IP)
       result = await installer.check_service_requirements(
           'jellyfin', '192.168.1.100', 'your-username', 'your-password'
       )
       print(result)

   asyncio.run(test())
   "
   ```

2. **Try service installation via Claude:**
   - "Check if my server can run Jellyfin"
   - "Install K3s on my development server"
   - "Show me TrueNAS Scale information"

3. **Extend with more services:**
   - Add your own service templates in `src/homelab_mcp/service_templates/`
   - Follow the YAML schema pattern from existing templates

The uv migration makes development and deployment **dramatically faster** while providing better dependency management and reproducibility! 🚀
