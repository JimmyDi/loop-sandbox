"""Dedicated local deployment only: temporarily rotate, verify reuse, restore token."""

import asyncio
import json
import uuid
from pathlib import Path

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from loop_sandbox.server.cli import configure
from loop_sandbox.server.credentials import read_credentials, save_credentials


async def main():
    root = Path.cwd()
    path = root / ".loop-sandbox/credentials.json"
    original = read_credentials(path)
    session_id = "rotation-" + uuid.uuid4().hex
    base = "http://127.0.0.1:8080"

    async def tool(token, name, arguments):
        async with streamablehttp_client(
            base + "/mcp/",
            headers={"Authorization": "Bearer " + token, "Loop-Session-Id": session_id},
        ) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                response = await session.call_tool(name, arguments)
                data = response.structuredContent or json.loads(response.content[0].text)
                assert not data.get("error"), data.get("error")
                return data

    async with httpx.AsyncClient(base_url=base) as api:

        async def active():
            response = await api.get(
                "/sandboxes", headers={"Authorization": "Bearer " + original["token"]}
            )
            response.raise_for_status()
            return {item["sandbox_id"] for item in response.json()}

        rejected = await api.get(
            "/sandboxes", headers={"Authorization": "Bearer synthetic-invalid-token"}
        )
        if rejected.status_code != 401:
            raise RuntimeError("Token rotation verification requires authentication enabled")
        initial = await active()
        try:
            first = await tool(
                original["token"], "write_file", {"path": "rotation.txt", "content": "retained"}
            )
            allocated = await active()
            configure(root, rotate=True)
            rotated = read_credentials(path)
            assert rotated["client_id"] == original["client_id"]
            assert (
                await api.get(
                    "/sandboxes", headers={"Authorization": "Bearer " + original["token"]}
                )
            ).status_code == 401
            second = await tool(rotated["token"], "read_file", {"path": "rotation.txt"})
            assert second["result"]["content"] == "retained"
            assert first["sandbox"]["generation"] == second["sandbox"]["generation"]
            response = await api.get(
                "/sandboxes", headers={"Authorization": "Bearer " + rotated["token"]}
            )
            assert {item["sandbox_id"] for item in response.json()} == allocated
        finally:
            save_credentials(path, original)
            for sandbox_id in await active():
                if sandbox_id not in initial:
                    await api.delete(
                        "/sandboxes/" + sandbox_id,
                        headers={"Authorization": "Bearer " + original["token"]},
                    )
    print(
        "PASS: live token revocation, stable identity, same worker/files; original credential restored"
    )


if __name__ == "__main__":
    asyncio.run(main())
