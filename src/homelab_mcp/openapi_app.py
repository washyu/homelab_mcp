"""FastAPI OpenAPI REST wrapper for MCP tool handlers.

Exposes each MCP tool as a REST endpoint under /api/tools/{tool_name},
plus a /api/tools listing and /health endpoint. Auto-generates OpenAPI
spec and Swagger UI from existing tool schemas.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import traceback
from typing import TYPE_CHECKING, Any

import jsonschema
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

if TYPE_CHECKING:
    from .auth import APIKeyAuth

from .tool_handlers import TOOL_HANDLERS
from .tool_schemas import get_all_tool_schemas

logger = logging.getLogger(__name__)

# Tools that work without any external infrastructure
# Everything NOT in this set requires SSH targets, Proxmox, or other infrastructure
STANDALONE_TOOLS: set[str] = {
    # Service template browsing (reads local YAML files)
    "list_available_services",
    "get_service_info",
    # Network sitemap queries (reads local database, may be empty)
    "get_network_sitemap",
    "analyze_network_topology",
    "suggest_deployments",
    # Credential listing (reads local keyring, may be empty)
    "list_registered_servers",
    # Proxmox script search (queries GitHub API, no Proxmox needed)
    "search_proxmox_scripts",
    "get_proxmox_script_info",
}

# What each tool category needs to function
INFRA_REQUIREMENTS: dict[str, str] = {
    "SSH": "an SSH target host. Register credentials first: POST /api/tools/register_server",
    "Network Discovery": "an SSH target host for discovery. Register credentials first: POST /api/tools/register_server",
    "VM & Containers": "a Docker or LXD host. Register credentials first: POST /api/tools/register_server",
    "Services": "a target host for service deployment. Register credentials first: POST /api/tools/register_server",
    "Credentials": "valid credential parameters (hostname, username, password)",
    "Infrastructure": "configured infrastructure targets. Register credentials first: POST /api/tools/register_server",
    "Proxmox": "a Proxmox VE host. Set PROXMOX_HOST and credentials via environment or POST /api/tools/register_server",
    "Drift Detection": "a Proxmox VE host with stored baselines. Set PROXMOX_HOST and credentials first",
}

# External reachability requirements: tool -> how to locate the target and what port to probe.
# Tools listed here get a TCP preflight before the handler runs. Unreachable targets
# short-circuit with HTTP 424 Failed Dependency.
#
# source="body": pull host from the request body field named by `field`.
# source="env":  pull host from the environment variable named by `field`.
_SSH_TOOLS_WITH_HOSTNAME = (
    "ssh_discover",
    "verify_mcp_admin",
    "ssh_execute_command",
    "start_interactive_shell",
    "update_mcp_admin_groups",
    "discover_and_map",
    "check_service_requirements",
    "install_service",
    "get_service_status",
    "plan_terraform_service",
    "destroy_terraform_service",
    "destroy_terraform_service_preview",
    "refresh_terraform_service",
    "check_ansible_service",
    "run_ansible_playbook",
    "register_server",
)
_PROXMOX_TOOLS_WITH_HOST = (
    "list_proxmox_resources",
    "get_proxmox_node_status",
    "get_proxmox_vm_status",
    "manage_proxmox_vm",
    "create_proxmox_vm",
    "clone_proxmox_vm",
    "delete_proxmox_vm",
    "delete_proxmox_vm_preview",
    "create_proxmox_lxc",
)

EXTERNAL_REQUIREMENTS: dict[str, dict[str, Any]] = {
    **{t: {"source": "body", "field": "hostname", "port": 22, "proto": "SSH"} for t in _SSH_TOOLS_WITH_HOSTNAME},
    **{t: {"source": "body", "field": "host", "port": 8006, "proto": "Proxmox API"} for t in _PROXMOX_TOOLS_WITH_HOST},
}


async def _check_reachable(host: str, port: int, timeout: float = 1.0) -> tuple[bool, str | None]:
    """TCP connect probe. Returns (reachable, error_reason)."""
    try:
        fut = asyncio.open_connection(host, port)
        reader, writer = await asyncio.wait_for(fut, timeout=timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception as close_err:  # noqa: BLE001 - close errors are not reachability failures
            logger.debug("wait_closed after reachability probe failed for %s:%s: %s", host, port, close_err)
        return True, None
    except TimeoutError:
        return False, f"TCP connect to {host}:{port} timed out after {timeout}s"
    except OSError as e:
        return False, f"TCP connect to {host}:{port} failed: {e}"


def _resolve_external_host(tool_name: str, body: dict[str, Any]) -> tuple[str, int, str] | None:
    """Resolve the external target for *tool_name* from request body or env.

    Returns (host, port, proto) if the tool has a configured requirement AND a
    host can be located. Returns None if no preflight applies (tool not in the
    table, or no host available — e.g. caller omitted the field so validation
    will catch it downstream).
    """
    req = EXTERNAL_REQUIREMENTS.get(tool_name)
    if not req:
        return None
    if req["source"] == "body":
        host = body.get(req["field"])
    else:
        host = os.getenv(req["field"])
    if not host or not isinstance(host, str):
        return None
    return host, int(req["port"]), str(req["proto"])


# Categories for organizing tools in the OpenAPI docs
TOOL_CATEGORIES: dict[str, list[str]] = {
    "SSH": [
        "ssh_discover",
        "verify_mcp_admin",
        "ssh_execute_command",
        "start_interactive_shell",
        "update_mcp_admin_groups",
    ],
    "Network Discovery": [
        "discover_and_map",
        "bulk_discover_and_map",
        "get_network_sitemap",
        "analyze_network_topology",
        "suggest_deployments",
        "get_device_changes",
    ],
    "VM & Containers": [
        "deploy_vm",
        "control_vm",
        "get_vm_status",
        "list_vms",
        "get_vm_logs",
        "remove_vm",
        "remove_vm_preview",
    ],
    "Services": [
        "list_available_services",
        "get_service_info",
        "check_service_requirements",
        "install_service",
        "get_service_status",
        "plan_terraform_service",
        "destroy_terraform_service",
        "destroy_terraform_service_preview",
        "refresh_terraform_service",
        "check_ansible_service",
        "run_ansible_playbook",
    ],
    "Credentials": [
        "register_server",
        "list_registered_servers",
    ],
    "Infrastructure": [
        "deploy_infrastructure",
        "update_device_config",
        "decommission_device",
        "decommission_device_preview",
        "scale_services",
        "validate_infrastructure_changes",
        "create_infrastructure_backup",
        "rollback_infrastructure_changes",
        "rollback_infrastructure_changes_preview",
    ],
    "Proxmox": [
        "search_proxmox_scripts",
        "get_proxmox_script_info",
        "list_proxmox_resources",
        "get_proxmox_node_status",
        "get_proxmox_vm_status",
        "manage_proxmox_vm",
        "create_proxmox_lxc",
        "create_proxmox_vm",
        "clone_proxmox_vm",
        "delete_proxmox_vm",
        "delete_proxmox_vm_preview",
    ],
    "Drift Detection": [
        "scan_infrastructure_drift",
    ],
}

# Reverse lookup: tool_name -> category
_TOOL_TO_CATEGORY: dict[str, str] = {}
for _cat, _tools in TOOL_CATEGORIES.items():
    for _tool in _tools:
        _TOOL_TO_CATEGORY[_tool] = _cat


def _get_tag(tool_name: str) -> str:
    """Get the OpenAPI tag for a tool."""
    return _TOOL_TO_CATEGORY.get(tool_name, "Other")


def _extract_text_content(result: dict[str, Any]) -> Any:
    """Extract the useful content from an MCP tool result.

    MCP handlers return {"content": [{"type": "text", "text": "..."}]}.
    This extracts the text and attempts to parse it as JSON for cleaner
    REST responses.
    """
    content = result.get("content", [])
    if not content:
        return result

    if len(content) == 1 and content[0].get("type") == "text":
        text = content[0]["text"]
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return text

    # Multiple content items — return as-is
    return content


_start_time = time.time()
_request_count = 0
_error_count = 0


def create_openapi_app(
    api_key: str | None = None,
    auth_enabled: bool = True,
) -> FastAPI | APIKeyAuth:
    """Create the FastAPI app with auto-generated routes for all MCP tools."""
    import contextlib
    from collections.abc import AsyncIterator

    from . import server as server_module
    from .config import get_config
    from .resource_manager import ResourceManager

    schemas = get_all_tool_schemas()

    @contextlib.asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        """Initialize the module-level ResourceManager so handlers that call
        ``server.get_resource_manager()`` work in OpenAPI mode.

        The MCP stdio/HTTP transports get this for free via the SDK lifespan;
        the OpenAPI transport calls handlers directly, so we replicate the
        setup here.
        """
        resource_manager = ResourceManager(get_config())
        await resource_manager.initialize()
        server_module._resource_manager = resource_manager
        logger.info("OpenAPI lifespan started — ResourceManager ready")
        try:
            yield
        finally:
            logger.info("Shutting down ResourceManager (OpenAPI lifespan)")
            server_module._resource_manager = None
            await resource_manager.shutdown()

    app = FastAPI(
        title="Homelab MCP Server - REST API",
        description=(
            "REST API wrapper for the Homelab MCP Server. "
            "Exposes all 56 MCP tools as standard REST endpoints with "
            "OpenAPI documentation. Each tool accepts a JSON body matching "
            "its input schema and returns the tool's result."
        ),
        version="1.3.2",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(StarletteHTTPException)  # type: ignore[misc,unused-ignore]
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "status": "error",
                "error": exc.detail or "Not Found",
            },
        )

    @app.exception_handler(RequestValidationError)  # type: ignore[misc,unused-ignore]
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "status": "error",
                "error": "Validation error",
                "details": exc.errors(),
            },
        )

    @app.get("/health", tags=["System"])  # type: ignore[misc,unused-ignore]
    async def health_check() -> dict[str, Any]:
        """Health check endpoint."""
        return {
            "status": "success",
            "result": {
                "server_status": "healthy",
                "uptime_seconds": round(time.time() - _start_time, 2),
                "total_requests": _request_count,
                "total_errors": _error_count,
                "error_rate": round(_error_count / max(_request_count, 1), 4),
                "transport": "openapi",
            },
        }

    @app.get("/api/tools", tags=["System"])  # type: ignore[misc,unused-ignore]
    async def list_tools() -> dict[str, Any]:
        """List all available tools with their schemas."""
        tools = []
        for name, schema in schemas.items():
            category = _get_tag(name)
            tools.append(
                {
                    "name": name,
                    "description": schema.get("description", ""),
                    "category": category,
                    "requires_infrastructure": name not in STANDALONE_TOOLS,
                    "input_schema": schema.get("inputSchema", {}),
                }
            )
        return {"tools": tools, "count": len(tools)}

    # Register a POST route for each tool
    for tool_name, handler in TOOL_HANDLERS.items():
        schema = schemas.get(tool_name, {})
        tool_description = schema.get("description", f"Execute the {tool_name} tool")
        input_schema = schema.get("inputSchema", {})
        tag = _get_tag(tool_name)
        required_fields = input_schema.get("required", [])

        # Build a summary of required params for the endpoint description
        param_summary = ""
        if required_fields:
            param_summary = f"\n\nRequired fields: `{'`, `'.join(required_fields)}`"

        ext_summary = ""
        ext_req = EXTERNAL_REQUIREMENTS.get(tool_name)
        if ext_req:
            loc = (
                f"`{ext_req['field']}` in request body"
                if ext_req["source"] == "body"
                else f"`{ext_req['field']}` environment variable"
            )
            ext_summary = (
                f"\n\n**External dependency:** connects to {ext_req['proto']} on "
                f"port {ext_req['port']} at the host given by {loc}. "
                f"A TCP reachability probe runs before the handler; unreachable "
                f"targets return **424 Failed Dependency** without executing the tool."
            )

        _register_tool_route(
            app,
            tool_name,
            handler,
            tool_description + param_summary + ext_summary,
            tag,
            input_schema,
        )

    if not auth_enabled:
        logger.warning("Authentication disabled — OpenAPI endpoints are unauthenticated")
        return app

    resolved_key = api_key or os.getenv("MCP_API_KEY")
    if resolved_key:
        from .auth import APIKeyAuth

        return APIKeyAuth(
            app,
            api_key=resolved_key,
            enabled=True,
            exclude_paths=["/health", "/docs", "/redoc", "/openapi.json"],
        )

    logger.warning("MCP_API_KEY not set — OpenAPI endpoints are unauthenticated")
    return app


def _classify_error(tool_name: str, error_msg: str) -> tuple[int, str]:
    """Classify an error and return the appropriate HTTP status code and status string.

    Returns 412 Precondition Failed for infrastructure-related errors (missing
    SSH targets, Proxmox hosts, credentials) with actionable remediation hints.
    Returns 500 for unexpected internal errors.
    """
    error_lower = error_msg.lower()

    # Infrastructure precondition patterns
    infra_patterns = [
        "no credentials found",
        "host unreachable",
        "connection refused",
        "connection timed out",
        "connection timeout",
        "ssh connection timeout",
        "authentication failed",
        "auth failed",
        "ssh_connect",
        "no proxmox",
        "proxmox_host",
        "could not resolve hostname",
        "network is unreachable",
        "no route to host",
        "credentials add",
        "retry_exhausted",
        "timed out",
        "timeout",
        "errno 111",
        "errno 113",
        "errno 110",
        "device not found",
        "device_id",
        "no device",
        "no infrastructure",
        "infrastructure not configured",
        "not registered",
        "unknown device",
        "not found in sitemap",
        "not found in db",
        "no baseline",
        "baseline available",
        "baseline not found",
        "no proxmox_host",
    ]

    # Non-standalone tools with infrastructure errors get 412
    if tool_name not in STANDALONE_TOOLS and any(p in error_lower for p in infra_patterns):
        return 412, "precondition_failed"

    # Non-standalone tools with empty errors are likely infra failures too
    if tool_name not in STANDALONE_TOOLS and not error_msg.strip():
        return 412, "precondition_failed"

    return 500, "error"


def _build_example(schema: dict[str, Any]) -> dict[str, Any]:
    """Build an example request body from a JSON schema for Swagger 'Try it out'."""
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    example: dict[str, Any] = {}
    type_defaults: dict[str, Any] = {
        "string": "",
        "integer": 0,
        "number": 0,
        "boolean": False,
        "array": [],
        "object": {},
    }
    for name, prop in props.items():
        if "default" in prop:
            example[name] = prop["default"]
        elif "enum" in prop:
            example[name] = prop["enum"][0]
        elif name in required:
            example[name] = type_defaults.get(prop.get("type", "string"), "")
        # Skip optional fields with no default — keep the example concise
    return example


def _format_validation_error(err: jsonschema.ValidationError) -> dict[str, Any]:
    """Render a jsonschema ValidationError into a stable, FastAPI-style detail entry."""
    loc = ["body", *list(err.absolute_path)]
    return {
        "loc": loc,
        "msg": err.message,
        "type": err.validator or "validation_error",
    }


def _get_remediation_hint(tool_name: str) -> str:
    """Get actionable remediation hint for a tool's infrastructure requirement."""
    category = _get_tag(tool_name)
    return INFRA_REQUIREMENTS.get(category, "external infrastructure")


def _register_tool_route(
    app: FastAPI,
    tool_name: str,
    handler: Any,
    description: str,
    tag: str,
    input_schema: dict[str, Any],
) -> None:
    """Register a POST /api/tools/{tool_name} route."""

    # Pre-build a jsonschema validator once at registration so each request
    # only pays for validation, not schema compilation.
    validator: jsonschema.protocols.Validator | None = None
    if input_schema and input_schema.get("properties"):
        try:
            cls = jsonschema.validators.validator_for(input_schema)
            cls.check_schema(input_schema)
            validator = cls(input_schema)
        except jsonschema.SchemaError as e:
            logger.warning(f"Tool {tool_name} has invalid input schema, skipping validation: {e}")

    @app.post(  # type: ignore[misc,unused-ignore]
        f"/api/tools/{tool_name}",
        tags=[tag],
        summary=tool_name,
        description=description,
        name=tool_name,
        openapi_extra={
            "requestBody": {
                "required": bool(input_schema.get("required")),
                "content": {
                    "application/json": {
                        "schema": input_schema,
                        "example": _build_example(input_schema),
                    }
                },
            }
        }
        if input_schema.get("properties")
        else None,
    )
    async def tool_endpoint(
        request: Request,
    ) -> JSONResponse:
        # `handler` and `tool_name` are captured from the enclosing
        # _register_tool_route scope — keeping them out of the signature
        # prevents FastAPI from exposing them as query parameters in Swagger.
        global _request_count, _error_count
        _request_count += 1

        # Parse request body — allow empty body for tools with no required params
        try:
            body = await request.json()
        except Exception:
            body = {}

        # Schema validation: enforce required fields and types at the framework
        # boundary so downstream handlers don't crash on missing keys.
        # `validator` is captured from the enclosing _register_tool_route scope
        # — keeping it out of the signature avoids FastAPI treating it as a
        # request parameter.
        if validator is not None:
            errors = sorted(validator.iter_errors(body), key=lambda e: list(e.absolute_path))
            if errors:
                _error_count += 1
                first = errors[0]
                first_path = ".".join(["body", *(str(p) for p in first.absolute_path)])
                return JSONResponse(
                    status_code=422,
                    content={
                        "status": "error",
                        "tool": tool_name,
                        "error": f"Validation error at {first_path}: {first.message}",
                        "details": [_format_validation_error(e) for e in errors],
                    },
                )

        # External dependency preflight: TCP-probe the target host before
        # invoking the handler. Fails fast with 424 when the target is down.
        target = _resolve_external_host(tool_name, body)
        if target is not None:
            host, port, proto = target
            reachable, reason = await _check_reachable(host, port)
            if not reachable:
                _error_count += 1
                return JSONResponse(
                    status_code=424,
                    content={
                        "status": "failed_dependency",
                        "tool": tool_name,
                        "error": reason or f"{host}:{port} unreachable",
                        "host": host,
                        "port": port,
                        "protocol": proto,
                        "requires": _get_remediation_hint(tool_name),
                    },
                )

        try:
            result = await handler(body)
            content = _extract_text_content(result)
            # Detect error results from handlers that don't raise exceptions.
            # Some handlers (e.g. vm_operations) emit `{status: error, message: ...}`
            # instead of `{status: error, error: ...}`, so we check both keys.
            if isinstance(content, dict) and content.get("status") == "error":
                _error_count += 1
                error_msg = content.get("error") or content.get("message") or "Tool execution failed"
                status_code, response_status = _classify_error(
                    tool_name,
                    error_msg,
                )
                resp: dict[str, Any] = {"status": response_status, "tool": tool_name, "error": error_msg}
                if status_code == 412:
                    resp["requires"] = _get_remediation_hint(tool_name)
                return JSONResponse(status_code=status_code, content=resp)
            return JSONResponse(
                status_code=200,
                content={"status": "success", "tool": tool_name, "result": content},
            )
        except ValueError as e:
            _error_count += 1
            return JSONResponse(
                status_code=400,
                content={"status": "error", "tool": tool_name, "error": str(e)},
            )
        except KeyError as e:
            # Handler accessed a required field that wasn't in the body. Treat
            # as a validation error rather than a 500 internal failure.
            _error_count += 1
            missing = str(e).strip("'\"")
            return JSONResponse(
                status_code=422,
                content={
                    "status": "error",
                    "tool": tool_name,
                    "error": "Validation error",
                    "details": [
                        {
                            "loc": ["body", missing],
                            "msg": f"Required field '{missing}' is missing",
                            "type": "missing",
                        }
                    ],
                },
            )
        except Exception as e:
            _error_count += 1
            error_msg = str(e)
            status_code, response_status = _classify_error(
                tool_name,
                error_msg,
            )
            logger.error(f"Tool {tool_name} failed: {e}\n{traceback.format_exc()}")
            resp = {"status": response_status, "tool": tool_name, "error": error_msg}
            if status_code == 412:
                resp["requires"] = _get_remediation_hint(tool_name)
            return JSONResponse(status_code=status_code, content=resp)
