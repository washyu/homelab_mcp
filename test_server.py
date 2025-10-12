#!/usr/bin/env python3
"""Minimal MCP server for testing Claude Desktop connectivity."""

import asyncio
import json


async def main():
    """Simple MCP server that only responds to tools/list."""

    while True:
        try:
            line = input()
            if not line:
                continue

            request = json.loads(line)

            if request.get("method") == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": {
                        "tools": [
                            {
                                "name": "test_tool",
                                "description": "A simple test tool",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {},
                                    "required": [],
                                },
                            }
                        ]
                    },
                }
            elif request.get("method") == "tools/call":
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": "Test response from minimal MCP server",
                            }
                        ]
                    },
                }
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "error": {"code": -32601, "message": "Method not found"},
                }

            print(json.dumps(response), flush=True)

        except EOFError:
            break
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": request.get("id", None) if "request" in locals() else None,
                "error": {"code": -32603, "message": f"Internal error: {str(e)}"},
            }
            print(json.dumps(error_response), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
