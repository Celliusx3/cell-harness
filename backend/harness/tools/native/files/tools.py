"""The file tools — `send_file` to `ask_about_images` — as the model is offered them."""

from __future__ import annotations

import asyncio
from pathlib import Path

from harness.files import ChatFileService
from harness.images import ImageService
from harness.llm import UserMessage
from harness.runtime.models import BotModels
from harness.tools.domain.context import ToolContext
from harness.tools.domain.outcome import (
    EXECUTION_ERROR,
    INVALID_ARGUMENTS,
    Failure,
    Ok,
    ToolOutcome,
)
from harness.tools.domain.tool import Tool
from harness.tools.native.files import _descriptions
from harness.tools.native.files._answer import ImageAnswer, parsed_reply
from harness.tools.native.files._archive import ArchiveError, extract_archive, pack_archive
from harness.tools.native.files._ask import (
    answer_target,
    can_see,
    images_to_send,
    model_reply,
    save_answer,
)
from harness.tools.native.files._chat_paths import paths_in_chat
from harness.tools.native.files._image import UnviewableImage, image_at
from harness.tools.native.files._jobs import ImageJob, JobFailure, JobsAnswered, jobs_in
from harness.tools.native.files.models import (
    AskAboutImageJobsArgs,
    AskAboutImagesArgs,
    ExtractArchiveArgs,
    MakeArchiveArgs,
    SendFileArgs,
    ViewImageArgs,
)

SEND_FILE = "send_file"
EXTRACT_ARCHIVE = "extract_archive"
MAKE_ARCHIVE = "make_archive"
VIEW_IMAGE = "view_image"
ASK_ABOUT_IMAGES = "ask_about_images"
ASK_ABOUT_IMAGE_JOBS = "ask_about_image_jobs"


def send_file_tool() -> Tool[SendFileArgs]:
    """The tool that names files to hand over."""

    async def execute(args: SendFileArgs, _context: ToolContext) -> ToolOutcome:
        return Ok(content=(), paths_to_send=tuple(args.paths))

    return Tool.from_model(
        name=SEND_FILE,
        description=_descriptions.SEND_FILE,
        args_model=SendFileArgs,
        execute=execute,
    )


def extract_archive_tool(files: ChatFileService, max_bytes: int) -> Tool[ExtractArchiveArgs]:
    """The tool that unpacks an archive of this chat's into numbered files and names them."""

    async def execute(args: ExtractArchiveArgs, context: ToolContext) -> ToolOutcome:
        found = paths_in_chat(files, context.origin.conversation_id, (args.path,))
        if isinstance(found, Failure):
            return found
        (archive,) = found
        try:
            unpacked = await asyncio.to_thread(extract_archive, archive, max_bytes)
        except ArchiveError as err:
            return Failure(INVALID_ARGUMENTS, str(err))
        return Ok("\n".join([f"{len(unpacked)} files, in order:", *map(str, unpacked)]))

    return Tool.from_model(
        name=EXTRACT_ARCHIVE,
        description=_descriptions.EXTRACT_ARCHIVE,
        args_model=ExtractArchiveArgs,
        execute=execute,
    )


def make_archive_tool(files: ChatFileService) -> Tool[MakeArchiveArgs]:
    """The tool that packs files of this chat's, in order, into one new archive and names it."""

    async def execute(args: MakeArchiveArgs, context: ToolContext) -> ToolOutcome:
        found = paths_in_chat(files, context.origin.conversation_id, args.paths)
        if isinstance(found, Failure):
            return found
        try:
            archive = await asyncio.to_thread(pack_archive, found, args.name)
        except ArchiveError as err:
            return Failure(INVALID_ARGUMENTS, str(err))
        return Ok(str(archive))

    return Tool.from_model(
        name=MAKE_ARCHIVE,
        description=_descriptions.MAKE_ARCHIVE,
        args_model=MakeArchiveArgs,
        execute=execute,
    )


def view_image_tool(files: ChatFileService) -> Tool[ViewImageArgs]:
    """The tool that shows the model one image file in this chat's files, by its path."""

    async def execute(args: ViewImageArgs, context: ToolContext) -> ToolOutcome:
        found = paths_in_chat(files, context.origin.conversation_id, (args.path,))
        if isinstance(found, Failure):
            return found
        (file,) = found
        try:
            image = await asyncio.to_thread(image_at, file)
        except UnviewableImage as err:
            return Failure(INVALID_ARGUMENTS, str(err))
        return Ok(f"The image at {args.path}", images=(image,))

    return Tool.from_model(
        name=VIEW_IMAGE,
        description=_descriptions.VIEW_IMAGE,
        args_model=ViewImageArgs,
        execute=execute,
    )


def ask_about_images_tool(
    files: ChatFileService, images: ImageService, models: BotModels
) -> Tool[AskAboutImagesArgs]:
    """The tool that asks the calling bot's model one question about images of this chat's."""

    async def execute(args: AskAboutImagesArgs, context: ToolContext) -> ToolOutcome:
        return await _asked(files, images, models, args, context)

    return Tool.from_model(
        name=ASK_ABOUT_IMAGES,
        description=_descriptions.ASK_ABOUT_IMAGES,
        args_model=AskAboutImagesArgs,
        execute=execute,
    )


def ask_about_image_jobs_tool(
    files: ChatFileService, images: ImageService, models: BotModels, *, at_once: int
) -> Tool[AskAboutImageJobsArgs]:
    """The tool that makes every `ask_about_images` call a jobs file in this chat lists,
    `at_once` of them at a time."""

    async def execute(args: AskAboutImageJobsArgs, context: ToolContext) -> ToolOutcome:
        found = paths_in_chat(files, context.origin.conversation_id, [args.jobs_path])
        if isinstance(found, Failure):
            return found
        jobs = await asyncio.to_thread(jobs_in, found[0])
        if isinstance(jobs, Failure):
            return jobs
        sight = await can_see(models, context.origin.bot_id)
        if isinstance(sight, Failure):
            return sight
        gate = asyncio.Semaphore(at_once)

        async def one(job: ImageJob) -> ToolOutcome:
            async with gate:
                return await _asked(files, images, models, job, context)

        outcomes = await asyncio.gather(*(one(job) for job in jobs))
        failed = [
            JobFailure(save_to=job.save_to, error=outcome.message)
            for job, outcome in zip(jobs, outcomes, strict=True)
            if isinstance(outcome, Failure)
        ]
        done = JobsAnswered(answered=len(jobs) - len(failed), failed=failed)
        return Ok(done.model_dump_json(), data=done.model_dump())

    return Tool.from_model(
        name=ASK_ABOUT_IMAGE_JOBS,
        description=_descriptions.ASK_ABOUT_IMAGE_JOBS,
        args_model=AskAboutImageJobsArgs,
        execute=execute,
    )


async def _asked(
    files: ChatFileService,
    images: ImageService,
    models: BotModels,
    args: AskAboutImagesArgs,
    context: ToolContext,
) -> ToolOutcome:
    """`args` asked of the calling bot's model, its reply saved when `args` says where."""
    chat_id = context.origin.conversation_id
    found = paths_in_chat(files, chat_id, args.paths)
    if isinstance(found, Failure):
        return found
    target = None if args.save_to is None else answer_target(files.folder(chat_id), args.save_to)
    if isinstance(target, Failure):
        return target
    try:
        shown = await asyncio.to_thread(images_to_send, images, found)
    except UnviewableImage as err:
        return Failure(INVALID_ARGUMENTS, str(err))
    if isinstance(shown, Failure):
        return shown
    question = UserMessage(content=args.instructions, images=shown)
    reply = await model_reply(models, context.origin.bot_id, question)
    if isinstance(reply, Failure):
        return reply
    return await _answered(reply, target)


async def _answered(reply: str, target: Path | None) -> ToolOutcome:
    """`reply` as the model and a script receive it, once written to `target` when there is one."""
    parsed = parsed_reply(reply)
    if target is None:
        return Ok(parsed.text, data=ImageAnswer(answer=parsed.value, saved_to=None).model_dump())
    try:
        await asyncio.to_thread(save_answer, target, parsed.text)
    except OSError as err:
        return Failure(EXECUTION_ERROR, f"the reply could not be saved to {target}: {err}")
    answer = ImageAnswer(answer=parsed.value, saved_to=str(target))
    return Ok(f"{parsed.text}\n\nSaved to {target}", data=answer.model_dump())
