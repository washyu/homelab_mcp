"""Credential redaction for logging and error responses (SEC-04).

Provides a logging filter that redacts sensitive data (passwords, tokens, API
keys, SSH private keys) from log output, and a utility to sanitize exception
messages before returning them to MCP clients.
"""

from __future__ import annotations

import logging
import re

# Compiled patterns for sensitive data. Each tuple is (regex, replacement).
# The regex captures a prefix group so the replacement preserves context
# while redacting the secret value.
_SENSITIVE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # PVEAPIToken must come before generic token pattern
    (re.compile(r"(PVEAPIToken=)\S+", re.IGNORECASE), r"\1[REDACTED]"),
    # Authorization header
    (re.compile(r"(Authorization:\s*)\S+.*", re.IGNORECASE), r"\1[REDACTED]"),
    # password=, password:, password" (various separators)
    (re.compile(r"(password[\"\s:=]+)\S+", re.IGNORECASE), r"\1[REDACTED]"),
    # token=, token:, token" (various separators)
    (re.compile(r"(token[\"\s:=]+)\S+", re.IGNORECASE), r"\1[REDACTED]"),
    # SSH private key blocks (any key type)
    (
        re.compile(
            r"-----BEGIN\s+\S*\s*PRIVATE KEY-----[\s\S]*?-----END\s+\S*\s*PRIVATE KEY-----",
            re.MULTILINE,
        ),
        "[REDACTED]",
    ),
]


def _redact(text: str) -> str:
    """Apply all sensitive patterns to redact credentials from text."""
    for pattern, replacement in _SENSITIVE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class CredentialFilter(logging.Filter):
    """Logging filter that redacts sensitive data from log records.

    Attach to a logger or handler to automatically scrub passwords,
    tokens, API keys, and SSH private keys from log output.

    Always allows messages through (returns True) -- it only modifies
    the message content, never suppresses it.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact sensitive data in the log record message and args."""
        if isinstance(record.msg, str):
            record.msg = _redact(record.msg)

        if isinstance(record.args, tuple):
            record.args = tuple(_redact(arg) if isinstance(arg, str) else arg for arg in record.args)

        return True


def sanitize_error(error: Exception) -> str:
    """Sanitize an exception message by redacting credentials.

    Use this instead of ``str(e)`` when including exception details in
    error responses returned to MCP clients or logged messages.

    Args:
        error: The exception to sanitize.

    Returns:
        The exception message with sensitive data redacted.
    """
    return _redact(str(error))
