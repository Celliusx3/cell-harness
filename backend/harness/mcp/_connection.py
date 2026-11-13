"""One connection: a task that owns the session, and a queue feeding it."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass, field

from mcp.types import CallToolResult, ReadResourceResult
from mcp.types import Tool as McpTool

from harness.mcp.client import McpClient, McpClientFactory
from harness.mcp.domain.commands import Command, ResourceReadCommand, ToolCallCommand
from harness.mcp.domain.errors import McpConnectionError, McpNotConnectedError, McpTimeoutError
from harness.mcp.domain.server import McpServer
from harness.mcp.domain.status import ServerStatus, Status
from harness.mcp.tool import build_tools
from harness.tools import Tool

logger = logging.getLogger("harness.mcp")

COMMAND_TIMEOUT_SECONDS = 60.0
REPLY_GRACE_SECONDS = 1.0
CLOSE_TIMEOUT_SECONDS = 10.0
MAX_TOOL_PAGES = 20


@dataclass
class Connection:
    """One server, its owning task, and the queue feeding it."""

    id: str
    server: McpServer
    factory: McpClientFactory
    status: Status = "connecting"
    error: str = ""
    tools: tuple[Tool[dict], ...] = ()
    published: tuple[McpTool, ...] = ()
    instructions: str = ""
    commands: asyncio.Queue[Command] = field(default_factory=asyncio.Queue)
    settled: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task[None] | None = None

    def snapshot(self) -> ServerStatus:
        return ServerStatus(
            id=self.id,
            status=self.status,
            error=self.error,
            tool_names=tuple(tool.name for tool in self.tools),
        )

    def wait_for(self, missing: tuple[str, ...]) -> None:
        """Stay unstarted, naming the keys it waits for; settled, so startup does not wait."""
        self.status = "waiting"
        self.error = "needs " + ", ".join(missing)
        self.settled.set()

    def start(self) -> None:
        self.task = asyncio.create_task(self._serve(), name=f"mcp:{self.id}")
        self.task.add_done_callback(self._report_exit)

    async def call(self, server_tool_name: str, arguments: dict) -> CallToolResult:
        loop = asyncio.get_running_loop()
        command = ToolCallCommand(
            server_tool_name=server_tool_name,
            arguments=arguments,
            deadline=loop.time() + COMMAND_TIMEOUT_SECONDS,
            reply=loop.create_future(),
        )
        return await self._submit(command, command.reply)

    async def read_resource(self, uri: str) -> ReadResourceResult:
        loop = asyncio.get_running_loop()
        command = ResourceReadCommand(
            uri=uri, deadline=loop.time() + COMMAND_TIMEOUT_SECONDS, reply=loop.create_future()
        )
        return await self._submit(command, command.reply)

    async def _submit[T](self, command: Command, reply: asyncio.Future[T]) -> T:
        """Queue one command for the owner and wait for its reply."""
        if self.task is None or self.task.done():
            raise McpNotConnectedError(f"{self.id} is not connected")
        self.commands.put_nowait(command)
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
        except BaseException:
            # Unwinding an anyio task group can raise a BaseExceptionGroup wrapping CancelledError.
            pass
        finally:
            self.task = None
            self.status = "disconnected"
            self.error = ""
            self.tools = ()
            self.published = ()
            self.instructions = ""

    async def _serve(self) -> None:
        """Open, publish the tools, service commands, close — all in one task."""
        try:
            async with self.factory(self.server) as client:
                self.published = tuple(await _list_all(client))
                self.tools = tuple(build_tools(self.id, self.published, self.call))
                self.instructions = client.instructions or ""
                self.status = "connected"
                self.settled.set()
                logger.info("MCP server %s connected with %d tools", self.id, len(self.tools))
                while True:
                    await self._run(client, await self.commands.get())
        except asyncio.CancelledError:
            self.status = "disconnected"
            raise
        except BaseException as err:  # anyio raises BaseExceptionGroup, which Exception misses
            self.status = "failed"
            self.error = describe_error(err)
            logger.warning("MCP server %s failed: %s", self.id, self.error)
        finally:
            self.settled.set()
            self.tools = ()
            self.published = ()
            self.instructions = ""
            self._fail_queued()

    async def _run(self, client: McpClient, command: Command) -> None:
        try:
            async with asyncio.timeout_at(command.deadline):
                result: CallToolResult | ReadResourceResult
                if isinstance(command, ToolCallCommand):
                    result = await client.call_tool(command.server_tool_name, command.arguments)
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
            _fail(command.reply, McpNotConnectedError(f"{self.id} is shutting down"))
            raise
        except BaseException as err:  # anyio raises BaseExceptionGroup, which Exception misses
            _fail(command.reply, McpConnectionError(describe_error(err)))
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


async def _list_all(client: McpClient) -> list[McpTool]:
    """Every tool the server offers, following its pagination."""
    tools: list[McpTool] = []
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
    """Deliver, unless the caller already gave up."""
    if not future.done():
        future.set_result(value)


def _fail(future: asyncio.Future, error: BaseException) -> None:
    if not future.done():
        future.set_exception(error)
    else:
        # asyncio warns "exception was never retrieved" unless someone reads it.
        with contextlib.suppress(BaseException):
            future.exception()


def describe_error(error: BaseException) -> str:
    """A one-line cause an operator can act on."""
    while isinstance(error, BaseExceptionGroup) and len(error.exceptions) == 1:
        error = error.exceptions[0]
    message = str(error).strip()
    return message or type(error).__name__
