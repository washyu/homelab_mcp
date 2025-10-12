#!/usr/bin/env python3
"""
MCP (Model Context Protocol) server for homelab system management.
"""

import asyncio
import json
import logging
import sys
from typing import Any

from .error_handling import health_checker
from .ssh_tools import ensure_mcp_ssh_key
from .tools import execute_tool, get_available_tools

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HomelabMCPServer:
    """MCP Server for homelab system discovery and monitoring."""

    def __init__(self) -> None:
        self.tools = get_available_tools()
        self.ssh_key_initialized = False

    async def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Handle incoming MCP requests with timeout protection."""
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")

        # Record request for health monitoring
        health_checker.record_request()

        try:
            if method == "initialize":
                # Initialize SSH key on first request with timeout
                if not self.ssh_key_initialized:
                    try:
                        await asyncio.wait_for(ensure_mcp_ssh_key(), timeout=10.0)
                        self.ssh_key_initialized = True
                    except TimeoutError:
                        logger.error("SSH key initialization timed out")
                        health_checker.record_error("timeout")
                        return self._error_response(
                            request_id, "SSH key initialization timed out"
                        )

                return self._success_response(
                    request_id,
                    {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "homelab-mcp", "version": "0.1.0"},
                    },
                )

            elif method == "tools/list":
                # Add the name field to each tool
                tools_list = []
                for name, tool_def in self.tools.items():
                    tool_with_name = tool_def.copy()
                    tool_with_name["name"] = name
                    tools_list.append(tool_with_name)
                return self._success_response(request_id, {"tools": tools_list})

            elif method == "tools/call":
                tool_name = params.get("name")
                tool_args = params.get("arguments", {})

                if tool_name not in self.tools:
                    health_checker.record_error("invalid_tool")
                    return self._error_response(
                        request_id, f"Unknown tool: {tool_name}"
                    )

                # Execute tool with timeout protection
                try:
                    result = await asyncio.wait_for(
                        execute_tool(tool_name, tool_args),
                        timeout=60.0,  # 60 second timeout for tool execution
                    )
                    return self._success_response(request_id, result)
                except TimeoutError:
                    logger.error(f"Tool '{tool_name}' execution timed out")
                    health_checker.record_error("timeout")
                    return self._error_response(
                        request_id,
                        f"Tool '{tool_name}' timed out after 60 seconds. The operation may still be running in the background.",
                    )

            elif method == "health/status":
                # Health check endpoint
                health_status = health_checker.get_health_status()
                return self._success_response(request_id, health_status)

            else:
                health_checker.record_error("unknown_method")
                return self._error_response(request_id, f"Unknown method: {method}")

        except Exception as e:
            logger.error(f"Unexpected error handling request: {str(e)}", exc_info=True)
            health_checker.record_error("unexpected")
            return self._error_response(request_id, f"Server error: {str(e)}")

    def _success_response(self, request_id: Any, result: Any) -> dict[str, Any]:
        """Create a successful JSON-RPC response."""
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def _error_response(
        self, request_id: Any, message: str, code: int = -32603
    ) -> dict[str, Any]:
        """Create an error JSON-RPC response."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }

    async def run_stdio(self) -> None:
        """Run the MCP server using stdio with robust error handling."""
        logger.info("Starting MCP server with enhanced error handling")

        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

        consecutive_errors = 0
        max_consecutive_errors = 10

        while True:
            try:
                # Read line from stdin with timeout to prevent hanging
                try:
                    line_bytes = await asyncio.wait_for(
                        reader.readline(), timeout=300.0
                    )  # 5 minute timeout
                    if not line_bytes:
                        logger.info("EOF received, shutting down server")
                        break
                except TimeoutError:
                    logger.warning(
                        "No input received for 5 minutes, server still running"
                    )
                    continue

                line = line_bytes.decode("utf-8").strip()
                if not line:
                    continue

                # Parse JSON-RPC request
                try:
                    request = json.loads(line)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {str(e)}")
                    error_response = self._error_response(
                        None, f"Invalid JSON: {str(e)}", -32700
                    )
                    print(json.dumps(error_response))
                    sys.stdout.flush()
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(
                            f"Too many consecutive errors ({consecutive_errors}), shutting down"
                        )
                        break
                    continue

                # Reset error counter on successful JSON parse
                consecutive_errors = 0

                # Check if this is a notification (no id field)
                if "id" not in request:
                    # Notifications don't get responses, just process them
                    method = request.get("method")
                    if method == "notifications/initialized":
                        logger.info("Client initialized notification received")
                    # Don't send any response for notifications
                    continue

                # Handle request with timeout protection
                try:
                    response = await asyncio.wait_for(
                        self.handle_request(request),
                        timeout=120.0,  # 2 minute timeout for complete request handling
                    )
                except TimeoutError:
                    logger.error("Request handling timed out after 2 minutes")
                    error_response = self._error_response(
                        request.get("id"),
                        "Request processing timed out after 2 minutes",
                        -32603,
                    )
                    response = error_response

                # Send response to stdout
                try:
                    print(json.dumps(response))
                    sys.stdout.flush()
                except Exception as e:
                    logger.error(f"Failed to send response: {str(e)}")

            except KeyboardInterrupt:
                logger.info("Received interrupt signal, shutting down gracefully")
                break
            except Exception as e:
                logger.error(
                    f"Unexpected error in server loop: {str(e)}", exc_info=True
                )
                consecutive_errors += 1

                # Try to send error response if we can identify the request
                try:
                    error_response = self._error_response(
                        None, f"Server error: {str(e)}", -32603
                    )
                    print(json.dumps(error_response))
                    sys.stdout.flush()
                except Exception:
                    logger.error("Failed to send error response")

                # If too many consecutive errors, shut down to prevent infinite loop
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(
                        f"Too many consecutive errors ({consecutive_errors}), shutting down"
                    )
                    break

                # Brief pause before continuing to avoid rapid error loops
                await asyncio.sleep(0.1)

        logger.info("MCP server shutdown complete")


async def main() -> None:
    """Main entry point."""
    server = HomelabMCPServer()
    await server.run_stdio()


if __name__ == "__main__":
    asyncio.run(main())
