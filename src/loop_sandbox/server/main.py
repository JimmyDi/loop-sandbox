"""Public HTTP application composition."""

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from loop_sandbox.integrations.mcp.app import app as mcp_app
from loop_sandbox.integrations.mcp.app import mcp
from loop_sandbox.integrations.model_agent.routes import router as agent_router
from loop_sandbox.server.auth import authentication_disabled, authorize, credentials
from loop_sandbox.server.lifecycle import lifespan
from loop_sandbox.server.routes import capabilities, health, sandboxes
from loop_sandbox.server.session_tools import monitors


@asynccontextmanager
async def application_lifespan(app):
    if not authentication_disabled():
        credentials()
    for key, default in (("SESSION_IDLE_SECONDS", "900"), ("SESSION_MAX_SECONDS", "3600")):
        if int(os.getenv(key, default)) < 1:
            raise RuntimeError(key + " must be a positive integer")
    async with lifespan(app), mcp.session_manager.run():
        try:
            yield
        finally:
            for task in list(monitors):
                task.cancel()
            await asyncio.gather(*monitors, return_exceptions=True)


app = FastAPI(
    title="Loop Sandbox", lifespan=application_lifespan, dependencies=[Depends(authorize)]
)
for router in (health.router, sandboxes.router, capabilities.router, agent_router):
    app.include_router(router)

app.mount("/mcp", mcp_app)
