"""`send_file`, `extract_archive`, `make_archive` and `view_image`, as the model is offered them."""

from __future__ import annotations

import asyncio

from harness.files import ChatFileService
from harness.tools.models.context import ToolContext
from harness.tools.models.outcome import INVALID_ARGUMENTS, Failure, Ok, ToolOutcome
from harness.tools.models.tool import Tool
from harness.tools.native.files import _descriptions
from harness.tools.native.files._archive import ArchiveError, extract_archive, pack_archive
from harness.tools.native.files._chat_paths import paths_in_chat
from harness.tools.native.files._image import UnviewableImage, image_at
from harness.tools.native.files.models import (
    ExtractArchiveArgs,
    MakeArchiveArgs,
    SendFileArgs,
    ViewImageArgs,
)

SEND_FILE = "send_file"
EXTRACT_ARCHIVE = "extract_archive"
MAKE_ARCHIVE = "make_archive"
VIEW_IMAGE = "view_image"


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
