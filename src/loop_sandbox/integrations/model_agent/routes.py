"""Optional model endpoint, composed by the controller application."""

from fastapi import APIRouter

from loop_sandbox.contracts.models import Prompt
from loop_sandbox.integrations.model_agent.runner import run_agent
from loop_sandbox.server import client

router = APIRouter()


@router.post("/sandboxes/{sid}/agent")
async def agent(sid: str, body: Prompt):
    return await run_agent(
        sid, body, client.forward, client.read, client.write, client.commands, client.browser
    )
