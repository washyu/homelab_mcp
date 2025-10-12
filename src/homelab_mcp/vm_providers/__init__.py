"""VM provider factory and imports."""

from .base import VMProvider
from .docker_provider import DockerProvider
from .lxd_provider import LXDProvider


def get_vm_provider(platform: str) -> VMProvider:
    """Factory function to get the appropriate VM provider."""
    platform_lower = platform.lower()

    if platform_lower == "docker":
        return DockerProvider()
    elif platform_lower == "lxd":
        return LXDProvider()
    else:
        raise ValueError(f"Unsupported platform: {platform}")


__all__ = ["VMProvider", "DockerProvider", "LXDProvider", "get_vm_provider"]
