"""
Factory for creating Docker clients with fallback support.
This module handles various Docker SDK import issues.
"""

import sys
import subprocess


def create_docker_client():
    """Create a Docker client with robust error handling."""

    # Method 1: Try standard import
    try:
        import docker

        if hasattr(docker, "from_env"):
            return docker.from_env()
    except (ImportError, AttributeError):
        pass

    # Method 2: Try direct import from docker package
    try:
        from docker import DockerClient

        return DockerClient.from_env()
    except (ImportError, AttributeError):
        pass

    # Method 3: Try importing docker.client directly
    try:
        import docker.client

        return docker.client.from_env()
    except (ImportError, AttributeError):
        pass

    # Method 4: Try subprocess approach (last resort)
    try:
        # Check if docker command exists
        subprocess.run(["docker", "--version"], capture_output=True, check=True)

        # If we get here, Docker CLI exists but SDK doesn't work
        # Try to install it
        print("Docker CLI found but Python SDK missing. Trying to install...")
        subprocess.run([sys.executable, "-m", "pip", "install", "docker"], check=True)

        # Try again after installation
        import docker

        return docker.from_env()

    except (subprocess.CalledProcessError, ImportError):
        pass

    # If all methods fail, return None
    return None


def get_docker_client_or_skip():
    """Get Docker client or raise pytest.skip with helpful message."""
    import pytest

    client = create_docker_client()
    if client is None:
        pytest.skip(
            "Docker not available. Install Docker and Docker SDK:\n"
            "1. Install Docker: https://docs.docker.com/get-docker/\n"
            "2. Install Docker SDK: pip install docker\n"
            "3. Make sure Docker daemon is running"
        )

    return client
