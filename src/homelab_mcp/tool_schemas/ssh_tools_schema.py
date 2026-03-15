"""Schema definitions for SSH-related tools."""

from typing import Any

SSH_TOOLS: dict[str, dict[str, Any]] = {
    "ssh_discover": {
        "description": "SSH into a system and gather hardware/system information. If credentials were stored with `credentials add`, username and password are auto-injected from the keyring — omit them.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "hostname": {"type": "string", "description": "Hostname or IP address"},
                "username": {
                    "type": "string",
                    "description": "SSH username. Omit if credentials were stored with `credentials add` — they are auto-injected.",
                },
                "password": {
                    "type": "string",
                    "description": "SSH password. Omit if credentials were stored with `credentials add` — they are auto-injected.",
                },
                "key_path": {
                    "type": "string",
                    "description": "Path to SSH private key",
                },
                "port": {
                    "type": "integer",
                    "description": "SSH port (default: 22)",
                    "default": 22,
                },
            },
            "required": ["hostname"],
        },
    },
    "setup_mcp_admin": {
        "description": "SSH into a remote system and setup mcp_admin user with admin permissions and SSH key access",
        "inputSchema": {
            "type": "object",
            "properties": {
                "hostname": {
                    "type": "string",
                    "description": "Hostname or IP address of the target system",
                },
                "username": {
                    "type": "string",
                    "description": "Admin username to connect with (must have sudo access)",
                },
                "password": {
                    "type": "string",
                    "description": "Password for the admin user",
                },
                "force_update_key": {
                    "type": "boolean",
                    "description": "Force update SSH key even if mcp_admin already has keys (default: true)",
                    "default": True,
                },
                "port": {
                    "type": "integer",
                    "description": "SSH port (default: 22)",
                    "default": 22,
                },
            },
            "required": ["hostname", "username", "password"],
        },
    },
    "verify_mcp_admin": {
        "description": "Verify SSH key access to mcp_admin account on a remote system",
        "inputSchema": {
            "type": "object",
            "properties": {
                "hostname": {
                    "type": "string",
                    "description": "Hostname or IP address of the target system",
                },
                "port": {
                    "type": "integer",
                    "description": "SSH port (default: 22)",
                    "default": 22,
                },
            },
            "required": ["hostname"],
        },
    },
    "ssh_execute_command": {
        "description": "Execute a command on a remote system via SSH. If credentials were stored with `credentials add`, username and password are auto-injected from the keyring — omit them.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "hostname": {"type": "string", "description": "Hostname or IP address"},
                "username": {
                    "type": "string",
                    "description": "SSH username. Omit if credentials were stored with `credentials add` — they are auto-injected.",
                },
                "password": {
                    "type": "string",
                    "description": "SSH password. Omit if credentials were stored with `credentials add` — they are auto-injected.",
                },
                "command": {
                    "type": "string",
                    "description": "Command to execute on the remote system",
                },
                "sudo": {
                    "type": "boolean",
                    "default": False,
                    "description": "Execute command with sudo privileges",
                },
                "port": {
                    "type": "integer",
                    "description": "SSH port (default: 22)",
                    "default": 22,
                },
            },
            "required": ["hostname", "command"],
        },
    },
    "start_interactive_shell": {
        "description": "Start an interactive web-based shell session on a remote system. Opens a browser-based terminal with full TTY support for running interactive commands and scripts. Perfect for Proxmox community scripts or any interactive command-line tools.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "hostname": {
                    "type": "string",
                    "description": "Hostname or IP address of the target system",
                },
                "username": {
                    "type": "string",
                    "description": "SSH username (optional, uses registered credentials if available)",
                },
                "password": {
                    "type": "string",
                    "description": "SSH password (optional, uses SSH keys if available)",
                },
                "port": {
                    "type": "integer",
                    "description": "SSH port (default: 22)",
                    "default": 22,
                },
                "initial_command": {
                    "type": "string",
                    "description": "Optional command to run automatically when shell starts (e.g., Proxmox script install command)",
                },
            },
            "required": ["hostname"],
        },
    },
    "update_mcp_admin_groups": {
        "description": "Update mcp_admin group memberships to include groups for installed services (docker, lxd, libvirt, kvm)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "hostname": {
                    "type": "string",
                    "description": "Hostname or IP address of the target system",
                },
                "username": {
                    "type": "string",
                    "description": "Admin username to connect with (must have sudo access)",
                },
                "password": {
                    "type": "string",
                    "description": "Password for the admin user",
                },
                "port": {
                    "type": "integer",
                    "description": "SSH port (default: 22)",
                    "default": 22,
                },
            },
            "required": ["hostname", "username", "password"],
        },
    },
}
