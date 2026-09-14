"""One connection: a task that owns the session, and a queue feeding it.

**Why a command loop rather than connect/close methods.** The SDK's `Client` is
an anyio context manager, and anyio's asyncio backend raises from
`CancelScope.__exit__` when the exiting task is not the entering one:

    RuntimeError: Attempted to exit cancel scope in a different task than it was
    entered in

Measured, not assumed — a spike closing from another task raised exactly that.
So one task per connection owns the session for its whole life, and callers
submit commands and await a reply. This is the shape `RunningChannel` in
`channels/protocol.py` already uses for a supervised task.

**One task per connection, not a supervisor hosting a task group.** That shape is
what anyio forces, because a `TaskGroup` can only spawn from its host task. In
pure asyncio `create_task` spawns from anywhere, so the only surviving constraint
is enter-and-exit-in-one-task and a supervisor would have nothing to do.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass, field
from typing import Literal

from mcp.types import CallToolResult, ReadResourceResult, Tool

from harness.config.sections import McpServer
from harness.mcp.client import ClientFactory, ClientLike
from harness.mcp.errors import (
    McpConnectionError,
    McpNotConnectedError,
    McpTimeoutError,
    describe,
)
from harness.mcp.tool import build_tools
from harness.tools.definition import ToolDefinition

logger = logging.getLogger("harness.mcp")

# How long a server gets to answer one command. The only configured number here.
COMMAND_TIMEOUT_SECONDS = 60.0
# Added to the caller's wait so the owner wins the race and posts the real
# message. Derived from the above, not a second setting.
REPLY_GRACE_SECONDS = 1.0
# Bounds teardown, so one wedged server cannot hang server shutdown.
CLOSE_TIMEOUT_SECONDS = 10.0
# A server whose `next_cursor` never clears must not spin forever.
MAX_TOOL_PAGES = 20

Status = Literal["connecting", "connected", "failed", "disconnected"]


@dataclass(frozen=True)
class ServerStatus:
    """One connection as the outside world sees it."""

    id: str
    status: Status
    error: str
    tool_names: tuple[str, ...]


@dataclass
class _Call:
    name: str
    arguments: dict
    deadline: float
    reply: asyncio.Future[CallToolResult]

    def describe(self) -> str:
        return repr(self.name)


@dataclass
class _Read:
    """`resources/read` — how an MCP App's HTML is fetched, over the same loop."""

    uri: str
    deadline: float
    reply: asyncio.Future[ReadResourceResult]

    def describe(self) -> str:
        return repr(self.uri)


_Command = _Call | _Read


@dataclass
class Connection:
    """One server, its owning task, and the queue feeding it."""

    id: str
    server: McpServer
    factory: ClientFactory
    status: Status = "connecting"
    error: str = ""
    tools: tuple[ToolDefinition[dict], ...] = ()
    # As the server published them — `_meta` included, which `tools` drops.
    # An app calls by these names, and its visibility rules live here.
    published: tuple[Tool, ...] = ()
    commands: asyncio.Queue[_Command] = field(default_factory=asyncio.Queue)
    task: asyncio.Task[None] | None = None

    def snapshot(self) -> ServerStatus:
        return ServerStatus(
            id=self.id,
            status=self.status,
            error=self.error,
            tool_names=tuple(tool.name for tool in self.tools),
        )

    def start(self) -> None:
        self.task = asyncio.create_task(self._serve(), name=f"mcp:{self.id}")
        # Without this a connection that died is silent: `create_task` holds the
        # exception until someone awaits, and nothing does.
        self.task.add_done_callback(self._report_exit)

    async def call(self, tool: str, arguments: dict) -> CallToolResult:
        loop = asyncio.get_running_loop()
        command = _Call(
            name=tool,
            arguments=arguments,
            deadline=loop.time() + COMMAND_TIMEOUT_SECONDS,
            reply=loop.create_future(),
        )
        return await self._submit(command, command.reply)

    async def read_resource(self, uri: str) -> ReadResourceResult:
        loop = asyncio.get_running_loop()
        command = _Read(
            uri=uri, deadline=loop.time() + COMMAND_TIMEOUT_SECONDS, reply=loop.create_future()
        )
        return await self._submit(command, command.reply)

    async def _submit[T](self, command: _Command, reply: asyncio.Future[T]) -> T:
        """Queue one command for the owner and wait for its reply.

        `reply` is `command.reply`, passed again so the answer is typed by the
        command that asked rather than by the union.
        """
        if self.task is None or self.task.done():
            raise McpNotConnectedError(f"{self.id} is not connected")
        self.commands.put_nowait(command)
        # Two waits, one number: the deadline above bounds how long the *server*
        # gets, this bounds how long the *loop* gets to be alive at all. The
        # grace lets the owner lose the race and still deliver the better error.
        try:
            return await asyncio.wait_for(reply, COMMAND_TIMEOUT_SECONDS + REPLY_GRACE_SECONDS)
        except TimeoutError as err:
            raise McpTimeoutError(f"{self.id} stopped answering") from err

    async def aclose(self) -> None:
        """Cancel the owner, which unwinds the session in the task that opened it."""
        if self.task is None:
            return
        self.task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(self.task), CLOSE_TIMEOUT_SECONDS)
        except TimeoutError:
            logger.error(
                "%s did not close within %.0fs; its process may survive",
                self.id,
                CLOSE_TIMEOUT_SECONDS,
            )
        except BaseException:  # noqa: BLE001
            # `suppress(CancelledError)` — the idiom elsewhere in this codebase —
            # is not enough here: unwinding an anyio task group can raise a
            # BaseExceptionGroup wrapping one, which that would not catch.
            pass
        finally:
            self.task = None
            self.status = "disconnected"
            self.error = ""
            self.tools = ()
            self.published = ()

    async def _serve(self) -> None:
        """Open, publish the tools, service commands, close — all in one task."""
        try:
            async with self.factory(self.server) as client:
                self.published = tuple(await _list_all(client))
                self.tools = tuple(build_tools(self.id, self.published, self.call))
                self.status = "connected"
                logger.info("MCP server %s connected with %d tools", self.id, len(self.tools))
                while True:
                    await self._run(client, await self.commands.get())
        except asyncio.CancelledError:
            self.status = "disconnected"
            raise
        except BaseException as err:  # noqa: BLE001 — the SDK raises ExceptionGroup
            self.status = "failed"
            self.error = describe(err)
            # The only report there is. This branch swallows the exception so the
            # task ends cleanly, and nothing awaits a connection — servers come
            # from config and are dialled once, with no caller to hand this to.
            logger.warning("MCP server %s failed: %s", self.id, self.error)
        finally:
            # A connection that died on its own stops offering tools without
            # anyone having to notice that it died.
            self.tools = ()
            self.published = ()
            self._fail_queued()

    async def _run(self, client: ClientLike, command: _Command) -> None:
        try:
            # Cancels *this* task at the await point; the SDK sends
            # notifications/cancelled, then `timeout_at` absorbs the
            # CancelledError and calls `Task.uncancel()`, so the session is still
            # open and the loop runs on. Verified against the real SDK before
            # this was written — a timed-out call leaves the next one working.
            async with asyncio.timeout_at(command.deadline):
                result: CallToolResult | ReadResourceResult
                if isinstance(command, _Call):
                    result = await client.call_tool(command.name, command.arguments)
                else:
                    result = await client.read_resource(command.uri)
        except TimeoutError:
            _fail(
                command.reply,
                McpTimeoutError(
                    f"{self.id} did not answer {command.describe()} within "
                    f"{COMMAND_TIMEOUT_SECONDS:.0f}s"
                ),
            )
        except asyncio.CancelledError:
            # Ours, not the deadline's. Let the owner die and take the session.
            _fail(command.reply, McpNotConnectedError(f"{self.id} is shutting down"))
            raise
        except BaseException as err:  # noqa: BLE001
            _fail(command.reply, McpConnectionError(describe(err)))
        else:
            _resolve(command.reply, result)

    def _fail_queued(self) -> None:
        """Answer everything still queued — nobody is left to run it."""
        while not self.commands.empty():
            _fail(
                self.commands.get_nowait().reply,
                McpNotConnectedError(f"{self.id} is not connected"),
            )

    def _report_exit(self, task: asyncio.Task[None]) -> None:
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            logger.error("MCP server %s stopped: %s", self.id, error, exc_info=error)


async def _list_all(client: ClientLike) -> list[Tool]:
    """Every tool the server offers, following its pagination."""
    tools: list[Tool] = []
    cursor: str | None = None
    for _ in range(MAX_TOOL_PAGES):
        page = await client.list_tools(cursor=cursor)
        tools.extend(page.tools)
        cursor = page.next_cursor
        if cursor is None:
            return tools
    logger.warning("stopped listing tools after %d pages", MAX_TOOL_PAGES)
    return tools


def _resolve(future: asyncio.Future, value: object) -> None:
    """Deliver, unless the caller already gave up.

    A caller whose own wait expired leaves a cancelled future behind; setting a
    result on it would raise and kill the owner task for someone else's timeout.
    """
    if not future.done():
        future.set_result(value)


def _fail(future: asyncio.Future, error: BaseException) -> None:
    if not future.done():
        future.set_exception(error)
    else:
        # Retrieved so the "never retrieved" warning does not fire for an
        # exception nobody is waiting for any more.
        with contextlib.suppress(BaseException):
            future.exception()
