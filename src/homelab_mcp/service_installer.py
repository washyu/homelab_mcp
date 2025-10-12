"""Service installation framework for homelab applications."""

import json
import subprocess
from pathlib import Path
from typing import Any

import yaml

from .ssh_tools import ssh_execute_command

# Service templates directory
TEMPLATES_DIR = Path(__file__).parent / "service_templates"


class AnsibleRunner:
    """Runner for executing Ansible playbooks."""

    def __init__(
        self, playbook_path: str, inventory_path: str, variables: dict | None = None
    ):
        self.playbook_path = playbook_path
        self.inventory_path = inventory_path
        self.variables = variables or {}
        self.results = {}

    async def run_playbook(self, extra_vars: dict | None = None) -> dict[str, Any]:
        """Execute the Ansible playbook."""
        cmd = ["ansible-playbook", "-i", self.inventory_path, self.playbook_path]

        # Add extra variables
        all_vars = {**self.variables, **(extra_vars or {})}
        if all_vars:
            vars_json = json.dumps(all_vars)
            cmd.extend(["--extra-vars", vars_json])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)

            self.results = {
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0,
            }

            return self.results

        except Exception as e:
            self.results = {
                "return_code": -1,
                "stdout": "",
                "stderr": str(e),
                "success": False,
            }
            return self.results


def generate_ansible_inventory(
    hostname: str, username: str, config: dict | None = None
) -> str:
    """Generate Ansible inventory content."""
    inventory = f"""[servers]
{hostname} ansible_user={username} ansible_ssh_private_key_file=~/.ssh/mcp_admin_rsa

[servers:vars]
ansible_python_interpreter=/usr/bin/python3
ansible_ssh_common_args='-o StrictHostKeyChecking=no'
"""

    if config and "additional_vars" in config:
        for key, value in config["additional_vars"].items():
            inventory += f"{key}={value}\n"

    return inventory


def render_template(template_content: str, variables: dict[str, Any]) -> str:
    """Simple template rendering with variable substitution."""
    result = template_content
    for key, value in variables.items():
        placeholder = f"{{{{{key}}}}}"
        result = result.replace(placeholder, str(value))
    return result


class ServiceInstaller:
    """Framework for installing and managing homelab services."""

    def __init__(self):
        self.templates = self._load_service_templates()

    def _load_service_templates(self) -> dict[str, dict]:
        """Load all service templates from the templates directory."""
        templates = {}

        # Ensure templates directory exists
        TEMPLATES_DIR.mkdir(exist_ok=True)

        # Load YAML template files
        for template_file in TEMPLATES_DIR.glob("*.yaml"):
            try:
                with open(template_file) as f:
                    service_data = yaml.safe_load(f)
                    service_name = template_file.stem
                    templates[service_name] = service_data
            except Exception as e:
                print(f"Warning: Failed to load template {template_file}: {e}")

        return templates

    def get_available_services(self) -> list[str]:
        """Get list of available service templates."""
        return list(self.templates.keys())

    def get_service_info(self, service_name: str) -> dict | None:
        """Get detailed information about a service."""
        return self.templates.get(service_name)

    async def check_service_requirements(
        self,
        service_name: str,
        hostname: str,
        username: str = "mcp_admin",
        password: str | None = None,
    ) -> dict[str, Any]:
        """Check if a device meets the requirements for a service."""
        if service_name not in self.templates:
            return {"status": "error", "error": f"Unknown service: {service_name}"}

        service = self.templates[service_name]
        requirements = service.get("requirements", {})
        results = {
            "service": service_name,
            "hostname": hostname,
            "requirements_met": True,
            "checks": {},
        }

        # Check available ports
        if "ports" in requirements:
            for port in requirements["ports"]:
                # Check if port is available
                cmd = f"ss -tlnp | grep :{port}"
                port_result = await ssh_execute_command(
                    hostname=hostname, username=username, password=password, command=cmd
                )

                port_data = json.loads(port_result)
                port_available = (
                    port_data.get("exit_code", 1) != 0
                )  # Port is free if command fails
                results["checks"][f"port_{port}"] = {
                    "required": True,
                    "available": port_available,
                    "status": "pass" if port_available else "fail",
                }
                if not port_available:
                    results["requirements_met"] = False

        # Check available memory
        if "memory_gb" in requirements:
            cmd = "free -m | grep '^Mem:' | awk '{print $2}'"
            mem_result = await ssh_execute_command(
                hostname=hostname, username=username, password=password, command=cmd
            )

            mem_data = json.loads(mem_result)
            if mem_data.get("exit_code") == 0:
                available_mb = int(mem_data.get("output", "0").split("Output:\n")[-1])
                required_mb = requirements["memory_gb"] * 1024
                memory_ok = available_mb >= required_mb

                results["checks"]["memory"] = {
                    "required_mb": required_mb,
                    "available_mb": available_mb,
                    "status": "pass" if memory_ok else "fail",
                }
                if not memory_ok:
                    results["requirements_met"] = False

        # Check disk space
        if "disk_gb" in requirements:
            cmd = "df / | tail -1 | awk '{print $4}'"
            disk_result = await ssh_execute_command(
                hostname=hostname, username=username, password=password, command=cmd
            )

            disk_data = json.loads(disk_result)
            if disk_data.get("exit_code") == 0:
                available_kb = int(disk_data.get("output", "0").split("Output:\n")[-1])
                required_kb = requirements["disk_gb"] * 1024 * 1024
                disk_ok = available_kb >= required_kb

                results["checks"]["disk_space"] = {
                    "required_gb": requirements["disk_gb"],
                    "available_gb": round(available_kb / 1024 / 1024, 2),
                    "status": "pass" if disk_ok else "fail",
                }
                if not disk_ok:
                    results["requirements_met"] = False

        return results

    async def install_service(
        self,
        service_name: str,
        hostname: str,
        username: str = "mcp_admin",
        password: str | None = None,
        config_override: dict | None = None,
    ) -> dict[str, Any]:
        """Install a service on the target device."""
        if service_name not in self.templates:
            return {"status": "error", "error": f"Unknown service: {service_name}"}

        service = self.templates[service_name]

        # Check requirements first
        req_check = await self.check_service_requirements(
            service_name, hostname, username, password
        )

        if not req_check["requirements_met"]:
            return {
                "status": "error",
                "error": "Requirements not met",
                "requirement_check": req_check,
            }

        # Get installation method
        install_method = service.get("installation", {}).get("method", "docker-compose")

        if install_method == "docker-compose":
            return await self._install_docker_compose_service(
                service_name, service, hostname, username, password, config_override
            )
        elif install_method == "script":
            return await self._install_script_service(
                service_name, service, hostname, username, password, config_override
            )
        elif install_method == "terraform":
            return await self._install_terraform_service(
                service_name, service, hostname, username, password, config_override
            )
        elif install_method == "ansible":
            return await self._install_ansible_service(
                service_name, service, hostname, username, password, config_override
            )
        elif install_method == "iso_installation":
            return await self._install_iso_service(
                service_name, service, hostname, username, password, config_override
            )
        else:
            return {
                "status": "error",
                "error": f"Unsupported installation method: {install_method}",
            }

    async def _install_docker_compose_service(
        self,
        service_name: str,
        service: dict,
        hostname: str,
        username: str,
        password: str | None,
        config_override: dict | None,
    ) -> dict[str, Any]:
        """Install a service using Docker Compose."""
        results = {
            "service": service_name,
            "hostname": hostname,
            "installation_method": "docker-compose",
            "steps": [],
        }

        try:
            # Step 1: Ensure Docker is installed
            docker_check = await ssh_execute_command(
                hostname=hostname,
                username=username,
                password=password,
                command="docker --version",
            )

            docker_data = json.loads(docker_check)
            if docker_data.get("exit_code") != 0:
                results["steps"].append(
                    {
                        "step": "check_docker",
                        "status": "fail",
                        "error": "Docker not installed",
                    }
                )
                return {"status": "error", "results": results}

            results["steps"].append({"step": "check_docker", "status": "success"})

            # Step 2: Ensure Docker Compose is available
            compose_check = await ssh_execute_command(
                hostname=hostname,
                username=username,
                password=password,
                command="docker compose version",
            )

            compose_data = json.loads(compose_check)
            if compose_data.get("exit_code") != 0:
                results["steps"].append(
                    {
                        "step": "check_docker_compose",
                        "status": "fail",
                        "error": "Docker Compose not available",
                    }
                )
                return {"status": "error", "results": results}

            results["steps"].append(
                {"step": "check_docker_compose", "status": "success"}
            )

            # Step 3: Create service directory
            service_dir = f"/opt/{service_name}"
            mkdir_result = await ssh_execute_command(
                hostname=hostname,
                username=username,
                password=password,
                command=f"sudo mkdir -p {service_dir}",
                sudo=False,  # sudo is included in command
            )

            mkdir_data = json.loads(mkdir_result)
            if mkdir_data.get("exit_code") != 0:
                results["steps"].append(
                    {
                        "step": "create_directory",
                        "status": "fail",
                        "error": f"Failed to create {service_dir}",
                    }
                )
                return {"status": "error", "results": results}

            results["steps"].append(
                {
                    "step": "create_directory",
                    "status": "success",
                    "directory": service_dir,
                }
            )

            # Step 4: Generate docker-compose.yml
            compose_content = service["installation"]["docker_compose"]

            # Apply configuration overrides
            if config_override:
                # Simple merge for now - could be more sophisticated
                compose_content = self._merge_config(compose_content, config_override)

            # Write docker-compose.yml to remote system
            compose_yaml = yaml.dump(compose_content, default_flow_style=False)
            write_compose = await ssh_execute_command(
                hostname=hostname,
                username=username,
                password=password,
                command=f"sudo tee {service_dir}/docker-compose.yml > /dev/null << 'EOF'\n{compose_yaml}\nEOF",
            )

            write_data = json.loads(write_compose)
            if write_data.get("exit_code") != 0:
                results["steps"].append(
                    {
                        "step": "write_compose_file",
                        "status": "fail",
                        "error": "Failed to write docker-compose.yml",
                    }
                )
                return {"status": "error", "results": results}

            results["steps"].append({"step": "write_compose_file", "status": "success"})

            # Step 5: Start the service
            start_result = await ssh_execute_command(
                hostname=hostname,
                username=username,
                password=password,
                command=f"cd {service_dir} && sudo docker compose up -d",
            )

            start_data = json.loads(start_result)
            if start_data.get("exit_code") != 0:
                results["steps"].append(
                    {
                        "step": "start_service",
                        "status": "fail",
                        "error": f"Failed to start service: {start_data.get('output', '')}",
                    }
                )
                return {"status": "error", "results": results}

            results["steps"].append(
                {
                    "step": "start_service",
                    "status": "success",
                    "output": start_data.get("output", ""),
                }
            )

            # Step 6: Verify service is running
            status_result = await ssh_execute_command(
                hostname=hostname,
                username=username,
                password=password,
                command=f"cd {service_dir} && sudo docker compose ps",
            )

            status_data = json.loads(status_result)
            results["steps"].append(
                {
                    "step": "verify_service",
                    "status": "success"
                    if status_data.get("exit_code") == 0
                    else "warning",
                    "container_status": status_data.get("output", ""),
                }
            )

            return {
                "status": "success",
                "service": service_name,
                "hostname": hostname,
                "access_url": f"http://{hostname}:{service.get('default_port', 8080)}",
                "installation_directory": service_dir,
                "results": results,
            }

        except Exception as e:
            results["steps"].append(
                {"step": "exception", "status": "fail", "error": str(e)}
            )
            return {"status": "error", "results": results}

    async def _install_script_service(
        self,
        service_name: str,
        service: dict,
        hostname: str,
        username: str,
        password: str | None,
        config_override: dict | None,
    ) -> dict[str, Any]:
        """Install a service using shell scripts."""
        # TODO: Implement script-based installation
        return {
            "status": "error",
            "error": "Script-based installation not yet implemented",
        }

    def _merge_config(self, base_config: dict, override: dict) -> dict:
        """Merge configuration override with base configuration."""
        # Simple recursive merge - could be enhanced
        result = base_config.copy()

        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value

        return result

    async def get_service_status(
        self,
        service_name: str,
        hostname: str,
        username: str = "mcp_admin",
        password: str | None = None,
    ) -> dict[str, Any]:
        """Get the current status of an installed service."""
        service_dir = f"/opt/{service_name}"

        # Check if service directory exists
        dir_check = await ssh_execute_command(
            hostname=hostname,
            username=username,
            password=password,
            command=f"test -d {service_dir}",
        )

        dir_data = json.loads(dir_check)
        if dir_data.get("exit_code") != 0:
            return {
                "status": "not_installed",
                "service": service_name,
                "hostname": hostname,
            }

        # Check container status
        status_result = await ssh_execute_command(
            hostname=hostname,
            username=username,
            password=password,
            command=f"cd {service_dir} && sudo docker compose ps --format json",
        )

        status_data = json.loads(status_result)

        return {
            "status": "installed",
            "service": service_name,
            "hostname": hostname,
            "container_status": status_data.get("output", ""),
            "service_directory": service_dir,
        }

    async def _install_terraform_service(
        self,
        service_name: str,
        service: dict,
        hostname: str,
        username: str,
        password: str | None,
        config_override: dict | None,
    ) -> dict[str, Any]:
        """Install a service using Terraform."""
        results = {
            "service": service_name,
            "hostname": hostname,
            "installation_method": "terraform",
            "steps": [],
        }

        try:
            # Step 1: Check if Terraform is installed
            tf_check = await ssh_execute_command(
                hostname=hostname,
                username=username,
                password=password,
                command="terraform version",
            )

            tf_data = json.loads(tf_check)
            if tf_data.get("exit_code") != 0:
                # Install Terraform
                install_cmd = """
                wget -O- https://apt.releases.hashicorp.com/gpg | gpg --dearmor | sudo tee /usr/share/keyrings/hashicorp-archive-keyring.gpg
                echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
                sudo apt update && sudo apt install -y terraform
                """
                install_result = await ssh_execute_command(
                    hostname=hostname,
                    username=username,
                    password=password,
                    command=install_cmd,
                    sudo=True,
                )

                install_data = json.loads(install_result)
                if install_data.get("exit_code") != 0:
                    results["steps"].append(
                        {
                            "step": "install_terraform",
                            "status": "fail",
                            "error": "Failed to install Terraform",
                        }
                    )
                    return {"status": "error", "results": results}

            results["steps"].append({"step": "check_terraform", "status": "success"})

            # Step 2: Create Terraform workspace
            tf_dir = f"/opt/terraform/{service_name}"
            mkdir_result = await ssh_execute_command(
                hostname=hostname,
                username=username,
                password=password,
                command=f"sudo mkdir -p {tf_dir} && sudo chown {username}:{username} {tf_dir}",
                sudo=True,
            )

            results["steps"].append(
                {
                    "step": "create_workspace",
                    "status": "success"
                    if json.loads(mkdir_result).get("exit_code") == 0
                    else "fail",
                }
            )

            # Step 3: Generate Terraform files
            tf_config = service["installation"]["terraform"]

            # Generate main.tf
            main_tf_content = tf_config["main_tf"]
            # Replace template variables
            main_tf_content = main_tf_content.replace("{{hostname}}", hostname)
            main_tf_content = main_tf_content.replace("{{service_name}}", service_name)

            # Write main.tf
            await self._write_remote_file(
                hostname, username, password, f"{tf_dir}/main.tf", main_tf_content
            )

            # Generate variables.tf if variables are defined
            if "variables" in tf_config:
                variables_tf = self._generate_variables_tf(tf_config["variables"])
                await self._write_remote_file(
                    hostname, username, password, f"{tf_dir}/variables.tf", variables_tf
                )

                # Generate terraform.tfvars
                tfvars = self._generate_tfvars(
                    tf_config["variables"],
                    config_override,
                    hostname,
                    username,
                    password,
                )
                await self._write_remote_file(
                    hostname, username, password, f"{tf_dir}/terraform.tfvars", tfvars
                )

            # Generate backend configuration
            if "backend" in tf_config:
                backend_tf = self._generate_backend_tf(
                    tf_config["backend"], service_name, hostname
                )
                await self._write_remote_file(
                    hostname, username, password, f"{tf_dir}/backend.tf", backend_tf
                )

            results["steps"].append(
                {"step": "generate_terraform_files", "status": "success"}
            )

            # Step 4: Terraform init
            init_result = await ssh_execute_command(
                hostname=hostname,
                username=username,
                password=password,
                command=f"cd {tf_dir} && terraform init -upgrade",
            )

            init_data = json.loads(init_result)
            results["steps"].append(
                {
                    "step": "terraform_init",
                    "status": "success" if init_data.get("exit_code") == 0 else "fail",
                    "output": init_data.get("output", ""),
                }
            )

            if init_data.get("exit_code") != 0:
                return {"status": "error", "results": results}

            # Step 5: Terraform plan
            plan_result = await ssh_execute_command(
                hostname=hostname,
                username=username,
                password=password,
                command=f"cd {tf_dir} && terraform plan -out=tfplan",
            )

            plan_data = json.loads(plan_result)
            results["steps"].append(
                {
                    "step": "terraform_plan",
                    "status": "success" if plan_data.get("exit_code") == 0 else "fail",
                }
            )

            if plan_data.get("exit_code") != 0:
                return {"status": "error", "results": results}

            # Step 6: Terraform apply
            apply_result = await ssh_execute_command(
                hostname=hostname,
                username=username,
                password=password,
                command=f"cd {tf_dir} && terraform apply -auto-approve tfplan",
            )

            apply_data = json.loads(apply_result)
            results["steps"].append(
                {
                    "step": "terraform_apply",
                    "status": "success" if apply_data.get("exit_code") == 0 else "fail",
                }
            )

            if apply_data.get("exit_code") != 0:
                return {"status": "error", "results": results}

            # Step 7: Get outputs
            outputs_result = await ssh_execute_command(
                hostname=hostname,
                username=username,
                password=password,
                command=f"cd {tf_dir} && terraform output -json",
            )

            outputs_data = json.loads(outputs_result)
            if outputs_data.get("exit_code") == 0:
                try:
                    outputs = json.loads(outputs_data.get("output", "{}"))
                    results["terraform_outputs"] = outputs
                except json.JSONDecodeError:
                    pass

            # Step 8: Save state backup if configured
            if (
                tf_config.get("state_management", {})
                .get("backup", {})
                .get("enabled", True)
            ):
                backup_result = await self._backup_terraform_state(
                    hostname,
                    username,
                    password,
                    f"{tf_dir}/terraform.tfstate",
                    service_name,
                )
                results["steps"].append(
                    {
                        "step": "backup_state",
                        "status": "success" if backup_result else "fail",
                    }
                )

            return {
                "status": "success",
                "service": service_name,
                "hostname": hostname,
                "terraform_directory": tf_dir,
                "outputs": results.get("terraform_outputs", {}),
                "results": results,
            }

        except Exception as e:
            results["steps"].append(
                {"step": "exception", "status": "fail", "error": str(e)}
            )
            return {"status": "error", "results": results}

    async def _write_remote_file(
        self,
        hostname: str,
        username: str,
        password: str | None,
        remote_path: str,
        content: str,
    ) -> bool:
        """Write content to a remote file."""
        # Escape single quotes in content
        escaped_content = content.replace("'", "'\"'\"'")

        # Use printf to avoid issues with special characters
        write_cmd = f"printf '%s' '{escaped_content}' > {remote_path}"

        result = await ssh_execute_command(
            hostname=hostname, username=username, password=password, command=write_cmd
        )

        data = json.loads(result)
        return data.get("exit_code") == 0

    def _generate_variables_tf(self, variables: dict) -> str:
        """Generate variables.tf file from template variables."""
        content = []
        for var_name, var_config in variables.items():
            var_block = f'variable "{var_name}" {{\n'

            if "type" in var_config:
                var_block += f"  type = {var_config['type']}\n"

            if "default" in var_config:
                default_val = var_config["default"]
                if isinstance(default_val, str):
                    var_block += f'  default = "{default_val}"\n'
                elif isinstance(default_val, bool):
                    var_block += f"  default = {str(default_val).lower()}\n"
                elif isinstance(default_val, list):
                    var_block += f"  default = {json.dumps(default_val)}\n"
                else:
                    var_block += f"  default = {default_val}\n"

            if "description" in var_config:
                var_block += f'  description = "{var_config["description"]}"\n'

            if "sensitive" in var_config and var_config["sensitive"]:
                var_block += "  sensitive = true\n"

            if "validation" in var_config:
                var_block += "  validation {\n"
                validation_values = ", ".join(
                    [f'"{v}"' for v in var_config["validation"]]
                )
                var_block += (
                    f"    condition = contains([{validation_values}], var.{var_name})\n"
                )
                var_block += f'    error_message = "Invalid value for {var_name}. Must be one of: {", ".join(var_config["validation"])}"\n'
                var_block += "  }\n"

            var_block += "}\n"
            content.append(var_block)

        return "\n".join(content)

    def _generate_tfvars(
        self,
        variables: dict,
        overrides: dict | None,
        hostname: str,
        username: str,
        password: str | None,
    ) -> str:
        """Generate terraform.tfvars file with actual values."""
        tfvars = {}

        # Process template variables
        for var_name, var_config in variables.items():
            if "default" in var_config:
                default = var_config["default"]
                # Replace template variables
                if isinstance(default, str):
                    default = default.replace("{{hostname}}", hostname)
                    default = default.replace(
                        "{{service_name}}",
                        self.service_name if hasattr(self, "service_name") else "",
                    )
                tfvars[var_name] = default

        # Add SSH credentials for Terraform to use
        tfvars["ssh_user"] = username
        if password:
            tfvars["ssh_password"] = password

        # Apply overrides
        if overrides:
            tfvars.update(overrides)

        # Generate tfvars content
        content = []
        for key, value in tfvars.items():
            if isinstance(value, str):
                content.append(f'{key} = "{value}"')
            elif isinstance(value, bool):
                content.append(f"{key} = {str(value).lower()}")
            elif isinstance(value, list):
                content.append(f"{key} = {json.dumps(value)}")
            else:
                content.append(f"{key} = {value}")

        return "\n".join(content)

    def _generate_backend_tf(
        self, backend_config: dict, service_name: str, hostname: str
    ) -> str:
        """Generate backend.tf for state management."""
        backend_type = backend_config.get("type", "local")

        if backend_type == "local":
            path = backend_config.get(
                "path", f"/opt/terraform-states/{service_name}-{hostname}.tfstate"
            )
            # Replace template variables
            path = path.replace("{{service_name}}", service_name)
            path = path.replace("{{hostname}}", hostname)

            return f'''terraform {{
  backend "local" {{
    path = "{path}"
  }}
}}'''

        elif backend_type == "s3":
            config = backend_config.get("config", {})
            bucket = config.get("bucket", "terraform-states")
            key = config.get(
                "key", f"services/{service_name}/{hostname}/terraform.tfstate"
            )
            # Replace template variables
            key = key.replace("{{service_name}}", service_name)
            key = key.replace("{{hostname}}", hostname)

            return f'''terraform {{
  backend "s3" {{
    bucket = "{bucket}"
    key    = "{key}"
    region = "{config.get("region", "us-east-1")}"
    encrypt = {str(config.get("encrypt", True)).lower()}
  }}
}}'''

        else:
            # Default to local backend
            return f"""terraform {{
  backend "local" {{
    path = "/opt/terraform-states/{service_name}-{hostname}.tfstate"
  }}
}}"""

    async def _backup_terraform_state(
        self,
        hostname: str,
        username: str,
        password: str | None,
        state_path: str,
        service_name: str,
    ) -> bool:
        """Backup Terraform state file."""
        backup_dir = "/opt/terraform-state-backups"
        timestamp = "$(date +%Y%m%d-%H%M%S)"
        backup_path = f"{backup_dir}/{service_name}-{timestamp}.tfstate"

        # Create backup directory
        mkdir_cmd = f"sudo mkdir -p {backup_dir} && sudo chown {username}:{username} {backup_dir}"
        await ssh_execute_command(
            hostname=hostname,
            username=username,
            password=password,
            command=mkdir_cmd,
            sudo=True,
        )

        # Copy state file to backup
        backup_cmd = f"cp {state_path} {backup_path}"
        result = await ssh_execute_command(
            hostname=hostname, username=username, password=password, command=backup_cmd
        )

        data = json.loads(result)
        return data.get("exit_code") == 0

    async def destroy_terraform_service(
        self,
        service_name: str,
        hostname: str,
        username: str = "mcp_admin",
        password: str | None = None,
    ) -> dict[str, Any]:
        """Destroy a Terraform-managed service."""
        tf_dir = f"/opt/terraform/{service_name}"

        # Check if Terraform directory exists
        dir_check = await ssh_execute_command(
            hostname=hostname,
            username=username,
            password=password,
            command=f"test -d {tf_dir}",
        )

        dir_data = json.loads(dir_check)
        if dir_data.get("exit_code") != 0:
            return {
                "status": "error",
                "error": f"Terraform directory not found: {tf_dir}",
            }

        # Run terraform destroy
        destroy_result = await ssh_execute_command(
            hostname=hostname,
            username=username,
            password=password,
            command=f"cd {tf_dir} && terraform destroy -auto-approve",
        )

        destroy_data = json.loads(destroy_result)

        # Clean up Terraform directory if destroy succeeded
        if destroy_data.get("exit_code") == 0:
            cleanup_result = await ssh_execute_command(
                hostname=hostname,
                username=username,
                password=password,
                command=f"sudo rm -rf {tf_dir}",
                sudo=True,
            )

        return {
            "status": "success" if destroy_data.get("exit_code") == 0 else "error",
            "service": service_name,
            "action": "destroy",
            "output": destroy_data.get("output", ""),
        }

    async def plan_terraform_service(
        self,
        service_name: str,
        hostname: str,
        username: str = "mcp_admin",
        password: str | None = None,
        config_override: dict | None = None,
    ) -> dict[str, Any]:
        """Generate a Terraform plan without applying changes."""
        if service_name not in self.templates:
            return {"status": "error", "error": f"Unknown service: {service_name}"}

        service = self.templates[service_name]
        tf_dir = f"/opt/terraform/{service_name}"

        # Check if already installed
        dir_check = await ssh_execute_command(
            hostname=hostname,
            username=username,
            password=password,
            command=f"test -d {tf_dir}",
        )

        dir_data = json.loads(dir_check)

        if dir_data.get("exit_code") == 0:
            # Service exists, just run plan
            plan_result = await ssh_execute_command(
                hostname=hostname,
                username=username,
                password=password,
                command=f"cd {tf_dir} && terraform plan",
            )

            plan_data = json.loads(plan_result)
            return {
                "status": "success" if plan_data.get("exit_code") == 0 else "error",
                "service": service_name,
                "action": "plan",
                "existing": True,
                "output": plan_data.get("output", ""),
            }
        else:
            # Service doesn't exist, need to set up first
            return {
                "status": "info",
                "service": service_name,
                "action": "plan",
                "existing": False,
                "message": "Service not installed. Run install_service first to see the plan.",
            }

    async def refresh_terraform_service(
        self,
        service_name: str,
        hostname: str,
        username: str = "mcp_admin",
        password: str | None = None,
    ) -> dict[str, Any]:
        """Refresh Terraform state and detect drift."""
        tf_dir = f"/opt/terraform/{service_name}"

        # Check if Terraform directory exists
        dir_check = await ssh_execute_command(
            hostname=hostname,
            username=username,
            password=password,
            command=f"test -d {tf_dir}",
        )

        dir_data = json.loads(dir_check)
        if dir_data.get("exit_code") != 0:
            return {"status": "error", "error": f"Service not found: {service_name}"}

        # Run terraform refresh
        refresh_result = await ssh_execute_command(
            hostname=hostname,
            username=username,
            password=password,
            command=f"cd {tf_dir} && terraform refresh",
        )

        refresh_data = json.loads(refresh_result)

        # Check for drift with plan
        plan_result = await ssh_execute_command(
            hostname=hostname,
            username=username,
            password=password,
            command=f"cd {tf_dir} && terraform plan -detailed-exitcode",
        )

        plan_data = json.loads(plan_result)
        # Exit code 2 means there are changes
        has_changes = plan_data.get("exit_code") == 2

        return {
            "status": "drift_detected" if has_changes else "in_sync",
            "service": service_name,
            "has_changes": has_changes,
            "refresh_output": refresh_data.get("output", ""),
            "plan_output": plan_data.get("output", "") if has_changes else None,
        }

    async def _install_ansible_service(
        self,
        service_name: str,
        service: dict,
        hostname: str,
        username: str,
        password: str | None,
        config_override: dict | None,
    ) -> dict[str, Any]:
        """Install a service using Ansible playbook."""
        ansible_config = service.get("installation", {}).get("ansible", {})

        if not ansible_config:
            return {
                "status": "error",
                "error": "No Ansible configuration found in service template",
            }

        # Create Ansible directory structure
        ansible_dir = f"/opt/ansible/{service_name}"
        setup_cmd = f"""
sudo mkdir -p {ansible_dir}/playbooks {ansible_dir}/inventory {ansible_dir}/group_vars {ansible_dir}/host_vars && 
sudo chown -R {username}:{username} {ansible_dir}
"""

        setup_result = await ssh_execute_command(
            hostname=hostname,
            username=username,
            password=password,
            command=setup_cmd,
            sudo=True,
        )

        setup_data = json.loads(setup_result)
        if setup_data.get("exit_code") != 0:
            return {
                "status": "error",
                "error": "Failed to create Ansible directory structure",
                "output": setup_data.get("output", ""),
            }

        # Generate inventory file
        inventory_content = self._generate_ansible_inventory(
            hostname, username, config_override
        )
        inventory_result = await ssh_execute_command(
            hostname=hostname,
            username=username,
            password=password,
            command=f"cat > {ansible_dir}/inventory/hosts << 'EOF'\n{inventory_content}\nEOF",
        )

        inventory_data = json.loads(inventory_result)
        if inventory_data.get("exit_code") != 0:
            return {
                "status": "error",
                "error": "Failed to create inventory file",
                "output": inventory_data.get("output", ""),
            }

        # Generate playbook
        playbook_content = self._generate_ansible_playbook(
            service, service_name, config_override
        )
        playbook_result = await ssh_execute_command(
            hostname=hostname,
            username=username,
            password=password,
            command=f"cat > {ansible_dir}/playbooks/{service_name}.yml << 'EOF'\n{playbook_content}\nEOF",
        )

        playbook_data = json.loads(playbook_result)
        if playbook_data.get("exit_code") != 0:
            return {
                "status": "error",
                "error": "Failed to create playbook",
                "output": playbook_data.get("output", ""),
            }

        # Generate group variables
        if config_override or service.get("default_config"):
            vars_content = self._generate_ansible_vars(service, config_override)
            vars_result = await ssh_execute_command(
                hostname=hostname,
                username=username,
                password=password,
                command=f"cat > {ansible_dir}/group_vars/all.yml << 'EOF'\n{vars_content}\nEOF",
            )

        # Install Ansible if not present
        ansible_check = await ssh_execute_command(
            hostname=hostname,
            username=username,
            password=password,
            command="which ansible-playbook",
        )

        ansible_data = json.loads(ansible_check)
        if ansible_data.get("exit_code") != 0:
            # Install Ansible
            install_cmd = """
if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update && sudo apt-get install -y ansible
elif command -v yum >/dev/null 2>&1; then
    sudo yum install -y epel-release && sudo yum install -y ansible
elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y ansible
elif command -v pacman >/dev/null 2>&1; then
    sudo pacman -S --noconfirm ansible
else
    echo "Unsupported package manager for Ansible installation"
    exit 1
fi
"""
            install_result = await ssh_execute_command(
                hostname=hostname,
                username=username,
                password=password,
                command=install_cmd,
                sudo=True,
            )

            install_data = json.loads(install_result)
            if install_data.get("exit_code") != 0:
                return {
                    "status": "error",
                    "error": "Failed to install Ansible",
                    "output": install_data.get("output", ""),
                }

        # Run the playbook
        run_cmd = f"cd {ansible_dir} && ansible-playbook -i inventory/hosts playbooks/{service_name}.yml"

        # Add verbose output if in debug mode
        if config_override and config_override.get("debug", False):
            run_cmd += " -vvv"

        run_result = await ssh_execute_command(
            hostname=hostname, username=username, password=password, command=run_cmd
        )

        run_data = json.loads(run_result)

        return {
            "status": "success" if run_data.get("exit_code") == 0 else "error",
            "service": service_name,
            "method": "ansible",
            "output": run_data.get("output", ""),
            "ansible_dir": ansible_dir,
            "playbook_path": f"{ansible_dir}/playbooks/{service_name}.yml",
        }

    def _generate_ansible_inventory(
        self, hostname: str, username: str, config_override: dict | None
    ) -> str:
        """Generate Ansible inventory file."""
        inventory = f"""[homelab]
{hostname} ansible_user={username} ansible_ssh_private_key_file=~/.ssh/mcp_admin_rsa

[homelab:vars]
ansible_python_interpreter=/usr/bin/python3
ansible_ssh_common_args='-o StrictHostKeyChecking=no'
"""

        # Add any custom inventory variables
        if config_override and "inventory_vars" in config_override:
            inventory += "\n"
            for key, value in config_override["inventory_vars"].items():
                inventory += f"{key}={value}\n"

        return inventory

    def _generate_ansible_playbook(
        self, service: dict, service_name: str, config_override: dict | None
    ) -> str:
        """Generate Ansible playbook from service template."""
        ansible_config = service.get("installation", {}).get("ansible", {})

        # Base playbook structure
        playbook = f"""---
- name: Deploy {service.get("name", service_name)}
  hosts: homelab
  become: yes
  gather_facts: yes
  
  vars:
    service_name: {service_name}
    service_description: "{service.get("description", "")}"
    
  tasks:
"""

        # Add pre-tasks if defined
        if "pre_tasks" in ansible_config:
            playbook += "    # Pre-installation tasks\n"
            for task in ansible_config["pre_tasks"]:
                playbook += self._format_ansible_task(task, 4)

        # Add main tasks
        if "tasks" in ansible_config:
            playbook += "    # Main installation tasks\n"
            for task in ansible_config["tasks"]:
                playbook += self._format_ansible_task(task, 4)

        # Add post-tasks if defined
        if "post_tasks" in ansible_config:
            playbook += "    # Post-installation tasks\n"
            for task in ansible_config["post_tasks"]:
                playbook += self._format_ansible_task(task, 4)

        # Add handlers if defined
        if "handlers" in ansible_config:
            playbook += "\n  handlers:\n"
            for handler in ansible_config["handlers"]:
                playbook += self._format_ansible_task(handler, 4)

        return playbook

    def _format_ansible_task(self, task: dict, indent: int) -> str:
        """Format an Ansible task with proper indentation."""
        spaces = " " * indent
        task_str = f"{spaces}- name: {task.get('name', 'Unnamed task')}\n"

        for key, value in task.items():
            if key == "name":
                continue

            if isinstance(value, dict):
                task_str += f"{spaces}  {key}:\n"
                for k, v in value.items():
                    task_str += f"{spaces}    {k}: {v}\n"
            elif isinstance(value, list):
                task_str += f"{spaces}  {key}:\n"
                for item in value:
                    task_str += f"{spaces}    - {item}\n"
            else:
                task_str += f"{spaces}  {key}: {value}\n"

        return task_str + "\n"

    def _generate_ansible_vars(
        self, service: dict, config_override: dict | None
    ) -> str:
        """Generate Ansible variables file."""
        vars_content = "---\n# Service configuration variables\n\n"

        # Add default configuration
        default_config = service.get("default_config", {})
        for key, value in default_config.items():
            vars_content += f"{key}: {yaml.dump(value).strip()}\n"

        # Add configuration overrides
        if config_override:
            vars_content += "\n# Configuration overrides\n"
            for key, value in config_override.items():
                if key not in ["debug", "inventory_vars"]:  # Skip special keys
                    vars_content += f"{key}: {yaml.dump(value).strip()}\n"

        return vars_content

    async def check_ansible_service(
        self,
        service_name: str,
        hostname: str,
        username: str = "mcp_admin",
        password: str | None = None,
    ) -> dict[str, Any]:
        """Check the status of an Ansible-managed service."""
        ansible_dir = f"/opt/ansible/{service_name}"

        # Check if Ansible directory exists
        dir_check = await ssh_execute_command(
            hostname=hostname,
            username=username,
            password=password,
            command=f"test -d {ansible_dir}",
        )

        dir_data = json.loads(dir_check)
        if dir_data.get("exit_code") != 0:
            return {
                "status": "not_found",
                "service": service_name,
                "error": f"Ansible deployment not found: {ansible_dir}",
            }

        # Check playbook exists
        playbook_path = f"{ansible_dir}/playbooks/{service_name}.yml"
        playbook_check = await ssh_execute_command(
            hostname=hostname,
            username=username,
            password=password,
            command=f"test -f {playbook_path}",
        )

        playbook_data = json.loads(playbook_check)
        if playbook_data.get("exit_code") != 0:
            return {
                "status": "error",
                "service": service_name,
                "error": f"Playbook not found: {playbook_path}",
            }

        # Get file information
        info_result = await ssh_execute_command(
            hostname=hostname,
            username=username,
            password=password,
            command=f"ls -la {ansible_dir}/playbooks/{service_name}.yml {ansible_dir}/inventory/hosts",
        )

        info_data = json.loads(info_result)

        # Check if Ansible is installed
        ansible_check = await ssh_execute_command(
            hostname=hostname,
            username=username,
            password=password,
            command="ansible-playbook --version",
        )

        ansible_data = json.loads(ansible_check)
        ansible_installed = ansible_data.get("exit_code") == 0

        return {
            "status": "deployed",
            "service": service_name,
            "ansible_dir": ansible_dir,
            "playbook_path": playbook_path,
            "ansible_installed": ansible_installed,
            "ansible_version": ansible_data.get("output", "").split("\n")[0]
            if ansible_installed
            else None,
            "files_info": info_data.get("output", ""),
        }

    async def run_ansible_playbook(
        self,
        service_name: str,
        hostname: str,
        username: str = "mcp_admin",
        password: str | None = None,
        tags: list[str] | None = None,
        extra_vars: dict | None = None,
        check_mode: bool = False,
    ) -> dict[str, Any]:
        """Run an existing Ansible playbook for a service."""
        ansible_dir = f"/opt/ansible/{service_name}"
        playbook_path = f"{ansible_dir}/playbooks/{service_name}.yml"

        # Check if playbook exists
        check_result = await self.check_ansible_service(
            service_name, hostname, username, password
        )
        if check_result["status"] != "deployed":
            return check_result

        # Build ansible-playbook command
        cmd = f"cd {ansible_dir} && ansible-playbook -i inventory/hosts playbooks/{service_name}.yml"

        # Add check mode if requested
        if check_mode:
            cmd += " --check"

        # Add tags if specified
        if tags:
            cmd += f" --tags {','.join(tags)}"

        # Add extra variables if specified
        if extra_vars:
            for key, value in extra_vars.items():
                cmd += f" --extra-vars '{key}={value}'"

        # Add verbose output
        cmd += " -v"

        # Run the playbook
        run_result = await ssh_execute_command(
            hostname=hostname, username=username, password=password, command=cmd
        )

        run_data = json.loads(run_result)

        return {
            "status": "success" if run_data.get("exit_code") == 0 else "error",
            "service": service_name,
            "action": "check" if check_mode else "run",
            "command": cmd,
            "output": run_data.get("output", ""),
            "exit_code": run_data.get("exit_code"),
        }

    async def _install_iso_service(
        self,
        service_name: str,
        service: dict,
        hostname: str,
        username: str,
        password: str | None,
        config_override: dict | None,
    ) -> dict[str, Any]:
        """Handle ISO-based installation (like TrueNAS, Proxmox, etc.)."""
        # ISO installations typically require manual intervention or VM/bare metal setup
        # This method provides guidance rather than automated installation

        installation_config = service.get("installation", {})
        download_url = installation_config.get("download_url")
        installation_steps = installation_config.get("installation_steps", [])
        requirements = installation_config.get("requirements", [])

        return {
            "status": "guidance",
            "service": service_name,
            "method": "iso_installation",
            "message": "ISO-based installations require manual setup",
            "guidance": {
                "download_url": download_url,
                "requirements": requirements,
                "installation_steps": installation_steps,
                "installation_type": installation_config.get(
                    "installation_type", "bare_metal_or_vm"
                ),
                "target_hostname": hostname,
                "next_steps": [
                    "Download the ISO from the provided URL",
                    "Create bootable media or mount ISO in VM",
                    "Boot target system from installation media",
                    "Follow the provided installation steps",
                    "Configure network settings to match target hostname",
                    "Complete post-installation configuration",
                ],
            },
        }
