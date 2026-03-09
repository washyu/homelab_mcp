"""Tests for input validation module (SEC-03)."""

import pytest

from homelab_mcp.validation import validate_hostname, validate_ip_network, validate_port


class TestValidateHostname:
    """Tests for validate_hostname()."""

    def test_valid_ipv4(self) -> None:
        assert validate_hostname("192.168.1.1") == "192.168.1.1"

    def test_valid_ipv4_localhost(self) -> None:
        assert validate_hostname("127.0.0.1") == "127.0.0.1"

    def test_valid_ipv6_loopback(self) -> None:
        assert validate_hostname("::1") == "::1"

    def test_valid_ipv6_full(self) -> None:
        assert validate_hostname("fe80::1") == "fe80::1"

    def test_valid_hostname_with_local_tld(self) -> None:
        assert validate_hostname("pve.local") == "pve.local"

    def test_valid_hostname_with_hyphen(self) -> None:
        assert validate_hostname("node-1") == "node-1"

    def test_valid_hostname_internal(self) -> None:
        assert validate_hostname("my-host.internal") == "my-host.internal"

    def test_valid_hostname_simple(self) -> None:
        assert validate_hostname("myhost") == "myhost"

    def test_valid_hostname_numeric_label(self) -> None:
        assert validate_hostname("host1.lab2.local") == "host1.lab2.local"

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            validate_hostname("")

    def test_too_long_raises(self) -> None:
        with pytest.raises(ValueError, match="253"):
            validate_hostname("a" * 254)

    def test_shell_metacharacters_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_hostname("host; rm -rf /")

    def test_spaces_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_hostname("host name")

    def test_leading_hyphen_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_hostname("-invalid")

    def test_trailing_hyphen_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_hostname("invalid-")

    def test_label_too_long_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_hostname("a" * 64 + ".local")

    def test_backtick_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_hostname("`whoami`")

    def test_pipe_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_hostname("host|cat")

    def test_dollar_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_hostname("$HOME")


class TestValidatePort:
    """Tests for validate_port()."""

    def test_valid_ssh_port(self) -> None:
        assert validate_port(22) == 22

    def test_valid_proxmox_port(self) -> None:
        assert validate_port(8006) == 8006

    def test_valid_min_port(self) -> None:
        assert validate_port(1) == 1

    def test_valid_max_port(self) -> None:
        assert validate_port(65535) == 65535

    def test_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="1.*65535"):
            validate_port(0)

    def test_too_high_raises(self) -> None:
        with pytest.raises(ValueError, match="1.*65535"):
            validate_port(65536)

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="1.*65535"):
            validate_port(-1)


class TestValidateIpNetwork:
    """Tests for validate_ip_network()."""

    def test_valid_ipv4_network(self) -> None:
        assert validate_ip_network("192.168.1.0/24") == "192.168.1.0/24"

    def test_valid_ipv6_network(self) -> None:
        result = validate_ip_network("fe80::/10")
        assert result == "fe80::/10"

    def test_valid_single_host(self) -> None:
        assert validate_ip_network("10.0.0.1/32") == "10.0.0.1/32"

    def test_invalid_network_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_ip_network("not-a-network")

    def test_strict_mode_rejects_host_bits(self) -> None:
        with pytest.raises(ValueError):
            validate_ip_network("192.168.1.1/24", strict=True)

    def test_non_strict_accepts_host_bits(self) -> None:
        # Non-strict mode clears host bits
        result = validate_ip_network("192.168.1.1/24", strict=False)
        assert result == "192.168.1.0/24"
