"""Tests for background job registry and ssh_execute_command background mode."""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from homelab_mcp import background_jobs
from homelab_mcp.tool_handlers.ssh_handlers import (
    handle_cancel_background_job,
    handle_get_background_job,
    handle_ssh_execute_command,
)


def _text_payload(result: dict) -> dict:
    return json.loads(result["content"][0]["text"])


@pytest.mark.asyncio
async def test_job_completes_and_result_is_polled():
    async def work() -> str:
        return "done-output"

    job_id = background_jobs.start_job("test job", work())
    # Poll until finished
    first_poll = None
    for _ in range(50):
        job = background_jobs.get_job(job_id)
        assert job is not None
        # New fields
        assert "elapsed_seconds" in job
        assert "stdout_tail" in job
        assert "stderr_tail" in job
        assert "output_is_growing" in job
        if first_poll is None:
            first_poll = job
        if job["status"] != "running":
            break
        await asyncio.sleep(0.01)
    assert job["status"] == "completed"
    assert job["result"] == "done-output"
    assert job["finished_at"] is not None
    # elapsed_seconds should be non-negative
    assert first_poll["elapsed_seconds"] >= 0


@pytest.mark.asyncio
async def test_job_failure_is_captured_not_raised():
    async def boom() -> str:
        raise RuntimeError("kaboom")

    job_id = background_jobs.start_job("failing job", boom())
    await asyncio.sleep(0.05)
    job = background_jobs.get_job(job_id)
    assert job["status"] == "failed"
    assert "kaboom" in job["error"]


@pytest.mark.asyncio
async def test_cancel_running_job():
    async def forever() -> str:
        await asyncio.sleep(60)
        return "never"

    job_id = background_jobs.start_job("long job", forever())
    assert background_jobs.cancel_job(job_id) is True
    await asyncio.sleep(0.05)
    assert background_jobs.get_job(job_id)["status"] == "cancelled"
    # Cancelling a finished job is a no-op
    assert background_jobs.cancel_job(job_id) is False


@pytest.mark.asyncio
async def test_handler_background_true_returns_job_id_immediately():
    with patch(
        "homelab_mcp.tool_handlers.ssh_handlers.ssh_execute_command",
        new=AsyncMock(return_value="ssh-result"),
    ) as mock_exec:
        result = await handle_ssh_execute_command({"hostname": "h", "command": "apt upgrade -y", "background": True})
        payload = _text_payload(result)
        assert payload["status"] == "success"
        job_id = payload["job_id"]

        await asyncio.sleep(0.05)
        poll = _text_payload(await handle_get_background_job({"job_id": job_id}))
        assert poll["job"]["status"] == "completed"
        assert poll["job"]["result"] == "ssh-result"
        # Background jobs must not inherit the 20s sync SSH timeout
        assert mock_exec.call_args.kwargs["timeout"] == 3600
        # New fields present
        assert "elapsed_seconds" in poll["job"]
        assert "stdout_tail" in poll["job"]
        assert "stderr_tail" in poll["job"]
        assert "output_is_growing" in poll["job"]


@pytest.mark.asyncio
async def test_handler_background_false_is_synchronous():
    with patch(
        "homelab_mcp.tool_handlers.ssh_handlers.ssh_execute_command",
        new=AsyncMock(return_value="sync-result"),
    ) as mock_exec:
        result = await handle_ssh_execute_command({"hostname": "h", "command": "uptime"})
        assert result["content"][0]["text"] == "sync-result"
        # background key must not leak into ssh_execute_command kwargs
        assert "background" not in mock_exec.call_args.kwargs


@pytest.mark.asyncio
async def test_huge_result_is_truncated():
    async def spammy() -> str:
        return "x" * 700_000

    job_id = background_jobs.start_job("spammy job", spammy())
    await asyncio.sleep(0.05)
    job = background_jobs.get_job(job_id)
    assert job["status"] == "completed"
    assert len(job["result"]) < 61_000
    assert "chars truncated" in job["result"]


@pytest.mark.asyncio
async def test_get_unknown_job_is_error():
    payload = _text_payload(await handle_get_background_job({"job_id": "job-nope"}))
    assert payload["status"] == "error"


# --- Live output capture, health signals, and buffer containment ---------------

_PUBLIC_KEYS = {
    "job_id",
    "description",
    "status",
    "started_at",
    "finished_at",
    "result",
    "error",
    "elapsed_seconds",
    "bytes_captured",
    "stdout_tail",
    "stderr_tail",
    "seconds_since_output",
    "output_is_growing",
    "stall_warning",
}


async def _slow() -> str:
    await asyncio.sleep(5)
    return "never-reached"


async def _quick() -> str:
    return "quick-result"


async def _drain(job_id: str) -> None:
    """Cancel a still-running job and let the cancellation land."""
    background_jobs.cancel_job(job_id)
    await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_get_job_never_leaks_internal_buffers():
    # Regression: the public view was built by filtering out underscore keys, which
    # let the unbounded stdout_buffer ship to the client on every single poll.
    job_id = background_jobs.start_job("buffer job", _slow())
    background_jobs.update_job_output(job_id, "x" * 200, "y" * 200)

    job = background_jobs.get_job(job_id)
    assert set(job) == _PUBLIC_KEYS
    assert not any(k.startswith("_") for k in job)
    assert "stdout_buffer" not in job
    assert "stderr_buffer" not in job
    await _drain(job_id)


@pytest.mark.asyncio
async def test_get_job_is_a_pure_read():
    # Regression: get_job used to mutate poll counters, so the second consecutive
    # call flipped output_is_growing to False on a perfectly healthy job.
    job_id = background_jobs.start_job("pure read job", _slow())
    background_jobs.update_job_output(job_id, "some output\n")

    polls = [background_jobs.get_job(job_id) for _ in range(3)]
    for field in ("output_is_growing", "bytes_captured", "seconds_since_output", "stall_warning"):
        assert len({p[field] for p in polls}) == 1, f"{field} changed across consecutive reads"
    assert polls[0]["output_is_growing"] is True
    await _drain(job_id)


@pytest.mark.asyncio
async def test_tail_lines_limits_returned_output():
    job_id = background_jobs.start_job("tail job", _slow())
    stdout = "".join(f"line{i}\n" for i in range(100))
    background_jobs.update_job_output(job_id, stdout)

    job = background_jobs.get_job(job_id, tail_lines=10)
    assert job["stdout_tail"].splitlines() == [f"line{i}" for i in range(90, 100)]
    assert "line50" not in job["stdout_tail"]
    # bytes_captured counts everything pushed, not just what the tail shows
    assert job["bytes_captured"] == len(stdout)
    await _drain(job_id)


@pytest.mark.asyncio
async def test_bytes_captured_is_monotonic_across_buffer_trim(monkeypatch):
    monkeypatch.setattr(background_jobs, "_MAX_BUFFER_CHARS", 100)
    job_id = background_jobs.start_job("trim job", _slow())
    for _ in range(10):
        background_jobs.update_job_output(job_id, "x" * 50)

    job = background_jobs.get_job(job_id)
    # Buffer was trimmed to the tail, but the byte counter never rewinds.
    assert job["bytes_captured"] == 500
    assert len(job["stdout_tail"]) == 100
    await _drain(job_id)


@pytest.mark.asyncio
async def test_elapsed_seconds_freezes_after_completion():
    job_id = background_jobs.start_job("freeze job", _quick())
    for _ in range(50):
        if background_jobs.get_job(job_id)["status"] != "running":
            break
        await asyncio.sleep(0.01)

    assert background_jobs.get_job(job_id)["status"] == "completed"
    first = background_jobs.get_job(job_id)["elapsed_seconds"]
    await asyncio.sleep(0.05)
    assert background_jobs.get_job(job_id)["elapsed_seconds"] == first


@pytest.mark.asyncio
async def test_stall_warning_when_output_goes_quiet(monkeypatch):
    monkeypatch.setattr(background_jobs, "_STALL_SECONDS", 0)
    job_id = background_jobs.start_job("stalled job", _slow())
    background_jobs.update_job_output(job_id, "last thing it ever said\n")

    job = background_jobs.get_job(job_id)
    assert job["status"] == "running"
    assert job["stall_warning"] is True
    assert job["output_is_growing"] is False
    await _drain(job_id)


@pytest.mark.asyncio
async def test_no_stall_warning_on_finished_job(monkeypatch):
    # A finished job is never "stalled", however long it was quiet for.
    monkeypatch.setattr(background_jobs, "_STALL_SECONDS", 0)
    job_id = background_jobs.start_job("finished job", _quick())
    for _ in range(50):
        if background_jobs.get_job(job_id)["status"] != "running":
            break
        await asyncio.sleep(0.01)

    job = background_jobs.get_job(job_id)
    assert job["status"] == "completed"
    assert job["stall_warning"] is False
    assert job["output_is_growing"] is False


@pytest.mark.asyncio
async def test_seconds_since_output_is_none_before_any_output():
    job_id = background_jobs.start_job("silent job", _slow())
    job = background_jobs.get_job(job_id)
    assert job["seconds_since_output"] is None
    assert job["output_is_growing"] is False
    assert job["bytes_captured"] == 0
    assert job["stdout_tail"] == ""
    await _drain(job_id)


@pytest.mark.asyncio
async def test_update_job_output_ignores_unknown_and_finished_jobs():
    background_jobs.update_job_output("job-nope", "ignored")  # must not raise

    job_id = background_jobs.start_job("done job", _quick())
    for _ in range(50):
        if background_jobs.get_job(job_id)["status"] != "running":
            break
        await asyncio.sleep(0.01)

    background_jobs.update_job_output(job_id, "too late")
    job = background_jobs.get_job(job_id)
    assert job["bytes_captured"] == 0
    assert job["stdout_tail"] == ""


@pytest.mark.asyncio
async def test_list_jobs_omits_result_and_tails():
    job_id = background_jobs.start_job("listed job", _quick())
    background_jobs.update_job_output(job_id, "chatty\n")
    for _ in range(50):
        if background_jobs.get_job(job_id)["status"] != "running":
            break
        await asyncio.sleep(0.01)

    listed = [j for j in background_jobs.list_jobs() if j["job_id"] == job_id]
    assert len(listed) == 1
    view = listed[0]
    for absent in ("result", "stdout_tail", "stderr_tail"):
        assert absent not in view
    for present in ("status", "elapsed_seconds", "bytes_captured", "stall_warning"):
        assert present in view


@pytest.mark.asyncio
async def test_cancel_unknown_job_is_error():
    payload = _text_payload(await handle_cancel_background_job({"job_id": "job-nope"}))
    assert payload["status"] == "error"
