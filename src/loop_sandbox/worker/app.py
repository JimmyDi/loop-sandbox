"""Per-sandbox capability server. No Docker socket or model key is mounted here."""

import asyncio
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from playwright.async_api import Error as BrowserError

from loop_sandbox.contracts.models import (
    BrowserAction,
    Command,
    FileEdit,
    FileWrite,
    ProcessCommand,
)
from loop_sandbox.worker import files, processes
from loop_sandbox.worker.browser import close_browser, run_browser
from loop_sandbox.worker.commands import run_command

ROOT = Path(os.getenv("WORKSPACE_ROOT", "/workspace")).resolve()
TOKEN = os.environ["WORKER_TOKEN"]
command_lock = asyncio.Lock()


async def authorize(x_worker_token: str = Header(default="")):
    if not secrets.compare_digest(x_worker_token, TOKEN):
        raise HTTPException(401, "Invalid worker token")


@asynccontextmanager
async def lifespan(app):
    ROOT.mkdir(parents=True, exist_ok=True)
    yield
    await processes.close()
    await close_browser(app.state)


app = FastAPI(lifespan=lifespan, dependencies=[Depends(authorize)])


@app.exception_handler(BrowserError)
async def browser_error(request: Request, error: BrowserError):
    return JSONResponse(status_code=502, content={"detail": str(error)[:2000]})


@app.get("/health")
def health():
    return {"status": "ready"}


@app.post("/files")
def write_file(body: FileWrite):
    return files.write_file(ROOT, body)


@app.get("/files")
def read_file(path: str):
    return files.read_file(ROOT, path)


@app.get("/download")
def download(path: str):
    return files.download(ROOT, path)


@app.post("/commands")
async def command(body: Command):
    async with command_lock:
        return await run_command(ROOT, body)


@app.post("/browser")
async def browser(body: BrowserAction):
    return await run_browser(app.state, body)


@app.post("/files/edit")
def edit_file(body: FileEdit):
    return files.edit_file(ROOT, body)


@app.post("/processes")
async def start_process(body: ProcessCommand):
    async with command_lock:
        return await processes.start(ROOT, body)


@app.get("/processes/{pid}")
def get_process(pid: str, cursor: int = 0):
    return processes.get(pid, cursor)


@app.delete("/processes/{pid}")
async def cancel_process(pid: str):
    return await processes.cancel(pid)
