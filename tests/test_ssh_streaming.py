"""Tests for incremental SSH output streaming into background jobs.

These use a hand-built stand-in for asyncssh's process object rather than a real
connection. That covers the pumping logic but deliberately cannot verify that
the asyncssh API surface exists -- see
test_ast_regression.test_every_asyncssh_attribute_reference_exists for that half.
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from homelab_mcp import background_jobs
from homelab_mcp.ssh_tools import _stream_command, _sudo_command
from homelab_mcp.tool_handlers.ssh_handlers import handle_ssh_execute_command


class _FakeReader:
    """Stand-in for asyncssh SSHReader: read() yields a chunk, then "" at EOF."""

    def __init__(self, chunks: list[str] | None = None) -> None:
        self._chunks = list(chunks or [])

    async def read(self, _n: int) -> str:
        if not self._chunks:
            return ""
        return self._chunks.pop(0)


class _GatedReader(_FakeReader):
    """A reader that releases one chunk per gate trip, so a test can interleave."""

    def __init__(self, chunks: list[str]) -> None:
        super().__init__(chunks)
        self.gate = asyncio.Event()

    async def read(self, _n: int) -> str:
        await self.gate.wait()
        self.gate.clear()
        if not self._chunks:
            return ""
        return self._chunks.pop(0)


class _FakeWriter:
    def __init__(self) -> None:
        self.written: list[str] = []
        self.eof_sent = False

    def write(self, data: str) -> None:
        self.written.append(data)

    def write_eof(self) -> None:
        self.eof_sent = True


class _FakeProcess:
    def __init__(self, stdout: _FakeReader, stderr: _FakeReader, exit_status: int = 0) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.stdin = _FakeWriter()
        self.exit_status = exit_status
        self.waited = False
        self.closed = False

    async def wait(self) -> None:
        self.waited = True

    def close(self) -> None:
        self.closed = True


class _FakeConn:
    def __init__(self, process: _FakeProcess) -> None:
        self.process = process
        self.commands: list[str] = []

    async def create_process(self, command: str) -> _FakeProcess:
        self.commands.append(command)
        return self.process


async def _idle() -> str:
    await asyncio.sleep(5)
    return "never-reached"


def _running_job() -> str:
    """A job parked in the running state, so update_job_output is not a no-op."""
    return background_jobs.start_job("stream target", _idle())


@pytest.mark.asyncio
async def test_output_is_published_while_the_command_is_still_running():
    # The whole point of streaming: the tail must grow mid-command, not only at
    # the end. A buffered implementation passes every other test in this file.
    reader = _GatedReader(["first chunk\n", "second chunk\n"])
    conn = _FakeConn(_FakeProcess(reader, _FakeReader()))
    job_id = _running_job()

    task = asyncio.create_task(_stream_command(conn, "slow-build", job_id))

    reader.gate.set()
    await asyncio.sleep(0.01)
    mid = background_jobs.get_job(job_id)
    assert mid["status"] == "running"
    assert "first chunk" in mid["stdout_tail"]
    assert "second chunk" not in mid["stdout_tail"]
    assert mid["output_is_growing"] is True

    reader.gate.set()
    await asyncio.sleep(0.01)
    assert "second chunk" in background_jobs.get_job(job_id)["stdout_tail"]

    reader.gate.set()
    stdout, _stderr, exit_status = await task
    assert stdout == "first chunk\nsecond chunk\n"
    assert exit_status == 0
    background_jobs.cancel_job(job_id)


@pytest.mark.asyncio
async def test_stdout_and_stderr_are_captured_separately():
    conn = _FakeConn(_FakeProcess(_FakeReader(["out\n"]), _FakeReader(["err\n"]), exit_status=3))
    job_id = _running_job()

    stdout, stderr, exit_status = await _stream_command(conn, "noisy", job_id)

    assert (stdout, stderr, exit_status) == ("out\n", "err\n", 3)
    job = background_jobs.get_job(job_id)
    assert job["stdout_tail"] == "out"
    assert job["stderr_tail"] == "err"
    assert job["bytes_captured"] == len("out\nerr\n")
    background_jobs.cancel_job(job_id)


@pytest.mark.asyncio
async def test_stdin_is_closed_so_reader_commands_do_not_hang():
    # Without write_eof a command that reads stdin blocks forever against a pipe
    # nobody writes to, and the job never finishes.
    process = _FakeProcess(_FakeReader(["done\n"]), _FakeReader())
    conn = _FakeConn(process)
    job_id = _running_job()

    await _stream_command(conn, "cat", job_id)

    assert process.stdin.eof_sent is True
    assert process.stdin.written == []
    background_jobs.cancel_job(job_id)


@pytest.mark.asyncio
async def test_sudo_password_goes_to_stdin_never_the_command_line():
    process = _FakeProcess(_FakeReader(["ok\n"]), _FakeReader())
    conn = _FakeConn(process)
    job_id = _running_job()
    secret = "hunter2"

    await _stream_command(conn, _sudo_command("apt upgrade", secret), job_id, stdin_input=secret + "\n")

    assert process.stdin.written == [secret + "\n"]
    assert process.stdin.eof_sent is True
    # Embedding it would expose the plaintext in the remote host's ps output.
    assert secret not in conn.commands[0]
    background_jobs.cancel_job(job_id)


@pytest.mark.asyncio
async def test_process_is_closed_even_when_a_stream_fails():
    class _ExplodingReader(_FakeReader):
        async def read(self, _n: int) -> str:
            raise ConnectionResetError("link dropped mid-command")

    process = _FakeProcess(_ExplodingReader(), _FakeReader())
    conn = _FakeConn(process)
    job_id = _running_job()

    with pytest.raises(ConnectionResetError):
        await _stream_command(conn, "doomed", job_id)

    assert process.closed is True
    background_jobs.cancel_job(job_id)


@pytest.mark.asyncio
async def test_partial_output_survives_a_mid_command_failure():
    # Streaming's other payoff: output already published stays readable even
    # though the command never produced a result.
    class _FailAfterOneChunk(_FakeReader):
        def __init__(self) -> None:
            super().__init__(["progress so far\n"])

        async def read(self, _n: int) -> str:
            if self._chunks:
                return self._chunks.pop(0)
            raise ConnectionResetError("link dropped")

    conn = _FakeConn(_FakeProcess(_FailAfterOneChunk(), _FakeReader()))
    job_id = _running_job()

    with pytest.raises(ConnectionResetError):
        await _stream_command(conn, "doomed", job_id)

    assert "progress so far" in background_jobs.get_job(job_id)["stdout_tail"]
    background_jobs.cancel_job(job_id)


def test_sudo_command_never_embeds_the_password():
    assert _sudo_command("ls", None) == "sudo ls"
    built = _sudo_command("ls", "s3cret")
    assert built == "sudo -S -p '' ls"
    assert "s3cret" not in built


@pytest.mark.asyncio
async def test_handler_hands_the_job_its_own_id():
    # Regression: the id must reach ssh_execute_command, otherwise the streaming
    # branch is never taken and background jobs silently fall back to buffered.
    with patch(
        "homelab_mcp.tool_handlers.ssh_handlers.ssh_execute_command",
        new=AsyncMock(return_value="ssh-result"),
    ) as mock_exec:
        result = await handle_ssh_execute_command({"hostname": "h", "command": "apt upgrade -y", "background": True})
        job_id = json.loads(result["content"][0]["text"])["job_id"]
        await asyncio.sleep(0.05)

    assert mock_exec.call_args.kwargs["job_id"] == job_id


@pytest.mark.asyncio
async def test_synchronous_calls_do_not_get_a_job_id():
    with patch(
        "homelab_mcp.tool_handlers.ssh_handlers.ssh_execute_command",
        new=AsyncMock(return_value="sync-result"),
    ) as mock_exec:
        await handle_ssh_execute_command({"hostname": "h", "command": "uptime"})

    assert "job_id" not in mock_exec.call_args.kwargs
