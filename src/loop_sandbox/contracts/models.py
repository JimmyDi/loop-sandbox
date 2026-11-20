from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OpenRequest(StrictModel):
    ttl_seconds: int = Field(default=900, ge=60, le=3600)


class Prompt(StrictModel):
    prompt: str = Field(min_length=1, max_length=16000)
    max_steps: int = Field(default=10, ge=1, le=20)


class FileWrite(StrictModel):
    path: str = Field(min_length=1, max_length=4096)
    content: str = Field(max_length=1_000_000)


class Command(StrictModel):
    command: str = Field(min_length=1, max_length=16000)
    timeout: int = Field(default=30, ge=1, le=60)


class BrowserAction(StrictModel):
    action: Literal["open", "set_content", "snapshot", "click", "fill", "screenshot"]
    url: str | None = Field(default=None, max_length=8192)
    selector: str | None = Field(default=None, max_length=4096)
    text: str | None = Field(default=None, max_length=1_000_000)


class FileEdit(StrictModel):
    path: str = Field(min_length=1, max_length=4096)
    old_text: str = Field(min_length=1, max_length=1_000_000)
    new_text: str = Field(max_length=1_000_000)


class ProcessCommand(StrictModel):
    command: str = Field(min_length=1, max_length=16000)
    cwd: str = Field(default=".", min_length=1, max_length=4096)
    timeout: int = Field(default=300, ge=1, le=1800)
