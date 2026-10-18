"""An image open in PhotoCraft: its steps run in batches, its saves waited for."""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from pydantic import BaseModel, ConfigDict, JsonValue

from comic import ComicError
from comic.connection import PhotoCraftError, Session

SAVE_SETTLE_SECONDS = 5.0
SETTLE_POLL_SECONDS = 0.05


def is_whole_image(path: Path) -> bool:
    """Whether `path` is there and opens as a complete image."""
    try:
        with Image.open(path) as image:
            image.verify()
    except (OSError, SyntaxError):
        return False
    return True


def wait_until_readable(path: Path) -> None:
    """Wait until a file PhotoCraft saved is readable here; across the mount it lands late."""
    deadline = time.monotonic() + SAVE_SETTLE_SECONDS
    while not is_whole_image(path):
        if time.monotonic() >= deadline:
            raise ComicError(
                f"PhotoCraft saved {path}, but it did not appear here within "
                f"{SAVE_SETTLE_SECONDS:g} seconds"
            )
        time.sleep(SETTLE_POLL_SECONDS)


class BatchStep(BaseModel):
    model_config = ConfigDict(frozen=True)

    command: str
    params: dict[str, JsonValue]


class OpenReply(BaseModel):
    model_config = ConfigDict(frozen=True)

    index: int


class StepResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: bool
    result: JsonValue = None
    error: str | None = None


class BatchReply(BaseModel):
    model_config = ConfigDict(frozen=True)

    results: list[StepResult]


@dataclass(frozen=True)
class Document:
    """An open PhotoCraft document: the session that reaches it and its index there."""

    session: Session
    index: int

    def run_steps(self, steps: list[BatchStep]) -> list[StepResult]:
        """Each step's result, run on this document; refused unless PhotoCraft ran every step."""
        activate = BatchStep(command="document.activate", params={"document": self.index})
        reply = self.session.request(
            "batch",
            {"steps": [step.model_dump() for step in [activate, *steps]], "stopOnError": False},
        )
        activated, *results = BatchReply.model_validate(reply).results
        if not activated.ok:
            raise PhotoCraftError(
                f"PhotoCraft could not activate document {self.index}: {activated.error}"
            )
        if len(results) != len(steps):
            raise PhotoCraftError(
                f"PhotoCraft answered {len(results)} of a batch of {len(steps)} steps"
            )
        return results

    def save(self, path: Path) -> None:
        """Saved by PhotoCraft on the Mac, then read only once this side sees the new file whole."""
        path.unlink(missing_ok=True)
        self.session.request("doc.save", {"path": str(path), "index": self.index})
        wait_until_readable(path)


@contextmanager
def opened(session: Session, path: Path) -> Iterator[Document]:
    """The image at `path` open as a PhotoCraft document until the block exits, then closed."""
    document = Document(
        session, OpenReply.model_validate(session.request("doc.open", {"path": str(path)})).index
    )
    try:
        yield document
    finally:
        session.request("doc.close", {"index": document.index})
