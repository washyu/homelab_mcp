"""Tests for SSH tools."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import asyncssh
import pytest

from src.homelab_mcp.ssh_tools import (
    _sudo_run,
    ensure_mcp_ssh_key,
    ssh_discover_system,
)


@pytest.mark.asyncio
@patch("src.homelab_mcp.ssh_tools.ssh_connect", new_callable=AsyncMock)
async def test_ssh_discover_success(mock_connect):
    """Test successful SSH discovery."""
    # Mock command results - in the order they are executed by ssh_discover_system
    # Only the commands that will actually be executed when CPU model succeeds on first try
    hostname_result = MagicMock()
    hostname_result.exit_status = 0
    hostname_result.stdout = "raspberrypi"

    # nproc command for CPU cores
    nproc_result = MagicMock()
    nproc_result.exit_status = 0
    nproc_result.stdout = "4"

    # CPU model name command (succeeds, so fallback methods won't be called)
    cpu_model_result = MagicMock()
    cpu_model_result.exit_status = 0
    cpu_model_result.stdout = "model name\t: Intel Core i5"

    # Memory command - free -b returns bytes
    mem_result = MagicMock()
    mem_result.exit_status = 0
    mem_result.stdout = """              total        used        free      shared  buff/cache   available
Mem:     8266850304  2254479360  4182536704   128974848  1829834240  5677662208"""

    # Disk command — Phase 35 D-09a.3: `df -B1 -T /` (adds Type column)
    # Columns: filesystem, type, 1B-blocks(size), used, available, use%, mount
    disk_result = MagicMock()
    disk_result.exit_status = 0
    disk_result.stdout = """Filesystem     Type  1B-blocks        Used    Available Use% Mounted on
/dev/sda1      ext4  21474836480  5905580032  14970068992  30% /"""

    # Network command
    net_result = MagicMock()
    net_result.exit_status = 0
    net_result.stdout = json.dumps(
        [
            {
                "ifname": "eth0",
                "operstate": "UP",
                "addr_info": [{"family": "inet", "local": "192.168.1.100"}],
            }
        ]
    )

    # Uptime command
    uptime_result = MagicMock()
    uptime_result.exit_status = 0
    uptime_result.stdout = "up 2 days, 3 hours, 45 minutes"

    # OS command
    os_result = MagicMock()
    os_result.exit_status = 0
    os_result.stdout = 'PRETTY_NAME="Ubuntu 22.04.3 LTS"'

    # Create mock connection
    mock_conn = AsyncMock()
    call_count = 0

    async def mock_run(*args, **kwargs):
        nonlocal call_count
        # Commands in actual order: hostname, nproc, cpu model, free, df, ip, uptime, os-release
        results = [
            hostname_result,
            nproc_result,
            cpu_model_result,
            mem_result,
            disk_result,
            net_result,
            uptime_result,
            os_result,
        ]
        if call_count < len(results):
            result = results[call_count]
            call_count += 1
            return result
        else:
            # Return a default failure result for any extra calls
            default_result = MagicMock()
            default_result.exit_status = 1
            default_result.stdout = ""
            return default_result

    mock_conn.run = mock_run

    # ssh_connect is async, returns a connection usable as async context manager
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_conn
    mock_ctx.__aexit__.return_value = None
    mock_connect.return_value = mock_ctx

    # Execute discovery
    result = await ssh_discover_system(hostname="test-host", username="test-user", password="test-pass")

    # Parse result
    result_data = json.loads(result)

    # Verify structure
    assert result_data["status"] == "success"
    assert result_data["hostname"] == "raspberrypi"  # Actual hostname from remote system
    assert result_data["connection_ip"] == "test-host"  # IP used to connect
    assert "data" in result_data

    # Verify CPU info (Phase 35 D-09a: `cores` not `count`)
    assert "cpu" in result_data["data"]
    assert result_data["data"]["cpu"]["model"] == "Intel Core i5"
    assert result_data["data"]["cpu"]["cores"] == 4

    # Verify memory info — Phase 35 D-09a emits 4 Gi-suffixed string fields
    # (total, used, free, available) per the sitemap consumer contract.
    assert "memory" in result_data["data"]
    assert "total" in result_data["data"]["memory"]
    assert "used" in result_data["data"]["memory"]
    assert "free" in result_data["data"]["memory"]
    assert "available" in result_data["data"]["memory"]

    # Verify disk info — Phase 35 D-09a emits 6 fields matching sitemap.py:88-94
    # (filesystem, size, used, available, use_percent, mount).
    assert "disk" in result_data["data"]
    assert "filesystem" in result_data["data"]["disk"]
    assert "size" in result_data["data"]["disk"]
    assert "used" in result_data["data"]["disk"]
    assert "available" in result_data["data"]["disk"]
    assert "use_percent" in result_data["data"]["disk"]
    assert "mount" in result_data["data"]["disk"]

    # Verify network info
    assert "network" in result_data["data"]
    assert len(result_data["data"]["network"]) == 1
    assert result_data["data"]["network"][0]["name"] == "eth0"
    assert "192.168.1.100" in result_data["data"]["network"][0]["addresses"]

    # Verify uptime and OS
    assert result_data["data"]["uptime"] == "up 2 days, 3 hours, 45 minutes"
    assert result_data["data"]["os"] == "Ubuntu 22.04.3 LTS"


@pytest.mark.asyncio
@patch("src.homelab_mcp.ssh_tools.ssh_connect", new_callable=AsyncMock)
async def test_ssh_discover_auth_failure(mock_connect):
    """Test SSH discovery with authentication failure."""
    mock_connect.side_effect = asyncssh.misc.PermissionDenied("Authentication failed")

    result = await ssh_discover_system(hostname="test-host", username="test-user", password="wrong-pass")

    result_data = json.loads(result)
    assert result_data["status"] == "error"
    assert result_data["connection_ip"] == "test-host"
    assert "authentication failed" in result_data["error"].lower()


@pytest.mark.asyncio
@patch("src.homelab_mcp.ssh_tools.ssh_connect", new_callable=AsyncMock)
async def test_ssh_discover_connection_timeout(mock_connect):
    """Test SSH discovery with connection timeout."""

    mock_connect.side_effect = TimeoutError()

    result = await ssh_discover_system(hostname="unreachable-host", username="test-user", password="test-pass")

    result_data = json.loads(result)
    assert result_data["status"] == "error"
    assert result_data["connection_ip"] == "unreachable-host"
    assert "timeout" in result_data["error"].lower()


@pytest.mark.asyncio
@patch("src.homelab_mcp.ssh_tools.get_database_adapter")
async def test_ssh_discover_no_credentials(mock_get_db):
    """Test SSH discovery without password or key."""
    # Mock database to return no stored credentials
    mock_adapter = MagicMock()
    mock_adapter.get_credential_by_hostname.return_value = None
    mock_get_db.return_value = mock_adapter

    result = await ssh_discover_system(hostname="test-host", username="test-user")

    result_data = json.loads(result)
    assert result_data["status"] == "error"
    # Updated error message since we now use credential resolver
    assert "No credentials" in result_data["error"]


@pytest.mark.asyncio
@patch("src.homelab_mcp.ssh_tools.ssh_connect", new_callable=AsyncMock)
async def test_ssh_discover_with_key_path(mock_connect):
    """Test SSH discovery using key file."""
    # Mock SSH connection
    mock_conn = AsyncMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_conn
    mock_ctx.__aexit__.return_value = None
    mock_connect.return_value = mock_ctx

    # Mock minimal command results
    mock_result = MagicMock()
    mock_result.exit_status = 1  # Commands fail
    mock_result.stdout = None
    mock_conn.run.return_value = mock_result

    # Execute discovery with key
    await ssh_discover_system(hostname="test-host", username="test-user", key_path="/path/to/key")

    # Verify ssh_connect was called with key_path parameter
    mock_connect.assert_called_once()
    call_kwargs = mock_connect.call_args.kwargs
    assert call_kwargs["key_path"] == "/path/to/key"


@pytest.mark.asyncio
@patch("src.homelab_mcp.ssh_tools.SSH_KEY_DIR")
@patch("src.homelab_mcp.ssh_tools.get_mcp_ssh_key_path")
@patch("src.homelab_mcp.ssh_tools.asyncssh.generate_private_key")
async def test_ensure_mcp_ssh_key_creates_new(mock_generate, mock_get_path, mock_key_dir):
    """Test SSH key generation when keys don't exist."""
    # Setup mock paths
    mock_key_path = MagicMock()
    mock_key_path.exists.return_value = False
    mock_key_path.__str__.return_value = "/home/user/.ssh/mcp/mcp_admin_key"
    mock_get_path.return_value = mock_key_path

    mock_pub_key_path = MagicMock()
    mock_pub_key_path.exists.return_value = False

    # Mock Path() constructor to return our pub key path
    with patch("src.homelab_mcp.ssh_tools.Path") as mock_path_class:
        mock_path_class.return_value = mock_pub_key_path

        # Mock directory
        mock_key_dir.mkdir = MagicMock()

        # Mock key generation
        mock_private_key = MagicMock()
        mock_private_key.export_private_key.return_value = b"private_key_data"
        mock_private_key.export_public_key.return_value = b"public_key_data"
        mock_generate.return_value = mock_private_key

        # Execute
        result = await ensure_mcp_ssh_key()

        # Verify key generation with comment parameter
        mock_generate.assert_called_once_with("ssh-rsa", key_size=2048, comment="mcp_admin@homelab")

        # Verify directory creation
        mock_key_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True, mode=0o700)

        # Verify file writes
        mock_key_path.write_bytes.assert_called_once_with(b"private_key_data")
        mock_key_path.chmod.assert_called_once_with(0o600)
        mock_pub_key_path.write_text.assert_called_once_with("public_key_data")
        mock_pub_key_path.chmod.assert_called_once_with(0o644)

        # Verify result
        assert result == "/home/user/.ssh/mcp/mcp_admin_key"


@pytest.mark.asyncio
@patch("src.homelab_mcp.ssh_tools.get_mcp_ssh_key_path")
async def test_ensure_mcp_ssh_key_uses_existing(mock_get_path):
    """Test that existing SSH keys are reused."""
    # Setup mock paths
    mock_key_path = MagicMock()
    mock_key_path.exists.return_value = True
    mock_key_path.__str__.return_value = "/home/user/.ssh/mcp/mcp_admin_key"
    mock_get_path.return_value = mock_key_path

    with patch("src.homelab_mcp.ssh_tools.Path") as mock_path_class:
        mock_pub_key_path = MagicMock()
        mock_pub_key_path.exists.return_value = True
        mock_path_class.return_value = mock_pub_key_path

        # Execute
        result = await ensure_mcp_ssh_key()

        # Verify result points to existing key
        assert result == "/home/user/.ssh/mcp/mcp_admin_key"


# (Removed in Phase 33: setup_remote_mcp_admin deleted per D-11)

# test_verify_mcp_admin_access_* REMOVED in Phase 33.1 (D-05).
# verify_mcp_admin_access function deleted from ssh_tools.py — tests that
# invoke it must also be deleted, not skipped (Phase 33 precedent D-02).
# Replacement onboarding check: connect_to_device prompt Step 6 calls
# `ssh_execute_command(hostname=..., command="sudo -n true")` to verify sudo
# availability of the registered user.


# test_ssh_discover_with_mcp_admin_auto_key REMOVED in Phase 33 (D-08/D-17).
# This test exercised the Tier 4 "default mcp_admin key auto-fallback" path in
# resolve_ssh_credentials, which has been intentionally deleted. The replacement
# test is tests/test_ssh_credentials.py::TestResolveSSHCredentials::test_mcp_admin_no_fallback,
# which proves the fallback no longer fires.


# (Removed in Phase 33: setup_remote_mcp_admin deleted per D-11)

# (Removed in Phase 33: setup_remote_mcp_admin deleted per D-11)

# (Removed in Phase 33: setup_remote_mcp_admin deleted per D-11)

# (Removed in Phase 33: setup_remote_mcp_admin deleted per D-11)


@pytest.mark.asyncio
async def test_ssh01_sudo_run_check_raises_in_password_branch():
    """SSH-01 regression: _sudo_run(password=..., check=True) forwards check= to conn.run.

    Before commit 9f752c0 the password branch dropped `check=`, so a non-zero exit from
    `sudo -S <command>` was silently ignored. This test proves the propagation path.

    Revert-proof: reverting commit 9f752c0 (restoring the branch that calls
    `conn.run(full_command)` without `check=check` in the password branch) causes
    conn.run to return a result object rather than raise — the test's
    `pytest.raises(asyncssh.ProcessError)` assertion fails.
    """
    mock_conn = AsyncMock()

    # Raise ProcessError from conn.run (simulates check=True catching non-zero exit).
    # asyncssh.ProcessError kwargs vary by version; use the minimal positional/kwarg
    # combination that instantiates cleanly on the asyncssh pinned in pyproject.toml.
    try:
        err: Exception = asyncssh.ProcessError(
            env=None,
            command="sudo -S ls",
            subsystem=None,
            exit_status=1,
            exit_signal=None,
            returncode=1,
            stdout="",
            stderr="permission denied",
        )
    except TypeError:
        # Fallback: if newer asyncssh changed the constructor, use RuntimeError so
        # the propagation path is still exercised. The exact exception class is not
        # what REG-01 guards — the propagation is. The executor MUST prefer the
        # asyncssh.ProcessError form; this fallback is a version-compat safety net.
        err = RuntimeError("simulated non-zero exit from sudo")

    mock_conn.run.side_effect = err

    with pytest.raises(type(err)):
        await _sudo_run(mock_conn, "ls", password="pw", check=True)

    # Prove check=True was forwarded to conn.run — guards the exact defect
    # in commit 9f752c0's parent (the password branch that dropped check=).
    mock_conn.run.assert_called_once()
    assert mock_conn.run.call_args.kwargs.get("check") is True, (
        f"check=True must be forwarded to conn.run; got kwargs={mock_conn.run.call_args.kwargs!r}"
    )


def test_ssh02_no_disjunctive_always_true_assertions() -> None:
    """SSH-02 meta-guard: no `assert X or <structurally-always-true>` in this file.

    Before commit d25c915 the assertion at test_ssh_discover_no_credentials (currently
    line ~191) read:
        assert "No credentials" in err or "other" in err
    which is equivalent to `True or True` for any non-empty `err` — the test always
    passed and never exercised the "No credentials" precondition it claimed to guard.

    This AST meta-test parses tests/test_ssh_tools.py (itself) and fails if any
    `ast.Assert(test=ast.BoolOp(op=ast.Or(), values=[_, <always_true>]))` pattern
    is present. "Structurally always true" is defined conservatively:
      - ast.Constant with a truthy value
      - nested ast.BoolOp(op=ast.Or) with an always-true branch
      - ast.Compare over two ast.Constant operands

    Revert-proof (captured in this plan's commit message, per CONTEXT.md D-05):
    temporarily mutate line ~191 to `assert "No credentials" in err or "other" in err`
    (where `"other"` is a non-empty string Constant — structurally always true),
    re-run this test, observe FAILED with offender line ~191. Do NOT commit the
    mutation — the commit message captures the diagnostic output.
    """
    import ast
    from pathlib import Path

    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)

    def _is_structurally_always_true(node: ast.expr) -> bool:
        """Conservative truthy-constant detector.

        Flags ONLY shapes provably true at parse time. Dynamic expressions
        (Name, Call, Attribute, Compare over non-constants) are NOT flagged,
        with ONE broadened exception for the `in` operator:

        A `Compare` node is treated as structurally always-true when:
        - `node.left` is an `ast.Constant` AND all comparators are `ast.Constant`
          (plain parse-time tautology like `"a" == "a"`), OR
        - `node.left` is an `ast.Constant` AND `node.ops[0]` is `ast.In`
          (a constant literal is `in` SOMETHING — tautological in a disjunctive
          `or` assert where the other branch is the real check).

        The `Constant in X` case is the exact shape of the d25c915 pre-fix defect
        and is special-cased because the comparator may be any expression
        (Subscript, Attribute, Name, Call) and still yield a tautology in context.
        See .planning/phases/32-regression-tests/32-CONTEXT.md decision D-10.
        """
        if isinstance(node, ast.Constant):
            # Non-empty string, non-zero number, True
            return bool(node.value)
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
            return any(_is_structurally_always_true(v) for v in node.values)
        if isinstance(node, ast.Compare):
            # (a) Constant <op> Constant is evaluable at parse time (e.g., `"a" == "a"`).
            if isinstance(node.left, ast.Constant) and all(isinstance(c, ast.Constant) for c in node.comparators):
                return True
            # (b) `<Constant literal> in <anything>` — in the context of a disjunctive
            # `or` assert where the other branch is the real check, a constant string
            # literal being `in` some container is a tautology. This is the exact
            # shape of the d25c915 pre-fix defect:
            #     assert "No credentials" in err or "other" in err["error"]
            # where the RHS is Compare(left=Constant("other"), ops=[In()], comparators=[Subscript(...)])
            # and is always-true whenever `err["error"]` is a non-empty string.
            # See CONTEXT.md decision D-10 for the full rationale.
            if isinstance(node.left, ast.Constant) and node.ops and isinstance(node.ops[0], ast.In):
                return True
        return False

    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert) and isinstance(node.test, ast.BoolOp):
            if isinstance(node.test.op, ast.Or):
                # Flag if any operand beyond the first is structurally always true.
                for operand in node.test.values[1:]:
                    if _is_structurally_always_true(operand):
                        offenders.append(f"line {node.lineno}: {ast.unparse(node)}")
                        break

    assert not offenders, (
        "Found `assert X or <always-true>` anti-pattern(s) in test_ssh_tools.py.\n"
        "Replace with explicit single-check asserts (see SSH-02 fix in commit d25c915):\n" + "\n".join(offenders)
    )


def test_setup_remote_mcp_admin_absent() -> None:
    """D-11: setup_remote_mcp_admin function must be removed from ssh_tools."""
    from src.homelab_mcp import ssh_tools

    assert not hasattr(ssh_tools, "setup_remote_mcp_admin"), (
        "setup_remote_mcp_admin must be deleted from ssh_tools.py (D-11)"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Phase 35 functional tests (D-17c + D-06 back-compat + W4 B1 dedent guard)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ssh_discover_system_partial_mode_on_probe_timeout_phase35(monkeypatch):
    """Phase 35 D-17c: when a per-subprocess timeout fires, the response
    must gain ``partial: true`` and ``timed_out_commands: [<cmd_name>]``;
    ``status`` stays ``"success"``; other probed fields continue to populate.
    """
    import json as _json
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from src.homelab_mcp import ssh_tools

    fake_conn = MagicMock()

    async def _fake_ssh_connect(**kwargs):
        class _Ctx:
            async def __aenter__(self_inner):
                return fake_conn

            async def __aexit__(self_inner, exc_type, exc, tb):
                return None

        return _Ctx()

    monkeypatch.setattr(
        ssh_tools,
        "resolve_ssh_credentials",
        lambda hostname, username, password, key_path, port: SimpleNamespace(
            hostname=hostname,
            username="testuser",
            port=port,
            password="x",
            key_path=None,
        ),
    )
    monkeypatch.setattr(ssh_tools, "ssh_connect", _fake_ssh_connect)

    def _fake_cp(stdout: str, exit_status: int = 0):
        return SimpleNamespace(stdout=stdout, stderr="", exit_status=exit_status)

    STDOUT_BY_CMD = {
        "hostname": "pve1\n",
        "nproc": "4\n",
        "cpuinfo": "model name : CPU Model Z9\n",
        "free": "              total        used        free      shared  buff/cache   available\nMem:    8589934592  2147483648  4294967296           0  2147483648  5368709120\n",
        "df": "Filesystem     Type  1B-blocks       Used   Available Use% Mounted on\n/dev/sda1      ext4  100000000000  40000000000  60000000000  40% /\n",
        "ip": '[{"ifname":"eth0","operstate":"UP","addr_info":[{"family":"inet","local":"10.0.0.5"}]}]\n',
        "uptime": "up 2 days, 3 hours\n",
        "os-release": 'PRETTY_NAME="Debian 12"\n',
        "lsusb": "Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub\n",
        "lspci": "00:00.0 Host bridge: Intel Corporation Device 4660 (rev 02)\n",
        "lsblk": "",
    }

    async def _mock_run_with_timeout(conn, command, *, cmd_name, timed_out, timeout=10.0):
        if cmd_name == "lsblk":
            timed_out.append("lsblk")
            return None
        return _fake_cp(STDOUT_BY_CMD.get(cmd_name, ""))

    monkeypatch.setattr(ssh_tools, "_run_with_timeout", _mock_run_with_timeout)

    result_str = await ssh_tools.ssh_discover_system(
        hostname="10.0.0.5",
        username="testuser",
        password="x",
    )
    result = _json.loads(result_str)
    assert result["status"] == "success", result
    assert result.get("partial") is True, "Phase 35 D-17c: expected `partial: true` when a probe times out"
    assert result.get("timed_out_commands") == ["lsblk"], result.get("timed_out_commands")
    assert result["data"].get("cpu", {}).get("cores") == 4
    assert "block_devices" not in result["data"]


@pytest.mark.asyncio
async def test_ssh_discover_system_omits_partial_keys_on_clean_run_phase35(monkeypatch):
    """Phase 35 D-06 back-compat: when NO per-cmd timeouts fire, the
    response JSON MUST NOT contain ``partial`` or ``timed_out_commands``
    keys — byte-for-byte equivalent to pre-Phase-35 shape.
    """
    import json as _json
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from src.homelab_mcp import ssh_tools

    fake_conn = MagicMock()

    async def _fake_ssh_connect(**kwargs):
        class _Ctx:
            async def __aenter__(self_inner):
                return fake_conn

            async def __aexit__(self_inner, exc_type, exc, tb):
                return None

        return _Ctx()

    monkeypatch.setattr(
        ssh_tools,
        "resolve_ssh_credentials",
        lambda hostname, username, password, key_path, port: SimpleNamespace(
            hostname=hostname,
            username="testuser",
            port=port,
            password="x",
            key_path=None,
        ),
    )
    monkeypatch.setattr(ssh_tools, "ssh_connect", _fake_ssh_connect)

    def _fake_cp(stdout: str, exit_status: int = 0):
        return SimpleNamespace(stdout=stdout, stderr="", exit_status=exit_status)

    async def _mock_run_with_timeout(conn, command, *, cmd_name, timed_out, timeout=10.0):
        return _fake_cp("pve1\n" if cmd_name == "hostname" else "")

    monkeypatch.setattr(ssh_tools, "_run_with_timeout", _mock_run_with_timeout)

    result_str = await ssh_tools.ssh_discover_system(hostname="10.0.0.5", username="u", password="p")
    result = _json.loads(result_str)
    assert result["status"] == "success"
    assert "partial" not in result, "Phase 35 D-06 back-compat regression: `partial` key present on clean run"
    assert "timed_out_commands" not in result, (
        "Phase 35 D-06 back-compat regression: `timed_out_commands` present on clean run"
    )


@pytest.mark.asyncio
async def test_ssh_discover_system_hostname_timeout_does_not_suppress_probes_phase35(monkeypatch):
    """Phase 35 D-17c (W4) — B1 dedent functional guard.

    Prior pre-Phase-35 defect: every probe block was nested inside the
    ``if hostname_result.exit_status == 0 and hostname_result.stdout:``
    branch. Once Phase 35 wrapped the hostname probe with
    ``_run_with_timeout``, a hostname probe timeout would produce
    ``hostname_result = None`` → the `if` guard falsey → EVERY subsequent
    probe skipped → ``system_info == {}``. Plan 01 Task 1 dedents all
    probe blocks so the hostname-success ``if`` gates ONLY the
    ``actual_hostname = ...`` overwrite. This test proves the fix.
    """
    import json as _json
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from src.homelab_mcp import ssh_tools

    fake_conn = MagicMock()

    async def _fake_ssh_connect(**kwargs):
        class _Ctx:
            async def __aenter__(self_inner):
                return fake_conn

            async def __aexit__(self_inner, exc_type, exc, tb):
                return None

        return _Ctx()

    monkeypatch.setattr(
        ssh_tools,
        "resolve_ssh_credentials",
        lambda hostname, username, password, key_path, port: SimpleNamespace(
            hostname=hostname,
            username="testuser",
            port=port,
            password="x",
            key_path=None,
        ),
    )
    monkeypatch.setattr(ssh_tools, "ssh_connect", _fake_ssh_connect)

    def _fake_cp(stdout: str, exit_status: int = 0):
        return SimpleNamespace(stdout=stdout, stderr="", exit_status=exit_status)

    STDOUT_BY_CMD = {
        "nproc": "8\n",
        "cpuinfo": "model name : Intel Xeon E5\n",
        "free": "              total        used        free      shared  buff/cache   available\nMem:    16777216000  4194304000  8388608000           0  4194304000  10485760000\n",
        "df": "Filesystem     Type  1B-blocks       Used   Available Use% Mounted on\n/dev/sda1      ext4  200000000000  80000000000  120000000000  40% /\n",
        "ip": '[{"ifname":"eth0","operstate":"UP","addr_info":[{"family":"inet","local":"10.0.0.5"}]}]\n',
        "uptime": "up 5 days\n",
        "os-release": 'PRETTY_NAME="Debian 12"\n',
        "lsusb": "Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub\n",
        "lspci": "00:00.0 Host bridge: Intel Corporation Device 4660 (rev 02)\n",
        "lsblk": "",
    }

    async def _mock_run_with_timeout(conn, command, *, cmd_name, timed_out, timeout=10.0):
        if cmd_name == "hostname":
            timed_out.append("hostname")
            return None
        return _fake_cp(STDOUT_BY_CMD.get(cmd_name, ""))

    monkeypatch.setattr(ssh_tools, "_run_with_timeout", _mock_run_with_timeout)

    result_str = await ssh_tools.ssh_discover_system(
        hostname="10.0.0.5",
        username="testuser",
        password="x",
    )
    result = _json.loads(result_str)

    assert result["status"] == "success", result
    assert result.get("partial") is True, "Phase 35 D-17c (W4): expected `partial: true` when hostname probe times out"
    assert "hostname" in result.get("timed_out_commands", []), (
        f"Phase 35 D-17c (W4): expected 'hostname' in timed_out_commands, got {result.get('timed_out_commands')!r}"
    )

    # B1 dedent proof: subsequent probes populated data despite hostname timeout.
    assert "cpu" in result["data"], (
        "Phase 35 B1 regression (W4): hostname probe timeout suppressed "
        "every subsequent probe — probe blocks are still nested inside the "
        "hostname-success `if` branch. Plan 01 Task 1 dedent not applied."
    )
    assert result["data"]["cpu"].get("cores") == 8, result["data"]
    # hostname field falls back to the connection-IP argument since the hostname
    # probe produced no stdout to overwrite actual_hostname.
    assert result["hostname"] == "10.0.0.5", result["hostname"]
