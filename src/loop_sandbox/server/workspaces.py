"""Disposable session bindings shared by protocol adapters."""

import asyncio
import os
import sqlite3
import time
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

from fastapi import HTTPException

from loop_sandbox.contracts.models import OpenRequest
from loop_sandbox.runtime.docker import is_running
from loop_sandbox.server.lifecycle import close_sandbox, open_sandbox
from loop_sandbox.server.state import lifecycle_lock, records

locks: dict[tuple[str, str], asyncio.Lock] = {}


@contextmanager
def database():
    path = Path(os.getenv("SESSION_DATABASE", "/tmp/loop-sandbox-sessions.sqlite3"))
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE IF NOT EXISTS bindings "
        "(owner TEXT, session TEXT, sandbox TEXT, generation INTEGER, "
        "PRIMARY KEY(owner, session))"
    )
    try:
        with connection:
            yield connection
    finally:
        connection.close()


@asynccontextmanager
async def workspace(owner: str, session: str):
    """Resolve once before dispatch; never retry a dispatched operation."""
    key = (owner, session)
    async with locks.setdefault(key, asyncio.Lock()):
        with database() as connection:
            row = connection.execute(
                "SELECT sandbox, generation FROM bindings WHERE owner=? AND session=?", key
            ).fetchone()
        sid, generation = row if row else (None, 0)
        rec = records.get(sid)
        created = False
        if rec and "container" in rec and not await asyncio.to_thread(is_running, rec):
            await close_sandbox(sid)
            rec = None
        if (
            not rec
            or (rec["expires_at"] <= time.time() and not rec.get("active", 0))
            or rec.get("hard_expires_at", float("inf")) <= time.time()
        ):
            if rec and sid in records:
                await close_sandbox(sid)
            allocated = await open_sandbox(OpenRequest())
            sid = allocated["sandbox_id"]
            generation += 1
            rec = records[sid]
            rec["idle_timeout"] = int(os.getenv("SESSION_IDLE_SECONDS", "900"))
            rec["hard_expires_at"] = time.time() + int(os.getenv("SESSION_MAX_SECONDS", "3600"))
            with database() as connection:
                connection.execute(
                    "INSERT OR REPLACE INTO bindings VALUES (?, ?, ?, ?)", (*key, sid, generation)
                )
            created = True
        async with lifecycle_lock:
            if sid not in records:
                raise HTTPException(409, "Sandbox recycled before dispatch; retry the operation")
            rec["active"] = rec.get("active", 0) + 1
            rec["expires_at"] = min(
                time.time() + rec.get("idle_timeout", 900), rec.get("hard_expires_at", float("inf"))
            )
    try:
        yield (
            sid,
            {
                "generation": generation,
                "created": created,
                "recreated": created and generation > 1,
                "files_restored": False,
            },
        )
    finally:
        async with lifecycle_lock:
            rec["active"] -= 1
            if rec["active"] == 0:
                rec["expires_at"] = min(
                    time.time() + rec.get("idle_timeout", 900),
                    rec.get("hard_expires_at", float("inf")),
                )
