"""Authenticated worker transport and typed capability calls."""

import time

import httpx
from fastapi import HTTPException, Response

from loop_sandbox.contracts.models import BrowserAction, Command, FileWrite
from loop_sandbox.server.state import records


async def forward(sid, method, route, **kwargs):
    rec = records.get(sid)
    if (
        not rec
        or (rec["expires_at"] <= time.time() and not rec.get("active", 0))
        or rec.get("hard_expires_at", float("inf")) <= time.time()
    ):
        raise HTTPException(404, "Sandbox missing or expired")
    try:
        async with httpx.AsyncClient(timeout=75, trust_env=False) as client:
            response = await client.request(
                method, rec["url"] + route, headers={"X-Worker-Token": rec["token"]}, **kwargs
            )
    except httpx.HTTPError as error:
        raise HTTPException(502, "Worker unavailable") from error
    if response.status_code >= 400:
        raise HTTPException(response.status_code, response.text[:2000])
    return response


async def commands(sid: str, body: Command):
    return (await forward(sid, "POST", "/commands", json=body.model_dump())).json()


async def write(sid: str, body: FileWrite):
    return (await forward(sid, "POST", "/files", json=body.model_dump())).json()


async def read(sid: str, path: str):
    return (await forward(sid, "GET", "/files", params={"path": path})).json()


async def download(sid: str, path: str):
    response = await forward(sid, "GET", "/download", params={"path": path})
    return Response(response.content, media_type="application/octet-stream")


async def browser(sid: str, body: BrowserAction):
    return (await forward(sid, "POST", "/browser", json=body.model_dump())).json()
