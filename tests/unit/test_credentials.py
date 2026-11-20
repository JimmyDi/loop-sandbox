import asyncio
import json

import pytest
from fastapi import HTTPException

from loop_sandbox.server.auth import authorize
from loop_sandbox.server.cli import configure
from loop_sandbox.server.credentials import read_credentials


def test_init_and_rotation_keep_identity_and_revoke_old_token(tmp_path, monkeypatch, capsys):
    path = configure(tmp_path)
    original = read_credentials(path)
    assert len(original["token"]) >= 43
    assert path.stat().st_mode & 0o777 == 0o600
    assert (tmp_path / ".env").stat().st_mode & 0o777 == 0o600
    assert configure(tmp_path) == path
    assert read_credentials(path) == original
    monkeypatch.setenv("LOOP_SANDBOX_CREDENTIALS", str(path))
    assert asyncio.run(authorize("Bearer " + original["token"])) == original["client_id"]
    configure(tmp_path, rotate=True)
    rotated = read_credentials(path)
    assert rotated["client_id"] == original["client_id"]
    assert rotated["token"] != original["token"]
    assert asyncio.run(authorize("Bearer " + rotated["token"])) == original["client_id"]
    with pytest.raises(HTTPException) as error:
        asyncio.run(authorize("Bearer " + original["token"]))
    assert error.value.status_code == 401
    assert original["token"] not in capsys.readouterr().out
    path.write_text("invalid JSON")
    with pytest.raises(HTTPException) as error:
        asyncio.run(authorize("Bearer " + original["token"]))
    assert error.value.status_code == 503  # No fallback to a legacy key.


def test_legacy_migration_preserves_binding_owner_and_unrelated_env(tmp_path, monkeypatch):
    import hashlib

    env = tmp_path / ".env"
    env.write_text("DEMO_API_KEY=synthetic-migration-token\nAPI_PORT=8080\n")
    before = env.read_text()
    value = read_credentials(configure(tmp_path))
    assert value["token"] == "synthetic-migration-token"
    assert value["client_id"] == hashlib.sha256(b"Bearer synthetic-migration-token").hexdigest()
    assert env.read_text() == before
    configure(tmp_path, rotate=True)
    assert (
        read_credentials(tmp_path / ".loop-sandbox/credentials.json")["client_id"]
        == value["client_id"]
    )


def test_credentials_refuse_insecure_files_and_symlinks(tmp_path):
    path = configure(tmp_path)
    path.chmod(0o644)
    with pytest.raises(ValueError):
        configure(tmp_path)
    path.unlink()
    other = tmp_path / "other.json"
    other.write_text(json.dumps({"client_id": "synthetic", "token": "synthetic"}))
    path.symlink_to(other)
    with pytest.raises(ValueError):
        configure(tmp_path)
    assert json.loads(other.read_text())["token"] == "synthetic"


def test_mcp_uses_verified_principal_not_client_header(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from loop_sandbox.integrations.mcp.app import AuthenticatedMcp

    path = configure(tmp_path)
    monkeypatch.setenv("LOOP_SANDBOX_CREDENTIALS", str(path))
    app = AuthenticatedMcp()

    async def echo(scope, receive, send):
        from starlette.responses import JSONResponse

        await JSONResponse({"owner": scope["loop.client_id"]})(scope, receive, send)

    app.app = echo
    client = TestClient(app)
    original = read_credentials(path)
    headers = {
        "Authorization": "Bearer " + original["token"],
        "Loop-Session-Id": "synthetic-session",
        "Loop-Client-Id": "forged-client",
    }
    assert client.get("/", headers=headers).json()["owner"] == original["client_id"]
    configure(tmp_path, rotate=True)
    assert client.get("/", headers=headers).status_code == 401
    headers["Authorization"] = "Bearer " + read_credentials(path)["token"]
    assert client.get("/", headers=headers).json()["owner"] == original["client_id"]


def test_explicit_auth_bypass_accepts_missing_and_invalid_tokens(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from starlette.responses import JSONResponse

    from loop_sandbox.integrations.mcp.app import AuthenticatedMcp
    from loop_sandbox.server.main import app as public_app

    monkeypatch.setenv("LOOP_SANDBOX_AUTH_DISABLED", "1")
    monkeypatch.setenv("LOOP_SANDBOX_CREDENTIALS", str(tmp_path / "missing.json"))
    assert asyncio.run(authorize("")) == "anonymous"
    assert asyncio.run(authorize("Bearer wrong")) == "anonymous"
    assert TestClient(public_app).get("/sandboxes").status_code == 200
    app = AuthenticatedMcp()

    async def echo(scope, receive, send):
        await JSONResponse({"owner": scope["loop.client_id"]})(scope, receive, send)

    app.app = echo
    client = TestClient(app)
    headers = {"Loop-Session-Id": "synthetic-session"}
    assert client.get("/", headers=headers).json() == {"owner": "anonymous"}
    assert client.get("/").status_code == 400  # Routing still requires a session.
    monkeypatch.setenv("LOOP_SANDBOX_AUTH_DISABLED", "0")
    monkeypatch.delenv("LOOP_SANDBOX_CREDENTIALS")
    with pytest.raises(HTTPException) as error:
        asyncio.run(authorize(""))
    assert error.value.status_code == 401
