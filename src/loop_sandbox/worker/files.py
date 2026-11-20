"""Bounded workspace file access."""

import os
import tempfile
from pathlib import Path

from fastapi import HTTPException, Response

from loop_sandbox.contracts.models import FileEdit, FileWrite


def resolve_path(root: Path, name: str):
    target = (root / name).resolve()
    if target != root and root not in target.parents:
        raise HTTPException(400, "Path must remain inside workspace")
    return target


def write_file(root: Path, body: FileWrite):
    target = resolve_path(root, body.path)
    if target.is_dir():
        raise HTTPException(400, "Path is a directory")
    if len(body.content.encode("utf-8")) > 1_000_000:
        raise HTTPException(413, "File exceeds 1 MB")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body.content, encoding="utf-8")
    return {"path": body.path, "bytes": target.stat().st_size}


def read_file(root: Path, path: str):
    target = resolve_path(root, path)
    if not target.is_file():
        raise HTTPException(404, "File not found")
    with target.open("rb") as stream:
        data = stream.read(1_000_001)
    if len(data) > 1_000_000:
        raise HTTPException(413, "File exceeds 1 MB; use download")
    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise HTTPException(415, "File is not UTF-8; use download") from error
    return {"path": path, "content": content}


def download(root: Path, path: str):
    target = resolve_path(root, path)
    if not target.is_file():
        raise HTTPException(404, "File not found")
    with target.open("rb") as stream:
        data = stream.read(5_000_001)
    if len(data) > 5_000_000:
        raise HTTPException(413, "File exceeds 5 MB")
    return Response(data, media_type="application/octet-stream")


def edit_file(root: Path, body: FileEdit):
    target = resolve_path(root, body.path)
    content = read_file(root, body.path)["content"]
    if content.count(body.old_text) != 1:
        raise HTTPException(409, "Edit requires exactly one matching occurrence")
    replacement = content.replace(body.old_text, body.new_text, 1)
    if len(replacement.encode("utf-8")) > 1_000_000:
        raise HTTPException(413, "File exceeds 1 MB")
    descriptor, temporary = tempfile.mkstemp(dir=target.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(replacement)
        if target.read_text(encoding="utf-8") != content:
            raise HTTPException(409, "File changed during edit")
        os.chmod(temporary, target.stat().st_mode & 0o777)
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return {"path": body.path, "bytes": len(replacement.encode("utf-8"))}
