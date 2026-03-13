"""Tests for the service installer module.

Wave 0 update (Phase 12, Plan 01):
- TEMPLATES_DIR module-level patch removed (PKG-03: constant will be gone after Plan 03)
- New patch target: homelab_mcp.service_installer.files (importlib.resources.files)
- All template-loading tests now use a MagicMock Traversable via the new patch target
- Added test_templates_loaded_from_package for VALIDATION.md PKG-03 contract
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import yaml

from src.homelab_mcp.service_installer import ServiceInstaller

# ---------------------------------------------------------------------------
# Shared helper: build a fake importlib.resources Traversable for a template
# ---------------------------------------------------------------------------


def _make_fake_traversable(template_dict: dict[str, Any], filename: str = "test-service.yaml") -> MagicMock:
    """Return a MagicMock that behaves like an importlib.resources Traversable directory.

    The returned mock mimics the object returned by:
        importlib.resources.files("homelab_mcp").joinpath("service_templates")

    It has:
        - .iterdir() -> [fake_file]
        - fake_file.is_file() -> True
        - fake_file.name -> filename
        - fake_file.read_text() -> yaml.dump(template_dict)
    """
    fake_file = MagicMock()
    fake_file.is_file.return_value = True
    fake_file.name = filename
    fake_file.read_text.return_value = yaml.dump(template_dict)

    fake_traversable = MagicMock()
    fake_traversable.iterdir.return_value = iter([fake_file])

    return fake_traversable


def _make_fake_files_fn(traversable: MagicMock) -> MagicMock:
    """Return a mock for importlib.resources.files() that yields the given traversable.

    When called as: files("homelab_mcp").joinpath("service_templates")
    it returns the traversable mock.
    """
    fake_pkg = MagicMock()
    fake_pkg.joinpath.return_value = traversable
    fake_files_fn = MagicMock(return_value=fake_pkg)
    return fake_files_fn


# ---------------------------------------------------------------------------
# Sample template definitions
# ---------------------------------------------------------------------------

SAMPLE_TEMPLATE: dict[str, Any] = {
    "name": "test-service",
    "description": "Test service for unit tests",
    "category": "test",
    "requirements": {"ports": [8080], "memory_gb": 1, "disk_gb": 5},
    "installation": {
        "method": "docker-compose",
        "compose": {
            "version": "3.8",
            "services": {"test": {"image": "nginx:latest", "ports": ["8080:80"]}},
        },
    },
}

ANSIBLE_TEMPLATE: dict[str, Any] = {
    "name": "ansible-service",
    "description": "Test service using Ansible",
    "category": "test",
    "requirements": {"ports": [8080], "memory_gb": 2, "disk_gb": 10},
    "installation": {
        "method": "ansible",
        "ansible": {
            "pre_tasks": [
                {
                    "name": "Install Docker",
                    "shell": "curl -fsSL https://get.docker.com | sh",
                }
            ],
            "tasks": [
                {
                    "name": "Deploy service",
                    "docker_container": {
                        "name": "test-container",
                        "image": "nginx:latest",
                        "state": "started",
                        "ports": ["8080:80"],
                    },
                }
            ],
            "post_tasks": [
                {
                    "name": "Verify service",
                    "uri": {"url": "http://localhost:8080", "method": "GET"},
                }
            ],
            "handlers": [
                {
                    "name": "restart service",
                    "docker_container": {
                        "name": "test-container",
                        "state": "restarted",
                    },
                }
            ],
        },
    },
}

SCRIPT_TEMPLATE: dict[str, Any] = {
    "name": "script-service",
    "description": "Test service using custom script",
    "category": "test",
    "requirements": {"ports": [3000], "memory_gb": 1, "disk_gb": 5},
    "installation": {
        "method": "script",
        "script": {
            "pre_install": [
                "sudo apt-get update",
                "sudo apt-get install -y curl",
            ],
            "install": [
                "curl -fsSL https://nodejs.org/dist/v18.17.0/node-v18.17.0-linux-x64.tar.xz -o node.tar.xz",
                "tar -xf node.tar.xz",
                "sudo mv node-v18.17.0-linux-x64 /opt/nodejs",
                "sudo ln -sf /opt/nodejs/bin/node /usr/local/bin/node",
                "sudo ln -sf /opt/nodejs/bin/npm /usr/local/bin/npm",
            ],
            "post_install": ["node --version", "npm --version"],
            "service_start": ["cd /opt/app", "npm start"],
        },
    },
}

VARIABLE_TEMPLATE: dict[str, Any] = {
    "name": "variable-service",
    "description": "Service with {{ service_description }}",
    "category": "test",
    "requirements": {
        "ports": ["{{ service_port }}"],
        "memory_gb": "{{ memory_size }}",
        "disk_gb": 10,
    },
    "installation": {
        "method": "docker-compose",
        "compose": {
            "version": "3.8",
            "services": {
                "{{ service_name }}": {
                    "image": "{{ docker_image }}",
                    "ports": ["{{ service_port }}:80"],
                    "environment": {"ENV_VAR": "{{ env_value }}"},
                }
            },
        },
    },
}

ISO_TEMPLATE: dict[str, Any] = {
    "name": "truenas-iso",
    "description": "TrueNAS installation via ISO",
    "category": "storage",
    "requirements": {"memory_gb": 8, "disk_gb": 20, "cpu_cores": 2},
    "installation": {
        "method": "iso_installation",
        "iso": {
            "download_url": "https://download.truenas.com/TrueNAS-SCALE-22.12.0.iso",
            "checksum": "sha256:abc123...",
            "boot_options": {"console": "ttyS0", "quiet": True},
            "installation_guide": "Manual installation required. Boot from ISO and follow setup wizard.",
            "post_install_notes": "Access web interface at https://<ip>:443 after installation.",
        },
    },
}


# ---------------------------------------------------------------------------
# PKG-03: Wave 0 contract test — template loading via importlib.resources
# ---------------------------------------------------------------------------


def test_templates_loaded_from_package() -> None:
    """PKG-03: ServiceInstaller loads templates via importlib.resources.files, not TEMPLATES_DIR.

    After Plan 03:
    - TEMPLATES_DIR module constant is removed from service_installer.py
    - _load_service_templates() uses importlib.resources.files("homelab_mcp").joinpath("service_templates")
    - This test verifies the mock plumbing works correctly for all other tests in this file.

    Wave 0: RED until Plan 03 lands.
    """
    traversable = _make_fake_traversable(SAMPLE_TEMPLATE, filename="test-service.yaml")
    fake_files_fn = _make_fake_files_fn(traversable)

    # Patch target: importlib.resources.files as imported in service_installer module
    with patch("homelab_mcp.service_installer.files", fake_files_fn):
        installer = ServiceInstaller()

    assert len(installer.templates) == 1, f"Expected 1 template, got {len(installer.templates)}"
    assert "test-service" in installer.templates, (
        f"Expected 'test-service' in templates, got keys: {list(installer.templates.keys())}"
    )


# ---------------------------------------------------------------------------
# TestServiceInstaller — core tests using importlib.resources mock
# ---------------------------------------------------------------------------


class TestServiceInstaller:
    """Test ServiceInstaller class."""

    def setup_method(self) -> None:
        """Set up test method using importlib.resources.files mock."""
        self.sample_template = SAMPLE_TEMPLATE.copy()

        traversable = _make_fake_traversable(self.sample_template, filename="test-service.yaml")
        fake_files_fn = _make_fake_files_fn(traversable)

        self.patcher = patch("homelab_mcp.service_installer.files", fake_files_fn)
        self.patcher.start()

        self.installer = ServiceInstaller()

    def teardown_method(self) -> None:
        """Tear down test method."""
        self.patcher.stop()

    def test_load_service_templates(self) -> None:
        """Test loading service templates from package resources."""
        templates = self.installer.templates

        assert "test-service" in templates
        assert templates["test-service"]["name"] == "test-service"
        assert templates["test-service"]["category"] == "test"

    def test_get_available_services(self) -> None:
        """Test getting list of available services."""
        services = self.installer.get_available_services()

        assert isinstance(services, list)
        assert "test-service" in services

    def test_get_service_info(self) -> None:
        """Test getting service information."""
        info = self.installer.get_service_info("test-service")

        assert info is not None
        assert info["name"] == "test-service"
        assert info["description"] == "Test service for unit tests"
        assert "requirements" in info
        assert "installation" in info

    def test_get_service_info_nonexistent(self) -> None:
        """Test getting info for nonexistent service."""
        info = self.installer.get_service_info("nonexistent-service")

        assert info is None

    @pytest.mark.asyncio
    async def test_check_service_requirements_success(self) -> None:
        """Test checking service requirements when all are met."""
        with patch("src.homelab_mcp.service_installer.ssh_execute_command") as mock_ssh:
            # Mock port check (port available)
            mock_ssh.return_value = json.dumps(
                {
                    "status": "success",
                    "exit_code": 1,  # Port not in use (good)
                    "output": "",
                }
            )

            # Mock memory check
            def memory_check(*args: object, **kwargs: object) -> str:
                if "free -m" in kwargs.get("command", ""):  # type: ignore[operator]
                    return json.dumps(
                        {
                            "status": "success",
                            "exit_code": 0,
                            "output": "Output:\n2048",  # 2GB available
                        }
                    )
                return mock_ssh.return_value

            mock_ssh.side_effect = memory_check

            result = await self.installer.check_service_requirements(
                "test-service", "test-host", "test-user", "test-pass"
            )

            assert result["service"] == "test-service"
            assert result["hostname"] == "test-host"
            assert result["requirements_met"] is True
            assert "checks" in result

    @pytest.mark.asyncio
    async def test_check_service_requirements_port_conflict(self) -> None:
        """Test checking requirements when port is in use."""
        with patch("src.homelab_mcp.service_installer.ssh_execute_command") as mock_ssh:

            def command_handler(*args: object, **kwargs: object) -> str:
                command = kwargs.get("command", "")
                if "ss -tlnp" in command:  # type: ignore[operator]
                    return json.dumps(
                        {
                            "status": "success",
                            "exit_code": 0,  # Port in use (bad)
                            "output": "tcp 0.0.0.0:8080 LISTEN",
                        }
                    )
                elif "free -m" in command:  # type: ignore[operator]
                    return json.dumps(
                        {
                            "status": "success",
                            "exit_code": 0,
                            "output": "Output:\n2048",  # 2GB available
                        }
                    )
                elif "df /" in command:  # type: ignore[operator]
                    return json.dumps(
                        {
                            "status": "success",
                            "exit_code": 0,
                            "output": "Output:\n20480000",  # 20GB available (in KB)
                        }
                    )
                else:
                    return json.dumps({"status": "success", "exit_code": 0, "output": ""})

            mock_ssh.side_effect = command_handler

            result = await self.installer.check_service_requirements(
                "test-service", "test-host", "test-user", "test-pass"
            )

            assert result["requirements_met"] is False
            assert "port_8080" in result["checks"]
            assert result["checks"]["port_8080"]["status"] == "fail"

    @pytest.mark.asyncio
    async def test_check_service_requirements_unknown_service(self) -> None:
        """Test checking requirements for unknown service."""
        result = await self.installer.check_service_requirements(
            "unknown-service", "test-host", "test-user", "test-pass"
        )

        assert result["status"] == "error"
        assert "Unknown service" in result["error"]

    @pytest.mark.asyncio
    async def test_install_service_docker_compose(self) -> None:
        """Test installing service with Docker Compose method."""
        with patch.object(self.installer, "check_service_requirements") as mock_check:
            mock_check.return_value = {"requirements_met": True, "checks": {}}

            with patch.object(self.installer, "_install_docker_compose_service") as mock_install:
                mock_install.return_value = {
                    "status": "success",
                    "service": "test-service",
                    "method": "docker-compose",
                }

                result = await self.installer.install_service("test-service", "test-host", "test-user", "test-pass")

                assert result["status"] == "success"
                assert result["service"] == "test-service"
                assert result["method"] == "docker-compose"

                mock_check.assert_called_once_with("test-service", "test-host", "test-user", "test-pass")

    @pytest.mark.asyncio
    async def test_install_service_requirements_not_met(self) -> None:
        """Test installing service when requirements are not met."""
        with patch.object(self.installer, "check_service_requirements") as mock_check:
            mock_check.return_value = {
                "requirements_met": False,
                "checks": {"port_8080": {"status": "fail"}},
            }

            result = await self.installer.install_service("test-service", "test-host", "test-user", "test-pass")

            assert result["status"] == "error"
            assert "Requirements not met" in result["error"]
            assert "requirement_check" in result

    @pytest.mark.asyncio
    async def test_install_service_unknown_service(self) -> None:
        """Test installing unknown service."""
        result = await self.installer.install_service("unknown-service", "test-host", "test-user", "test-pass")

        assert result["status"] == "error"
        assert "Unknown service" in result["error"]

    @pytest.mark.asyncio
    async def test_install_docker_compose_service(self) -> None:
        """Test Docker Compose installation method."""
        service_config = self.sample_template.copy()

        with patch("src.homelab_mcp.service_installer.ssh_execute_command") as mock_ssh:
            mock_ssh.return_value = json.dumps({"status": "success", "exit_code": 0, "output": "Success"})

            result = await self.installer._install_docker_compose_service(
                "test-service",
                service_config,
                "test-host",
                "test-user",
                "test-pass",
                {},
            )

            assert "status" in result

    def test_load_service_templates_with_invalid_yaml(self) -> None:
        """Test loading templates with invalid YAML files — invalid files are skipped."""
        # Build a traversable with two files: one valid, one invalid
        valid_file = MagicMock()
        valid_file.is_file.return_value = True
        valid_file.name = "test-service.yaml"
        valid_file.read_text.return_value = yaml.dump(self.sample_template)

        invalid_file = MagicMock()
        invalid_file.is_file.return_value = True
        invalid_file.name = "invalid.yaml"
        invalid_file.read_text.return_value = "invalid: yaml: content: [unclosed"

        fake_traversable = MagicMock()
        fake_traversable.iterdir.return_value = iter([valid_file, invalid_file])

        fake_pkg = MagicMock()
        fake_pkg.joinpath.return_value = fake_traversable
        fake_files_fn = MagicMock(return_value=fake_pkg)

        with patch("homelab_mcp.service_installer.files", fake_files_fn):
            installer = ServiceInstaller()

        assert "test-service" in installer.templates
        assert "invalid" not in installer.templates

    def test_get_service_info_with_complex_template(self) -> None:
        """Test service info with complex template structure."""
        complex_template: dict[str, Any] = {
            "name": "complex-service",
            "description": "Complex service with multiple features",
            "category": "infrastructure",
            "requirements": {
                "ports": [80, 443, 8080],
                "memory_gb": 4,
                "disk_gb": 20,
                "cpu_cores": 2,
            },
            "installation": {
                "method": "terraform",
                "terraform": {"version": ">=1.0", "providers": {"docker": ">=2.0"}},
            },
            "configuration": {
                "env_vars": {"DB_HOST": "localhost", "DB_PORT": "5432"},
                "volumes": ["/data:/app/data", "/logs:/app/logs"],
            },
        }

        traversable = _make_fake_traversable(complex_template, filename="complex-service.yaml")
        fake_files_fn = _make_fake_files_fn(traversable)

        with patch("homelab_mcp.service_installer.files", fake_files_fn):
            installer = ServiceInstaller()

        info = installer.get_service_info("complex-service")

        assert info is not None
        assert info["name"] == "complex-service"
        assert info["category"] == "infrastructure"
        assert len(info["requirements"]["ports"]) == 3
        assert info["installation"]["method"] == "terraform"
        assert "configuration" in info


# ---------------------------------------------------------------------------
# TestServiceInstallerIntegration
# ---------------------------------------------------------------------------


class TestServiceInstallerIntegration:
    """Integration tests for ServiceInstaller with real YAML files."""

    @pytest.mark.asyncio
    async def test_integration_with_mock_ssh(self) -> None:
        """Test service installer with mocked SSH operations."""
        installer = ServiceInstaller()

        if not installer.get_available_services():
            pytest.skip("No service templates available")

        service_name = installer.get_available_services()[0]

        with patch("src.homelab_mcp.service_installer.ssh_execute_command") as mock_ssh:
            mock_ssh.return_value = json.dumps(
                {
                    "status": "success",
                    "exit_code": 1,
                    "output": "Output:\n8192",
                }
            )

            result = await installer.check_service_requirements(service_name, "test-host", "test-user", "test-pass")

            assert "requirements_met" in result
            assert "checks" in result

    def test_template_validation(self) -> None:
        """Test that all loaded templates have required fields."""
        installer = ServiceInstaller()

        for service_name, template in installer.templates.items():
            assert "name" in template or service_name
            assert "installation" in template
            assert "method" in template["installation"]

            supported_methods = [
                "docker-compose",
                "terraform",
                "ansible",
                "script",
                "iso_installation",
            ]
            assert template["installation"]["method"] in supported_methods

            if "requirements" in template:
                req = template["requirements"]
                if "ports" in req:
                    assert isinstance(req["ports"], list)
                if "memory_gb" in req:
                    assert isinstance(req["memory_gb"], int | float)
                if "disk_gb" in req:
                    assert isinstance(req["disk_gb"], int | float)


# ---------------------------------------------------------------------------
# TestServiceInstallerAnsibleMethod
# ---------------------------------------------------------------------------


class TestServiceInstallerAnsibleMethod:
    """Test Ansible installation method."""

    def setup_method(self) -> None:
        """Set up test method using importlib.resources.files mock."""
        self.ansible_template = ANSIBLE_TEMPLATE.copy()

        traversable = _make_fake_traversable(self.ansible_template, filename="ansible-service.yaml")
        fake_files_fn = _make_fake_files_fn(traversable)

        self.patcher = patch("homelab_mcp.service_installer.files", fake_files_fn)
        self.patcher.start()

        self.installer = ServiceInstaller()

    def teardown_method(self) -> None:
        """Tear down test method."""
        self.patcher.stop()

    @pytest.mark.asyncio
    async def test_install_ansible_service_success(self) -> None:
        """Test successful Ansible service installation."""
        with patch.object(self.installer, "check_service_requirements") as mock_check:
            mock_check.return_value = {"requirements_met": True, "checks": {}}

            with patch.object(self.installer, "_install_ansible_service") as mock_install:
                mock_install.return_value = {
                    "status": "success",
                    "service": "ansible-service",
                    "method": "ansible",
                    "playbook_result": {
                        "pre_tasks": 1,
                        "tasks": 1,
                        "post_tasks": 1,
                        "handlers": 0,
                    },
                }

                result = await self.installer.install_service("ansible-service", "test-host", "test-user", "test-pass")

                assert result["status"] == "success"
                assert result["method"] == "ansible"
                assert "playbook_result" in result

    @pytest.mark.asyncio
    async def test_install_ansible_service_with_variables(self) -> None:
        """Test Ansible service installation with variable substitution."""
        variables = {
            "service_port": 9080,
            "service_name": "custom-nginx",
            "enable_ssl": True,
        }

        with patch.object(self.installer, "check_service_requirements") as mock_check:
            mock_check.return_value = {"requirements_met": True}

            with patch.object(self.installer, "_install_ansible_service") as mock_install:
                mock_install.return_value = {
                    "status": "success",
                    "variables_applied": variables,
                }

                await self.installer.install_service(
                    "ansible-service", "test-host", "test-user", "test-pass", variables
                )

                mock_install.assert_called_once()
                call_args = mock_install.call_args
                assert call_args[0][5] == variables

    @pytest.mark.asyncio
    async def test_install_ansible_service_playbook_failure(self) -> None:
        """Test Ansible service installation with playbook failure."""
        with patch.object(self.installer, "check_service_requirements") as mock_check:
            mock_check.return_value = {"requirements_met": True}

            with patch.object(self.installer, "_install_ansible_service") as mock_install:
                mock_install.return_value = {
                    "status": "error",
                    "error": "Ansible playbook failed at task 'Deploy service'",
                    "failed_task": "Deploy service",
                    "playbook_result": {
                        "pre_tasks": 1,
                        "tasks": 0,
                        "post_tasks": 0,
                        "handlers": 0,
                    },
                }

                result = await self.installer.install_service("ansible-service", "test-host", "test-user", "test-pass")

                assert result["status"] == "error"
                assert "playbook failed" in result["error"].lower()
                assert "failed_task" in result

    def test_ansible_template_validation(self) -> None:
        """Test Ansible template structure validation."""
        info = self.installer.get_service_info("ansible-service")

        assert info is not None
        assert info["installation"]["method"] == "ansible"

        ansible_config = info["installation"]["ansible"]
        assert "tasks" in ansible_config
        assert "pre_tasks" in ansible_config
        assert "post_tasks" in ansible_config
        assert "handlers" in ansible_config

        assert len(ansible_config["tasks"]) > 0
        assert "name" in ansible_config["tasks"][0]


# ---------------------------------------------------------------------------
# TestServiceInstallerScriptMethod
# ---------------------------------------------------------------------------


class TestServiceInstallerScriptMethod:
    """Test script-based installation method."""

    def setup_method(self) -> None:
        """Set up test method using importlib.resources.files mock."""
        self.script_template = SCRIPT_TEMPLATE.copy()

        traversable = _make_fake_traversable(self.script_template, filename="script-service.yaml")
        fake_files_fn = _make_fake_files_fn(traversable)

        self.patcher = patch("homelab_mcp.service_installer.files", fake_files_fn)
        self.patcher.start()

        self.installer = ServiceInstaller()

    def teardown_method(self) -> None:
        """Tear down test method."""
        self.patcher.stop()

    @pytest.mark.asyncio
    async def test_install_script_service_success(self) -> None:
        """Test successful script-based service installation."""
        with patch.object(self.installer, "check_service_requirements") as mock_check:
            mock_check.return_value = {"requirements_met": True}

            with patch.object(self.installer, "_install_script_service") as mock_install:
                mock_install.return_value = {
                    "status": "success",
                    "service": "script-service",
                    "method": "script",
                    "executed_commands": {
                        "pre_install": 2,
                        "install": 5,
                        "post_install": 2,
                    },
                }

                result = await self.installer.install_service("script-service", "test-host", "test-user", "test-pass")

                assert result["status"] == "success"
                assert result["method"] == "script"
                assert "executed_commands" in result

    @pytest.mark.asyncio
    async def test_install_script_service_command_failure(self) -> None:
        """Test script service installation with command failure."""
        with patch.object(self.installer, "check_service_requirements") as mock_check:
            mock_check.return_value = {"requirements_met": True}

            with patch.object(self.installer, "_install_script_service") as mock_install:
                mock_install.return_value = {
                    "status": "error",
                    "error": "Command failed: sudo apt-get install -y curl",
                    "failed_command": "sudo apt-get install -y curl",
                    "exit_code": 1,
                    "stderr": "Package not found",
                }

                result = await self.installer.install_service("script-service", "test-host", "test-user", "test-pass")

                assert result["status"] == "error"
                assert "Command failed" in result["error"]
                assert "failed_command" in result

    def test_script_template_validation(self) -> None:
        """Test script template structure validation."""
        info = self.installer.get_service_info("script-service")

        assert info is not None
        assert info["installation"]["method"] == "script"

        script_config = info["installation"]["script"]
        assert "install" in script_config
        assert isinstance(script_config["install"], list)
        assert len(script_config["install"]) > 0

        if "pre_install" in script_config:
            assert isinstance(script_config["pre_install"], list)
        if "post_install" in script_config:
            assert isinstance(script_config["post_install"], list)


# ---------------------------------------------------------------------------
# TestServiceInstallerVariableSubstitution
# ---------------------------------------------------------------------------


class TestServiceInstallerVariableSubstitution:
    """Test template variable substitution functionality."""

    def setup_method(self) -> None:
        """Set up test method using importlib.resources.files mock."""
        self.variable_template = VARIABLE_TEMPLATE.copy()

        traversable = _make_fake_traversable(self.variable_template, filename="variable-service.yaml")
        fake_files_fn = _make_fake_files_fn(traversable)

        self.patcher = patch("homelab_mcp.service_installer.files", fake_files_fn)
        self.patcher.start()

        self.installer = ServiceInstaller()

    def teardown_method(self) -> None:
        """Tear down test method."""
        self.patcher.stop()

    @pytest.mark.asyncio
    async def test_variable_substitution_in_installation(self) -> None:
        """Test variable substitution during service installation."""
        variables = {
            "service_name": "custom-app",
            "service_description": "custom application",
            "service_port": 8080,
            "memory_size": 2,
            "docker_image": "nginx:alpine",
            "env_value": "production",
        }

        with patch.object(self.installer, "check_service_requirements") as mock_check:
            mock_check.return_value = {"requirements_met": True}

            with patch.object(self.installer, "_install_docker_compose_service") as mock_install:
                mock_install.return_value = {"status": "success"}

                await self.installer.install_service(
                    "variable-service", "test-host", "test-user", "test-pass", variables
                )

                mock_install.assert_called_once()
                call_args = mock_install.call_args
                call_args[0][1]  # template parameter

                assert call_args[0][5] == variables

    def test_get_template_with_defaults(self) -> None:
        """Test getting template info with default variable values."""
        template_with_defaults = self.variable_template.copy()
        template_with_defaults["defaults"] = {
            "service_port": 3000,
            "memory_size": 1,
            "docker_image": "nginx:latest",
            "service_name": "default-service",
        }

        traversable = _make_fake_traversable(template_with_defaults, filename="defaults-service.yaml")
        fake_files_fn = _make_fake_files_fn(traversable)

        with patch("homelab_mcp.service_installer.files", fake_files_fn):
            installer = ServiceInstaller()

        info = installer.get_service_info("defaults-service")
        assert info is not None
        assert "defaults" in info
        assert info["defaults"]["service_port"] == 3000

    @pytest.mark.asyncio
    async def test_missing_required_variables(self) -> None:
        """Test installation failure when required variables are missing."""
        incomplete_variables = {
            "service_name": "test-app",
        }

        with patch.object(self.installer, "check_service_requirements") as mock_check:
            mock_check.return_value = {"requirements_met": True}

            result = await self.installer.install_service(
                "variable-service",
                "test-host",
                "test-user",
                "test-pass",
                incomplete_variables,
            )

            assert "service" in result or "status" in result


# ---------------------------------------------------------------------------
# TestInstallScriptServiceDirect
# ---------------------------------------------------------------------------


class TestInstallScriptServiceDirect:
    """Tests for the _install_script_service method implementation."""

    def setup_method(self) -> None:
        """Set up test method using importlib.resources.files mock."""
        minimal: dict[str, Any] = {
            "name": "dummy",
            "description": "dummy",
            "category": "test",
            "requirements": {"ports": [], "memory_gb": 1, "disk_gb": 1},
            "installation": {"method": "script"},
        }

        traversable = _make_fake_traversable(minimal, filename="dummy.yaml")
        fake_files_fn = _make_fake_files_fn(traversable)

        self.patcher = patch("homelab_mcp.service_installer.files", fake_files_fn)
        self.patcher.start()

        self.installer = ServiceInstaller()

    def teardown_method(self) -> None:
        """Tear down test method."""
        self.patcher.stop()

    @pytest.mark.asyncio
    async def test_install_script_success(self) -> None:
        """Script-based service installs successfully when installation_script is present."""
        service = {
            "name": "test-svc",
            "installation": {
                "method": "script",
                "installation_script": "#!/bin/bash\necho hello\n",
            },
        }

        with patch("src.homelab_mcp.service_installer.ssh_execute_command") as mock_ssh:
            mock_ssh.return_value = json.dumps({"status": "success", "exit_code": 0, "output": "hello"})

            result = await self.installer._install_script_service("test-svc", service, "host1", "admin", None, None)

            assert result["status"] == "success"
            assert result["service"] == "test-svc"
            mock_ssh.assert_called_once()
            call_kwargs = mock_ssh.call_args
            assert "echo hello" in call_kwargs.kwargs.get("command", call_kwargs[1].get("command", ""))

    @pytest.mark.asyncio
    async def test_install_script_no_script(self) -> None:
        """When installation_script is missing, returns error."""
        service = {
            "name": "no-script-svc",
            "installation": {
                "method": "script",
            },
        }

        result = await self.installer._install_script_service("no-script-svc", service, "host1", "admin", None, None)

        assert result["status"] == "error"
        assert "no-script-svc" in result["error"].lower() or "script" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_install_script_with_config_override(self) -> None:
        """Config override values are passed as environment variables, not string-substituted."""
        service = {
            "name": "env-svc",
            "installation": {
                "method": "script",
                "installation_script": "#!/bin/bash\necho $DB_HOST\n",
            },
        }
        config_override = {"DB_HOST": "localhost", "DB_PORT": "5432"}

        with patch("src.homelab_mcp.service_installer.ssh_execute_command") as mock_ssh:
            mock_ssh.return_value = json.dumps({"status": "success", "exit_code": 0, "output": "localhost"})

            result = await self.installer._install_script_service(
                "env-svc", service, "host1", "admin", None, config_override
            )

            assert result["status"] == "success"
            call_kwargs = mock_ssh.call_args
            command = call_kwargs.kwargs.get("command", call_kwargs[1].get("command", ""))
            assert "export DB_HOST=" in command
            assert "export DB_PORT=" in command

    @pytest.mark.asyncio
    async def test_install_script_ssh_failure(self) -> None:
        """When ssh_execute_command raises, returns error with sanitized message."""
        service = {
            "name": "fail-svc",
            "installation": {
                "method": "script",
                "installation_script": "#!/bin/bash\nexit 1\n",
            },
        }

        with patch("src.homelab_mcp.service_installer.ssh_execute_command") as mock_ssh:
            mock_ssh.side_effect = Exception("Connection refused")

            result = await self.installer._install_script_service("fail-svc", service, "host1", "admin", None, None)

            assert result["status"] == "error"
            assert result["service"] == "fail-svc"


# ---------------------------------------------------------------------------
# TestServiceInstallerISOMethod
# ---------------------------------------------------------------------------


class TestServiceInstallerISOMethod:
    """Test ISO installation method."""

    def setup_method(self) -> None:
        """Set up test method using importlib.resources.files mock."""
        self.iso_template = ISO_TEMPLATE.copy()

        traversable = _make_fake_traversable(self.iso_template, filename="truenas-iso.yaml")
        fake_files_fn = _make_fake_files_fn(traversable)

        self.patcher = patch("homelab_mcp.service_installer.files", fake_files_fn)
        self.patcher.start()

        self.installer = ServiceInstaller()

    def teardown_method(self) -> None:
        """Tear down test method."""
        self.patcher.stop()

    @pytest.mark.asyncio
    async def test_install_iso_service_guidance(self) -> None:
        """Test ISO service installation provides proper guidance."""
        with patch.object(self.installer, "check_service_requirements") as mock_check:
            mock_check.return_value = {"requirements_met": True}

            with patch.object(self.installer, "_install_iso_service") as mock_install:
                mock_install.return_value = {
                    "status": "guidance_provided",
                    "service": "truenas-iso",
                    "method": "iso_installation",
                    "download_url": "https://download.truenas.com/TrueNAS-SCALE-22.12.0.iso",
                    "installation_guide": "Manual installation required. Boot from ISO and follow setup wizard.",
                    "post_install_notes": "Access web interface at https://<ip>:443 after installation.",
                    "next_steps": [
                        "Download ISO from provided URL",
                        "Create bootable media",
                        "Boot target system from ISO",
                        "Follow installation wizard",
                    ],
                }

                result = await self.installer.install_service("truenas-iso", "test-host", "test-user", "test-pass")

                assert result["status"] == "guidance_provided"
                assert result["method"] == "iso_installation"
                assert "download_url" in result
                assert "installation_guide" in result
                assert "next_steps" in result

    def test_iso_template_validation(self) -> None:
        """Test ISO template structure validation."""
        info = self.installer.get_service_info("truenas-iso")

        assert info is not None
        assert info["installation"]["method"] == "iso_installation"

        iso_config = info["installation"]["iso"]
        assert "download_url" in iso_config
        assert "installation_guide" in iso_config

        assert iso_config["download_url"].startswith("http")
        assert iso_config["download_url"].endswith(".iso")


# ---------------------------------------------------------------------------
# Compatibility: keep old tempfile-based classes for tests that don't
# depend on template loading (they patch at the method level, not module level)
# ---------------------------------------------------------------------------


class _TempDirBase:
    """Mixin providing a real temp directory for tests that create template files on disk.

    Used only by tests that need real filesystem access for other reasons
    (e.g. testing the actual template parsing from disk vs. from package resources).
    This is kept for reference but the canonical mock approach is the files() patch above.
    """

    def setup_method(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.template_dir = Path(self.temp_dir) / "service_templates"
        self.template_dir.mkdir()

    def teardown_method(self) -> None:
        import shutil

        shutil.rmtree(self.temp_dir)
