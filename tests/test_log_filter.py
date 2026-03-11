"""Tests for credential redaction logging filter (SEC-04)."""

import logging

from homelab_mcp.log_filter import CredentialFilter, sanitize_error


class TestCredentialFilter:
    """Tests for CredentialFilter logging filter."""

    def setup_method(self) -> None:
        """Create a logger with CredentialFilter for each test."""
        self.filter = CredentialFilter()

    def _make_record(self, msg: str) -> logging.LogRecord:
        """Create a LogRecord with the given message."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg=msg,
            args=None,
            exc_info=None,
        )
        return record

    def test_redacts_password_equals(self) -> None:
        record = self._make_record("password=secret123")
        self.filter.filter(record)
        assert "secret123" not in record.msg
        assert "[REDACTED]" in record.msg

    def test_redacts_token_colon(self) -> None:
        record = self._make_record("token: abc123")
        self.filter.filter(record)
        assert "abc123" not in record.msg
        assert "[REDACTED]" in record.msg

    def test_redacts_pve_api_token(self) -> None:
        record = self._make_record("PVEAPIToken=user@pam!tok=uuid-value-here")
        self.filter.filter(record)
        assert "uuid-value-here" not in record.msg
        assert "[REDACTED]" in record.msg

    def test_redacts_authorization_bearer(self) -> None:
        record = self._make_record("Authorization: Bearer xyz-token-value")
        self.filter.filter(record)
        assert "xyz-token-value" not in record.msg
        assert "[REDACTED]" in record.msg

    def test_redacts_ssh_private_key(self) -> None:
        key_block = "-----BEGIN RSA PRIVATE KEY-----\nMIIBogIBAAJBALRiMLAHudd...\n-----END RSA PRIVATE KEY-----"
        record = self._make_record(f"Found key: {key_block}")
        self.filter.filter(record)
        assert "MIIBogIBAAJBALRiMLAHudd" not in record.msg
        assert "[REDACTED]" in record.msg

    def test_passes_through_normal_message(self) -> None:
        record = self._make_record("Connected to host 192.168.1.1 on port 22")
        self.filter.filter(record)
        assert record.msg == "Connected to host 192.168.1.1 on port 22"

    def test_always_returns_true(self) -> None:
        """Filter should allow all messages through (just redacted)."""
        record = self._make_record("password=secret")
        result = self.filter.filter(record)
        assert result is True

    def test_redacts_in_args_tuple(self) -> None:
        """Filter should also redact string args."""
        record = self._make_record("Connection failed: %s")
        record.args = ("password=secret123",)
        self.filter.filter(record)
        assert "secret123" not in str(record.args)

    def test_redacts_password_with_quotes(self) -> None:
        record = self._make_record('password"secret123"')
        self.filter.filter(record)
        assert "secret123" not in record.msg

    def test_redacts_token_equals(self) -> None:
        record = self._make_record("token=mytoken123")
        self.filter.filter(record)
        assert "mytoken123" not in record.msg
        assert "[REDACTED]" in record.msg

    def test_redacts_openssh_private_key(self) -> None:
        key_block = (
            "-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXktdjEAAAAAB...\n-----END OPENSSH PRIVATE KEY-----"
        )
        record = self._make_record(f"Key data: {key_block}")
        self.filter.filter(record)
        assert "b3BlbnNzaC1rZXktdjEAAAAAB" not in record.msg


class TestSanitizeError:
    """Tests for sanitize_error()."""

    def test_sanitizes_password_in_exception(self) -> None:
        err = Exception("password=secret")
        result = sanitize_error(err)
        assert "secret" not in result
        assert "[REDACTED]" in result

    def test_passes_through_normal_error(self) -> None:
        err = Exception("normal error")
        result = sanitize_error(err)
        assert result == "normal error"

    def test_sanitizes_token_in_exception(self) -> None:
        err = Exception("Failed with token: abc123xyz")
        result = sanitize_error(err)
        assert "abc123xyz" not in result

    def test_returns_string(self) -> None:
        err = Exception("test error")
        result = sanitize_error(err)
        assert isinstance(result, str)

    def test_sanitizes_authorization_header(self) -> None:
        err = Exception("Request failed: Authorization: Bearer my-secret-token")
        result = sanitize_error(err)
        assert "my-secret-token" not in result
