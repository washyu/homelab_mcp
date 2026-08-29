"""Handler functions for SSH-related tools."""

import json
import os
from typing import Any

from .. import background_jobs
from ..shell_session import session_manager
from ..ssh_tools import (
    ssh_discover_system,
    ssh_execute_command,
)
from ..validation import validate_hostname, validate_port


async def handle_ssh_discover(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle ssh_discover tool."""
    result = await ssh_discover_system(**arguments)
    return {"content": [{"type": "text", "text": result}]}


async def handle_ssh_execute_command(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle ssh_execute_command tool.

    With background=true the command runs as a background job and the call
    returns a job_id immediately — poll get_background_job for the result.
    Use for long-running commands that would exceed the MCP client timeout.
    """
    arguments = dict(arguments)
    if arguments.pop("background", False):
        # Background exists to outlive timeouts: raise the SSH-side timeout to 1h
        # instead of the 20s sync default. Internal only — Phase 26-02 guard says
        # timeout must not appear in the tool schema.
        # ponytail: 1h ceiling; make it configurable if a job ever legitimately runs longer.
        arguments.setdefault("timeout", 3600)
        # start_job_with_id, not start_job: ssh_execute_command needs its own
        # job_id to stream partial output back while the command is still running.
        job_id = background_jobs.start_job_with_id(
            description=f"ssh {arguments.get('hostname', '?')}: {arguments.get('command', '')[:80]}",
            make_coro=lambda jid: ssh_execute_command(job_id=jid, **arguments),
        )
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "status": "success",
                            "job_id": job_id,
                            "note": "Command running in background. Poll get_background_job with this job_id for status and output.",
                        },
                        indent=2,
                    ),
                }
            ]
        }
    result = await ssh_execute_command(**arguments)
    return {"content": [{"type": "text", "text": result}]}


async def handle_get_background_job(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle get_background_job tool. Without job_id, lists all jobs."""
    job_id = arguments.get("job_id")
    tail_lines = arguments.get("tail_lines", 50)
    if not job_id:
        payload: dict[str, Any] = {"status": "success", "jobs": background_jobs.list_jobs()}
    else:
        job = background_jobs.get_job(job_id, tail_lines=tail_lines)
        if job is None:
            payload = {"status": "error", "error": f"Unknown job_id: {job_id}"}
        else:
            payload = {"status": "success", "job": job}
    return {"content": [{"type": "text", "text": json.dumps(payload, indent=2)}]}


async def handle_cancel_background_job(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle cancel_background_job tool."""
    job_id = arguments["job_id"]
    if background_jobs.cancel_job(job_id):
        payload: dict[str, Any] = {"status": "success", "job_id": job_id, "note": "Cancellation requested."}
    else:
        job = background_jobs.get_job(job_id)
        reason = f"Job already {job['status']}" if job else f"Unknown job_id: {job_id}"
        payload = {"status": "error", "error": reason}
    return {"content": [{"type": "text", "text": json.dumps(payload, indent=2)}]}


async def handle_start_interactive_shell(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle start_interactive_shell tool."""
    validate_hostname(arguments["hostname"])
    if "port" in arguments:
        validate_port(arguments.get("port", 22))

    # SHELL-04: Guard against stdio mode — interactive shell requires HTTP server mode
    if os.getenv("MCP_HTTP_ENABLED", "false").lower() != "true":
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "status": "error",
                            "error": (
                                "start_interactive_shell only works in HTTP server mode. "
                                "Restart the server with: uvx homelab-mcp --http --port 8080\n"
                                "Then open the returned shell URL in your browser."
                            ),
                            "error_type": "stdio_mode_unsupported",
                        },
                        indent=2,
                    ),
                }
            ]
        }

    # Get initial command if provided
    initial_command = arguments.get("initial_command")

    # Create shell session
    session_id, session = await session_manager.create_session(
        hostname=arguments["hostname"],
        username=arguments.get("username"),
        password=arguments.get("password"),
        port=arguments.get("port", 22),
        initial_command=initial_command,
    )

    # Get the MCP HTTP server host/port from environment or defaults
    mcp_host = os.getenv("MCP_HTTP_HOST", "localhost")
    mcp_port = os.getenv("MCP_HTTP_PORT", "8080")

    # Build the shell URL
    shell_url = f"http://{mcp_host}:{mcp_port}/shell/{session_id}"

    message = f"Interactive shell started. Open this URL in your browser:\n{shell_url}\n\nSession will expire after 30 minutes of inactivity."
    if initial_command:
        message += f"\n\nInitial command executed:\n{initial_command}"

    result = {
        "status": "success",
        "session_id": session_id,
        "shell_url": shell_url,
        "hostname": session.hostname,
        "username": session.username,
        "message": message,
    }
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
