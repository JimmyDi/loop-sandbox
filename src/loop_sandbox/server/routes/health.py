from fastapi import APIRouter

from loop_sandbox.runtime.docker import daemon
from loop_sandbox.server.state import records

router = APIRouter()


@router.get("/health")
def health():
    client = daemon()
    try:
        return {"docker": client.ping(), "sandboxes": len(records)}
    finally:
        client.close()
