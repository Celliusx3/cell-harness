"""One question, with no history, to the calling bot's model about files; its saved reply."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Sequence
from contextlib import aclosing
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from harness.images import ImageService
from harness.llm import Completion, Image, StreamFailure, Usage, UserMessage
from harness.prompts import ASKED_TEXT_FILE
from harness.runtime.models import PICK_A_MODEL, BotModels, ModelChoice, NoModel
from harness.tools.domain.outcome import (
    EXECUTION_ERROR,
    INVALID_ARGUMENTS,
    REFUSED,
    Failure,
    ReturnedImage,
)
from harness.tools.native.files import image_at, image_media_type

TEXT_MAX_BYTES = 200 * 1024
SIGNATURE_BYTES = 8
NO_SIGHT = "the bot's model cannot see images, so it cannot be asked about them"
NO_REPLY = "the model call ended with no reply"


class UnsendableFile(ValueError):
    """A file that is neither an image nor UTF-8 text, or is too long to send as text."""


class ModelReply(BaseModel):
    """The text a model replied, and the tokens the call took when the provider said."""

    model_config = ConfigDict(frozen=True)

    text: str
    usage: Usage | None


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


def file_part(file: Path) -> ReturnedImage | str:
    """`file` as the model is sent it: a PNG or JPEG as an image, else its text in a tag."""
    with file.open("rb") as reader:
        data = reader.read(TEXT_MAX_BYTES + 1)
    if image_media_type(data[:SIGNATURE_BYTES]) is not None:
        return image_at(file)
    if len(data) > TEXT_MAX_BYTES:
        raise UnsendableFile(f"{file} is larger than {TEXT_MAX_BYTES} bytes, the most text sent")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as err:
        raise UnsendableFile(f"{file} is neither a PNG or JPEG image nor UTF-8 text") from err
    return ASKED_TEXT_FILE.format(path=file, text=text)


def question_of(
    images: ImageService, instructions: str, files: Sequence[Path]
) -> UserMessage | Failure:
    """`instructions`, then each text file, each image kept; raises on a file it cannot send."""
    parts = [file_part(file) for file in files]
    returned = tuple(part for part in parts if isinstance(part, ReturnedImage))
    kept = images.keep_result_images(returned)
    shown = tuple(block for block in kept if isinstance(block, Image))
    if len(shown) != len(returned):
        return Failure(EXECUTION_ERROR, "an image could not be kept to send to the model")
    texts = (part for part in parts if isinstance(part, str))
    return UserMessage(content="\n\n".join((instructions, *texts)), images=shown)


async def model_of(models: BotModels, bot_id: str) -> ModelChoice | Failure:
    """`bot_id`'s model; a refusal telling the person to pick one when it has none."""
    choice = await models.model_for(bot_id)
    return Failure(REFUSED, PICK_A_MODEL) if isinstance(choice, NoModel) else choice


async def model_reply(choice: ModelChoice, question: UserMessage) -> ModelReply | Failure:
    """What `choice` replies to `question` alone, asked with no tools; else why not."""
    if question.images and not choice.has_vision:
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
    if completed is None:
        return Failure(EXECUTION_ERROR, NO_REPLY)
    return ModelReply(text=completed.full_text, usage=completed.usage)
