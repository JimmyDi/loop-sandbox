import asyncio
import time
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from loop_sandbox.contracts.models import FileEdit, FileWrite, ProcessCommand
from loop_sandbox.server import workspaces
from loop_sandbox.server.state import records
from loop_sandbox.worker import files, processes


def test_session_reuse_isolation_and_generation(tmp_path, monkeypatch):
    monkeypatch.setenv("SESSION_DATABASE", str(tmp_path / "bindings.db"))
    workspaces.locks.clear()
    records.clear()
    count = 0

    async def allocate(body):
        nonlocal count
        count += 1
        sid = str(count)
        records[sid] = {"expires_at": time.time() + 900}
        return {"sandbox_id": sid}

    monkeypatch.setattr(workspaces, "open_sandbox", allocate)

    async def scenario():
        async def resolve(owner, session):
            async with workspaces.workspace(owner, session) as value:
                return value

        first, parallel = await asyncio.gather(resolve("user", "chat"), resolve("user", "chat"))
        assert first[0] == parallel[0]
        assert count == 1
        other = await resolve("other-user", "chat")
        assert other[0] != first[0]
        records[first[0]]["expires_at"] = time.time() - 1
        records[first[0]]["active"] = 1
        still_active = await resolve("user", "chat")
        assert still_active[0] == first[0]
        records.pop(first[0])
        replacement = await resolve("user", "chat")
        assert replacement[1]["generation"] == 2
        assert replacement[1]["recreated"]
        assert not replacement[1]["files_restored"]

    asyncio.run(scenario())
    records.clear()
    workspaces.locks.clear()


def test_exact_edit_and_path_escape(tmp_path):
    files.write_file(tmp_path, FileWrite(path="a.txt", content="hello world"))
    files.edit_file(tmp_path, FileEdit(path="a.txt", old_text="world", new_text="sandbox"))
    assert files.read_file(tmp_path, "a.txt")["content"] == "hello sandbox"
    with pytest.raises(HTTPException) as conflict:
        files.edit_file(tmp_path, FileEdit(path="a.txt", old_text="missing", new_text="x"))
    assert conflict.value.status_code == 409
    with pytest.raises(HTTPException):
        files.read_file(tmp_path, "../escape")


def test_background_command_poll_cancel_timeout(tmp_path):
    async def scenario():
        try:
            started = await processes.start(tmp_path, ProcessCommand(command="printf hello"))
            pid = started["process_id"]
            await processes.jobs[pid]["task"]
            result = processes.get(pid)
            assert result["output"] == "hello"
            assert result["exit_code"] == 0
            assert processes.get(pid, result["cursor"])["output"] == ""
            started = await processes.start(tmp_path, ProcessCommand(command="sleep 30"))
            result = await processes.cancel(started["process_id"])
            assert result["cancelled"] and not result["running"]
            started = await processes.start(tmp_path, ProcessCommand(command="sleep 30", timeout=1))
            await processes.jobs[started["process_id"]]["task"]
            assert processes.get(started["process_id"])["timed_out"]
        finally:
            await processes.close()

    asyncio.run(scenario())


def test_no_reallocation_on_transport_failure(tmp_path, monkeypatch):
    from loop_sandbox.server import session_tools

    monkeypatch.setenv("SESSION_DATABASE", str(tmp_path / "bindings.db"))
    records.clear()
    workspaces.locks.clear()

    async def allocate(body):
        records["existing"] = {"expires_at": time.time() + 900}
        return {"sandbox_id": "existing"}

    allocator = AsyncMock(side_effect=allocate)
    monkeypatch.setattr(workspaces, "open_sandbox", allocator)
    monkeypatch.setattr(
        session_tools, "forward", AsyncMock(side_effect=HTTPException(502, "Unavailable"))
    )

    async def scenario():
        for _ in range(2):
            result = await session_tools.operation(
                "user", "chat", "write_file", {"path": "a", "content": "b"}
            )
            assert result["error"]["status"] == 502
        assert allocator.await_count == 1

    asyncio.run(scenario())
    records.clear()
    workspaces.locks.clear()
