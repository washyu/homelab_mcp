"""
Enhanced error handling utilities for the MCP server.
Provides timeout protection, retry logic, and graceful failure handling.
"""

import asyncio
import functools
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, TypeVar

from .log_filter import sanitize_error

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class MCPTimeout(Exception):
    """Custom timeout exception for MCP operations."""

    pass


class MCPConnectionError(Exception):
    """Custom connection error for MCP operations."""

    pass


def timeout_wrapper(timeout_seconds: float = 30.0, default_response: dict[str, Any] | None = None) -> Callable[[F], F]:
    """
    Decorator to wrap async functions with timeout protection.

    Args:
        timeout_seconds: Maximum time to wait before timing out
        default_response: Default response to return on timeout
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                # Apply timeout to the function execution
                # Check if arguments dict contains a timeout override (for tool calls)
                effective_timeout = timeout_seconds
                for arg in args:
                    if isinstance(arg, dict) and "timeout" in arg:
                        effective_timeout = max(float(arg["timeout"]) + 5.0, timeout_seconds)
                        break
                result = await asyncio.wait_for(func(*args, **kwargs), timeout=effective_timeout)
                return result
            except TimeoutError:
                error_msg = f"Operation '{func.__name__}' timed out after {timeout_seconds} seconds"
                logger.error(error_msg)

                if default_response:
                    return default_response

                # Return structured error response
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {
                                    "status": "error",
                                    "error": error_msg,
                                    "error_type": "timeout",
                                    "timestamp": datetime.now(UTC).isoformat(),
                                },
                                indent=2,
                            ),
                        }
                    ]
                }
            except Exception as e:
                error_msg = f"Unexpected error in '{func.__name__}': {sanitize_error(e)}"
                logger.error(error_msg, exc_info=True)

                return {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {
                                    "status": "error",
                                    "error": error_msg,
                                    "error_type": "unexpected",
                                    "timestamp": datetime.now(UTC).isoformat(),
                                },
                                indent=2,
                            ),
                        }
                    ]
                }

        return wrapper  # type: ignore[return-value]

    return decorator


def retry_on_failure(
    max_retries: int = 3, delay_seconds: float = 1.0, backoff_multiplier: float = 2.0
) -> Callable[[F], F]:
    """
    Decorator to retry failed operations with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        delay_seconds: Initial delay between retries
        backoff_multiplier: Multiplier for delay on each retry
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            delay = delay_seconds

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except (ConnectionError, MCPConnectionError, OSError) as e:
                    # Let timeout errors bubble up to SSH wrapper for proper handling
                    if isinstance(e, asyncio.TimeoutError | TimeoutError):
                        raise e
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries + 1} failed for '{func.__name__}': {sanitize_error(e)}. Retrying in {delay}s..."
                        )
                        await asyncio.sleep(delay)
                        delay *= backoff_multiplier
                    else:
                        logger.error(f"All {max_retries + 1} attempts failed for '{func.__name__}'")
                        break
                except Exception as e:
                    # Check if this is an SSH-specific error that should bubble up
                    if hasattr(e, "__module__") and "asyncssh" in str(e.__module__):
                        # Let SSH wrapper handle SSH-specific errors
                        raise e
                    # Don't retry on other non-connection errors
                    logger.error(f"Non-retryable error in '{func.__name__}': {sanitize_error(e)}")
                    last_exception = e  # type: ignore[assignment]
                    break

            # If we get here, all retries failed
            last_err_msg = sanitize_error(last_exception) if last_exception else "unknown error"
            error_msg = f"Operation '{func.__name__}' failed after {max_retries + 1} attempts: {last_err_msg}"
            error_response = json.dumps(
                {
                    "status": "error",
                    "error": error_msg,
                    "error_type": "retry_exhausted",
                    "attempts": max_retries + 1,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                indent=2,
            )
            return error_response

        return wrapper  # type: ignore[return-value]

    return decorator


async def safe_json_response(data: Any, fallback_message: str = "Operation completed") -> dict[str, Any]:
    """
    Safely create a JSON response, handling cases where data might be malformed.

    Args:
        data: Data to include in response (string or dict)
        fallback_message: Message to use if data is invalid

    Returns:
        Properly formatted MCP response
    """
    try:
        if isinstance(data, str):
            # Try to parse as JSON first
            try:
                parsed_data = json.loads(data)
                response_text = json.dumps(parsed_data, indent=2)
            except json.JSONDecodeError:
                # If not valid JSON, wrap as plain text
                response_text = json.dumps(
                    {
                        "status": "success",
                        "message": data,
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                    indent=2,
                )
        elif isinstance(data, dict):
            response_text = json.dumps(data, indent=2)
        else:
            # Handle any other data type by converting to string
            response_text = json.dumps(
                {
                    "status": "success",
                    "message": str(data),
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                indent=2,
            )

        return {"content": [{"type": "text", "text": response_text}]}

    except Exception as e:
        logger.error(f"Failed to create JSON response: {sanitize_error(e)}")
        fallback_response = json.dumps(
            {
                "status": "error",
                "error": f"Response formatting failed: {sanitize_error(e)}",
                "fallback_message": fallback_message,
                "timestamp": datetime.now(UTC).isoformat(),
            },
            indent=2,
        )

        return {"content": [{"type": "text", "text": fallback_response}]}


def ssh_connection_wrapper(timeout_seconds: float = 15.0) -> Callable[[F], F]:
    """
    Specialized wrapper for SSH operations with connection-specific error handling.

    Args:
        timeout_seconds: Timeout for SSH operations
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> str:
            # Allow callers to override the decorator's default timeout
            effective_timeout = kwargs.pop("timeout", None) or timeout_seconds
            try:
                result = await asyncio.wait_for(func(*args, **kwargs), timeout=effective_timeout)
                # Return successful result as-is (should be JSON string)
                return str(result)
            except TimeoutError:
                hostname = kwargs.get("hostname", args[0] if args else "unknown")
                error_response = json.dumps(
                    {
                        "status": "error",
                        "connection_ip": hostname,
                        "error": f"SSH connection timeout after {effective_timeout} seconds",
                        "error_type": "ssh_timeout",
                        "suggestions": [
                            "Check if the target device is reachable",
                            "Verify SSH service is running on the target",
                            "Check network connectivity",
                            "Try increasing the timeout value",
                        ],
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                    indent=2,
                )
                return error_response
            except (ConnectionError, OSError) as e:
                hostname = kwargs.get("hostname", args[0] if args else "unknown")
                # Check if this is a timeout error
                if isinstance(e, asyncio.TimeoutError | TimeoutError):
                    error_response = json.dumps(
                        {
                            "status": "error",
                            "connection_ip": hostname,
                            "error": f"SSH connection timeout: {sanitize_error(e)}",
                            "error_type": "ssh_timeout",
                            "timestamp": datetime.now(UTC).isoformat(),
                        },
                        indent=2,
                    )
                else:
                    error_response = json.dumps(
                        {
                            "status": "error",
                            "connection_ip": hostname,
                            "error": f"SSH connection failed: {sanitize_error(e)}",
                            "error_type": "ssh_connection_error",
                            "timestamp": datetime.now(UTC).isoformat(),
                        },
                        indent=2,
                    )
                return error_response
            except Exception as e:
                hostname = kwargs.get("hostname", "unknown")

                # Check for authentication-specific errors
                if "PermissionDenied" in str(type(e)) or "Authentication failed" in str(e):
                    error_response = json.dumps(
                        {
                            "status": "error",
                            "connection_ip": hostname,
                            "error": f"SSH key authentication failed: {sanitize_error(e)}",
                            "error_type": "ssh_auth_error",
                            "timestamp": datetime.now(UTC).isoformat(),
                        },
                        indent=2,
                    )
                else:
                    error_response = json.dumps(
                        {
                            "status": "error",
                            "connection_ip": hostname,
                            "error": f"SSH operation failed: {sanitize_error(e)}",
                            "error_type": "ssh_general_error",
                            "timestamp": datetime.now(UTC).isoformat(),
                        },
                        indent=2,
                    )
                return error_response

        return wrapper  # type: ignore[return-value]

    return decorator


class HealthChecker:
    """Health checker for monitoring MCP server status."""

    def __init__(self) -> None:
        self.start_time = datetime.now(UTC)
        self.request_count = 0
        self.error_count = 0
        self.timeout_count = 0

    def record_request(self) -> None:
        """Record a new request."""
        self.request_count += 1

    def record_error(self, error_type: str = "general") -> None:
        """Record an error."""
        self.error_count += 1
        if error_type == "timeout":
            self.timeout_count += 1

    def get_health_status(self) -> dict[str, Any]:
        """Get current health status."""
        uptime = (datetime.now(UTC) - self.start_time).total_seconds()

        return {
            "status": "healthy"
            if (self.request_count == 0) or (self.error_count < self.request_count * 0.5)
            else "degraded",
            "uptime_seconds": uptime,
            "total_requests": self.request_count,
            "total_errors": self.error_count,
            "timeout_errors": self.timeout_count,
            "error_rate": self.error_count / max(self.request_count, 1),
            "start_time": self.start_time.isoformat(),
            "timestamp": datetime.now(UTC).isoformat(),
        }


# Global health checker instance
health_checker = HealthChecker()
