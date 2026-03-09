"""
Proxmox Community Scripts integration.

Provides access to the community-scripts/ProxmoxVE GitHub repository
for discovering and using Proxmox installation scripts.
"""

import logging
import re
from typing import Any

import aiohttp

from .log_filter import sanitize_error

logger = logging.getLogger(__name__)

# GitHub API base URLs
GITHUB_API_BASE = "https://api.github.com/repos/community-scripts/ProxmoxVE"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/community-scripts/ProxmoxVE/main"

# Cache for script listings (avoid hitting GitHub API repeatedly)
_script_cache: dict[str, list[dict[str, Any]]] = {}
_cache_ttl = 3600  # 1 hour


async def _fetch_github_api(url: str) -> dict[str, Any] | list[dict[str, Any]]:
    """Fetch data from GitHub API."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.json()  # type: ignore[no-any-return]


async def _fetch_script_content(category: str, script_name: str) -> str:
    """Fetch the raw content of a script."""
    url = f"{GITHUB_RAW_BASE}/{category}/{script_name}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.text()


def _parse_script_metadata(content: str) -> dict[str, Any]:
    """
    Parse metadata from script content.

    Proxmox scripts define metadata using environment variables with defaults:
    var_tags="${var_tags:-automation;smarthome}"
    var_cpu="${var_cpu:-2}"
    var_ram="${var_ram:-2048}"
    var_disk="${var_disk:-16}"
    var_os="${var_os:-debian}"
    var_version="${var_version:-12}"
    """
    metadata = {}

    # Extract variable definitions
    var_pattern = r'var_(\w+)="\$\{var_\w+:-([^}]+)\}"'
    matches = re.findall(var_pattern, content)

    for var_name, default_value in matches:
        if var_name == "tags":
            # Tags are semicolon-separated
            metadata["tags"] = default_value.split(";")
        elif var_name in ["cpu", "ram", "disk"]:
            # Numeric values
            try:
                metadata[var_name] = int(default_value)
            except ValueError:
                metadata[var_name] = default_value
        else:
            metadata[var_name] = default_value

    # Extract description from comments (if present)
    # Look for lines starting with # near the top
    lines = content.split("\n")[:20]  # Check first 20 lines
    description_lines = []
    for line in lines:
        if line.strip().startswith("#") and not line.strip().startswith("#!"):
            # Remove # and extra spaces
            desc = line.strip().lstrip("#").strip()
            if desc and not desc.startswith("Copyright") and not desc.startswith("License"):
                description_lines.append(desc)

    if description_lines:
        metadata["description"] = " ".join(description_lines)

    return metadata


async def get_script_categories() -> list[str]:
    """Get available script categories."""
    return ["ct", "vm", "install", "misc"]


async def list_scripts_in_category(category: str) -> list[dict[str, Any]]:
    """
    List all scripts in a specific category.

    Args:
        category: The category (ct, vm, install, misc)

    Returns:
        List of script information dictionaries
    """
    # Check cache first
    cache_key = f"list_{category}"
    if cache_key in _script_cache:
        logger.debug(f"Using cached script list for category: {category}")
        return _script_cache[cache_key]

    logger.info(f"Fetching script list for category: {category}")

    try:
        # Fetch from GitHub API
        url = f"{GITHUB_API_BASE}/contents/{category}"
        contents = await _fetch_github_api(url)

        if not isinstance(contents, list):
            return []

        scripts = []
        for item in contents:
            if item["type"] == "file" and item["name"].endswith(".sh"):
                scripts.append(
                    {
                        "name": item["name"],
                        "path": item["path"],
                        "download_url": item["download_url"],
                        "size": item["size"],
                        "category": category,
                    }
                )

        # Cache the results
        _script_cache[cache_key] = scripts

        return scripts

    except Exception as e:
        logger.error(f"Error fetching scripts for category {category}: {str(e)}")
        return []


async def search_scripts(
    query: str,
    category: str | None = None,
    include_metadata: bool = False,
) -> list[dict[str, Any]]:
    """
    Search for Proxmox community scripts.

    Args:
        query: Search query (matches script name or tags)
        category: Optional category filter (ct, vm, install, misc)
        include_metadata: If True, fetch and parse script metadata (slower)

    Returns:
        List of matching scripts with their information
    """
    logger.info(f"Searching for scripts: query={query}, category={category}")

    # Determine which categories to search
    if category:
        categories = [category]
    else:
        categories = await get_script_categories()

    # Collect all scripts from requested categories
    all_scripts = []
    for cat in categories:
        scripts = await list_scripts_in_category(cat)
        all_scripts.extend(scripts)

    # Filter by query
    query_lower = query.lower()
    matching_scripts = []

    for script in all_scripts:
        script_name_lower = script["name"].lower()

        # Check if query matches script name
        if query_lower in script_name_lower.replace(".sh", "").replace("-", " "):
            matching_scripts.append(script)
            continue

        # If including metadata, also check tags
        if include_metadata:
            try:
                content = await _fetch_script_content(script["category"], script["name"])
                metadata = _parse_script_metadata(content)

                # Check tags
                tags = metadata.get("tags", [])
                if any(query_lower in tag.lower() for tag in tags):
                    script["metadata"] = metadata
                    matching_scripts.append(script)
            except Exception as e:
                logger.debug(f"Could not fetch metadata for {script['name']}: {str(e)}")

    logger.info(f"Found {len(matching_scripts)} matching scripts")
    return matching_scripts


async def get_script_details(
    script_name: str,
    category: str | None = None,
) -> dict[str, Any] | None:
    """
    Get detailed information about a specific script.

    Args:
        script_name: Name of the script (e.g., "homeassistant.sh")
        category: Optional category hint (speeds up search)

    Returns:
        Script details including metadata, or None if not found
    """
    logger.info(f"Getting details for script: {script_name}")

    # If category provided, search only that category
    if category:
        categories = [category]
    else:
        categories = await get_script_categories()

    # Find the script
    for cat in categories:
        scripts = await list_scripts_in_category(cat)
        for script in scripts:
            if script["name"] == script_name:
                # Found it - fetch metadata
                try:
                    content = await _fetch_script_content(cat, script_name)
                    metadata = _parse_script_metadata(content)

                    return {
                        **script,
                        "metadata": metadata,
                        "content_preview": content[:500],  # First 500 chars
                    }
                except Exception as e:
                    logger.error(f"Error fetching script details: {str(e)}")
                    return script

    return None


async def execute_proxmox_script(
    hostname: str,
    script_name: str,
    username: str = "root",
    password: str | None = None,
    port: int = 22,
    category: str | None = None,
    config: dict[str, Any] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Execute a Proxmox community script on a remote host via SSH.

    Args:
        hostname: Proxmox host IP or hostname
        script_name: Name of the script to execute (e.g., "podman.sh")
        username: SSH username (default: root)
        password: SSH password (if not using keys)
        port: SSH port (default: 22)
        category: Optional category hint (ct, vm, install, misc)
        config: Optional configuration overrides (e.g., {"var_cpu": 4, "var_ram": 4096})
        dry_run: If True, show what would be executed without running it

    Returns:
        Execution result with status, output, and any errors
    """
    from .ssh_tools import ssh_execute_command

    logger.info(f"Executing Proxmox script '{script_name}' on {hostname}")

    # Get script details first
    script_details = await get_script_details(script_name, category)
    if not script_details:
        return {
            "status": "error",
            "message": f"Script '{script_name}' not found",
        }

    download_url = script_details["download_url"]
    metadata = script_details.get("metadata", {})

    # Build environment variable exports
    env_vars = []
    if config:
        for key, value in config.items():
            # Ensure var_ prefix
            if not key.startswith("var_"):
                key = f"var_{key}"
            env_vars.append(f'export {key}="{value}"')

    # Build the execution command
    env_prefix = "\n".join(env_vars) + "\n" if env_vars else ""
    exec_command = f'{env_prefix}bash -c "$(wget -qO- {download_url})"'

    if dry_run:
        return {
            "status": "dry_run",
            "script": script_name,
            "download_url": download_url,
            "metadata": metadata,
            "command": exec_command,
            "message": "Dry run - command not executed",
        }

    try:
        # Execute via SSH using existing infrastructure
        logger.info(f"Executing '{script_name}' on {hostname}...")

        output = await ssh_execute_command(
            hostname=hostname,
            username=username,
            password=password,
            port=port,
            command=exec_command,
            sudo=False,  # Script handles its own sudo if needed
        )

        return {
            "status": "success",
            "script": script_name,
            "output": output,
            "message": f"Script '{script_name}' executed successfully",
        }

    except Exception as e:
        logger.error(f"Error executing script on {hostname}: {str(e)}")
        return {
            "status": "error",
            "script": script_name,
            "message": f"Execution failed: {sanitize_error(e)}",
        }
