"""In-process background job registry for long-running tool calls.

Lets a tool call return immediately with a job_id while the real work keeps
running in an asyncio task; the client polls get_background_job for status
and the final result. Built for ssh_execute_command (long installs, upgrades,
builds) where MCP client request timeouts would otherwise kill the call.

The MCP spec's tasks/* polling protocol is deliberately absent from every
negotiated protocol version in mcp SDK 2.0, so this is application-level by
design - it works with every client.

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

#: Stored results larger than this are middle-truncated (curl progress bars
#: and build logs can reach hundreds of KB, which breaks MCP client polling).
_MAX_RESULT_CHARS = 60_000

#: Live stdout/stderr buffers are trimmed to this many characters, keeping the
#: tail. Unbounded buffers would let one chatty job exhaust server memory.
_MAX_BUFFER_CHARS = 200_000

#: A running job that has produced no new output for this long is reported as
#: stalled. Time-based, not poll-based, so the signal does not depend on how
#: often the client happens to poll.
_STALL_SECONDS = 120

_jobs: dict[str, dict[str, Any]] = {}
_counter = itertools.count(1)


def start_job(description: str, coro: Coroutine[Any, Any, str]) -> str:
    """Run *coro* as a background job and return its job_id immediately.

    *coro* must resolve to the tool's normal string result; it is stored
    verbatim as the job result.
    """
    job_id = f"job-{next(_counter)}"
    task = asyncio.get_running_loop().create_task(_run(job_id, coro))
    now = datetime.now(UTC)
    _jobs[job_id] = {
        "job_id": job_id,
        "description": description,
        "status": "running",
        "started_at": now.isoformat(),
        "finished_at": None,
        "result": None,
        "error": None,
        "_task": task,
        "_coro": coro,
        "_started_ts": now,
        "_finished_ts": None,
        "_stdout_buffer": "",
        "_stderr_buffer": "",
        "_bytes_captured": 0,
        "_last_output_ts": None,
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
    now = datetime.now(UTC)
    entry["status"] = "cancelled"
    entry["finished_at"] = now.isoformat()
    entry["_finished_ts"] = now
    entry["_coro"].close()  # never-started coroutine; suppress the un-awaited warning


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
    now = datetime.now(UTC)
    entry["finished_at"] = now.isoformat()
    entry["_finished_ts"] = now


def update_job_output(job_id: str, stdout_chunk: str = "", stderr_chunk: str = "") -> None:
    """Append live output for a running job; ignored for unknown or finished jobs."""
    entry = _jobs.get(job_id)
    if entry is None or entry["status"] != "running":
        return
    if not stdout_chunk and not stderr_chunk:
        return
    # Counted before trimming and never recomputed from the buffers, so this
    # stays monotonic across trims and remains a usable progress signal.
    entry["_bytes_captured"] += len(stdout_chunk.encode("utf-8", errors="replace")) + len(
        stderr_chunk.encode("utf-8", errors="replace")
    )
    entry["_last_output_ts"] = datetime.now(UTC)
    if stdout_chunk:
        entry["_stdout_buffer"] = (entry["_stdout_buffer"] + stdout_chunk)[-_MAX_BUFFER_CHARS:]
    if stderr_chunk:
        entry["_stderr_buffer"] = (entry["_stderr_buffer"] + stderr_chunk)[-_MAX_BUFFER_CHARS:]


def _tail(text: str, n: int) -> str:
    """Return the last *n* lines of *text*."""
    if n <= 0:
        return ""
    lines = text.splitlines()
    if len(lines) <= n:
        return text
    return "\n".join(lines[-n:])


def _public_view(entry: dict[str, Any], tail_lines: int) -> dict[str, Any]:
    """Build the client-facing view of a job entry.

    Every key is listed explicitly rather than filtered out of *entry*: an
    allowlist by construction is the only thing that reliably keeps the
    unbounded internal buffers from being shipped to the client on every poll.
    """
    now = datetime.now(UTC)
    finished_ts: datetime | None = entry["_finished_ts"]
    # Freezes once the job ends, so a job that finished an hour ago does not
    # report an hour of elapsed time.
    end_ts = finished_ts if finished_ts is not None else now
    elapsed_seconds = int((end_ts - entry["_started_ts"]).total_seconds())

    last_output_ts: datetime | None = entry["_last_output_ts"]
    seconds_since_output: int | None = None
    if last_output_ts is not None:
        seconds_since_output = int((now - last_output_ts).total_seconds())

    running = entry["status"] == "running"
    # A job that has never emitted anything is judged on its total age instead.
    quiet_seconds = seconds_since_output if seconds_since_output is not None else elapsed_seconds
    output_is_growing = running and seconds_since_output is not None and seconds_since_output < _STALL_SECONDS
    stall_warning = running and quiet_seconds >= _STALL_SECONDS

    return {
        "job_id": entry["job_id"],
        "description": entry["description"],
        "status": entry["status"],
        "started_at": entry["started_at"],
        "finished_at": entry["finished_at"],
        "result": entry["result"],
        "error": entry["error"],
        "elapsed_seconds": elapsed_seconds,
        "bytes_captured": entry["_bytes_captured"],
        "stdout_tail": _tail(entry["_stdout_buffer"], tail_lines),
        "stderr_tail": _tail(entry["_stderr_buffer"], tail_lines),
        "seconds_since_output": seconds_since_output,
        "output_is_growing": output_is_growing,
        "stall_warning": stall_warning,
    }


def get_job(job_id: str, tail_lines: int = 50) -> dict[str, Any] | None:
    """Return a public view of the job, or None if unknown. Pure read."""
    entry = _jobs.get(job_id)
    if entry is None:
        return None
    return _public_view(entry, tail_lines)


def list_jobs() -> list[dict[str, Any]]:
    """Return public views of all tracked jobs, oldest first, without result or output tails."""
    out: list[dict[str, Any]] = []
    for entry in _jobs.values():
        view = _public_view(entry, 0)
        for key in ("result", "stdout_tail", "stderr_tail"):
            view.pop(key, None)
        out.append(view)
    return out


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
