"""One question, with no history, to the calling bot's model about images; its saved file."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Sequence
from contextlib import aclosing
from pathlib import Path

from harness.images import ImageService
from harness.llm import Completion, Image, StreamFailure, UserMessage
from harness.runtime.models import PICK_A_MODEL, BotModels, NoModel
from harness.tools.domain.outcome import EXECUTION_ERROR, INVALID_ARGUMENTS, REFUSED, Failure
from harness.tools.native.files._image import image_at

NO_SIGHT = "the bot's model cannot see images, so it cannot be asked about them"
NO_REPLY = "the model call ended with no reply"


def answer_target(folder: Path, save_to: str) -> Path | Failure:
    """`save_to` resolved, when it is absolute and names a file inside `folder`; else a refusal."""
    candidate = Path(save_to)
    if not candidate.is_absolute():
        return Failure(INVALID_ARGUMENTS, f"{save_to} is not an absolute path")
    resolved = candidate.resolve()
    if resolved == folder or not resolved.is_relative_to(folder) or resolved.is_dir():
        return Failure(INVALID_ARGUMENTS, f"{save_to} is not a file path in this chat's folder")
    return resolved


def save_answer(target: Path, text: str) -> None:
    """`text` written whole to `target`, its folders made: a reader never sees half of it."""
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, staged = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as writer:
            writer.write(text)
        os.replace(staged, target)
    except BaseException:
        Path(staged).unlink(missing_ok=True)
        raise


def images_to_send(images: ImageService, files: Sequence[Path]) -> tuple[Image, ...] | Failure:
    """Each of `files` read as a PNG or JPEG and kept for the model; else `UnviewableImage`."""
    kept = images.keep_result_images(tuple(image_at(file) for file in files))
    shown = tuple(block for block in kept if isinstance(block, Image))
    if len(shown) != len(files):
        return Failure(EXECUTION_ERROR, "an image could not be kept to send to the model")
    return shown


async def model_reply(models: BotModels, bot_id: str, question: UserMessage) -> str | Failure:
    """The text `bot_id`'s model replies to `question` alone, asked with no tools; else why not."""
    choice = await models.model_for(bot_id)
    if isinstance(choice, NoModel):
        return Failure(REFUSED, PICK_A_MODEL)
    if not choice.has_vision:
        return Failure(REFUSED, NO_SIGHT)
    completed: Completion | None = None
    async with aclosing(
        choice.client.stream_completion([question], choice.model, tools=None)
    ) as stream:
        async for event in stream:
            if isinstance(event, StreamFailure):
                return Failure(EXECUTION_ERROR, f"the model call failed: {event.reason}")
            if isinstance(event, Completion):
                completed = event
    return Failure(EXECUTION_ERROR, NO_REPLY) if completed is None else completed.full_text
