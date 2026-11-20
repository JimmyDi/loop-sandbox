"""Streamable HTTP MCP adapter. Session identity never comes from model arguments."""

import re
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from starlette.responses import JSONResponse

from loop_sandbox.server.auth import authorize
from loop_sandbox.server.session_tools import operation

mcp = FastMCP(
    "Loop Sandbox",
    stateless_http=True,
    json_response=True,
    streamable_http_path="/",
    instructions=(
        "All tools operate in one disposable session sandbox at /workspace. "
        "exec starts a background Bash command; poll with get_process. "
        "A new sandbox generation loses all previous files and processes. "
        "Never assume files survived a generation change."
    ),
)


def identity(ctx: Context):
    request = ctx.request_context.request
    owner = request.scope["loop.client_id"]
    return owner, request.headers["loop-session-id"]


@mcp.tool()
async def read_file(path: str, ctx: Context) -> dict[str, Any]:
    """Read a UTF-8 file in the disposable workspace (maximum 1 MB)."""
    return await operation(*identity(ctx), "read_file", {"path": path})


@mcp.tool()
async def write_file(path: str, content: str, ctx: Context) -> dict[str, Any]:
    """Write a UTF-8 file, creating parent directories (maximum 1 MB)."""
    return await operation(*identity(ctx), "write_file", {"path": path, "content": content})


@mcp.tool()
async def edit_file(path: str, old_text: str, new_text: str, ctx: Context) -> dict[str, Any]:
    """Replace exactly one occurrence; ambiguous or missing matches are conflicts."""
    return await operation(
        *identity(ctx), "edit_file", {"path": path, "old_text": old_text, "new_text": new_text}
    )


@mcp.tool()
async def exec(command: str, ctx: Context, cwd: str = ".", timeout: int = 300) -> dict[str, Any]:  # noqa: ASYNC109
    """Start Bash in the workspace; returns process_id for polling or cancellation."""
    return await operation(
        *identity(ctx), "exec", {"command": command, "cwd": cwd, "timeout": timeout}
    )


@mcp.tool()
async def get_process(process_id: str, ctx: Context, cursor: int = 0) -> dict[str, Any]:
    """Get status and up to 64 KiB of output; pass returned byte cursor to continue."""
    return await operation(
        *identity(ctx), "get_process", {"process_id": process_id, "cursor": cursor}
    )


@mcp.tool()
async def cancel_process(process_id: str, ctx: Context) -> dict[str, Any]:
    """Kill the command process group. Never restarts a previous command."""
    return await operation(*identity(ctx), "cancel_process", {"process_id": process_id})


class AuthenticatedMcp:
    def __init__(self):
        self.app = mcp.streamable_http_app()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            from fastapi import HTTPException
            from starlette.requests import Request

            request = Request(scope)
            try:
                scope["loop.client_id"] = await authorize(request.headers.get("authorization", ""))
            except HTTPException as error:
                await JSONResponse({"error": "Unauthorized"}, status_code=error.status_code)(
                    scope, receive, send
                )
                return
            if not re.fullmatch(
                r"[A-Za-z0-9_-]{1,128}", request.headers.get("loop-session-id", "")
            ):
                await JSONResponse({"error": "Valid Loop-Session-Id required"}, status_code=400)(
                    scope, receive, send
                )
                return
        await self.app(scope, receive, send)


app = AuthenticatedMcp()
