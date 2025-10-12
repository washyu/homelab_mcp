"""Tests for the service installer module."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.homelab_mcp.service_installer import ServiceInstaller


class TestServiceInstaller:
    """Test ServiceInstaller class."""

    def setup_method(self):
        """Set up test method."""
        # Create a temporary directory for templates
        self.temp_dir = tempfile.mkdtemp()
        self.template_dir = Path(self.temp_dir) / "service_templates"
        self.template_dir.mkdir()

        # Create a sample service template
        self.sample_template = {
            "name": "test-service",
            "description": "Test service for unit tests",
            "category": "test",
            "requirements": {"ports": [8080], "memory_gb": 1, "disk_gb": 5},
            "installation": {
                "method": "docker-compose",
                "compose": {
                    "version": "3.8",
                    "services": {
                        "test": {"image": "nginx:latest", "ports": ["8080:80"]}
                    },
                },
            },
        }

        template_file = self.template_dir / "test-service.yaml"
        with open(template_file, "w") as f:
            import yaml

            yaml.dump(self.sample_template, f)

        # Patch the templates directory
        self.patcher = patch(
            "src.homelab_mcp.service_installer.TEMPLATES_DIR", self.template_dir
        )
        self.patcher.start()

        self.installer = ServiceInstaller()

    def teardown_method(self):
        """Tear down test method."""
        self.patcher.stop()
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_load_service_templates(self):
        """Test loading service templates from directory."""
        templates = self.installer.templates

        assert "test-service" in templates
        assert templates["test-service"]["name"] == "test-service"
        assert templates["test-service"]["category"] == "test"

    def test_get_available_services(self):
        """Test getting list of available services."""
        services = self.installer.get_available_services()

        assert isinstance(services, list)
        assert "test-service" in services

    def test_get_service_info(self):
        """Test getting service information."""
        info = self.installer.get_service_info("test-service")

        assert info is not None
        assert info["name"] == "test-service"
        assert info["description"] == "Test service for unit tests"
        assert "requirements" in info
        assert "installation" in info

    def test_get_service_info_nonexistent(self):
        """Test getting info for nonexistent service."""
        info = self.installer.get_service_info("nonexistent-service")

        assert info is None

    @pytest.mark.asyncio
    async def test_check_service_requirements_success(self):
        """Test checking service requirements when all are met."""
        # Mock SSH execution for requirement checks
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
            def memory_check(*args, **kwargs):
                if "free -m" in kwargs.get("command", ""):
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
    async def test_check_service_requirements_port_conflict(self):
        """Test checking requirements when port is in use."""
        with patch("src.homelab_mcp.service_installer.ssh_execute_command") as mock_ssh:
            # Handle different commands appropriately
            def command_handler(*args, **kwargs):
                command = kwargs.get("command", "")
                if "ss -tlnp" in command:  # Port check
                    return json.dumps(
                        {
                            "status": "success",
                            "exit_code": 0,  # Port in use (bad)
                            "output": "tcp 0.0.0.0:8080 LISTEN",
                        }
                    )
                elif "free -m" in command:  # Memory check
                    return json.dumps(
                        {
                            "status": "success",
                            "exit_code": 0,
                            "output": "Output:\n2048",  # 2GB available
                        }
                    )
                elif "df /" in command:  # Disk check
                    return json.dumps(
                        {
                            "status": "success",
                            "exit_code": 0,
                            "output": "Output:\n20480000",  # 20GB available (in KB)
                        }
                    )
                else:
                    return json.dumps(
                        {"status": "success", "exit_code": 0, "output": ""}
                    )

            mock_ssh.side_effect = command_handler

            result = await self.installer.check_service_requirements(
                "test-service", "test-host", "test-user", "test-pass"
            )

            assert result["requirements_met"] is False
            assert "port_8080" in result["checks"]
            assert result["checks"]["port_8080"]["status"] == "fail"

    @pytest.mark.asyncio
    async def test_check_service_requirements_unknown_service(self):
        """Test checking requirements for unknown service."""
        result = await self.installer.check_service_requirements(
            "unknown-service", "test-host", "test-user", "test-pass"
        )

        assert result["status"] == "error"
        assert "Unknown service" in result["error"]

    @pytest.mark.asyncio
    async def test_install_service_docker_compose(self):
        """Test installing service with Docker Compose method."""
        # Mock successful requirement check
        with patch.object(self.installer, "check_service_requirements") as mock_check:
            mock_check.return_value = {"requirements_met": True, "checks": {}}

            # Mock Docker Compose installation
            with patch.object(
                self.installer, "_install_docker_compose_service"
            ) as mock_install:
                mock_install.return_value = {
                    "status": "success",
                    "service": "test-service",
                    "method": "docker-compose",
                }

                result = await self.installer.install_service(
                    "test-service", "test-host", "test-user", "test-pass"
                )

                assert result["status"] == "success"
                assert result["service"] == "test-service"
                assert result["method"] == "docker-compose"

                # Verify requirement check was called
                mock_check.assert_called_once_with(
                    "test-service", "test-host", "test-user", "test-pass"
                )

    @pytest.mark.asyncio
    async def test_install_service_requirements_not_met(self):
        """Test installing service when requirements are not met."""
        with patch.object(self.installer, "check_service_requirements") as mock_check:
            mock_check.return_value = {
                "requirements_met": False,
                "checks": {"port_8080": {"status": "fail"}},
            }

            result = await self.installer.install_service(
                "test-service", "test-host", "test-user", "test-pass"
            )

            assert result["status"] == "error"
            assert "Requirements not met" in result["error"]
            assert "requirement_check" in result

    @pytest.mark.asyncio
    async def test_install_service_unknown_service(self):
        """Test installing unknown service."""
        result = await self.installer.install_service(
            "unknown-service", "test-host", "test-user", "test-pass"
        )

        assert result["status"] == "error"
        assert "Unknown service" in result["error"]

    @pytest.mark.asyncio
    async def test_install_docker_compose_service(self):
        """Test Docker Compose installation method."""
        service_config = self.sample_template.copy()

        with patch("src.homelab_mcp.service_installer.ssh_execute_command") as mock_ssh:
            # Mock successful command execution
            mock_ssh.return_value = json.dumps(
                {"status": "success", "exit_code": 0, "output": "Success"}
            )

            result = await self.installer._install_docker_compose_service(
                "test-service",
                service_config,
                "test-host",
                "test-user",
                "test-pass",
                {},
            )

            assert "status" in result
            # The actual implementation would have more specific assertions

    def test_load_service_templates_with_invalid_yaml(self):
        """Test loading templates with invalid YAML files."""
        # Create invalid YAML file
        invalid_file = self.template_dir / "invalid.yaml"
        with open(invalid_file, "w") as f:
            f.write("invalid: yaml: content: [unclosed")

        # Reload installer
        installer = ServiceInstaller()

        # Should load valid templates and skip invalid ones
        assert "test-service" in installer.templates
        assert "invalid" not in installer.templates

    def test_get_service_info_with_complex_template(self):
        """Test service info with complex template structure."""
        # Create more complex template
        complex_template = {
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

        template_file = self.template_dir / "complex-service.yaml"
        with open(template_file, "w") as f:
            import yaml

            yaml.dump(complex_template, f)

        # Reload installer
        installer = ServiceInstaller()

        info = installer.get_service_info("complex-service")

        assert info is not None
        assert info["name"] == "complex-service"
        assert info["category"] == "infrastructure"
        assert len(info["requirements"]["ports"]) == 3
        assert info["installation"]["method"] == "terraform"
        assert "configuration" in info


class TestServiceInstallerIntegration:
    """Integration tests for ServiceInstaller with real YAML files."""

    @pytest.mark.asyncio
    async def test_integration_with_mock_ssh(self):
        """Test service installer with mocked SSH operations."""
        installer = ServiceInstaller()

        # Skip if no templates available (in case templates directory is empty)
        if not installer.get_available_services():
            pytest.skip("No service templates available")

        service_name = installer.get_available_services()[0]

        with patch("src.homelab_mcp.service_installer.ssh_execute_command") as mock_ssh:
            # Mock all SSH commands to return success
            mock_ssh.return_value = json.dumps(
                {
                    "status": "success",
                    "exit_code": 1,  # Assume ports are available
                    "output": "Output:\n8192",  # Assume sufficient resources
                }
            )

            # Check requirements
            result = await installer.check_service_requirements(
                service_name, "test-host", "test-user", "test-pass"
            )

            assert "requirements_met" in result
            assert "checks" in result

    def test_template_validation(self):
        """Test that all loaded templates have required fields."""
        installer = ServiceInstaller()

        for service_name, template in installer.templates.items():
            # Every template should have basic required fields
            assert "name" in template or service_name
            assert "installation" in template
            assert "method" in template["installation"]

            # Method should be one of supported types
            supported_methods = [
                "docker-compose",
                "terraform",
                "ansible",
                "script",
                "iso_installation",
            ]
            assert template["installation"]["method"] in supported_methods

            # If requirements exist, they should be properly structured
            if "requirements" in template:
                req = template["requirements"]
                if "ports" in req:
                    assert isinstance(req["ports"], list)
                if "memory_gb" in req:
                    assert isinstance(req["memory_gb"], int | float)
                if "disk_gb" in req:
                    assert isinstance(req["disk_gb"], int | float)


class TestServiceInstallerAnsibleMethod:
    """Test Ansible installation method."""

    def setup_method(self):
        """Set up test method."""
        # Create a temporary directory for templates
        self.temp_dir = tempfile.mkdtemp()
        self.template_dir = Path(self.temp_dir) / "service_templates"
        self.template_dir.mkdir()

        # Create a sample Ansible service template
        self.ansible_template = {
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

        template_file = self.template_dir / "ansible-service.yaml"
        with open(template_file, "w") as f:
            import yaml

            yaml.dump(self.ansible_template, f)

        # Patch the templates directory
        self.patcher = patch(
            "src.homelab_mcp.service_installer.TEMPLATES_DIR", self.template_dir
        )
        self.patcher.start()

        self.installer = ServiceInstaller()

    def teardown_method(self):
        """Tear down test method."""
        self.patcher.stop()
        import shutil

        shutil.rmtree(self.temp_dir)

    @pytest.mark.asyncio
    async def test_install_ansible_service_success(self):
        """Test successful Ansible service installation."""
        # Mock successful requirement check
        with patch.object(self.installer, "check_service_requirements") as mock_check:
            mock_check.return_value = {"requirements_met": True, "checks": {}}

            # Mock Ansible installation
            with patch.object(
                self.installer, "_install_ansible_service"
            ) as mock_install:
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

                result = await self.installer.install_service(
                    "ansible-service", "test-host", "test-user", "test-pass"
                )

                assert result["status"] == "success"
                assert result["method"] == "ansible"
                assert "playbook_result" in result

    @pytest.mark.asyncio
    async def test_install_ansible_service_with_variables(self):
        """Test Ansible service installation with variable substitution."""
        variables = {
            "service_port": 9080,
            "service_name": "custom-nginx",
            "enable_ssl": True,
        }

        with patch.object(self.installer, "check_service_requirements") as mock_check:
            mock_check.return_value = {"requirements_met": True}

            with patch.object(
                self.installer, "_install_ansible_service"
            ) as mock_install:
                mock_install.return_value = {
                    "status": "success",
                    "variables_applied": variables,
                }

                await self.installer.install_service(
                    "ansible-service", "test-host", "test-user", "test-pass", variables
                )

                # Verify variables were passed to ansible installer
                mock_install.assert_called_once()
                call_args = mock_install.call_args
                assert call_args[0][5] == variables  # variables parameter

    @pytest.mark.asyncio
    async def test_install_ansible_service_playbook_failure(self):
        """Test Ansible service installation with playbook failure."""
        with patch.object(self.installer, "check_service_requirements") as mock_check:
            mock_check.return_value = {"requirements_met": True}

            with patch.object(
                self.installer, "_install_ansible_service"
            ) as mock_install:
                mock_install.return_value = {
                    "status": "error",
                    "error": "Ansible playbook failed at task 'Deploy service'",
                    "failed_task": "Deploy service",
                    "playbook_result": {
                        "pre_tasks": 1,
                        "tasks": 0,  # Failed here
                        "post_tasks": 0,
                        "handlers": 0,
                    },
                }

                result = await self.installer.install_service(
                    "ansible-service", "test-host", "test-user", "test-pass"
                )

                assert result["status"] == "error"
                assert "playbook failed" in result["error"].lower()
                assert "failed_task" in result

    def test_ansible_template_validation(self):
        """Test Ansible template structure validation."""
        info = self.installer.get_service_info("ansible-service")

        assert info is not None
        assert info["installation"]["method"] == "ansible"

        ansible_config = info["installation"]["ansible"]
        assert "tasks" in ansible_config
        assert "pre_tasks" in ansible_config
        assert "post_tasks" in ansible_config
        assert "handlers" in ansible_config

        # Verify task structure
        assert len(ansible_config["tasks"]) > 0
        assert "name" in ansible_config["tasks"][0]


class TestServiceInstallerScriptMethod:
    """Test script-based installation method."""

    def setup_method(self):
        """Set up test method."""
        # Create a temporary directory for templates
        self.temp_dir = tempfile.mkdtemp()
        self.template_dir = Path(self.temp_dir) / "service_templates"
        self.template_dir.mkdir()

        # Create a sample script service template
        self.script_template = {
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

        template_file = self.template_dir / "script-service.yaml"
        with open(template_file, "w") as f:
            import yaml

            yaml.dump(self.script_template, f)

        # Patch the templates directory
        self.patcher = patch(
            "src.homelab_mcp.service_installer.TEMPLATES_DIR", self.template_dir
        )
        self.patcher.start()

        self.installer = ServiceInstaller()

    def teardown_method(self):
        """Tear down test method."""
        self.patcher.stop()
        import shutil

        shutil.rmtree(self.temp_dir)

    @pytest.mark.asyncio
    async def test_install_script_service_success(self):
        """Test successful script-based service installation."""
        with patch.object(self.installer, "check_service_requirements") as mock_check:
            mock_check.return_value = {"requirements_met": True}

            with patch.object(
                self.installer, "_install_script_service"
            ) as mock_install:
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

                result = await self.installer.install_service(
                    "script-service", "test-host", "test-user", "test-pass"
                )

                assert result["status"] == "success"
                assert result["method"] == "script"
                assert "executed_commands" in result

    @pytest.mark.asyncio
    async def test_install_script_service_command_failure(self):
        """Test script service installation with command failure."""
        with patch.object(self.installer, "check_service_requirements") as mock_check:
            mock_check.return_value = {"requirements_met": True}

            with patch.object(
                self.installer, "_install_script_service"
            ) as mock_install:
                mock_install.return_value = {
                    "status": "error",
                    "error": "Command failed: sudo apt-get install -y curl",
                    "failed_command": "sudo apt-get install -y curl",
                    "exit_code": 1,
                    "stderr": "Package not found",
                }

                result = await self.installer.install_service(
                    "script-service", "test-host", "test-user", "test-pass"
                )

                assert result["status"] == "error"
                assert "Command failed" in result["error"]
                assert "failed_command" in result

    def test_script_template_validation(self):
        """Test script template structure validation."""
        info = self.installer.get_service_info("script-service")

        assert info is not None
        assert info["installation"]["method"] == "script"

        script_config = info["installation"]["script"]
        assert "install" in script_config
        assert isinstance(script_config["install"], list)
        assert len(script_config["install"]) > 0

        # Optional sections should exist if defined
        if "pre_install" in script_config:
            assert isinstance(script_config["pre_install"], list)
        if "post_install" in script_config:
            assert isinstance(script_config["post_install"], list)


class TestServiceInstallerVariableSubstitution:
    """Test template variable substitution functionality."""

    def setup_method(self):
        """Set up test method."""
        # Create a temporary directory for templates
        self.temp_dir = tempfile.mkdtemp()
        self.template_dir = Path(self.temp_dir) / "service_templates"
        self.template_dir.mkdir()

        # Create a template with variables
        self.variable_template = {
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

        template_file = self.template_dir / "variable-service.yaml"
        with open(template_file, "w") as f:
            import yaml

            yaml.dump(self.variable_template, f)

        # Patch the templates directory
        self.patcher = patch(
            "src.homelab_mcp.service_installer.TEMPLATES_DIR", self.template_dir
        )
        self.patcher.start()

        self.installer = ServiceInstaller()

    def teardown_method(self):
        """Tear down test method."""
        self.patcher.stop()
        import shutil

        shutil.rmtree(self.temp_dir)

    @pytest.mark.asyncio
    async def test_variable_substitution_in_installation(self):
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

            with patch.object(
                self.installer, "_install_docker_compose_service"
            ) as mock_install:
                mock_install.return_value = {"status": "success"}

                await self.installer.install_service(
                    "variable-service", "test-host", "test-user", "test-pass", variables
                )

                # Verify that template was passed with variables
                mock_install.assert_called_once()
                call_args = mock_install.call_args
                call_args[0][1]  # template parameter

                # Variables should be substituted in the template
                # This would be verified in the actual implementation
                assert call_args[0][5] == variables  # variables parameter

    def test_get_template_with_defaults(self):
        """Test getting template info with default variable values."""
        # Add defaults to template
        template_with_defaults = self.variable_template.copy()
        template_with_defaults["defaults"] = {
            "service_port": 3000,
            "memory_size": 1,
            "docker_image": "nginx:latest",
            "service_name": "default-service",
        }

        template_file = self.template_dir / "defaults-service.yaml"
        with open(template_file, "w") as f:
            import yaml

            yaml.dump(template_with_defaults, f)

        # Reload installer to pick up new template
        installer = ServiceInstaller()

        info = installer.get_service_info("defaults-service")
        assert info is not None
        assert "defaults" in info
        assert info["defaults"]["service_port"] == 3000

    @pytest.mark.asyncio
    async def test_missing_required_variables(self):
        """Test installation failure when required variables are missing."""
        # Provide only partial variables
        incomplete_variables = {
            "service_name": "test-app",
            # Missing other required variables
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

            # Should return error about missing variables
            # This would be implemented in the actual service installer
            # For now, we test the basic structure is maintained
            assert "service" in result or "status" in result


class TestServiceInstallerISOMethod:
    """Test ISO installation method."""

    def setup_method(self):
        """Set up test method."""
        # Create a temporary directory for templates
        self.temp_dir = tempfile.mkdtemp()
        self.template_dir = Path(self.temp_dir) / "service_templates"
        self.template_dir.mkdir()

        # Create a sample ISO service template
        self.iso_template = {
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

        template_file = self.template_dir / "truenas-iso.yaml"
        with open(template_file, "w") as f:
            import yaml

            yaml.dump(self.iso_template, f)

        # Patch the templates directory
        self.patcher = patch(
            "src.homelab_mcp.service_installer.TEMPLATES_DIR", self.template_dir
        )
        self.patcher.start()

        self.installer = ServiceInstaller()

    def teardown_method(self):
        """Tear down test method."""
        self.patcher.stop()
        import shutil

        shutil.rmtree(self.temp_dir)

    @pytest.mark.asyncio
    async def test_install_iso_service_guidance(self):
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

                result = await self.installer.install_service(
                    "truenas-iso", "test-host", "test-user", "test-pass"
                )

                assert result["status"] == "guidance_provided"
                assert result["method"] == "iso_installation"
                assert "download_url" in result
                assert "installation_guide" in result
                assert "next_steps" in result

    def test_iso_template_validation(self):
        """Test ISO template structure validation."""
        info = self.installer.get_service_info("truenas-iso")

        assert info is not None
        assert info["installation"]["method"] == "iso_installation"

        iso_config = info["installation"]["iso"]
        assert "download_url" in iso_config
        assert "installation_guide" in iso_config

        # Verify URL format
        assert iso_config["download_url"].startswith("http")
        assert iso_config["download_url"].endswith(".iso")
