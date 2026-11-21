"""The workspace tools as offered: read, write, edit and search, by absolute path."""

from __future__ import annotations

from pathlib import Path

from harness.files import FolderEntries, TextEdit, WorkspaceFileError, WorkspaceTextService
from harness.files.domain.errors import NoWorkspaceError
from harness.tools.domain.context import CallOrigin, ToolContext
from harness.tools.domain.outcome import INVALID_ARGUMENTS, Failure, Ok, ToolOutcome
from harness.tools.domain.tool import Tool
from harness.tools.native.workspace import _descriptions
from harness.tools.native.workspace._found import found
from harness.tools.native.workspace._lines import LineRange, listed, numbered
from harness.tools.native.workspace.models import (
    WorkspaceEditArgs,
    WorkspaceReadArgs,
    WorkspaceSearchArgs,
    WorkspaceWriteArgs,
)

WORKSPACE_READ = "workspace_read"
WORKSPACE_WRITE = "workspace_write"
WORKSPACE_EDIT = "workspace_edit"
WORKSPACE_SEARCH = "workspace_search"
WORKSPACE_TOOLS = (WORKSPACE_READ, WORKSPACE_WRITE, WORKSPACE_EDIT, WORKSPACE_SEARCH)
WROTE = "Wrote {path}."
EDITED = "Edited {path}."


def roots_of(origin: CallOrigin) -> tuple[Path, ...]:
    """The workspaces the call's turn was told of: its chat's, and the bot's own in a group."""
    return tuple(root for root in (origin.workspace, origin.own_workspace) if root is not None)


def _refused(err: WorkspaceFileError) -> Failure:
    return Failure(INVALID_ARGUMENTS, str(err))


def workspace_read_tool(texts: WorkspaceTextService) -> Tool[WorkspaceReadArgs]:
    """The tool that reads a file's lines, numbered, or lists a folder."""

    async def execute(args: WorkspaceReadArgs, context: ToolContext) -> ToolOutcome:
        origin = context.origin
        try:
            read = await texts.read(roots_of(origin), args.path, origin.history_id)
            if isinstance(read, FolderEntries):
                return Ok(listed(read))
            lines = LineRange(start=args.start_line or 1, end=args.end_line)
            return Ok(numbered(read.path, read.text, lines))
        except WorkspaceFileError as err:
            return _refused(err)

    return Tool.from_model(
        name=WORKSPACE_READ,
        description=_descriptions.WORKSPACE_READ,
        args_model=WorkspaceReadArgs,
        execute=execute,
    )


def workspace_write_tool(texts: WorkspaceTextService) -> Tool[WorkspaceWriteArgs]:
    """The tool that creates one new text file."""

    async def execute(args: WorkspaceWriteArgs, context: ToolContext) -> ToolOutcome:
        origin = context.origin
        try:
            target = await texts.write(roots_of(origin), args.path, args.text, origin.history_id)
        except WorkspaceFileError as err:
            return _refused(err)
        return Ok(WROTE.format(path=target))

    return Tool.from_model(
        name=WORKSPACE_WRITE,
        description=_descriptions.WORKSPACE_WRITE,
        args_model=WorkspaceWriteArgs,
        execute=execute,
    )


def workspace_edit_tool(texts: WorkspaceTextService) -> Tool[WorkspaceEditArgs]:
    """The tool that replaces one exact piece of a file's text, read first."""

    async def execute(args: WorkspaceEditArgs, context: ToolContext) -> ToolOutcome:
        origin = context.origin
        change = TextEdit(find=args.find, replace=args.replace)
        try:
            target = await texts.edit(roots_of(origin), args.path, change, origin.history_id)
        except WorkspaceFileError as err:
            return _refused(err)
        return Ok(EDITED.format(path=target))

    return Tool.from_model(
        name=WORKSPACE_EDIT,
        description=_descriptions.WORKSPACE_EDIT,
        args_model=WorkspaceEditArgs,
        execute=execute,
    )


def workspace_search_tool(texts: WorkspaceTextService) -> Tool[WorkspaceSearchArgs]:
    """The tool that finds a text, ignoring case, in every text file under a folder."""

    async def execute(args: WorkspaceSearchArgs, context: ToolContext) -> ToolOutcome:
        origin = context.origin
        try:
            folder = _search_folder(args.path, origin)
            hits = await texts.search(roots_of(origin), args.query, folder)
        except WorkspaceFileError as err:
            return _refused(err)
        return Ok(found(hits, folder))

    return Tool.from_model(
        name=WORKSPACE_SEARCH,
        description=_descriptions.WORKSPACE_SEARCH,
        args_model=WorkspaceSearchArgs,
        execute=execute,
    )


def _search_folder(path: str | None, origin: CallOrigin) -> str:
    """The folder a search names, else the chat's workspace; refused when there is neither."""
    if path is not None:
        return path
    if origin.workspace is None:
        raise NoWorkspaceError()
    return str(origin.workspace)


def workspace_tools(texts: WorkspaceTextService) -> tuple[Tool, ...]:
    """The four workspace tools, each reaching the workspaces its call's turn was told of."""
    return (
        workspace_read_tool(texts),
        workspace_write_tool(texts),
        workspace_edit_tool(texts),
        workspace_search_tool(texts),
    )
