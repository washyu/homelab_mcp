"""SSH tools for system discovery and management."""

import asyncio
import asyncssh
import json
import socket
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, cast

from .error_handling import ssh_connection_wrapper, retry_on_failure

# Configure logging
logger = logging.getLogger(__name__)

# Get the path for storing SSH keys
SSH_KEY_DIR = Path.home() / ".ssh" / "mcp"


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
    key = asyncssh.generate_private_key('ssh-rsa', key_size=2048, 
                                       comment='mcp_admin@homelab')
    
    # Save private key
    key_path.write_bytes(key.export_private_key())
    key_path.chmod(0o600)
    
    # Save public key
    public_key = key.export_public_key().decode('utf-8')
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
    port: int = 22
) -> str:
    """SSH into a remote system and setup mcp_admin user with SSH key access."""
    # First ensure we have a key
    key_path = await ensure_mcp_ssh_key()
    pub_key_path = Path(key_path + ".pub")
    
    # Read public key
    public_key = pub_key_path.read_text().strip()
    
    try:
        # Connect with admin credentials
        connect_kwargs = {
            "host": hostname,
            "port": port, 
            "username": username,
            "password": password,
            "known_hosts": None,
            "connect_timeout": 10
        }
        
        async with await asyncssh.connect(**connect_kwargs) as conn:
            setup_results = {}
            
            # Check if mcp_admin user already exists
            user_check = await conn.run('id mcp_admin', check=False)
            user_exists = user_check.exit_status == 0
            
            if not user_exists:
                # Clean up any leftover home directory before creating user
                await conn.run('sudo rm -rf /home/mcp_admin', check=False)
                
                # Create mcp_admin user
                create_user = await conn.run(
                    'sudo useradd -m -s /bin/bash -G sudo mcp_admin', 
                    check=False
                )
                if create_user.exit_status != 0:
                    setup_results['user_creation'] = f"Failed: {create_user.stderr}"
                else:
                    setup_results['user_creation'] = "Success: mcp_admin user created"
                    # Ensure proper ownership of home directory
                    await conn.run('sudo chown -R mcp_admin:mcp_admin /home/mcp_admin', check=False)
            else:
                setup_results['user_creation'] = "User already exists"
            
            # Ensure mcp_admin is in sudo group
            sudo_group = await conn.run('sudo usermod -a -G sudo mcp_admin', check=False)
            if sudo_group.exit_status == 0:
                setup_results['sudo_access'] = "Success: Added to sudo group"
            else:
                setup_results['sudo_access'] = f"Failed: {sudo_group.stderr}"
            
            # Check if our key is already in authorized_keys
            key_check = await conn.run(
                f'sudo grep -F "{public_key}" /home/mcp_admin/.ssh/authorized_keys 2>/dev/null',
                check=False
            )
            
            key_exists = key_check.exit_status == 0
            
            if key_exists and not force_update_key:
                setup_results['ssh_key'] = "SSH key already exists"
            else:
                # Setup SSH directory (more robust approach)
                # First ensure the home directory exists and has proper ownership
                await conn.run('sudo mkdir -p /home/mcp_admin', check=False)
                await conn.run('sudo chown mcp_admin:mcp_admin /home/mcp_admin', check=False)
                
                # Create .ssh directory as root, then change ownership
                mkdir_cmd = await conn.run(
                    'sudo mkdir -p /home/mcp_admin/.ssh && '
                    'sudo chown mcp_admin:mcp_admin /home/mcp_admin/.ssh && '
                    'sudo chmod 700 /home/mcp_admin/.ssh',
                    check=False
                )
                
                if mkdir_cmd.exit_status != 0:
                    setup_results['ssh_key'] = f"Failed to create .ssh directory: {mkdir_cmd.stderr}"
                else:
                    if force_update_key and key_exists:
                        # Remove old MCP keys (those with mcp_admin@ comment)
                        await conn.run(
                            'sudo grep -v "mcp_admin@" /home/mcp_admin/.ssh/authorized_keys | '
                            'sudo -u mcp_admin tee /home/mcp_admin/.ssh/authorized_keys.tmp && '
                            'sudo -u mcp_admin mv /home/mcp_admin/.ssh/authorized_keys.tmp /home/mcp_admin/.ssh/authorized_keys',
                            check=False
                        )
                        
                    # Add new key
                    add_key = await conn.run(
                        f'echo "{public_key}" | sudo -u mcp_admin tee -a /home/mcp_admin/.ssh/authorized_keys && '
                        'sudo -u mcp_admin chmod 600 /home/mcp_admin/.ssh/authorized_keys',
                        check=False
                    )
                    
                    if add_key.exit_status == 0:
                        if key_exists and force_update_key:
                            setup_results['ssh_key'] = "Success: SSH key updated"
                        else:
                            setup_results['ssh_key'] = "Success: SSH key installed"
                    else:
                        setup_results['ssh_key'] = f"Failed: {add_key.stderr}"
            
            # Enable passwordless sudo for mcp_admin
            sudoers_setup = await conn.run(
                'echo "mcp_admin ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/mcp_admin',
                check=False
            )
            
            if sudoers_setup.exit_status == 0:
                setup_results['passwordless_sudo'] = "Success: Passwordless sudo enabled"
            else:
                setup_results['passwordless_sudo'] = f"Failed: {sudoers_setup.stderr}"
            
            # Test SSH key authentication
            test_conn = await conn.run('sudo -u mcp_admin whoami', check=False)
            if test_conn.exit_status == 0:
                setup_results['test_access'] = "Success: mcp_admin access verified"
            else:
                setup_results['test_access'] = f"Failed: {test_conn.stderr}"
        
        return json.dumps({
            "status": "success",
            "hostname": hostname,
            "mcp_admin_setup": setup_results,
            "ssh_key_path": key_path,
            "public_key": public_key
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            "status": "error",
            "hostname": hostname,
            "error": str(e)
        }, indent=2)


@ssh_connection_wrapper(timeout_seconds=15.0)
async def verify_mcp_admin_access(hostname: str, port: int = 22) -> str:
    """Verify SSH key access to mcp_admin account on remote system."""
    key_path = get_mcp_ssh_key_path()
    
    if not key_path.exists():
        return json.dumps({
            "status": "error",
            "hostname": hostname,
            "error": "MCP SSH key not found. Run ensure_mcp_ssh_key() first."
        }, indent=2)
    
    # Test SSH connection with key
    connect_kwargs = {
        "host": hostname,
        "port": port,
        "username": "mcp_admin",
        "client_keys": [str(key_path)],
        "known_hosts": None,
        "connect_timeout": 10
    }
    
    async with await asyncssh.connect(**connect_kwargs) as conn:
        # Test basic access
        whoami_result = await conn.run('whoami', check=False)
        if whoami_result.exit_status != 0:
            raise Exception("Failed to execute whoami command")
        
        # Test sudo access
        sudo_result = await conn.run('sudo -n whoami', check=False)
        sudo_access = sudo_result.exit_status == 0
        
        # Get system hostname
        hostname_result = await conn.run('hostname', check=False)
        remote_hostname = hostname
        if hostname_result.exit_status == 0 and hostname_result.stdout:
            remote_hostname = cast(str, hostname_result.stdout).strip()
        
        # Check group memberships
        groups_result = await conn.run('groups', check=False)
        user_groups = []
        if groups_result.exit_status == 0 and groups_result.stdout:
            groups_output = cast(str, groups_result.stdout).strip()
            # Parse groups output (format: "mcp_admin : mcp_admin sudo docker ...")
            if ':' in groups_output:
                user_groups = groups_output.split(':', 1)[1].strip().split()
            else:
                user_groups = groups_output.split()
        
        # Check which service groups the user belongs to
        service_groups = [g for g in user_groups if g in ['docker', 'lxd', 'libvirt', 'kvm']]
        
    return json.dumps({
        "status": "success",
        "hostname": remote_hostname,
        "connection_ip": hostname,
        "mcp_admin": {
            "ssh_access": "Success: Connected with SSH key",
            "sudo_access": "Success: Passwordless sudo working" if sudo_access else "Failed: No sudo access",
            "username": cast(str, whoami_result.stdout).strip() if whoami_result.stdout else "unknown",
            "groups": user_groups,
            "service_groups": service_groups
        }
    }, indent=2)


@ssh_connection_wrapper(timeout_seconds=30.0)
@retry_on_failure(max_retries=1, delay_seconds=1.0)
async def ssh_discover_system(
    hostname: str, 
    username: str, 
    password: Optional[str] = None, 
    key_path: Optional[str] = None,
    port: int = 22
) -> str:
    """SSH into a system and gather hardware/system information."""
    # Connect via SSH
    connect_kwargs = {
        "host": hostname,
        "port": port,
        "username": username,
        "known_hosts": None,
        "connect_timeout": 10
    }
    
    if key_path:
        connect_kwargs["client_keys"] = [key_path]
    elif password:
        connect_kwargs["password"] = password
    elif username == "mcp_admin":
        # Use MCP key for mcp_admin user if available
        mcp_key_path = get_mcp_ssh_key_path()
        if mcp_key_path.exists():
            connect_kwargs["client_keys"] = [str(mcp_key_path)]
        else:
            raise ValueError("MCP SSH key not found and no password provided for mcp_admin")
    else:
        raise ValueError("Either password or key_path must be provided")
    
    async with await asyncssh.connect(**connect_kwargs) as conn:
        system_info = {}
        
        # Get actual hostname from the remote system
        hostname_result = await conn.run('hostname', check=False)
        actual_hostname = hostname  # Default to the IP/hostname we connected with
        if hostname_result.exit_status == 0 and hostname_result.stdout:
            actual_hostname = cast(str, hostname_result.stdout).strip()
            
            # Get CPU info
            cpu_info = {}
            cpu_result = await conn.run('nproc', check=False)
            if cpu_result.exit_status == 0 and cpu_result.stdout:
                cpu_info['count'] = int(cast(str, cpu_result.stdout).strip())
            
            cpu_model_result = await conn.run('grep "model name" /proc/cpuinfo | head -1', check=False)
            if cpu_model_result.exit_status == 0 and cpu_model_result.stdout:
                model_line = cast(str, cpu_model_result.stdout).strip()
                if ':' in model_line:
                    cpu_info['model'] = model_line.split(':', 1)[1].strip()
            
            if cpu_info:
                system_info['cpu'] = cpu_info
            
            # Get memory info
            mem_result = await conn.run('free -b', check=False)
            if mem_result.exit_status == 0 and mem_result.stdout:
                lines = cast(str, mem_result.stdout).strip().split('\n')
                for line in lines:
                    if line.startswith('Mem:'):
                        parts = line.split()
                        if len(parts) >= 3:
                            system_info['memory'] = {
                                'total': int(parts[1]),
                                'used': int(parts[2])
                            }
                            break
            
            # Get disk usage
            disk_result = await conn.run('df -B1 /', check=False)
            if disk_result.exit_status == 0 and disk_result.stdout:
                lines = cast(str, disk_result.stdout).strip().split('\n')
                if len(lines) > 1:
                    # Skip header, get data line
                    parts = lines[1].split()
                    if len(parts) >= 4:
                        system_info['disk'] = {
                            'total': int(parts[1]),
                            'used': int(parts[2]),
                            'available': int(parts[3])
                        }
            
            # Get network interfaces
            network_info = []
            # Try modern ip command first
            ip_result = await conn.run('ip -j addr show 2>/dev/null', check=False)
            if ip_result.exit_status == 0 and ip_result.stdout:
                try:
                    interfaces = json.loads(cast(str, ip_result.stdout))
                    for iface in interfaces:
                        if iface.get('ifname') and iface['ifname'] != 'lo':
                            iface_info = {
                                'name': iface['ifname'],
                                'state': iface.get('operstate', 'unknown'),
                                'addresses': []
                            }
                            for addr_info in iface.get('addr_info', []):
                                if addr_info.get('family') in ['inet', 'inet6']:
                                    iface_info['addresses'].append(addr_info.get('local'))
                            if iface_info['addresses']:
                                network_info.append(iface_info)
                    system_info['network'] = network_info
                except json.JSONDecodeError:
                    # Fallback to basic parsing if JSON output not supported
                    pass
            
            # Get system uptime
            uptime_result = await conn.run('uptime -p', check=False)
            if uptime_result.exit_status == 0 and uptime_result.stdout:
                system_info['uptime'] = cast(str, uptime_result.stdout).strip()
            
            # Get OS information
            os_result = await conn.run('cat /etc/os-release | grep PRETTY_NAME', check=False)
            if os_result.exit_status == 0 and os_result.stdout:
                os_line = cast(str, os_result.stdout).strip()
                if '=' in os_line:
                    system_info['os'] = os_line.split('=', 1)[1].strip('"')
            
            # Get USB devices
            usb_devices = []
            lsusb_result = await conn.run('lsusb 2>/dev/null', check=False)
            if lsusb_result.exit_status == 0 and lsusb_result.stdout:
                for line in cast(str, lsusb_result.stdout).strip().split('\n'):
                    if line:
                        # Parse lsusb output: Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub
                        parts = line.split(' ', 6)
                        if len(parts) >= 7:
                            device_info = {
                                'bus': parts[1],
                                'device': parts[3].rstrip(':'),
                                'vendor_id': parts[5].split(':')[0],
                                'product_id': parts[5].split(':')[1],
                                'description': parts[6] if len(parts) > 6 else 'Unknown'
                            }
                            usb_devices.append(device_info)
            if usb_devices:
                system_info['usb_devices'] = usb_devices
            
            # Get PCI devices
            pci_devices = []
            lspci_result = await conn.run('lspci 2>/dev/null', check=False)
            if lspci_result.exit_status == 0 and lspci_result.stdout:
                for line in cast(str, lspci_result.stdout).strip().split('\n'):
                    if line:
                        # Parse lspci output: 00:00.0 Host bridge: Intel Corporation Device 4660 (rev 02)
                        parts = line.split(' ', 2)
                        if len(parts) >= 3:
                            device_info = {
                                'slot': parts[0],
                                'class': parts[1].rstrip(':'),
                                'description': parts[2]
                            }
                            # Identify important device types
                            if 'network' in parts[1].lower() or 'ethernet' in parts[2].lower() or 'wireless' in parts[2].lower():
                                device_info['type'] = 'network'
                            elif 'vga' in parts[1].lower() or 'display' in parts[1].lower():
                                device_info['type'] = 'graphics'
                            elif 'usb' in parts[1].lower() or 'usb' in parts[2].lower():
                                device_info['type'] = 'usb_controller'
                            elif 'sata' in parts[1].lower() or 'storage' in parts[1].lower():
                                device_info['type'] = 'storage'
                            pci_devices.append(device_info)
            if pci_devices:
                system_info['pci_devices'] = pci_devices
            
            # Get block devices (drives)
            block_devices = []
            lsblk_result = await conn.run('lsblk -J -o NAME,SIZE,TYPE,MOUNTPOINT,MODEL 2>/dev/null', check=False)
            if lsblk_result.exit_status == 0 and lsblk_result.stdout:
                try:
                    lsblk_data = json.loads(cast(str, lsblk_result.stdout))
                    if 'blockdevices' in lsblk_data:
                        for device in lsblk_data['blockdevices']:
                            if device.get('type') == 'disk':
                                device_info = {
                                    'name': device.get('name'),
                                    'size': device.get('size'),
                                    'model': device.get('model', 'Unknown'),
                                    'partitions': []
                                }
                                # Add partition info if available
                                if 'children' in device:
                                    for child in device['children']:
                                        if child.get('type') == 'part':
                                            device_info['partitions'].append({
                                                'name': child.get('name'),
                                                'size': child.get('size'),
                                                'mountpoint': child.get('mountpoint')
                                            })
                                block_devices.append(device_info)
                except json.JSONDecodeError:
                    pass
            if block_devices:
                system_info['block_devices'] = block_devices
        
    return json.dumps({
        "status": "success",
        "hostname": actual_hostname,
        "connection_ip": hostname,
        "data": system_info
    }, indent=2)


@ssh_connection_wrapper(timeout_seconds=20.0)
async def ssh_execute_command(
    hostname: str,
    username: str,
    command: str,
    password: Optional[str] = None,
    sudo: bool = False,
    port: int = 22,
    **kwargs
) -> str:
    """Execute a command on a remote system via SSH."""
    ssh_key_path = None
    client_keys = []
    
    # Use MCP admin key if username is mcp_admin
    if username == 'mcp_admin':
        mcp_key_path = await ensure_mcp_ssh_key()
        if mcp_key_path:
            client_keys = [mcp_key_path]
    
    # Prepare connection options
    connect_kwargs = {
        'host': hostname,
        'port': port,
        'username': username,
        'known_hosts': None
    }
    
    if client_keys:
        connect_kwargs['client_keys'] = client_keys
    
    if password:
        connect_kwargs['password'] = password
    
    async with asyncssh.connect(**connect_kwargs) as conn:
        # Prepare the command with sudo if requested
        if sudo:
            if username == 'mcp_admin':
                # mcp_admin has passwordless sudo
                full_command = f"sudo {command}"
            else:
                # Other users might need password for sudo
                full_command = f"echo '{password}' | sudo -S {command}" if password else f"sudo {command}"
        else:
            full_command = command
        
        # Execute the command
        result = await conn.run(full_command, check=False)
        
        output = []
        if result.stdout:
            output.append(f"Output:\n{result.stdout.strip()}")
        if result.stderr:
            output.append(f"Error:\n{result.stderr.strip()}")
        
    return json.dumps({
        "status": "success",
        "hostname": hostname,
        "command": command,
        "exit_code": result.exit_status,
        "output": "\n\n".join(output) if output else "Command executed successfully (no output)"
    }, indent=2)


async def update_mcp_admin_groups(
    hostname: str,
    username: str,
    password: str,
    port: int = 22
) -> str:
    """Update mcp_admin group memberships to include service management groups."""
    try:
        # Connect via SSH with admin credentials
        connect_kwargs = {
            "host": hostname,
            "port": port,
            "username": username,
            "password": password,
            "known_hosts": None,
            "connect_timeout": 10
        }
        
        async with await asyncssh.connect(**connect_kwargs) as conn:
            results = {}
            
            # Check if mcp_admin user exists
            user_check = await conn.run('id mcp_admin', check=False)
            if user_check.exit_status != 0:
                return json.dumps({
                    "status": "error",
                    "hostname": hostname,
                    "error": "mcp_admin user does not exist. Run setup_mcp_admin first."
                }, indent=2)
            
            # Get current groups
            current_groups_result = await conn.run('groups mcp_admin', check=False)
            current_groups = []
            if current_groups_result.exit_status == 0 and current_groups_result.stdout:
                groups_output = cast(str, current_groups_result.stdout).strip()
                # Parse groups output (format: "mcp_admin : mcp_admin sudo docker ...")
                if ':' in groups_output:
                    current_groups = groups_output.split(':', 1)[1].strip().split()
                else:
                    current_groups = groups_output.split()
            
            results['current_groups'] = current_groups
            
            # Check which services are installed and add to relevant groups
            service_checks = {
                'docker': 'which docker',
                'lxd': 'which lxc',
                'libvirt': 'which virsh',
                'kvm': 'test -e /dev/kvm'
            }
            
            available_services = []
            for service, check_cmd in service_checks.items():
                service_check = await conn.run(check_cmd, check=False)
                if service_check.exit_status == 0:
                    available_services.append(service)
            
            results['installed_services'] = available_services
            
            # Add mcp_admin to groups for installed services
            added_groups = []
            failed_groups = []
            skipped_groups = []
            
            for group in ['docker', 'lxd', 'libvirt', 'kvm']:
                # Skip if service not installed
                if group not in available_services:
                    skipped_groups.append(f"{group} (service not installed)")
                    continue
                
                # Check if group exists
                group_check = await conn.run(f'getent group {group}', check=False)
                if group_check.exit_status != 0:
                    skipped_groups.append(f"{group} (group doesn't exist)")
                    continue
                
                # Check if already in group
                if group in current_groups:
                    continue
                
                # Add user to group
                add_group = await conn.run(f'sudo usermod -a -G {group} mcp_admin', check=False)
                if add_group.exit_status == 0:
                    added_groups.append(group)
                else:
                    failed_groups.append(f"{group}: {add_group.stderr}")
            
            # Get updated groups
            updated_groups_result = await conn.run('groups mcp_admin', check=False)
            updated_groups = []
            if updated_groups_result.exit_status == 0 and updated_groups_result.stdout:
                groups_output = cast(str, updated_groups_result.stdout).strip()
                if ':' in groups_output:
                    updated_groups = groups_output.split(':', 1)[1].strip().split()
                else:
                    updated_groups = groups_output.split()
            
            results['updated_groups'] = updated_groups
            results['added_groups'] = added_groups
            if failed_groups:
                results['failed_groups'] = failed_groups
            if skipped_groups:
                results['skipped_groups'] = skipped_groups
            
            # Test Docker access if docker group was added
            if 'docker' in updated_groups:
                docker_test = await conn.run('sudo -u mcp_admin docker ps', check=False)
                if docker_test.exit_status == 0:
                    results['docker_access'] = "Success: mcp_admin can access Docker"
                else:
                    results['docker_access'] = "Failed: Docker access test failed (may need to logout/login)"
            
            return json.dumps({
                "status": "success",
                "hostname": hostname,
                "results": results,
                "note": "User may need to logout and login again for group changes to take effect"
            }, indent=2)
            
    except Exception as e:
        return json.dumps({
            "status": "error",
            "hostname": hostname,
            "error": str(e)
        }, indent=2)