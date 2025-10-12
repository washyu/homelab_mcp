"""Pytest configuration for integration tests."""

import asyncio
import subprocess
import time
import pytest
from pathlib import Path


@pytest.fixture(scope="session")
def docker_client():
    """Create Docker client for managing test containers."""
    from .docker_client_factory import get_docker_client_or_skip

    return get_docker_client_or_skip()


@pytest.fixture(scope="session")
def test_container(docker_client):
    """Start and manage the test Ubuntu container."""
    project_root = Path(__file__).parent.parent.parent
    compose_file = project_root / "docker-compose.test.yml"

    # Start the container using docker-compose
    subprocess.run(
        ["docker-compose", "-f", str(compose_file), "up", "-d", "--build"],
        check=True,
        cwd=project_root,
    )

    # Wait for container to be ready
    container = docker_client.containers.get("mcp-test-ubuntu")

    # Wait for SSH to be ready with asyncssh (which is what our tools use)
    import asyncssh

    max_retries = 30
    ssh_ready = False

    for i in range(max_retries):
        try:

            async def test_ssh_connection():
                async with await asyncssh.connect(
                    host="localhost",
                    port=2222,
                    username="testadmin",
                    password="testpass123",
                    known_hosts=None,
                    connect_timeout=5,
                ) as conn:
                    await conn.run("whoami")
                    return True

            # Test the connection
            import asyncio

            result = asyncio.run(test_ssh_connection())
            if result:
                ssh_ready = True
                break
        except Exception as e:
            print(f"SSH connection attempt {i + 1}: {e}")
        time.sleep(2)

    if not ssh_ready:
        raise RuntimeError(
            "Container SSH service failed to start or respond to asyncssh connections"
        )

    yield {
        "container": container,
        "hostname": "localhost",
        "port": 2222,
        "admin_user": "testadmin",
        "admin_pass": "testpass123",
        "test_user": "testuser",
        "test_pass": "userpass123",
    }

    # Cleanup
    subprocess.run(
        ["docker-compose", "-f", str(compose_file), "down", "-v"], cwd=project_root
    )


@pytest.fixture
def clean_container(test_container):
    """Ensure container is in clean state before each test."""
    container = test_container["container"]

    # Kill any processes belonging to mcp_admin first
    container.exec_run("pkill -u mcp_admin || true", detach=False)

    # Remove mcp_admin user if it exists (without force flag to avoid permission issues)
    container.exec_run("userdel -r mcp_admin 2>/dev/null || true", detach=False)

    # Clean up any leftover home directory and ensure clean state
    container.exec_run("rm -rf /home/mcp_admin || true")
    container.exec_run("rm -f /etc/sudoers.d/mcp_admin || true")

    # Clean up SSH keys from testadmin
    container.exec_run("rm -rf /home/testadmin/.ssh/authorized_keys || true")
    container.exec_run("rm -rf /home/testadmin/.ssh/known_hosts || true")

    yield test_container


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
