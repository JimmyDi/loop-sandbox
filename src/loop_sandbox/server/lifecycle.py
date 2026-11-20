"""Sandbox allocation, leases, recovery, and cleanup."""

import asyncio
import logging
import secrets
import time
import uuid
from contextlib import asynccontextmanager

import docker
from fastapi import HTTPException

from loop_sandbox.contracts.models import OpenRequest
from loop_sandbox.runtime.docker import cleanup, provision, sweep
from loop_sandbox.server.client import forward
from loop_sandbox.server.state import lifecycle_lock, records

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    await asyncio.to_thread(sweep)

    async def reap():
        while True:
            await asyncio.sleep(10)
            async with lifecycle_lock:
                for sid, rec in list(records.items()):
                    if (rec["expires_at"] <= time.time() and not rec.get("active", 0)) or (
                        rec.get("hard_expires_at", float("inf")) <= time.time()
                    ):
                        try:
                            await asyncio.to_thread(cleanup, rec)
                            records.pop(sid, None)
                        except docker.errors.DockerException:
                            log.exception("Cleanup failed; retrying next tick")

    task = asyncio.create_task(reap())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        for rec in list(records.values()):
            try:
                await asyncio.to_thread(cleanup, rec)
            except docker.errors.DockerException:
                log.exception("Shutdown cleanup failed; restart will retry")
        records.clear()


async def open_sandbox(body: OpenRequest):
    async with lifecycle_lock:
        if len(records) >= 4:
            raise HTTPException(429, "Demo capacity: 4 sandboxes")
        sid, token = uuid.uuid4().hex, secrets.token_urlsafe(32)
        allocation = asyncio.create_task(asyncio.to_thread(provision, sid, token))
        try:
            rec = await asyncio.shield(allocation)
        except asyncio.CancelledError:
            rec = await allocation
            rec["expires_at"] = 0
            records[sid] = rec
            try:
                await asyncio.to_thread(cleanup, rec)
                records.pop(sid, None)
            except docker.errors.DockerException:
                log.exception("Cancelled allocation cleanup failed; reaper will retry")
            raise
        rec["expires_at"] = time.time() + body.ttl_seconds
        records[sid] = rec
        try:
            async with asyncio.timeout(45):
                while True:
                    try:
                        await forward(sid, "GET", "/health")
                        return {"sandbox_id": sid, "expires_at": rec["expires_at"]}
                    except HTTPException:
                        await asyncio.sleep(0.5)
        except BaseException as error:
            rec["expires_at"] = 0
            try:
                await asyncio.shield(asyncio.to_thread(cleanup, rec))
                records.pop(sid, None)
            except docker.errors.DockerException:
                log.exception("Startup cleanup failed; reaper will retry")
            if isinstance(error, TimeoutError):
                raise HTTPException(504, "Worker startup timed out") from error
            raise


def list_sandboxes():
    return [
        {"sandbox_id": sid, "expires_at": rec["expires_at"]}
        for sid, rec in records.items()
        if rec["expires_at"] > time.time()
    ]


async def close_sandbox(sid: str):
    async with lifecycle_lock:
        rec = records.get(sid)
        if not rec:
            raise HTTPException(404, "Sandbox not found")
        await asyncio.to_thread(cleanup, rec)
        records.pop(sid, None)
        return {"closed": True}
