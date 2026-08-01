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
    for _ in range(50):
        job = background_jobs.get_job(job_id)
        assert job is not None
        if job["status"] != "running":
            break
        await asyncio.sleep(0.01)
    assert job["status"] == "completed"
    assert job["result"] == "done-output"
    assert job["finished_at"] is not None


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


@pytest.mark.asyncio
async def test_cancel_unknown_job_is_error():
    payload = _text_payload(await handle_cancel_background_job({"job_id": "job-nope"}))
    assert payload["status"] == "error"
