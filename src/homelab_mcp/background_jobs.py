"""In-process background job registry for long-running tool calls.

Lets a tool call return immediately with a job_id while the real work keeps
running in an asyncio task; the client polls get_background_job for status
and the final result. Built for ssh_execute_command (long installs, upgrades,
builds) where MCP client request timeouts would otherwise kill the call.

The MCP spec's tasks/* polling protocol is deliberately absent from every
negotiated protocol version in mcp SDK 2.0, so this is application-level by
design — it works with every client.

ponytail: in-memory only; jobs are lost on server restart. Persist to the
SQLite db if that ever matters.
"""

from __future__ import annotations

import asyncio
import itertools
import logging
from collections.abc import Coroutine
from datetime import UTC, datetime
from typing import Any

from .log_filter import sanitize_error

logger = logging.getLogger(__name__)

#: Finished jobs kept for polling before the oldest are pruned.
_MAX_FINISHED = 50

_jobs: dict[str, dict[str, Any]] = {}
_counter = itertools.count(1)


def start_job(description: str, coro: Coroutine[Any, Any, str]) -> str:
    """Run *coro* as a background job and return its job_id immediately.

    *coro* must resolve to the tool's normal string result; it is stored
    verbatim as the job result.
    """
    job_id = f"job-{next(_counter)}"
    task = asyncio.get_running_loop().create_task(_run(job_id, coro))
    _jobs[job_id] = {
        "job_id": job_id,
        "description": description,
        "status": "running",
        "started_at": datetime.now(UTC).isoformat(),
        "finished_at": None,
        "result": None,
        "error": None,
        "_task": task,
        "_coro": coro,
    }
    # Covers cancellation before _run's first tick, where _run never executes
    # and could not record the terminal state itself.
    task.add_done_callback(lambda _t: _finalize(job_id))
    _prune()
    return job_id


def _finalize(job_id: str) -> None:
    entry = _jobs.get(job_id)
    if entry is None or entry["status"] != "running":
        return
    entry["status"] = "cancelled"
    entry["finished_at"] = datetime.now(UTC).isoformat()
    entry["_coro"].close()  # never-started coroutine; suppress the un-awaited warning


#: Stored results larger than this are middle-truncated (curl progress bars
#: and build logs can reach hundreds of KB, which breaks MCP client polling).
_MAX_RESULT_CHARS = 60_000


def _truncate(result: str) -> str:
    if len(result) <= _MAX_RESULT_CHARS:
        return result
    dropped = len(result) - 10_000 - 40_000
    return f"{result[:10_000]}\n...[{dropped} chars truncated]...\n{result[-40_000:]}"


async def _run(job_id: str, coro: Coroutine[Any, Any, str]) -> None:
    entry = _jobs[job_id]
    try:
        entry["result"] = _truncate(await coro)
        entry["status"] = "completed"
    except asyncio.CancelledError:
        entry["status"] = "cancelled"
    except Exception as e:
        entry["error"] = sanitize_error(e)
        entry["status"] = "failed"
        logger.warning("Background job %s failed: %s", job_id, entry["error"])
    entry["finished_at"] = datetime.now(UTC).isoformat()


def get_job(job_id: str) -> dict[str, Any] | None:
    """Return a public view of the job, or None if unknown."""
    entry = _jobs.get(job_id)
    if entry is None:
        return None
    return {k: v for k, v in entry.items() if not k.startswith("_")}


def list_jobs() -> list[dict[str, Any]]:
    """Return public views of all tracked jobs, oldest first, without results."""
    return [{k: v for k, v in e.items() if not k.startswith("_") and k != "result"} for e in _jobs.values()]


def cancel_job(job_id: str) -> bool:
    """Cancel a running job. Returns True if it was running and got cancelled."""
    entry = _jobs.get(job_id)
    if entry is None or entry["status"] != "running":
        return False
    task: asyncio.Task[None] = entry["_task"]
    return task.cancel()


def _prune() -> None:
    finished = [jid for jid, e in _jobs.items() if e["status"] != "running"]
    for jid in finished[: max(0, len(finished) - _MAX_FINISHED)]:
        del _jobs[jid]
