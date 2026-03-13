"""Homelab MCP Server - A Model Context Protocol server for homelab management."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__: str = version("homelab-mcp")
except PackageNotFoundError:
    __version__ = "unknown"
