import asyncio
import json
import os

import httpx
from fastapi import HTTPException

from loop_sandbox.contracts.models import BrowserAction, Command, FileWrite, Prompt
from loop_sandbox.integrations.model_agent.tools import TOOLS


async def run_agent(sid: str, body: Prompt, forward, read, write, commands, browser):
    try:
        async with asyncio.timeout(600):
            return await agent_loop(sid, body, forward, read, write, commands, browser)
    except TimeoutError as error:
        raise HTTPException(504, "Agent exceeded 600 second time budget") from error
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as error:
        raise HTTPException(502, "Model unavailable or malformed response") from error


async def agent_loop(sid: str, body: Prompt, forward, read, write, commands, browser):
    await forward(sid, "GET", "/health")
    key = os.getenv("LLM_API_KEY")
    if not key:
        raise HTTPException(503, "Set LLM_API_KEY and recreate api container")
    messages = [
        {
            "role": "system",
            "content": "Complete tasks using tools. Work in /workspace. Inspect exit_code and timed_out; verify artifacts by reading them. Network is off unless configured. Never claim an operation succeeded without tool evidence.",
        },
        {"role": "user", "content": body.prompt},
    ]
    trace = []
    async with httpx.AsyncClient(timeout=120) as client:
        for _ in range(body.max_steps):
            response = await client.post(
                os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
                + "/chat/completions",
                headers={"Authorization": "Bearer " + key},
                json={
                    "model": os.getenv("LLM_MODEL", "gpt-4.1"),
                    "messages": messages,
                    "tools": TOOLS,
                },
            )
            if response.status_code >= 400:
                raise HTTPException(
                    502, "Model upstream rejected request: HTTP " + str(response.status_code)
                )
            message = response.json()["choices"][0]["message"]
            calls = message.get("tool_calls") or []
            messages.append(
                {k: message[k] for k in ("role", "content", "tool_calls") if k in message}
            )
            if not calls:
                return {"answer": message.get("content"), "trace": trace}
            if len(calls) > 16:
                raise HTTPException(502, "Model returned too many tool calls")
            for call in calls:
                name = call["function"]["name"]
                args = {}
                try:
                    args = json.loads(call["function"]["arguments"])
                    if not isinstance(args, dict):
                        raise ValueError("Tool arguments must be an object")
                    if name == "read_file":
                        result = await read(sid, **args)
                    elif name == "write_file":
                        result = await write(sid, FileWrite.model_validate(args))
                    elif name == "run_command":
                        result = await commands(sid, Command.model_validate(args))
                    elif name == "browser":
                        result = await browser(sid, BrowserAction.model_validate(args))
                    else:
                        result = {"error": "Unknown tool"}
                except (HTTPException, ValueError, TypeError) as error:
                    result = {"error": str(getattr(error, "detail", error))[:2000]}
                trace.append({"tool": name, "arguments": args, "result": result})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": json.dumps(result, ensure_ascii=False)[:20000],
                    }
                )
    raise HTTPException(422, {"error": "Agent step limit reached", "trace": trace})
