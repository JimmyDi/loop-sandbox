"""Session-scoped operations; protocol-neutral sandbox resolution and leases."""

import asyncio
import time

from fastapi import HTTPException

from loop_sandbox.contracts.models import FileEdit, FileWrite, ProcessCommand
from loop_sandbox.server.client import forward
from loop_sandbox.server.state import records
from loop_sandbox.server.workspaces import workspace

monitors = set()


async def operation(owner, session, name, arguments):
    async with workspace(owner, session) as (sid, metadata):
        try:
            if name == "read_file":
                result = (await forward(sid, "GET", "/files", params=arguments)).json()
            elif name == "write_file":
                body = FileWrite(**arguments)
                result = (await forward(sid, "POST", "/files", json=body.model_dump())).json()
            elif name == "edit_file":
                body = FileEdit(**arguments)
                result = (await forward(sid, "POST", "/files/edit", json=body.model_dump())).json()
            elif name == "exec":
                body = ProcessCommand(**arguments)
                result = (await forward(sid, "POST", "/processes", json=body.model_dump())).json()
                pid = result["process_id"]
                # The monitor holds a lease until the background process ends.
                rec = records[sid]
                rec["active"] += 1

                async def monitor():
                    try:
                        while True:
                            status = (await forward(sid, "GET", "/processes/" + pid)).json()
                            if not status["running"]:
                                return
                            await asyncio.sleep(1)
                    finally:
                        rec["active"] -= 1
                        rec["expires_at"] = min(
                            time.time() + rec.get("idle_timeout", 900),
                            rec.get("hard_expires_at", float("inf")),
                        )

                task = asyncio.create_task(monitor())
                monitors.add(task)
                task.add_done_callback(monitors.discard)
                task.add_done_callback(lambda done: None if done.cancelled() else done.exception())
                result["process_id"] = str(metadata["generation"]) + ":" + pid
            else:
                generation, separator, pid = arguments["process_id"].partition(":")
                if not separator or generation != str(metadata["generation"]):
                    raise HTTPException(410, "Process belongs to a recycled sandbox generation")
                method = "DELETE" if name == "cancel_process" else "GET"
                params = {"cursor": arguments.get("cursor", 0)} if method == "GET" else {}
                result = (await forward(sid, method, "/processes/" + pid, params=params)).json()
                result["process_id"] = arguments["process_id"]
            return {"sandbox": metadata, "result": result}
        except HTTPException as error:
            return {
                "sandbox": metadata,
                "error": {"status": error.status_code, "message": error.detail},
            }
