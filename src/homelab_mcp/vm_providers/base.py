"""Abstract base class for VM providers."""

from abc import ABC, abstractmethod
from typing import Any


class VMProvider(ABC):
    """Abstract base class for VM/container providers."""

    @abstractmethod
    async def deploy_vm(self, conn: Any, vm_name: str, vm_config: dict[str, Any]) -> dict[str, Any]:
        """Deploy a new VM/container."""
        pass

    @abstractmethod
    async def start_vm(self, conn: Any, vm_name: str) -> dict[str, Any]:
        """Start an existing VM/container."""
        pass

    @abstractmethod
    async def stop_vm(self, conn: Any, vm_name: str) -> dict[str, Any]:
        """Stop a running VM/container."""
        pass

    @abstractmethod
    async def restart_vm(self, conn: Any, vm_name: str) -> dict[str, Any]:
        """Restart a VM/container."""
        pass

    @abstractmethod
    async def get_vm_status(self, conn: Any, vm_name: str) -> dict[str, Any]:
        """Get the status of a VM/container."""
        pass

    @abstractmethod
    async def list_vms(self, conn: Any) -> dict[str, Any]:
        """List all VMs/containers."""
        pass

    @abstractmethod
    async def get_vm_logs(self, conn: Any, vm_name: str, lines: int = 100) -> dict[str, Any]:
        """Get logs from a VM/container."""
        pass

    @abstractmethod
    async def remove_vm(self, conn: Any, vm_name: str, force: bool = False) -> dict[str, Any]:
        """Remove a VM/container."""
        pass

    async def control_vm(self, conn: Any, vm_name: str, action: str) -> dict[str, Any]:
        """Control VM state with the specified action."""
        action_lower = action.lower()

        if action_lower == "start":
            return await self.start_vm(conn, vm_name)
        elif action_lower == "stop":
            return await self.stop_vm(conn, vm_name)
        elif action_lower == "restart":
            return await self.restart_vm(conn, vm_name)
        else:
            return {
                "status": "error",
                "message": f"Unknown action: {action}. Supported actions: start, stop, restart",
            }

    def _format_error(self, operation: str, vm_name: str, error: str) -> dict[str, Any]:
        """Format error response consistently."""
        return {
            "status": "error",
            "operation": operation,
            "vm_name": vm_name,
            "error": error,
        }

    def _format_success(self, operation: str, vm_name: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
        """Format success response consistently."""
        result = {"status": "success", "operation": operation, "vm_name": vm_name}
        if details:
            result.update(details)
        return result

    async def _run_command(self, conn: Any, command: str) -> dict[str, Any]:
        """Run a command and return structured result."""
        try:
            result = await conn.run(command)
            return {
                "exit_status": result.exit_status,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except Exception as e:
            return {"exit_status": -1, "stdout": "", "stderr": str(e)}
