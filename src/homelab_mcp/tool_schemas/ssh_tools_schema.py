"""Schema definitions for SSH-related tools."""

from typing import Any

SSH_TOOLS: dict[str, dict[str, Any]] = {
    "ssh_discover": {
        "description": "SSH into a system and gather hardware/system information. If credentials were stored with `credentials add`, username and password are auto-injected from the keyring — omit them. If authentication fails with 'No credentials found', run `homelab-mcp credentials add <hostname> <username>` in the terminal or call `list_keyring_credentials` to see what is already stored. Recommended follow-up after onboarding: run the configure_host_fingerprint prompt to capture per-host capability signals for drift detection.",
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
    "ssh_execute_command": {
        "description": "Execute a command on a remote system via SSH. If credentials were stored with `credentials add`, username and password are auto-injected from the keyring — omit them. If authentication fails with 'No credentials found', run `homelab-mcp credentials add <hostname> <username>` in the terminal or call `list_keyring_credentials` to see what is already stored.",
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
                "background": {
                    "type": "boolean",
                    "default": False,
                    "description": (
                        "Run the command as a background job and return a job_id immediately "
                        "instead of waiting for completion. Use for long-running commands "
                        "(installs, upgrades, builds) that could exceed the client timeout. "
                        "Poll get_background_job with the returned job_id for status and output."
                    ),
                },
            },
            "required": ["hostname", "command"],
        },
    },
    "get_background_job": {
        "description": (
            "Get the status and result of a background job started by ssh_execute_command "
            "with background=true. Returns status (running/completed/failed/cancelled) and, "
            "once finished, the command output. Omit job_id to list all jobs."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "Job ID returned when the job was started. Omit to list all jobs.",
                },
            },
            "required": [],
        },
    },
    "cancel_background_job": {
        "description": "Cancel a running background job started by ssh_execute_command with background=true.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "Job ID to cancel"},
            },
            "required": ["job_id"],
        },
    },
    "start_interactive_shell": {
        "description": "Start an interactive web-based shell session on a remote system. Opens a browser-based terminal with full TTY support for running interactive commands and scripts. Perfect for Proxmox community scripts or any interactive command-line tools. Requires HTTP server mode (--http flag). In stdio mode, this tool returns an error with setup instructions.",
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
}
