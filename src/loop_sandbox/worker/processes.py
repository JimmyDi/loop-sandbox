"""Bounded background Bash jobs; process groups are killed on timeout/cancel."""

import asyncio
import os
import signal
import tempfile
import uuid
from pathlib import Path

from fastapi import HTTPException

from loop_sandbox.contracts.models import ProcessCommand
from loop_sandbox.worker.files import resolve_path

jobs = {}


def kill(proc):
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


async def start(root: Path, body: ProcessCommand):
    if len(jobs) >= 64:
        raise HTTPException(429, "Process history capacity reached; recycle the sandbox")
    if sum(not job["task"].done() for job in jobs.values()) >= 4:
        raise HTTPException(429, "At most four commands may run concurrently")
    cwd = resolve_path(root, body.cwd)
    output = tempfile.TemporaryFile(dir="/tmp")
    try:
        proc = await asyncio.create_subprocess_exec(
            "/bin/bash",
            "-lc",
            body.command,
            cwd=cwd,
            stdout=output,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
        )
    except BaseException:
        output.close()
        raise
    pid = uuid.uuid4().hex
    job = {"proc": proc, "output": output, "timed_out": False, "cancelled": False}

    async def finish():
        try:
            await asyncio.wait_for(proc.wait(), body.timeout)
        except TimeoutError:
            job["timed_out"] = True
        finally:
            kill(proc)
            await proc.wait()

    job["task"] = asyncio.create_task(finish())
    jobs[pid] = job
    return {"process_id": pid}


def get(pid: str, cursor: int = 0):
    job = jobs.get(pid)
    if not job:
        raise HTTPException(404, "Process not found in this sandbox generation")
    output = job["output"]
    size = os.fstat(output.fileno()).st_size
    position = min(max(cursor, 0), min(size, 1_000_000))
    data = os.pread(output.fileno(), min(65536, 1_000_000 - position), position)
    return {
        "process_id": pid,
        "running": not job["task"].done(),
        "exit_code": job["proc"].returncode,
        "output": data.decode("utf-8", errors="replace"),
        "cursor": position + len(data),
        "truncated": size > 1_000_000,
        "timed_out": job["timed_out"],
        "cancelled": job["cancelled"],
    }


async def cancel(pid: str):
    if pid not in jobs:
        raise HTTPException(404, "Process not found in this sandbox generation")
    job = jobs[pid]
    job["cancelled"] = True
    kill(job["proc"])
    await job["task"]
    return get(pid)


async def close():
    for pid in list(jobs):
        await cancel(pid)
        jobs[pid]["output"].close()
    jobs.clear()
