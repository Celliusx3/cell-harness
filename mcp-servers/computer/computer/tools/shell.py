"""shell: a bot's command run in the computer, answered done or still running."""

from __future__ import annotations

from typing import Annotated

from mcp.server import MCPServer
from pydantic import Field

from computer.machine import HOME
from computer.models import CommandRun
from computer.shell import Job
from computer.tools import Computer, computer_for_one_call
from computer.tools.descriptions import (
    COMMAND_DESCRIPTION,
    CWD_DESCRIPTION,
    SHELL_DESCRIPTION,
    STDIN_DESCRIPTION,
)

Command = Annotated[str, Field(min_length=1, description=COMMAND_DESCRIPTION)]
Stdin = Annotated[str, Field(description=STDIN_DESCRIPTION)]
AbsoluteFolder = Annotated[str, Field(pattern=r"^/[^\x00]*$")]
Cwd = Annotated[AbsoluteFolder | None, Field(description=CWD_DESCRIPTION)]


def register(server: MCPServer, computer: Computer) -> None:
    """shell, offered to the model."""

    @server.tool(name="shell", description=SHELL_DESCRIPTION)
    async def shell(command: Command, stdin: Stdin = "", cwd: Cwd = None) -> CommandRun:
        job = Job(command=command, stdin=stdin, cwd=HOME if cwd is None else cwd)
        async with computer_for_one_call(computer.machine):
            return await computer.shell.run(job)
