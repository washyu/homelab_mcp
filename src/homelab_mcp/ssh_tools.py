"""SSH tools for system discovery and management."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import asyncssh

from .credential_store import get_credential, list_credentials
from .database import get_database_adapter
from .error_handling import retry_on_failure, ssh_connection_wrapper
from .log_filter import sanitize_error
from .ssh_connection import ssh_connect

# Configure logging
logger = logging.getLogger(__name__)

# Get the path for storing SSH keys
SSH_KEY_DIR = Path.home() / ".ssh" / "mcp"


class CredentialNotFoundError(RuntimeError):
    """Raised when no credentials are found for a hostname in any tier."""

    pass


@dataclass
class SSHCredentials:
    """Resolved SSH credentials for connection."""

    hostname: str
    username: str
    port: int = 22
    key_path: str | None = None
    password: str | None = None
    credential_id: int | None = None  # Database ID if from stored credentials


def resolve_ssh_credentials(
    hostname: str,
    username: str | None = None,
    password: str | None = None,
    key_path: str | None = None,
    port: int = 22,
) -> SSHCredentials:
    """
    Resolve SSH credentials with priority order:
    1. Explicit credentials passed to function (backward compatible)
    2. Stored credentials from ssh_credentials table
    3. Default mcp_admin key (if username is mcp_admin or None)

    Args:
        hostname: Target hostname or IP
        username: SSH username (optional)
        password: SSH password (optional)
        key_path: Path to SSH key (optional)
        port: SSH port (default 22)

    Returns:
        SSHCredentials with resolved connection parameters
    """
    # If explicit password or key_path provided, use those (backward compatible)
    if password or key_path:
        return SSHCredentials(
            hostname=hostname,
            username=username or "mcp_admin",
            port=port,
            key_path=key_path,
            password=password,
        )

    # Tier 2: Keyring lookup (INJECT-01) — only runs when no explicit password/key_path
    registry_entries = list_credentials(credential_type="ssh")
    matched = [e for e in registry_entries if e["hostname"] == hostname]
    if matched:
        stored_username = matched[0]["username"]
        resolved_username = username or stored_username
        keyring_password = get_credential(hostname, stored_username, credential_type="ssh")
        if keyring_password:
            logger.debug("Auto-injected keyring credential for %s", hostname)
            return SSHCredentials(
                hostname=hostname,
                username=resolved_username,
                port=port,
                password=keyring_password,
            )
        logger.warning(
            "Credential desync for %s (user: %s): registry entry exists but keyring "
            "returned None — re-run 'homelab-mcp credentials add %s %s' to restore",
            hostname, stored_username, hostname, stored_username,
        )

    # Try to find stored credentials
    try:
        db = get_database_adapter()
        db.connect()
        db.init_schema()

        stored_cred = db.get_credential_by_hostname(hostname, username)
        db.close()

        if stored_cred:
            logger.debug(f"Found stored credentials for {hostname}")
            resolved_key_path = stored_cred.get("key_path")

            # If no key_path stored and username is mcp_admin, use default MCP key
            if not resolved_key_path and stored_cred.get("username") == "mcp_admin":
                mcp_key = get_mcp_ssh_key_path()
                if mcp_key.exists():
                    resolved_key_path = str(mcp_key)

            return SSHCredentials(
                hostname=hostname,
                username=stored_cred.get("username", "mcp_admin"),
                port=stored_cred.get("port", 22),
                key_path=resolved_key_path,
                credential_id=stored_cred.get("id"),
            )
    except Exception as e:
        logger.warning(f"Error looking up stored credentials: {e}")

    # Fall back to default mcp_admin key if available
    resolved_username = username or "mcp_admin"
    if resolved_username == "mcp_admin":
        mcp_key = get_mcp_ssh_key_path()
        if mcp_key.exists():
            return SSHCredentials(
                hostname=hostname,
                username=resolved_username,
                port=port,
                key_path=str(mcp_key),
            )

    raise CredentialNotFoundError(
        f"No credentials found for {hostname}. "
        "Run `homelab-mcp credentials add <hostname> <username>` in your terminal, "
        "or call the `register_server` MCP tool to store credentials."
    )


def get_mcp_ssh_key_path() -> Path:
    """Get the path to the MCP SSH private key."""
    return SSH_KEY_DIR / "mcp_admin_key"


async def ensure_mcp_ssh_key() -> str:
    """Ensure MCP SSH key exists, generate if not."""
    key_path = get_mcp_ssh_key_path()
    pub_key_path = Path(str(key_path) + ".pub")

    # Create directory if it doesn't exist
    SSH_KEY_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)

    # Check if key already exists
    if key_path.exists() and pub_key_path.exists():
        return str(key_path)

    # Generate new SSH key pair
    key = asyncssh.generate_private_key("ssh-rsa", key_size=2048, comment="mcp_admin@homelab")

    # Save private key
    key_path.write_bytes(key.export_private_key())
    key_path.chmod(0o600)

    # Save public key
    public_key = key.export_public_key().decode("utf-8")
    pub_key_path.write_text(public_key)
    pub_key_path.chmod(0o644)

    return str(key_path)


@ssh_connection_wrapper(timeout_seconds=30.0)
@retry_on_failure(max_retries=2, delay_seconds=2.0)
async def setup_remote_mcp_admin(
    hostname: str,
    username: str,
    password: str,
    force_update_key: bool = True,
    port: int = 22,
) -> str:
    """SSH into a remote system and setup mcp_admin user with SSH key access."""
    # First ensure we have a key
    key_path = await ensure_mcp_ssh_key()
    pub_key_path = Path(key_path + ".pub")

    # Read public key
    public_key = pub_key_path.read_text().strip()

    try:
        # Connect with admin credentials
        async with await ssh_connect(
            hostname=hostname,
            username=username,
            port=port,
            password=password,
        ) as conn:
            setup_results = {}

            # Check if mcp_admin user already exists
            user_check = await conn.run("id mcp_admin", check=False)
            user_exists = user_check.exit_status == 0

            if not user_exists:
                # Clean up any leftover home directory before creating user
                await conn.run("sudo rm -rf /home/mcp_admin", check=False)

                # Create mcp_admin user
                create_user = await conn.run("sudo useradd -m -s /bin/bash -G sudo mcp_admin", check=False)
                if create_user.exit_status != 0:
                    stderr_text = (
                        create_user.stderr.decode()
                        if isinstance(create_user.stderr, bytes)
                        else str(create_user.stderr)
                    )
                    setup_results["user_creation"] = f"Failed: {stderr_text}"
                else:
                    setup_results["user_creation"] = "Success: mcp_admin user created"
                    # Ensure proper ownership of home directory
                    await conn.run("sudo chown -R mcp_admin:mcp_admin /home/mcp_admin", check=False)
            else:
                setup_results["user_creation"] = "User already exists"

            # Ensure mcp_admin is in sudo group
            sudo_group = await conn.run("sudo usermod -a -G sudo mcp_admin", check=False)
            if sudo_group.exit_status == 0:
                setup_results["sudo_access"] = "Success: Added to sudo group"
            else:
                stderr_text = (
                    sudo_group.stderr.decode() if isinstance(sudo_group.stderr, bytes) else str(sudo_group.stderr)
                )
                setup_results["sudo_access"] = f"Failed: {stderr_text}"

            # Check if our key is already in authorized_keys
            key_check = await conn.run(
                f'sudo grep -F "{public_key}" /home/mcp_admin/.ssh/authorized_keys 2>/dev/null',
                check=False,
            )

            key_exists = key_check.exit_status == 0

            if key_exists and not force_update_key:
                setup_results["ssh_key"] = "SSH key already exists"
            else:
                # Setup SSH directory (more robust approach)
                # First ensure the home directory exists and has proper ownership
                await conn.run("sudo mkdir -p /home/mcp_admin", check=False)
                await conn.run("sudo chown mcp_admin:mcp_admin /home/mcp_admin", check=False)

                # Create .ssh directory as root, then change ownership
                mkdir_cmd = await conn.run(
                    "sudo mkdir -p /home/mcp_admin/.ssh && "
                    "sudo chown mcp_admin:mcp_admin /home/mcp_admin/.ssh && "
                    "sudo chmod 700 /home/mcp_admin/.ssh",
                    check=False,
                )

                if mkdir_cmd.exit_status != 0:
                    stderr_text = (
                        mkdir_cmd.stderr.decode() if isinstance(mkdir_cmd.stderr, bytes) else str(mkdir_cmd.stderr)
                    )
                    setup_results["ssh_key"] = f"Failed to create .ssh directory: {stderr_text}"
                else:
                    if force_update_key and key_exists:
                        # Remove old MCP keys (those with mcp_admin@ comment)
                        await conn.run(
                            'sudo grep -v "mcp_admin@" /home/mcp_admin/.ssh/authorized_keys | '
                            "sudo -u mcp_admin tee /home/mcp_admin/.ssh/authorized_keys.tmp && "
                            "sudo -u mcp_admin mv /home/mcp_admin/.ssh/authorized_keys.tmp /home/mcp_admin/.ssh/authorized_keys",
                            check=False,
                        )

                    # Add new key
                    add_key = await conn.run(
                        f'echo "{public_key}" | sudo -u mcp_admin tee -a /home/mcp_admin/.ssh/authorized_keys && '
                        "sudo -u mcp_admin chmod 600 /home/mcp_admin/.ssh/authorized_keys",
                        check=False,
                    )

                    if add_key.exit_status == 0:
                        if key_exists and force_update_key:
                            setup_results["ssh_key"] = "Success: SSH key updated"
                        else:
                            setup_results["ssh_key"] = "Success: SSH key installed"
                    else:
                        stderr_text = (
                            add_key.stderr.decode() if isinstance(add_key.stderr, bytes) else str(add_key.stderr)
                        )
                        setup_results["ssh_key"] = f"Failed: {stderr_text}"

            # Enable passwordless sudo for mcp_admin
            sudoers_setup = await conn.run(
                'echo "mcp_admin ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/mcp_admin',
                check=False,
            )

            if sudoers_setup.exit_status == 0:
                setup_results["passwordless_sudo"] = "Success: Passwordless sudo enabled"
            else:
                stderr_text = (
                    sudoers_setup.stderr.decode()
                    if isinstance(sudoers_setup.stderr, bytes)
                    else str(sudoers_setup.stderr)
                )
                setup_results["passwordless_sudo"] = f"Failed: {stderr_text}"

            # Test SSH key authentication
            test_conn = await conn.run("sudo -u mcp_admin whoami", check=False)
            if test_conn.exit_status == 0:
                setup_results["test_access"] = "Success: mcp_admin access verified"
            else:
                stderr_text = (
                    test_conn.stderr.decode() if isinstance(test_conn.stderr, bytes) else str(test_conn.stderr)
                )
                setup_results["test_access"] = f"Failed: {stderr_text}"

        return json.dumps(
            {
                "status": "success",
                "hostname": hostname,
                "mcp_admin_setup": setup_results,
                "ssh_key_path": key_path,
                "public_key": public_key,
            },
            indent=2,
        )

    except Exception as e:
        return json.dumps({"status": "error", "hostname": hostname, "error": sanitize_error(e)}, indent=2)


@ssh_connection_wrapper(timeout_seconds=15.0)
async def verify_mcp_admin_access(hostname: str, port: int = 22) -> str:
    """Verify SSH key access to mcp_admin account on remote system."""
    key_path = get_mcp_ssh_key_path()

    if not key_path.exists():
        return json.dumps(
            {
                "status": "error",
                "hostname": hostname,
                "error": "MCP SSH key not found. Run ensure_mcp_ssh_key() first.",
            },
            indent=2,
        )

    # Test SSH connection with key
    async with await ssh_connect(
        hostname=hostname,
        username="mcp_admin",
        port=port,
        key_path=str(key_path),
    ) as conn:
        # Test basic access
        whoami_result = await conn.run("whoami", check=False)
        if whoami_result.exit_status != 0:
            raise Exception("Failed to execute whoami command")

        # Test sudo access
        sudo_result = await conn.run("sudo -n whoami", check=False)
        sudo_access = sudo_result.exit_status == 0

        # Get system hostname
        hostname_result = await conn.run("hostname", check=False)
        remote_hostname = hostname
        if hostname_result.exit_status == 0 and hostname_result.stdout:
            remote_hostname = cast(str, hostname_result.stdout).strip()

        # Check group memberships
        groups_result = await conn.run("groups", check=False)
        user_groups = []
        if groups_result.exit_status == 0 and groups_result.stdout:
            groups_output = cast(str, groups_result.stdout).strip()
            # Parse groups output (format: "mcp_admin : mcp_admin sudo docker ...")
            if ":" in groups_output:
                user_groups = groups_output.split(":", 1)[1].strip().split()
            else:
                user_groups = groups_output.split()

        # Check which service groups the user belongs to
        service_groups = [g for g in user_groups if g in ["docker", "lxd", "libvirt", "kvm"]]

    return json.dumps(
        {
            "status": "success",
            "hostname": remote_hostname,
            "connection_ip": hostname,
            "mcp_admin": {
                "ssh_access": "Success: Connected with SSH key",
                "sudo_access": "Success: Passwordless sudo working" if sudo_access else "Failed: No sudo access",
                "username": cast(str, whoami_result.stdout).strip() if whoami_result.stdout else "unknown",
                "groups": user_groups,
                "service_groups": service_groups,
            },
        },
        indent=2,
    )


@ssh_connection_wrapper(timeout_seconds=30.0)
@retry_on_failure(max_retries=1, delay_seconds=1.0)
async def ssh_discover_system(
    hostname: str,
    username: str | None = None,
    password: str | None = None,
    key_path: str | None = None,
    port: int = 22,
) -> str:
    """SSH into a system and gather hardware/system information."""
    # Resolve credentials using priority order
    creds = resolve_ssh_credentials(
        hostname=hostname,
        username=username,
        password=password,
        key_path=key_path,
        port=port,
    )

    # Connect via SSH
    if not creds.key_path and not creds.password:
        raise ValueError(
            f"No credentials found for {hostname}. "
            "Store them with `credentials add` or pass password/key_path explicitly."
        )

    async with await ssh_connect(
        hostname=creds.hostname,
        username=creds.username,
        port=creds.port,
        password=creds.password,
        key_path=creds.key_path,
    ) as conn:
        system_info: dict[str, Any] = {}

        # Get actual hostname from the remote system
        hostname_result = await conn.run("hostname", check=False)
        actual_hostname = hostname  # Default to the IP/hostname we connected with
        if hostname_result.exit_status == 0 and hostname_result.stdout:
            actual_hostname = cast(str, hostname_result.stdout).strip()

            # Get CPU info
            cpu_info: dict[str, Any] = {}
            cpu_result = await conn.run("nproc", check=False)
            if cpu_result.exit_status == 0 and cpu_result.stdout:
                cpu_info["count"] = int(cast(str, cpu_result.stdout).strip())

            cpu_model_result = await conn.run('grep "model name" /proc/cpuinfo | head -1', check=False)
            if cpu_model_result.exit_status == 0 and cpu_model_result.stdout:
                model_line = cast(str, cpu_model_result.stdout).strip()
                if ":" in model_line:
                    cpu_info["model"] = model_line.split(":", 1)[1].strip()

            if cpu_info:
                system_info["cpu"] = cpu_info

            # Get memory info
            mem_result = await conn.run("free -b", check=False)
            if mem_result.exit_status == 0 and mem_result.stdout:
                lines = cast(str, mem_result.stdout).strip().split("\n")
                for line in lines:
                    if line.startswith("Mem:"):
                        parts = line.split()
                        if len(parts) >= 3:
                            system_info["memory"] = {
                                "total": int(parts[1]),
                                "used": int(parts[2]),
                            }
                            break

            # Get disk usage
            disk_result = await conn.run("df -B1 /", check=False)
            if disk_result.exit_status == 0 and disk_result.stdout:
                lines = cast(str, disk_result.stdout).strip().split("\n")
                if len(lines) > 1:
                    # Skip header, get data line
                    parts = lines[1].split()
                    if len(parts) >= 4:
                        system_info["disk"] = {
                            "total": int(parts[1]),
                            "used": int(parts[2]),
                            "available": int(parts[3]),
                        }

            # Get network interfaces
            network_info: list[dict[str, Any]] = []
            # Try modern ip command first
            ip_result = await conn.run("ip -j addr show 2>/dev/null", check=False)
            if ip_result.exit_status == 0 and ip_result.stdout:
                try:
                    interfaces = json.loads(cast(str, ip_result.stdout))
                    for iface in interfaces:
                        if iface.get("ifname") and iface["ifname"] != "lo":
                            iface_info = {
                                "name": iface["ifname"],
                                "state": iface.get("operstate", "unknown"),
                                "addresses": [],
                            }
                            for addr_info in iface.get("addr_info", []):
                                if addr_info.get("family") in ["inet", "inet6"]:
                                    iface_info["addresses"].append(addr_info.get("local"))
                            if iface_info["addresses"]:
                                network_info.append(iface_info)
                    system_info["network"] = network_info
                except json.JSONDecodeError:
                    # Fallback to basic parsing if JSON output not supported
                    logger.debug(
                        "JSON parsing failed for network interface data on %s, falling back to basic parsing", hostname
                    )

            # Get system uptime
            uptime_result = await conn.run("uptime -p", check=False)
            if uptime_result.exit_status == 0 and uptime_result.stdout:
                system_info["uptime"] = cast(str, uptime_result.stdout).strip()

            # Get OS information
            os_result = await conn.run("cat /etc/os-release | grep PRETTY_NAME", check=False)
            if os_result.exit_status == 0 and os_result.stdout:
                os_line = cast(str, os_result.stdout).strip()
                if "=" in os_line:
                    system_info["os"] = os_line.split("=", 1)[1].strip('"')

            # Get USB devices
            usb_devices: list[dict[str, str]] = []
            lsusb_result = await conn.run("lsusb 2>/dev/null", check=False)
            if lsusb_result.exit_status == 0 and lsusb_result.stdout:
                for line in cast(str, lsusb_result.stdout).strip().split("\n"):
                    if line:
                        # Parse lsusb output: Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub
                        parts = line.split(" ", 6)
                        if len(parts) >= 7:
                            usb_device_info = {
                                "bus": parts[1],
                                "device": parts[3].rstrip(":"),
                                "vendor_id": parts[5].split(":")[0],
                                "product_id": parts[5].split(":")[1],
                                "description": parts[6] if len(parts) > 6 else "Unknown",
                            }
                            usb_devices.append(usb_device_info)
            if usb_devices:
                system_info["usb_devices"] = usb_devices

            # Get PCI devices
            pci_devices: list[dict[str, str]] = []
            lspci_result = await conn.run("lspci 2>/dev/null", check=False)
            if lspci_result.exit_status == 0 and lspci_result.stdout:
                for line in cast(str, lspci_result.stdout).strip().split("\n"):
                    if line:
                        # Parse lspci output: 00:00.0 Host bridge: Intel Corporation Device 4660 (rev 02)
                        parts = line.split(" ", 2)
                        if len(parts) >= 3:
                            pci_device_info = {
                                "slot": parts[0],
                                "class": parts[1].rstrip(":"),
                                "description": parts[2],
                            }
                            # Identify important device types
                            if (
                                "network" in parts[1].lower()
                                or "ethernet" in parts[2].lower()
                                or "wireless" in parts[2].lower()
                            ):
                                pci_device_info["type"] = "network"
                            elif "vga" in parts[1].lower() or "display" in parts[1].lower():
                                pci_device_info["type"] = "graphics"
                            elif "usb" in parts[1].lower() or "usb" in parts[2].lower():
                                pci_device_info["type"] = "usb_controller"
                            elif "sata" in parts[1].lower() or "storage" in parts[1].lower():
                                pci_device_info["type"] = "storage"
                            pci_devices.append(pci_device_info)
            if pci_devices:
                system_info["pci_devices"] = pci_devices

            # Get block devices (drives)
            block_devices: list[dict[str, Any]] = []
            lsblk_result = await conn.run("lsblk -J -o NAME,SIZE,TYPE,MOUNTPOINT,MODEL 2>/dev/null", check=False)
            if lsblk_result.exit_status == 0 and lsblk_result.stdout:
                try:
                    lsblk_data = json.loads(cast(str, lsblk_result.stdout))
                    if "blockdevices" in lsblk_data:
                        for device in lsblk_data["blockdevices"]:
                            if device.get("type") == "disk":
                                block_device_info: dict[str, Any] = {
                                    "name": device.get("name"),
                                    "size": device.get("size"),
                                    "model": device.get("model", "Unknown"),
                                    "partitions": [],
                                }
                                # Add partition info if available
                                if "children" in device:
                                    for child in device["children"]:
                                        if child.get("type") == "part":
                                            partition_info = {
                                                "name": child.get("name"),
                                                "size": child.get("size"),
                                                "mountpoint": child.get("mountpoint"),
                                            }
                                            partitions_list = block_device_info.get("partitions", [])
                                            if isinstance(partitions_list, list):
                                                partitions_list.append(partition_info)
                                block_devices.append(block_device_info)
                except json.JSONDecodeError:
                    logger.debug("JSON parsing failed for block device data on %s", hostname)
            if block_devices:
                system_info["block_devices"] = block_devices

    return json.dumps(
        {
            "status": "success",
            "hostname": actual_hostname,
            "connection_ip": hostname,
            "data": system_info,
        },
        indent=2,
    )


@ssh_connection_wrapper(timeout_seconds=20.0)
async def ssh_execute_command(
    hostname: str,
    username: str | None = None,
    command: str = "",
    password: str | None = None,
    sudo: bool = False,
    port: int = 22,
    **kwargs: Any,
) -> str:
    """Execute a command on a remote system via SSH."""
    # Resolve credentials using priority order
    creds = resolve_ssh_credentials(
        hostname=hostname,
        username=username,
        password=password,
        port=port,
    )

    # Determine key path, falling back to mcp_admin key if needed
    resolved_key = creds.key_path
    if not resolved_key and not creds.password:
        if creds.username == "mcp_admin":
            mcp_key_path = await ensure_mcp_ssh_key()
            if mcp_key_path:
                resolved_key = mcp_key_path
        else:
            raise ValueError(
                f"No credentials found for {hostname}. Store them with `credentials add` or pass password explicitly."
            )

    async with await ssh_connect(
        hostname=creds.hostname,
        username=creds.username,
        port=creds.port,
        password=creds.password,
        key_path=resolved_key,
    ) as conn:
        # Prepare the command with sudo if requested
        if sudo:
            if creds.username == "mcp_admin":
                # mcp_admin has passwordless sudo
                full_command = f"sudo {command}"
            else:
                # Other users might need password for sudo
                full_command = f"echo '{creds.password}' | sudo -S {command}" if creds.password else f"sudo {command}"
        else:
            full_command = command

        # Execute the command
        result = await conn.run(full_command, check=False)

        output = []
        if result.stdout:
            stdout_text = result.stdout.decode() if isinstance(result.stdout, bytes) else str(result.stdout)
            output.append(f"Output:\n{stdout_text.strip()}")
        if result.stderr:
            stderr_text = result.stderr.decode() if isinstance(result.stderr, bytes) else str(result.stderr)
            output.append(f"Error:\n{stderr_text.strip()}")

    return json.dumps(
        {
            "status": "success",
            "hostname": hostname,
            "command": command,
            "exit_code": result.exit_status,
            "output": "\n\n".join(output) if output else "Command executed successfully (no output)",
        },
        indent=2,
    )


async def update_mcp_admin_groups(hostname: str, username: str, password: str, port: int = 22) -> str:
    """Update mcp_admin group memberships to include service management groups."""
    try:
        # Connect via SSH with admin credentials
        async with await ssh_connect(
            hostname=hostname,
            username=username,
            port=port,
            password=password,
        ) as conn:
            results: dict[str, Any] = {}

            # Check if mcp_admin user exists
            user_check = await conn.run("id mcp_admin", check=False)
            if user_check.exit_status != 0:
                return json.dumps(
                    {
                        "status": "error",
                        "hostname": hostname,
                        "error": "mcp_admin user does not exist. Run setup_mcp_admin first.",
                    },
                    indent=2,
                )

            # Get current groups
            current_groups_result = await conn.run("groups mcp_admin", check=False)
            current_groups = []
            if current_groups_result.exit_status == 0 and current_groups_result.stdout:
                groups_output = cast(str, current_groups_result.stdout).strip()
                # Parse groups output (format: "mcp_admin : mcp_admin sudo docker ...")
                if ":" in groups_output:
                    current_groups = groups_output.split(":", 1)[1].strip().split()
                else:
                    current_groups = groups_output.split()

            results["current_groups"] = current_groups

            # Check which services are installed and add to relevant groups
            service_checks = {
                "docker": "which docker",
                "lxd": "which lxc",
                "libvirt": "which virsh",
                "kvm": "test -e /dev/kvm",
            }

            available_services = []
            for service, check_cmd in service_checks.items():
                service_check = await conn.run(check_cmd, check=False)
                if service_check.exit_status == 0:
                    available_services.append(service)

            results["installed_services"] = available_services

            # Add mcp_admin to groups for installed services
            added_groups = []
            failed_groups = []
            skipped_groups = []

            for group in ["docker", "lxd", "libvirt", "kvm"]:
                # Skip if service not installed
                if group not in available_services:
                    skipped_groups.append(f"{group} (service not installed)")
                    continue

                # Check if group exists
                group_check = await conn.run(f"getent group {group}", check=False)
                if group_check.exit_status != 0:
                    skipped_groups.append(f"{group} (group doesn't exist)")
                    continue

                # Check if already in group
                if group in current_groups:
                    continue

                # Add user to group
                add_group = await conn.run(f"sudo usermod -a -G {group} mcp_admin", check=False)
                if add_group.exit_status == 0:
                    added_groups.append(group)
                else:
                    stderr_text = (
                        add_group.stderr.decode() if isinstance(add_group.stderr, bytes) else str(add_group.stderr)
                    )
                    failed_groups.append(f"{group}: {stderr_text}")

            # Get updated groups
            updated_groups_result = await conn.run("groups mcp_admin", check=False)
            updated_groups = []
            if updated_groups_result.exit_status == 0 and updated_groups_result.stdout:
                groups_output = cast(str, updated_groups_result.stdout).strip()
                if ":" in groups_output:
                    updated_groups = groups_output.split(":", 1)[1].strip().split()
                else:
                    updated_groups = groups_output.split()

            results["updated_groups"] = updated_groups
            results["added_groups"] = added_groups
            if failed_groups:
                results["failed_groups"] = failed_groups
            if skipped_groups:
                results["skipped_groups"] = skipped_groups

            # Test Docker access if docker group was added
            if "docker" in updated_groups:
                docker_test = await conn.run("sudo -u mcp_admin docker ps", check=False)
                if docker_test.exit_status == 0:
                    results["docker_access"] = "Success: mcp_admin can access Docker"
                else:
                    results["docker_access"] = "Failed: Docker access test failed (may need to logout/login)"

            return json.dumps(
                {
                    "status": "success",
                    "hostname": hostname,
                    "results": results,
                    "note": "User may need to logout and login again for group changes to take effect",
                },
                indent=2,
            )

    except Exception as e:
        return json.dumps({"status": "error", "hostname": hostname, "error": sanitize_error(e)}, indent=2)
    # This should never be reached, but mypy requires it
    return json.dumps(
        {"status": "error", "hostname": hostname, "error": "Unexpected execution path"},
        indent=2,
    )


# Server Registration Functions


async def register_server(
    hostname: str,
    username: str = "mcp_admin",
    key_path: str | None = None,
    port: int = 22,
    display_name: str | None = None,
    verify_connection: bool = True,
) -> str:
    """
    Register a server with SSH credentials for persistent access.

    Args:
        hostname: Hostname or IP address of the server
        username: SSH username (default: mcp_admin)
        key_path: Path to SSH private key (optional, uses default MCP key if None)
        port: SSH port (default: 22)
        display_name: Friendly name for the server (optional)
        verify_connection: Whether to verify SSH connection before saving

    Returns:
        JSON string with registration result
    """
    try:
        db = get_database_adapter()
        db.connect()
        db.init_schema()

        # Check if server already registered
        existing = db.get_credential_by_hostname(hostname, username)
        if existing:
            db.close()
            return json.dumps(
                {
                    "status": "error",
                    "error": f"Server {hostname} with username {username} is already registered",
                    "existing_id": existing.get("id"),
                },
                indent=2,
            )

        # Determine key path to use
        resolved_key_path = key_path
        if not resolved_key_path and username == "mcp_admin":
            mcp_key = get_mcp_ssh_key_path()
            if mcp_key.exists():
                resolved_key_path = str(mcp_key)

        # Optionally verify connection before saving
        last_verified = None
        if verify_connection and resolved_key_path:
            try:
                async with await ssh_connect(
                    hostname=hostname,
                    username=username,
                    port=port,
                    key_path=resolved_key_path,
                ) as conn:
                    result = await conn.run("hostname", check=False)
                    if result.exit_status == 0:
                        last_verified = "verified"
            except Exception as e:
                db.close()
                return json.dumps(
                    {
                        "status": "error",
                        "error": f"Connection verification failed: {e}",
                        "hostname": hostname,
                    },
                    indent=2,
                )

        # Add credential to database
        credential_id = db.add_credential(
            hostname=hostname,
            username=username,
            key_path=resolved_key_path,
            port=port,
            display_name=display_name,
        )

        if last_verified:
            db.update_last_verified(credential_id)

        db.close()

        return json.dumps(
            {
                "status": "success",
                "message": f"Server {hostname} registered successfully",
                "credential_id": credential_id,
                "hostname": hostname,
                "username": username,
                "port": port,
                "display_name": display_name,
                "key_path": resolved_key_path,
                "connection_verified": last_verified is not None,
            },
            indent=2,
        )

    except Exception as e:
        return json.dumps({"status": "error", "error": sanitize_error(e), "hostname": hostname}, indent=2)


def list_registered_servers(active_only: bool = True) -> str:
    """
    List all registered servers with their credentials.

    Args:
        active_only: Only show active servers (default: True)

    Returns:
        JSON string with list of registered servers
    """
    try:
        db = get_database_adapter()
        db.connect()
        db.init_schema()

        credentials = db.list_credentials(active_only=active_only)
        db.close()

        # Format for display
        servers = []
        for cred in credentials:
            servers.append(
                {
                    "id": cred.get("id"),
                    "hostname": cred.get("hostname"),
                    "username": cred.get("username"),
                    "port": cred.get("port"),
                    "display_name": cred.get("display_name"),
                    "is_active": bool(cred.get("is_active")),
                    "last_verified": cred.get("last_verified"),
                    "has_key": bool(cred.get("key_path")),
                    "device_id": cred.get("device_id"),
                }
            )

        return json.dumps(
            {
                "status": "success",
                "total_servers": len(servers),
                "servers": servers,
            },
            indent=2,
        )

    except Exception as e:
        return json.dumps({"status": "error", "error": sanitize_error(e)}, indent=2)


def update_server_credentials(
    credential_id: int | None = None,
    hostname: str | None = None,
    **kwargs: Any,
) -> str:
    """
    Update credentials for an existing registered server.

    Args:
        credential_id: ID of the credential to update (optional if hostname provided)
        hostname: Hostname to look up (optional if credential_id provided)
        **kwargs: Fields to update (username, key_path, port, display_name, is_active)

    Returns:
        JSON string with update result
    """
    try:
        db = get_database_adapter()
        db.connect()
        db.init_schema()

        # Find credential by ID or hostname
        if credential_id:
            cred = db.get_credential(credential_id)
        elif hostname:
            cred = db.get_credential_by_hostname(hostname)
            if cred:
                credential_id = cred.get("id")
        else:
            db.close()
            return json.dumps(
                {
                    "status": "error",
                    "error": "Must provide either credential_id or hostname",
                },
                indent=2,
            )

        if not cred:
            db.close()
            return json.dumps(
                {
                    "status": "error",
                    "error": "Credential not found",
                },
                indent=2,
            )

        # Update the credential
        assert credential_id is not None
        success = db.update_credential(credential_id, **kwargs)
        db.close()

        if success:
            return json.dumps(
                {
                    "status": "success",
                    "message": "Credential updated successfully",
                    "credential_id": credential_id,
                    "updated_fields": list(kwargs.keys()),
                },
                indent=2,
            )
        else:
            return json.dumps(
                {
                    "status": "error",
                    "error": "No fields updated",
                },
                indent=2,
            )

    except Exception as e:
        return json.dumps({"status": "error", "error": sanitize_error(e)}, indent=2)


def remove_server(
    credential_id: int | None = None,
    hostname: str | None = None,
) -> str:
    """
    Remove a server from the registered servers list.

    Args:
        credential_id: ID of the credential to remove (optional if hostname provided)
        hostname: Hostname to look up (optional if credential_id provided)

    Returns:
        JSON string with removal result
    """
    try:
        db = get_database_adapter()
        db.connect()
        db.init_schema()

        # Find credential by ID or hostname
        if credential_id:
            cred = db.get_credential(credential_id)
        elif hostname:
            cred = db.get_credential_by_hostname(hostname)
            if cred:
                credential_id = cred.get("id")
        else:
            db.close()
            return json.dumps(
                {
                    "status": "error",
                    "error": "Must provide either credential_id or hostname",
                },
                indent=2,
            )

        if not cred:
            db.close()
            return json.dumps(
                {
                    "status": "error",
                    "error": "Credential not found",
                },
                indent=2,
            )

        # Store info for response before deleting
        removed_hostname = cred.get("hostname")
        removed_username = cred.get("username")

        # Delete the credential
        assert credential_id is not None
        success = db.delete_credential(credential_id)
        db.close()

        if success:
            return json.dumps(
                {
                    "status": "success",
                    "message": f"Server {removed_hostname} removed successfully",
                    "credential_id": credential_id,
                    "hostname": removed_hostname,
                    "username": removed_username,
                },
                indent=2,
            )
        else:
            return json.dumps(
                {
                    "status": "error",
                    "error": "Failed to delete credential",
                },
                indent=2,
            )

    except Exception as e:
        return json.dumps({"status": "error", "error": sanitize_error(e)}, indent=2)
