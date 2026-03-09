"""Tests for the HTTP transport module.

Tests cover both the new SDK-based http_app and the auth/config utilities.
"""

from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from src.homelab_mcp.auth import generate_api_key, validate_api_key_strength
from src.homelab_mcp.http_app import create_http_app


@pytest.fixture
def api_key():
    """Generate a test API key."""
    return generate_api_key()


@pytest.fixture
def app():
    """Create an HTTP app (no auth wrapper)."""
    return create_http_app()


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    def test_health_check_returns_ok(self, client):
        """Test that health endpoint returns 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "transport" in data
        assert data["transport"] == "http"


class TestRootEndpoint:
    """Tests for the root / endpoint."""

    def test_root_returns_server_info(self, client):
        """Test that root endpoint returns server information."""
        response = client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == "homelab-mcp"
        assert data["protocol"] == "MCP"
        assert data["transport"] == "streamable-http"
        assert "endpoints" in data


class TestAPIKeyAuth:
    """Tests for API key authentication."""

    def test_generate_api_key_length(self):
        """Test that generated API keys have sufficient length."""
        key = generate_api_key()
        assert len(key) >= 32

    def test_validate_api_key_strength_short(self):
        """Test validation rejects short keys."""
        is_valid, message = validate_api_key_strength("short")
        assert not is_valid
        assert "16 characters" in message

    def test_validate_api_key_strength_alpha_only(self):
        """Test validation rejects alpha-only keys."""
        is_valid, message = validate_api_key_strength("abcdefghijklmnopqrstuvwxyz")
        assert not is_valid
        assert "mix of characters" in message

    def test_validate_api_key_strength_valid(self):
        """Test validation accepts valid keys."""
        key = generate_api_key()
        is_valid, message = validate_api_key_strength(key)
        assert is_valid


class TestHTTPConfig:
    """Tests for HTTP configuration."""

    def test_http_config_defaults(self):
        """Test HTTP config default values."""
        from src.homelab_mcp.config import HTTPConfig

        config = HTTPConfig()
        assert config.enabled is False
        assert config.host == "0.0.0.0"
        assert config.port == 8080
        assert config.auth_enabled is True

    def test_http_config_validation_no_api_key(self):
        """Test HTTP config validation when auth enabled but no key."""
        from src.homelab_mcp.config import HTTPConfig

        with patch.dict("os.environ", {"MCP_HTTP_ENABLED": "true", "MCP_AUTH_ENABLED": "true"}):
            config = HTTPConfig()
            config.enabled = True
            config.auth_enabled = True
            config.api_key = None

            errors = config.validate()
            assert any("MCP_API_KEY" in error for error in errors)

    def test_http_config_validation_short_api_key(self):
        """Test HTTP config validation for short API key."""
        from src.homelab_mcp.config import HTTPConfig

        config = HTTPConfig()
        config.api_key = "short"

        errors = config.validate()
        assert any("16 characters" in error for error in errors)

    def test_http_config_validation_invalid_port(self):
        """Test HTTP config validation for invalid port."""
        from src.homelab_mcp.config import HTTPConfig

        config = HTTPConfig()
        config.port = 99999

        errors = config.validate()
        assert any("port" in error.lower() for error in errors)
