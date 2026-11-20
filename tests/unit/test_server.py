import asyncio
import time
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from loop_sandbox.contracts.models import OpenRequest
from loop_sandbox.server import client as worker_client
from loop_sandbox.server import lifecycle
from loop_sandbox.server import main as api
from loop_sandbox.server.state import records


def test_api_validation_and_capacity():
    headers = {"Authorization": "Bearer test-key"}
    client = TestClient(api.app)
    assert client.post("/sandboxes", headers=headers, json={"ttl_seconds": 1}).status_code == 422
    assert (
        client.post(
            "/sandboxes/x/commands", headers=headers, json={"command": "echo hi", "timeout": 61}
        ).status_code
        == 422
    )
    assert (
        client.post("/sandboxes/x/browser", headers=headers, json={"action": "invalid"}).status_code
        == 422
    )
    with patch.dict(records, {str(i): {} for i in range(4)}, clear=True):
        result = client.post("/sandboxes", headers=headers, json={})
        assert result.status_code == 429


def test_expired_sandbox_is_not_forwarded():
    with patch.dict(records, {"expired": {"expires_at": time.time() - 1}}, clear=True):
        with pytest.raises(HTTPException) as result:
            asyncio.run(worker_client.forward("expired", "GET", "/health"))
        assert result.value.status_code == 404
        assert lifecycle.list_sandboxes() == []


def test_cancelled_allocation_is_cleaned():
    import threading

    started = threading.Event()
    release = threading.Event()

    def allocate(*args):
        started.set()
        release.wait(5)
        return {"container": "test", "network": "test"}

    async def exercise():
        task = asyncio.create_task(lifecycle.open_sandbox(OpenRequest()))
        await asyncio.to_thread(started.wait, 5)
        task.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    with (
        patch.dict(records, {}, clear=True),
        patch.object(lifecycle, "provision", allocate),
        patch.object(lifecycle, "cleanup") as cleanup,
    ):
        asyncio.run(exercise())
        cleanup.assert_called_once()
        assert records == {}


def test_lifespan_reaps_expired_and_retries_cleanup():
    import docker

    actual_sleep = asyncio.sleep
    calls = []

    async def fast_tick(seconds):
        await actual_sleep(0.01)

    def cleanup(record):
        calls.append(record)
        if len(calls) == 1:
            raise docker.errors.DockerException("temporary")

    async def exercise():
        with (
            patch.object(lifecycle, "sweep"),
            patch.object(lifecycle, "cleanup", cleanup),
            patch.object(lifecycle.asyncio, "sleep", fast_tick),
        ):
            async with lifecycle.lifespan(api.app):
                records["expired"] = {"expires_at": 0}
                async with asyncio.timeout(2):
                    while records:
                        await actual_sleep(0.01)
            assert len(calls) == 2

    with patch.dict(records, {}, clear=True):
        asyncio.run(exercise())


def test_public_auth():
    # No lifespan here: a Docker daemon is deliberately not involved.
    client = TestClient(api.app)
    assert client.get("/sandboxes").status_code == 401
    assert client.get("/sandboxes", headers={"Authorization": "Bearer test-key"}).status_code == 200
