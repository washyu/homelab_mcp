"""Tests for the error handling module."""

import asyncio
import json

import pytest

from src.homelab_mcp.error_handling import (
    HealthChecker,
    MCPConnectionError,
    MCPTimeout,
    health_checker,
    retry_on_failure,
    safe_json_response,
    ssh_connection_wrapper,
    timeout_wrapper,
)


class TestTimeoutWrapper:
    """Test timeout wrapper decorator."""

    @pytest.mark.asyncio
    async def test_timeout_wrapper_success(self):
        """Test timeout wrapper with successful operation."""

        @timeout_wrapper(timeout_seconds=1.0)
        async def quick_operation():
            return {"status": "success", "data": "test"}

        result = await quick_operation()
        assert result == {"status": "success", "data": "test"}

    @pytest.mark.asyncio
    async def test_timeout_wrapper_timeout(self):
        """Test timeout wrapper with timeout."""

        @timeout_wrapper(timeout_seconds=0.1)
        async def slow_operation():
            await asyncio.sleep(1.0)  # Will timeout
            return {"status": "success"}

        result = await slow_operation()

        # Should return structured error response
        assert "content" in result
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"

        error_data = json.loads(result["content"][0]["text"])
        assert error_data["status"] == "error"
        assert error_data["error_type"] == "timeout"
        assert "timed out after 0.1 seconds" in error_data["error"]

    @pytest.mark.asyncio
    async def test_timeout_wrapper_with_default_response(self):
        """Test timeout wrapper with custom default response."""
        default_response = {"custom": "default"}

        @timeout_wrapper(timeout_seconds=0.1, default_response=default_response)
        async def slow_operation():
            await asyncio.sleep(1.0)
            return {"status": "success"}

        result = await slow_operation()
        assert result == default_response

    @pytest.mark.asyncio
    async def test_timeout_wrapper_exception(self):
        """Test timeout wrapper with unexpected exception."""

        @timeout_wrapper(timeout_seconds=1.0)
        async def failing_operation():
            raise ValueError("Test error")

        result = await failing_operation()

        assert "content" in result
        error_data = json.loads(result["content"][0]["text"])
        assert error_data["status"] == "error"
        assert error_data["error_type"] == "unexpected"
        assert "Test error" in error_data["error"]


class TestRetryOnFailure:
    """Test retry on failure decorator."""

    @pytest.mark.asyncio
    async def test_retry_success_first_attempt(self):
        """Test retry decorator with success on first attempt."""

        @retry_on_failure(max_retries=3, delay_seconds=0.01)
        async def successful_operation():
            return {"status": "success"}

        result = await successful_operation()
        assert result == {"status": "success"}

    @pytest.mark.asyncio
    async def test_retry_success_after_failures(self):
        """Test retry decorator with success after failures."""
        attempt_count = 0

        @retry_on_failure(max_retries=3, delay_seconds=0.01)
        async def flaky_operation():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ConnectionError("Connection failed")
            return {"status": "success", "attempts": attempt_count}

        result = await flaky_operation()
        assert result == {"status": "success", "attempts": 3}
        assert attempt_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted(self):
        """Test retry decorator when all retries are exhausted."""

        @retry_on_failure(max_retries=2, delay_seconds=0.01)
        async def always_failing():
            raise ConnectionError("Always fails")

        result = await always_failing()

        # Should return JSON string directly, not wrapped format
        error_data = json.loads(result)
        assert error_data["status"] == "error"
        assert error_data["error_type"] == "retry_exhausted"
        assert error_data["attempts"] == 3  # max_retries + 1
        assert "Always fails" in error_data["error"]

    @pytest.mark.asyncio
    async def test_retry_non_retryable_error(self):
        """Test retry decorator with non-retryable error."""

        @retry_on_failure(max_retries=3, delay_seconds=0.01)
        async def operation_with_logic_error():
            raise ValueError("Logic error - should not retry")

        result = await operation_with_logic_error()

        # Should return JSON string directly, not wrapped format
        error_data = json.loads(result)
        assert error_data["status"] == "error"
        assert error_data["error_type"] == "retry_exhausted"
        assert "Logic error" in error_data["error"]


class TestSSHConnectionWrapper:
    """Test SSH connection wrapper decorator."""

    @pytest.mark.asyncio
    async def test_ssh_wrapper_success(self):
        """Test SSH wrapper with successful operation."""

        @ssh_connection_wrapper(timeout_seconds=1.0)
        async def ssh_operation(hostname="test-host"):
            return json.dumps({"status": "success", "hostname": hostname})

        result = await ssh_operation(hostname="example.com")
        data = json.loads(result)
        assert data["status"] == "success"
        assert data["hostname"] == "example.com"

    @pytest.mark.asyncio
    async def test_ssh_wrapper_timeout(self):
        """Test SSH wrapper with timeout."""

        @ssh_connection_wrapper(timeout_seconds=0.1)
        async def slow_ssh_operation(hostname="test-host"):
            await asyncio.sleep(1.0)
            return json.dumps({"status": "success"})

        result = await slow_ssh_operation(hostname="slow-host")
        data = json.loads(result)
        assert data["status"] == "error"
        assert data["error_type"] == "ssh_timeout"
        assert data["connection_ip"] == "slow-host"
        assert "suggestions" in data
        assert len(data["suggestions"]) > 0

    @pytest.mark.asyncio
    async def test_ssh_wrapper_connection_error(self):
        """Test SSH wrapper with connection error."""

        @ssh_connection_wrapper(timeout_seconds=1.0)
        async def failing_ssh_operation(hostname="test-host"):
            raise ConnectionError("SSH connection refused")

        result = await failing_ssh_operation(hostname="unreachable-host")
        data = json.loads(result)
        assert data["status"] == "error"
        assert data["error_type"] == "ssh_connection_error"
        assert data["connection_ip"] == "unreachable-host"
        assert "SSH connection refused" in data["error"]

    @pytest.mark.asyncio
    async def test_ssh_wrapper_general_error(self):
        """Test SSH wrapper with general error."""

        @ssh_connection_wrapper(timeout_seconds=1.0)
        async def ssh_operation_with_error(hostname="test-host"):
            raise ValueError("Invalid parameters")

        result = await ssh_operation_with_error(hostname="test-host")
        data = json.loads(result)
        assert data["status"] == "error"
        assert data["error_type"] == "ssh_general_error"
        assert data["connection_ip"] == "test-host"
        assert "Invalid parameters" in data["error"]


class TestSafeJsonResponse:
    """Test safe JSON response utility."""

    @pytest.mark.asyncio
    async def test_safe_json_response_with_dict(self):
        """Test safe JSON response with dictionary."""
        data = {"status": "success", "data": "test"}
        result = await safe_json_response(data)

        assert "content" in result
        assert result["content"][0]["type"] == "text"

        parsed = json.loads(result["content"][0]["text"])
        assert parsed == data

    @pytest.mark.asyncio
    async def test_safe_json_response_with_valid_json_string(self):
        """Test safe JSON response with valid JSON string."""
        data = '{"status": "success", "message": "test"}'
        result = await safe_json_response(data)

        assert "content" in result
        parsed = json.loads(result["content"][0]["text"])
        assert parsed["status"] == "success"
        assert parsed["message"] == "test"

    @pytest.mark.asyncio
    async def test_safe_json_response_with_invalid_json_string(self):
        """Test safe JSON response with invalid JSON string."""
        data = "This is not JSON"
        result = await safe_json_response(data)

        assert "content" in result
        parsed = json.loads(result["content"][0]["text"])
        assert parsed["status"] == "success"
        assert parsed["message"] == "This is not JSON"

    @pytest.mark.asyncio
    async def test_safe_json_response_with_other_type(self):
        """Test safe JSON response with other data types."""
        data = 12345
        result = await safe_json_response(data)

        assert "content" in result
        parsed = json.loads(result["content"][0]["text"])
        assert parsed["status"] == "success"
        assert parsed["message"] == "12345"

    @pytest.mark.asyncio
    async def test_safe_json_response_fallback(self):
        """Test safe JSON response with fallback message."""

        # Create an object that will cause JSON serialization to fail
        class UnserializableObject:
            def __str__(self):
                raise Exception("Cannot stringify")

        data = UnserializableObject()
        fallback = "Operation completed"

        # Just test that the function handles unserializable objects gracefully
        # by converting them to string
        result = await safe_json_response(data, fallback)

        assert "content" in result
        parsed = json.loads(result["content"][0]["text"])
        assert parsed["status"] == "error"
        assert parsed["fallback_message"] == fallback
        assert "Response formatting failed" in parsed["error"]


class TestHealthChecker:
    """Test health checker functionality."""

    def setup_method(self):
        """Set up test method."""
        self.checker = HealthChecker()

    def test_health_checker_initial_state(self):
        """Test health checker initial state."""
        status = self.checker.get_health_status()

        assert status["status"] == "healthy"
        assert status["total_requests"] == 0
        assert status["total_errors"] == 0
        assert status["timeout_errors"] == 0
        assert status["error_rate"] == 0.0
        assert "uptime_seconds" in status
        assert "start_time" in status
        assert "timestamp" in status

    def test_health_checker_record_requests(self):
        """Test recording requests."""
        self.checker.record_request()
        self.checker.record_request()

        status = self.checker.get_health_status()
        assert status["total_requests"] == 2

    def test_health_checker_record_errors(self):
        """Test recording errors."""
        self.checker.record_error("general")
        self.checker.record_error("timeout")

        status = self.checker.get_health_status()
        assert status["total_errors"] == 2
        assert status["timeout_errors"] == 1

    def test_health_checker_error_rate(self):
        """Test error rate calculation."""
        # Add some requests and errors
        self.checker.record_request()
        self.checker.record_request()
        self.checker.record_request()
        self.checker.record_request()

        self.checker.record_error()
        self.checker.record_error()

        status = self.checker.get_health_status()
        assert status["error_rate"] == 0.5  # 2 errors / 4 requests

    def test_health_checker_degraded_status(self):
        """Test degraded status when error rate is high."""
        # Add requests with high error rate
        self.checker.record_request()
        self.checker.record_request()

        self.checker.record_error()
        self.checker.record_error()  # 100% error rate

        status = self.checker.get_health_status()
        assert status["status"] == "degraded"

    def test_global_health_checker(self):
        """Test global health checker instance."""
        # Test that global health checker works
        health_checker.record_request()
        status = health_checker.get_health_status()

        assert "status" in status
        assert "total_requests" in status


class TestCustomExceptions:
    """Test custom exception classes."""

    def test_mcp_timeout_exception(self):
        """Test MCPTimeout exception."""
        with pytest.raises(MCPTimeout):
            raise MCPTimeout("Operation timed out")

    def test_mcp_connection_error_exception(self):
        """Test MCPConnectionError exception."""
        with pytest.raises(MCPConnectionError):
            raise MCPConnectionError("Connection failed")


class TestIntegration:
    """Test integration of error handling components."""

    @pytest.mark.asyncio
    async def test_combined_decorators(self):
        """Test combining multiple decorators."""

        @timeout_wrapper(timeout_seconds=1.0)
        @retry_on_failure(max_retries=1, delay_seconds=0.01)
        async def complex_operation(should_fail=True):
            if should_fail:
                raise ConnectionError("Simulated connection error")
            return {"status": "success"}

        # Should retry once then fail
        result = await complex_operation(should_fail=True)

        # The retry decorator returns JSON string directly
        error_data = json.loads(result)
        assert error_data["status"] == "error"
        assert error_data["error_type"] == "retry_exhausted"
        assert "connection error" in error_data["error"].lower()

    @pytest.mark.asyncio
    async def test_ssh_wrapper_with_retry(self):
        """Test SSH wrapper combined with retry."""
        attempt_count = 0

        @ssh_connection_wrapper(timeout_seconds=1.0)
        @retry_on_failure(max_retries=2, delay_seconds=0.01)
        async def flaky_ssh_operation(hostname="test"):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                raise ConnectionError("Network issue")
            return json.dumps({"status": "success", "hostname": hostname})

        result = await flaky_ssh_operation(hostname="retry-host")
        data = json.loads(result)

        assert data["status"] == "success"
        assert data["hostname"] == "retry-host"
        assert attempt_count == 2


# --- Regression guards (v1.5 / PR #39) ---


@pytest.mark.asyncio
async def test_err01_timeout_message_reports_effective_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """ERR-01 regression: timeout error f-string reports effective_timeout, not decorator default.

    Production computes effective_timeout = max(override + 5.0, timeout_seconds).
    Before commit bdb76bb the error f-string at error_handling.py:58 used `timeout_seconds`
    (the decorator default) — so a caller passing {"timeout": 30} with the default 2.0s
    decorator would see "timed out after 2.0 seconds" rather than the true 35.0s value.

    Revert-proof: reverting commit bdb76bb (restoring `{timeout_seconds}` in the f-string)
    causes this test to fail on the `"35.0 seconds" in error_data["error"]` assertion.

    Speed: we monkeypatch asyncio.wait_for to raise TimeoutError immediately — the test
    never sleeps for 35 real seconds.
    """

    @timeout_wrapper(timeout_seconds=2.0)
    async def op(kwargs: dict) -> dict:
        return {"ok": True}

    async def fake_wait_for(coro, timeout):
        # Close the coroutine to avoid "coroutine was never awaited" RuntimeWarning
        coro.close()
        raise TimeoutError()

    monkeypatch.setattr(
        "src.homelab_mcp.error_handling.asyncio.wait_for",
        fake_wait_for,
    )

    # {"timeout": 30} → effective_timeout = max(30 + 5.0, 2.0) = 35.0
    result = await op({"timeout": 30})

    assert "content" in result, f"expected MCP-wrapped response; got {result!r}"
    error_data = json.loads(result["content"][0]["text"])

    assert error_data["status"] == "error"
    assert error_data["error_type"] == "timeout"

    # The core assertion — this is what ERR-01 guards.
    assert "35.0 seconds" in error_data["error"], (
        f"Expected effective_timeout (35.0s) in error msg; got: {error_data['error']!r}"
    )
    assert "2.0 seconds" not in error_data["error"], (
        f"Error msg must NOT report decorator default (2.0s); got: {error_data['error']!r}"
    )
