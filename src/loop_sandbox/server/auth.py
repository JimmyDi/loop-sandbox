"""Bearer authentication with a stable server-owned client identity."""

import hashlib
import os
import secrets
from pathlib import Path

from fastapi import Header, HTTPException

from loop_sandbox.server.credentials import read_credentials


def authentication_disabled() -> bool:
    return os.getenv("LOOP_SANDBOX_AUTH_DISABLED", "0") == "1"


def credentials():
    path = os.getenv("LOOP_SANDBOX_CREDENTIALS")
    if path:
        return read_credentials(Path(path))
    token = os.getenv("DEMO_API_KEY", "")
    if not token or token == "replace-with-a-random-local-key":
        raise ValueError("Initialize controller credentials before starting the API")
    return {
        "token": token,
        "client_id": hashlib.sha256(("Bearer " + token).encode()).hexdigest(),
    }


async def authorize(authorization: str = Header(default="")) -> str:
    if authentication_disabled():
        return "anonymous"
    try:
        value = credentials()
    except (OSError, ValueError):
        raise HTTPException(503, "Controller credentials unavailable") from None
    if not secrets.compare_digest(authorization.encode(), ("Bearer " + value["token"]).encode()):
        raise HTTPException(401, "Invalid API key")
    return value["client_id"]
