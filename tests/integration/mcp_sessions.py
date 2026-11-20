"""Exercise the real MCP endpoint and Docker workers, without a model provider."""

import asyncio
import json
import os
import uuid
from pathlib import Path

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main():
    token = (
        os.getenv("DEMO_API_KEY")
        or json.loads(Path(".loop-sandbox/credentials.json").read_text())["token"]
    )
    base = os.getenv("API_URL", "http://127.0.0.1:8080")
    headers = {"Authorization": "Bearer " + token}
    async with httpx.AsyncClient(base_url=base, headers=headers) as api:
        initial = {item["sandbox_id"] for item in (await api.get("/sandboxes")).json()}

        async def active():
            return {item["sandbox_id"] for item in (await api.get("/sandboxes")).json()}

        try:
            async with streamablehttp_client(
                base + "/mcp/",
                headers={
                    **headers,
                    "Loop-Session-Id": "integration-" + uuid.uuid4().hex,
                },
            ) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    catalog = await session.list_tools()
                    assert len(catalog.tools) == 6
                    assert await active() == initial, "Discovery must not allocate a worker"

                    async def call(name, arguments):
                        result = await session.call_tool(name, arguments)
                        assert not result.isError, result
                        assert result.structuredContent, "Structured status is required"
                        return result.structuredContent

                    written = await call("write_file", {"path": "test.txt", "content": "one"})
                    assert written["sandbox"]["generation"] == 1
                    allocated = (await active()) - initial
                    assert len(allocated) == 1
                    result = await call("read_file", {"path": "test.txt"})
                    assert result["result"]["content"] == "one"
                    assert await active() == initial | allocated
                    process = await call("exec", {"command": "sleep 30"})
                    pid = process["result"]["process_id"]
                    cancelled = await call("cancel_process", {"process_id": pid})
                    assert cancelled["result"]["cancelled"]
                    assert not cancelled["result"]["running"]
                    for sid in allocated:
                        (await api.delete("/sandboxes/" + sid)).raise_for_status()
                    result = await call("read_file", {"path": "test.txt"})
                    assert result["sandbox"]["generation"] == 2
                    assert result["sandbox"]["recreated"]
                    assert result["error"]["status"] == 404
                    result = await call("get_process", {"process_id": pid})
                    assert result["error"]["status"] == 410
            response = await api.post(
                "/mcp/", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
            )
            assert response.status_code == 400
            response = await api.post(
                "/mcp/",
                headers={"Authorization": "Bearer invalid", "Loop-Session-Id": "test"},
                json={},
            )
            assert response.status_code == 401
            print(
                "PASS: real MCP discovery, reuse, files, cancellation, recycling, stale processes, identity/auth"
            )
        finally:
            for sid in (await active()) - initial:
                await api.delete("/sandboxes/" + sid)


if __name__ == "__main__":
    asyncio.run(main())
