"""Private, atomically replaced controller credentials."""

import json
import os
import secrets
import tempfile
from pathlib import Path


def read_credentials(path: Path) -> dict[str, str]:
    if path.is_symlink() or path.stat().st_mode & 0o077:
        raise ValueError("Credential file must be private (mode 0600) and not a symlink")
    value = json.loads(path.read_text())
    if not isinstance(value, dict) or not all(
        isinstance(value.get(key), str) and value[key] for key in ("client_id", "token")
    ):
        raise ValueError("Invalid credential file")
    return value


def save_credentials(path: Path, value: dict[str, str]):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("Refusing a symlink credential file")
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def new_credentials(client_id: str | None = None):
    return {"client_id": client_id or secrets.token_hex(16), "token": secrets.token_urlsafe(32)}
