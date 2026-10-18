"""What a tool call returns, and the codes a failure carries."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from harness.llm import Block, Text, text_of
from harness.prompts import ERROR_PREFIX

INVALID_ARGUMENTS = "INVALID_ARGUMENTS"
UNKNOWN_TOOL = "UNKNOWN_TOOL"
EXECUTION_ERROR = "EXECUTION_ERROR"
REFUSED = "REFUSED"
BLOCKED = "BLOCKED"


class ToolUi(BaseModel):
    """The interface a result is drawn with — MCP Apps' `_meta.ui.resourceUri`."""

    model_config = ConfigDict(frozen=True)

    server: str
    resource_uri: str
    data: object | None = None


@dataclass(frozen=True)
class ReturnedImage:
    """An image a tool returned, decoded."""

    media_type: str
    data: bytes


@dataclass(frozen=True)
class Ok:
    """A call that produced a result."""

    content: tuple[Block, ...]
    data: object | None = None
    ui: ToolUi | None = None
    hand_over_paths: tuple[str, ...] = ()
    images: tuple[ReturnedImage, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.content, str):
            object.__setattr__(self, "content", (Text(text=self.content),))

    @property
    def text(self) -> str:
        """The prose alone — for a reader that wants a string, like the bridge."""
        return text_of(self.content)


@dataclass(frozen=True)
class Failure:
    """A call that did not."""

    code: str
    message: str


@dataclass(frozen=True)
class Pending:
    """A call the *client* answers, later."""


ToolOutcome = Ok | Failure | Pending


def blocks_of(outcome: Ok | Failure) -> tuple[Block, ...]:
    """What the model sees, as blocks."""
    if isinstance(outcome, Ok):
        return outcome.content
    return (Text(text=f"{ERROR_PREFIX}{outcome.message}"),)
