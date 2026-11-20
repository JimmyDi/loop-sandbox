import asyncio
import os
from unittest.mock import patch

import httpx
import pytest
from fastapi import HTTPException

from loop_sandbox.contracts.models import Prompt
from loop_sandbox.integrations.model_agent import runner as agent_module
from loop_sandbox.integrations.model_agent.routes import agent
from loop_sandbox.server import client as worker_client


def test_real_agent_dispatch_loop_with_fake_model_transport():
    # Verify tool-call handling and second model turn; no claim of real model E2E.
    sent = []
    replies = [
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call1",
                                "type": "function",
                                "function": {
                                    "name": "read_file",
                                    "arguments": '{"path":"result.json"}',
                                },
                            }
                        ],
                    }
                }
            ]
        },
        {"choices": [{"message": {"role": "assistant", "content": "total=30"}}]},
    ]

    class Reply:
        status_code = 200

        def __init__(self, body):
            self.body = body

        def json(self):
            return self.body

    class FakeHttp:
        def __init__(self, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, **kw):
            import copy

            sent.append(copy.deepcopy(kw["json"]))
            return Reply(replies.pop(0))

    async def forward(sid, method, route, **kwargs):
        if route == "/health":
            return Reply({"status": "ready"})
        assert sid == "sandbox-a" and kwargs["params"]["path"] == "result.json"
        return Reply({"content": '{"total":30}'})

    with (
        patch.dict(os.environ, {"LLM_API_KEY": "fake-test-key"}),
        patch.object(worker_client, "forward", side_effect=forward),
        patch.object(agent_module.httpx, "AsyncClient", FakeHttp),
    ):
        result = asyncio.run(agent("sandbox-a", Prompt(prompt="calculate")))
    assert result["answer"] == "total=30"
    assert result["trace"][0]["tool"] == "read_file"
    assert sent[1]["messages"][-1]["role"] == "tool"
    assert sent[1]["messages"][-1]["tool_call_id"] == "call1"


def test_agent_network_error_and_missing_key():
    async def forward(*args, **kwargs):
        return None

    async def invoke():
        return await agent_module.run_agent(
            "x", Prompt(prompt="hello"), forward, None, None, None, None
        )

    with patch.dict("os.environ", {"LLM_API_KEY": ""}):
        with pytest.raises(HTTPException) as result:
            asyncio.run(invoke())
        assert result.value.status_code == 503

    async def failing_post(*args, **kwargs):
        raise httpx.ConnectError("offline")

    with (
        patch.dict("os.environ", {"LLM_API_KEY": "test"}),
        patch.object(httpx.AsyncClient, "post", failing_post),
    ):
        with pytest.raises(HTTPException) as result:
            asyncio.run(invoke())
        assert result.value.status_code == 502


def test_agent_rejects_bad_tool_args_and_preserves_step_trace():
    class Model:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, *args, **kwargs):
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "tool_calls": [
                                    {
                                        "id": "1",
                                        "type": "function",
                                        "function": {
                                            "name": "run_command",
                                            "arguments": '{"command":"echo hi","timeout":999}',
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                },
            )

    async def forward(*args, **kwargs):
        return None

    async def invoke():
        return await agent_module.run_agent(
            "x", Prompt(prompt="test", max_steps=1), forward, None, None, None, None
        )

    with (
        patch.dict("os.environ", {"LLM_API_KEY": "test"}),
        patch.object(agent_module.httpx, "AsyncClient", Model),
    ):
        with pytest.raises(HTTPException) as result:
            asyncio.run(invoke())
        assert result.value.status_code == 422
        assert "error" in result.value.detail["trace"][0]["result"]


def test_tool_schema():
    assert {t["function"]["name"] for t in agent_module.TOOLS} == {
        "read_file",
        "write_file",
        "run_command",
        "browser",
    }
