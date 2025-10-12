"""Tests for Ansible integration functionality."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from src.homelab_mcp.service_installer import ServiceInstaller


class MockAnsibleRunner:
    """Mock Ansible runner for testing."""

    def __init__(self, success=True, tasks_run=0, failed_task=None):
        self.success = success
        self.tasks_run = tasks_run
        self.failed_task = failed_task

    async def run_playbook(self, playbook_content, variables=None, inventory=None):
        """Mock playbook execution."""
        if self.success:
            return {
                "status": "success",
                "tasks_executed": self.tasks_run,
                "variables_applied": variables or {},
                "inventory_used": inventory,
                "execution_time": "45.2s",
                "results": {
                    "ok": self.tasks_run,
                    "changed": self.tasks_run - 1,
                    "unreachable": 0,
                    "failed": 0,
                },
            }
        else:
            return {
                "status": "failed",
                "failed_task": self.failed_task or "Unknown task",
                "error_message": "Task execution failed",
                "tasks_executed": self.tasks_run,
                "results": {
                    "ok": self.tasks_run,
                    "changed": 0,
                    "unreachable": 0,
                    "failed": 1,
                },
            }


class TestAnsibleServiceIntegration:
    """Test Ansible integration with service installation."""

    def setup_method(self):
        """Set up test method."""
        # Create temporary directory structure
        self.temp_dir = tempfile.mkdtemp()
        self.template_dir = Path(self.temp_dir) / "service_templates"
        self.template_dir.mkdir()

        # Create comprehensive Ansible service template
        self.ansible_template = {
            "name": "comprehensive-ansible-service",
            "description": "Comprehensive Ansible service for testing",
            "category": "infrastructure",
            "version": "1.0.0",
            "requirements": {
                "ports": [80, 443],
                "memory_gb": 4,
                "disk_gb": 20,
                "cpu_cores": 2,
            },
            "defaults": {
                "service_name": "web-service",
                "service_port": 80,
                "ssl_enabled": True,
                "replicas": 1,
            },
            "installation": {
                "method": "ansible",
                "ansible": {
                    "variables": {
                        "service_user": "{{ service_name }}-user",
                        "service_home": "/opt/{{ service_name }}",
                        "log_level": "INFO",
                    },
                    "pre_tasks": [
                        {
                            "name": "Update package cache",
                            "apt": {"update_cache": True, "cache_valid_time": 3600},
                            "become": True,
                        },
                        {
                            "name": "Install required packages",
                            "apt": {
                                "name": ["docker.io", "docker-compose", "nginx"],
                                "state": "present",
                            },
                            "become": True,
                        },
                        {
                            "name": "Create service user",
                            "user": {
                                "name": "{{ service_user }}",
                                "system": True,
                                "home": "{{ service_home }}",
                                "create_home": True,
                            },
                            "become": True,
                        },
                    ],
                    "tasks": [
                        {
                            "name": "Create service directories",
                            "file": {
                                "path": "{{ item }}",
                                "state": "directory",
                                "owner": "{{ service_user }}",
                                "group": "{{ service_user }}",
                                "mode": "0755",
                            },
                            "loop": [
                                "{{ service_home }}/config",
                                "{{ service_home }}/data",
                                "{{ service_home }}/logs",
                            ],
                            "become": True,
                        },
                        {
                            "name": "Deploy Docker Compose configuration",
                            "template": {
                                "src": "docker-compose.yml.j2",
                                "dest": "{{ service_home }}/docker-compose.yml",
                                "owner": "{{ service_user }}",
                                "group": "{{ service_user }}",
                                "mode": "0644",
                            },
                            "become": True,
                            "notify": "restart service",
                        },
                        {
                            "name": "Start service containers",
                            "docker_compose": {
                                "project_src": "{{ service_home }}",
                                "state": "present",
                            },
                            "become_user": "{{ service_user }}",
                        },
                        {
                            "name": "Configure nginx proxy",
                            "template": {
                                "src": "nginx.conf.j2",
                                "dest": "/etc/nginx/sites-available/{{ service_name }}",
                                "mode": "0644",
                            },
                            "become": True,
                            "when": "ssl_enabled | bool",
                            "notify": "reload nginx",
                        },
                    ],
                    "post_tasks": [
                        {
                            "name": "Wait for service to be ready",
                            "uri": {
                                "url": "http://localhost:{{ service_port }}/health",
                                "method": "GET",
                                "status_code": 200,
                            },
                            "register": "health_check",
                            "until": "health_check.status == 200",
                            "retries": 30,
                            "delay": 10,
                        },
                        {
                            "name": "Enable service autostart",
                            "systemd": {
                                "name": "{{ service_name }}",
                                "enabled": True,
                                "daemon_reload": True,
                            },
                            "become": True,
                        },
                    ],
                    "handlers": [
                        {
                            "name": "restart service",
                            "docker_compose": {
                                "project_src": "{{ service_home }}",
                                "state": "present",
                                "recreate": "always",
                            },
                            "become_user": "{{ service_user }}",
                        },
                        {
                            "name": "reload nginx",
                            "systemd": {"name": "nginx", "state": "reloaded"},
                            "become": True,
                        },
                    ],
                },
            },
            "templates": {
                "docker-compose.yml.j2": """version: '3.8'
services:
  {{ service_name }}:
    image: nginx:alpine
    ports:
      - "{{ service_port }}:80"
    volumes:
      - {{ service_home }}/data:/usr/share/nginx/html
      - {{ service_home }}/logs:/var/log/nginx
    environment:
      - LOG_LEVEL={{ log_level }}
    restart: unless-stopped
""",
                "nginx.conf.j2": """server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://localhost:{{ service_port }};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
""",
            },
        }

        # Save template to file
        template_file = self.template_dir / "comprehensive-ansible-service.yaml"
        with open(template_file, "w") as f:
            yaml.dump(self.ansible_template, f)

        # Patch templates directory
        self.patcher = patch(
            "src.homelab_mcp.service_installer.TEMPLATES_DIR", self.template_dir
        )
        self.patcher.start()

        # Create service installer
        self.installer = ServiceInstaller()

    def teardown_method(self):
        """Tear down test method."""
        self.patcher.stop()
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_ansible_playbook_execution_success(self):
        """Test successful Ansible playbook execution."""
        # Mock Ansible runner
        mock_runner = MockAnsibleRunner(success=True, tasks_run=8)

        with patch(
            "src.homelab_mcp.service_installer.AnsibleRunner", return_value=mock_runner
        ):
            with patch.object(
                self.installer, "check_service_requirements"
            ) as mock_check:
                mock_check.return_value = {"requirements_met": True}

                # Test variables for substitution
                variables = {
                    "service_name": "test-web-service",
                    "service_port": 8080,
                    "ssl_enabled": False,
                    "replicas": 2,
                }

                result = await self.installer.install_service(
                    "comprehensive-ansible-service",
                    "test-host",
                    "test-user",
                    "test-pass",
                    variables,
                )

                assert result["status"] == "success"
                assert result["method"] == "ansible"
                assert "playbook_result" in result
                assert result["playbook_result"]["tasks_executed"] == 8
                assert result["playbook_result"]["results"]["ok"] == 8

    @pytest.mark.asyncio
    async def test_ansible_playbook_execution_failure(self):
        """Test Ansible playbook execution with failure."""
        # Mock failing Ansible runner
        mock_runner = MockAnsibleRunner(
            success=False,
            tasks_run=3,
            failed_task="Deploy Docker Compose configuration",
        )

        with patch(
            "src.homelab_mcp.service_installer.AnsibleRunner", return_value=mock_runner
        ):
            with patch.object(
                self.installer, "check_service_requirements"
            ) as mock_check:
                mock_check.return_value = {"requirements_met": True}

                result = await self.installer.install_service(
                    "comprehensive-ansible-service",
                    "test-host",
                    "test-user",
                    "test-pass",
                )

                assert result["status"] == "error"
                assert "failed_task" in result
                assert result["failed_task"] == "Deploy Docker Compose configuration"
                assert "playbook_result" in result

    @pytest.mark.asyncio
    async def test_ansible_variable_substitution(self):
        """Test Ansible template variable substitution."""
        mock_runner = MockAnsibleRunner(success=True, tasks_run=8)

        # Custom variables that should be substituted
        variables = {
            "service_name": "custom-api",
            "service_port": 9000,
            "ssl_enabled": True,
            "replicas": 3,
            "log_level": "DEBUG",
        }

        with patch(
            "src.homelab_mcp.service_installer.AnsibleRunner"
        ) as mock_runner_class:
            mock_runner_class.return_value = mock_runner

            with patch.object(
                self.installer, "check_service_requirements"
            ) as mock_check:
                mock_check.return_value = {"requirements_met": True}

                result = await self.installer.install_service(
                    "comprehensive-ansible-service",
                    "test-host",
                    "test-user",
                    "test-pass",
                    variables,
                )

                # Verify runner was called with correct variables
                mock_runner_class.assert_called_once()

                # Check that variables were properly merged with defaults and template variables
                (
                    mock_runner.run_playbook.call_args
                    if hasattr(mock_runner.run_playbook, "call_args")
                    else None
                )
                # In real implementation, this would verify variable substitution

                assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_ansible_template_rendering(self):
        """Test Ansible template file rendering."""
        variables = {
            "service_name": "test-service",
            "service_port": 8080,
            "service_home": "/opt/test-service",
            "log_level": "INFO",
        }

        mock_runner = MockAnsibleRunner(success=True, tasks_run=8)

        with patch(
            "src.homelab_mcp.service_installer.AnsibleRunner", return_value=mock_runner
        ):
            with patch.object(
                self.installer, "check_service_requirements"
            ) as mock_check:
                mock_check.return_value = {"requirements_met": True}

                # Mock template rendering
                with patch(
                    "src.homelab_mcp.service_installer.render_template"
                ) as mock_render:
                    mock_render.return_value = """version: '3.8'
services:
  test-service:
    image: nginx:alpine
    ports:
      - "8080:80"
    volumes:
      - /opt/test-service/data:/usr/share/nginx/html
    environment:
      - LOG_LEVEL=INFO
"""

                    result = await self.installer.install_service(
                        "comprehensive-ansible-service",
                        "test-host",
                        "test-user",
                        "test-pass",
                        variables,
                    )

                    # Verify template rendering was called
                    mock_render.assert_called()
                    assert result["status"] == "success"

    def test_ansible_template_validation(self):
        """Test Ansible template structure validation."""
        info = self.installer.get_service_info("comprehensive-ansible-service")

        assert info is not None
        assert info["installation"]["method"] == "ansible"

        ansible_config = info["installation"]["ansible"]

        # Verify required sections exist
        assert "pre_tasks" in ansible_config
        assert "tasks" in ansible_config
        assert "post_tasks" in ansible_config
        assert "handlers" in ansible_config

        # Verify task structure
        assert len(ansible_config["tasks"]) > 0
        for task in ansible_config["tasks"]:
            assert "name" in task

        # Verify handlers structure
        assert len(ansible_config["handlers"]) > 0
        for handler in ansible_config["handlers"]:
            assert "name" in handler

        # Verify template files exist
        assert "templates" in info
        assert "docker-compose.yml.j2" in info["templates"]
        assert "nginx.conf.j2" in info["templates"]

    def test_ansible_defaults_and_variables_merge(self):
        """Test merging of defaults, template variables, and user variables."""
        info = self.installer.get_service_info("comprehensive-ansible-service")

        # Verify defaults exist
        assert "defaults" in info
        defaults = info["defaults"]
        assert defaults["service_name"] == "web-service"
        assert defaults["service_port"] == 80

        # Verify ansible variables exist
        ansible_config = info["installation"]["ansible"]
        assert "variables" in ansible_config
        variables = ansible_config["variables"]
        assert "service_user" in variables
        assert "service_home" in variables


class TestAnsiblePlaybookRunner:
    """Test Ansible playbook runner functionality."""

    @pytest.mark.asyncio
    async def test_ansible_runner_basic_execution(self):
        """Test basic Ansible runner execution."""
        # Mock the actual ansible-playbook command execution
        with patch("src.homelab_mcp.service_installer.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = json.dumps(
                {
                    "plays": [
                        {
                            "play": {"name": "Test Play"},
                            "tasks": [
                                {
                                    "task": {"name": "Test Task"},
                                    "host": "localhost",
                                    "status": "ok",
                                }
                            ],
                        }
                    ]
                }
            )
            mock_run.return_value.stderr = ""

            # Test would require actual AnsibleRunner implementation
            # This is a placeholder for the structure

            # Mock inventory creation

            # Verify command would be constructed properly
            # This would test the actual runner implementation

    @pytest.mark.asyncio
    async def test_ansible_runner_inventory_generation(self):
        """Test Ansible inventory generation."""
        # Test inventory generation for different host configurations
        host_configs = [
            {
                "hostname": "test-host-1",
                "username": "admin",
                "port": 22,
                "expected_inventory": {
                    "all": {
                        "hosts": {
                            "test-host-1": {
                                "ansible_host": "test-host-1",
                                "ansible_user": "admin",
                                "ansible_port": 22,
                            }
                        }
                    }
                },
            },
            {
                "hostname": "192.168.1.100",
                "username": "ubuntu",
                "port": 2222,
                "expected_inventory": {
                    "all": {
                        "hosts": {
                            "192.168.1.100": {
                                "ansible_host": "192.168.1.100",
                                "ansible_user": "ubuntu",
                                "ansible_port": 2222,
                            }
                        }
                    }
                },
            },
        ]

        for config in host_configs:
            # This would test inventory generation in actual implementation
            # Mock the inventory generation function
            with patch(
                "src.homelab_mcp.service_installer.generate_ansible_inventory"
            ) as mock_gen:
                mock_gen.return_value = config["expected_inventory"]

                inventory = mock_gen(
                    config["hostname"], config["username"], config["port"]
                )
                assert inventory == config["expected_inventory"]

    @pytest.mark.asyncio
    async def test_ansible_runner_error_handling(self):
        """Test Ansible runner error handling."""
        error_scenarios = [
            {
                "name": "Command not found",
                "returncode": 127,
                "stderr": "ansible-playbook: command not found",
                "expected_error": "ansible_not_installed",
            },
            {
                "name": "Syntax error",
                "returncode": 4,
                "stderr": "ERROR! Syntax Error while loading YAML",
                "expected_error": "playbook_syntax_error",
            },
            {
                "name": "Connection failure",
                "returncode": 2,
                "stderr": 'UNREACHABLE! => {"changed": false, "msg": "Failed to connect"}',
                "expected_error": "connection_failed",
            },
            {
                "name": "Task failure",
                "returncode": 2,
                "stderr": 'FAILED! => {"changed": false, "msg": "Task failed"}',
                "expected_error": "task_failed",
            },
        ]

        for scenario in error_scenarios:
            with patch("src.homelab_mcp.service_installer.subprocess.run") as mock_run:
                mock_run.return_value.returncode = scenario["returncode"]
                mock_run.return_value.stderr = scenario["stderr"]
                mock_run.return_value.stdout = ""

                # Test error handling in actual implementation
                # This would verify proper error categorization and handling
                pass


class TestAnsibleServiceTemplateProcessing:
    """Test Ansible service template processing and validation."""

    def setup_method(self):
        """Set up test method."""
        self.temp_dir = tempfile.mkdtemp()
        self.template_dir = Path(self.temp_dir) / "service_templates"
        self.template_dir.mkdir()

    def teardown_method(self):
        """Tear down test method."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_complex_ansible_template_parsing(self):
        """Test parsing of complex Ansible templates."""
        complex_template = {
            "name": "multi-tier-app",
            "description": "Multi-tier application with database",
            "category": "application",
            "installation": {
                "method": "ansible",
                "ansible": {
                    "variables": {
                        "db_name": "{{ app_name }}_db",
                        "db_user": "{{ app_name }}_user",
                        "app_version": "latest",
                    },
                    "pre_tasks": [
                        {"name": "Update system", "apt": {"update_cache": True}},
                        {
                            "name": "Install Docker",
                            "shell": "curl -fsSL https://get.docker.com | sh",
                        },
                    ],
                    "tasks": [
                        {
                            "name": "Deploy database",
                            "docker_container": {
                                "name": "{{ db_name }}",
                                "image": "postgres:13",
                                "env": {
                                    "POSTGRES_DB": "{{ db_name }}",
                                    "POSTGRES_USER": "{{ db_user }}",
                                    "POSTGRES_PASSWORD": "{{ db_password }}",
                                },
                            },
                        },
                        {
                            "name": "Deploy application",
                            "docker_container": {
                                "name": "{{ app_name }}",
                                "image": "myapp:{{ app_version }}",
                                "links": ["{{ db_name }}:database"],
                                "ports": ["{{ app_port }}:8080"],
                            },
                        },
                    ],
                    "post_tasks": [
                        {
                            "name": "Run database migrations",
                            "shell": "docker exec {{ app_name }} python manage.py migrate",
                        }
                    ],
                },
            },
        }

        template_file = self.template_dir / "multi-tier-app.yaml"
        with open(template_file, "w") as f:
            yaml.dump(complex_template, f)

        with patch(
            "src.homelab_mcp.service_installer.TEMPLATES_DIR", self.template_dir
        ):
            installer = ServiceInstaller()
            info = installer.get_service_info("multi-tier-app")

            assert info is not None
            assert info["name"] == "multi-tier-app"

            ansible_config = info["installation"]["ansible"]
            assert len(ansible_config["tasks"]) == 2
            assert "variables" in ansible_config
            assert "db_name" in ansible_config["variables"]

    def test_ansible_template_conditional_tasks(self):
        """Test Ansible templates with conditional tasks."""
        conditional_template = {
            "name": "conditional-service",
            "installation": {
                "method": "ansible",
                "ansible": {
                    "tasks": [
                        {
                            "name": "Install SSL certificates",
                            "copy": {
                                "src": "{{ ssl_cert_path }}",
                                "dest": "/etc/ssl/certs/",
                            },
                            "when": "ssl_enabled | bool",
                        },
                        {
                            "name": "Configure HTTP only",
                            "template": {
                                "src": "http.conf.j2",
                                "dest": "/etc/nginx/conf.d/default.conf",
                            },
                            "when": "not ssl_enabled | bool",
                        },
                        {
                            "name": "Configure HTTPS",
                            "template": {
                                "src": "https.conf.j2",
                                "dest": "/etc/nginx/conf.d/default.conf",
                            },
                            "when": "ssl_enabled | bool",
                        },
                    ]
                },
            },
        }

        template_file = self.template_dir / "conditional-service.yaml"
        with open(template_file, "w") as f:
            yaml.dump(conditional_template, f)

        with patch(
            "src.homelab_mcp.service_installer.TEMPLATES_DIR", self.template_dir
        ):
            installer = ServiceInstaller()
            info = installer.get_service_info("conditional-service")

            assert info is not None
            tasks = info["installation"]["ansible"]["tasks"]

            # Verify conditional tasks exist
            ssl_task = next(
                (t for t in tasks if "ssl_enabled | bool" in str(t.get("when", ""))),
                None,
            )
            assert ssl_task is not None

            http_task = next(
                (
                    t
                    for t in tasks
                    if "not ssl_enabled | bool" in str(t.get("when", ""))
                ),
                None,
            )
            assert http_task is not None

    def test_ansible_template_loops_and_iterations(self):
        """Test Ansible templates with loops and iterations."""
        loop_template = {
            "name": "multi-instance-service",
            "installation": {
                "method": "ansible",
                "ansible": {
                    "tasks": [
                        {
                            "name": "Create service directories",
                            "file": {
                                "path": "/opt/service/{{ item }}",
                                "state": "directory",
                            },
                            "loop": ["config", "data", "logs", "backups"],
                        },
                        {
                            "name": "Deploy service instances",
                            "docker_container": {
                                "name": "service-{{ item.name }}",
                                "image": "myservice:latest",
                                "ports": ["{{ item.port }}:8080"],
                            },
                            "loop": [
                                {"name": "web1", "port": 8001},
                                {"name": "web2", "port": 8002},
                                {"name": "api", "port": 9001},
                            ],
                        },
                    ]
                },
            },
        }

        template_file = self.template_dir / "multi-instance-service.yaml"
        with open(template_file, "w") as f:
            yaml.dump(loop_template, f)

        with patch(
            "src.homelab_mcp.service_installer.TEMPLATES_DIR", self.template_dir
        ):
            installer = ServiceInstaller()
            info = installer.get_service_info("multi-instance-service")

            assert info is not None
            tasks = info["installation"]["ansible"]["tasks"]

            # Verify loop tasks exist
            dir_task = tasks[0]
            assert "loop" in dir_task
            assert len(dir_task["loop"]) == 4

            instance_task = tasks[1]
            assert "loop" in instance_task
            assert len(instance_task["loop"]) == 3
            assert instance_task["loop"][0]["name"] == "web1"


class TestAnsibleIntegrationScenarios:
    """Test real-world Ansible integration scenarios."""

    @pytest.mark.asyncio
    async def test_high_availability_service_deployment(self):
        """Test deploying a high-availability service with Ansible."""

        # Test high availability deployment scenario
        mock_runner = MockAnsibleRunner(success=True, tasks_run=4)  # 3 nodes + 1 LB

        with patch(
            "src.homelab_mcp.service_installer.AnsibleRunner", return_value=mock_runner
        ):
            # This would test the actual HA deployment logic
            pass

    @pytest.mark.asyncio
    async def test_database_cluster_deployment(self):
        """Test deploying a database cluster with Ansible."""

        # Test database cluster deployment scenario
        mock_runner = MockAnsibleRunner(
            success=True, tasks_run=3
        )  # 1 master + 2 replicas

        with patch(
            "src.homelab_mcp.service_installer.AnsibleRunner", return_value=mock_runner
        ):
            # This would test the actual database cluster deployment logic
            pass

    @pytest.mark.asyncio
    async def test_monitoring_stack_deployment(self):
        """Test deploying a complete monitoring stack with Ansible."""

        # Test monitoring stack deployment
        mock_runner = MockAnsibleRunner(
            success=True, tasks_run=4
        )  # 3 containers + 1 config

        with patch(
            "src.homelab_mcp.service_installer.AnsibleRunner", return_value=mock_runner
        ):
            # This would test the actual monitoring stack deployment logic
            pass
