from unittest.mock import patch

from fastapi.testclient import TestClient

from loop_sandbox.worker import app as worker


def test_worker_auth_file_roundtrip_and_path_boundary():
    with TestClient(worker.app) as client:
        assert client.get("/health").status_code == 401
        headers = {"X-Worker-Token": "test-worker"}
        result = client.post(
            "/files", headers=headers, json={"path": "a/b.txt", "content": "hello"}
        )
        assert result.status_code == 200
        assert (
            client.get("/files", headers=headers, params={"path": "a/b.txt"}).json()["content"]
            == "hello"
        )
        assert (
            client.get("/download", headers=headers, params={"path": "a/b.txt"}).content == b"hello"
        )
        assert (
            client.get("/files", headers=headers, params={"path": "../escape.txt"}).status_code
            == 400
        )
        assert client.get("/files", headers=headers, params={"path": "missing"}).status_code == 404


def test_binary_download_and_symlink_boundary(tmp_path):
    with patch.object(worker, "ROOT", tmp_path):
        (tmp_path / "binary").write_bytes(b"\xff\xfe")
        (tmp_path / "outside").symlink_to(tmp_path.parent)
        with TestClient(worker.app) as client:
            headers = {"X-Worker-Token": "test-worker"}
            assert (
                client.get("/files", headers=headers, params={"path": "binary"}).status_code == 415
            )
            assert (
                client.get("/download", headers=headers, params={"path": "binary"}).content
                == b"\xff\xfe"
            )
            assert (
                client.get("/files", headers=headers, params={"path": "outside/secret"}).status_code
                == 400
            )
