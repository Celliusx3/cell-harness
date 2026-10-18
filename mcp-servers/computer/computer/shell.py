"""A bot's commands, each run detached in the computer as a job that later calls wait on."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping, Sequence
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from computer.clock import Clock
from computer.docker import COMMAND_TIMEOUT_SECONDS, CommandResult, Docker
from computer.jobs import LOOK_SCRIPT, RUNNER_NAME, RUNNER_SCRIPT, WRITE_SCRIPT
from computer.machine import JOBS_ROOT
from computer.models import CommandRun

logger = logging.getLogger("computer")

WAIT_SECONDS = 15.0
POLL_SECONDS = 0.5
MOST_OUTPUT = 10_000
MOST_OUTPUT_BYTES = MOST_OUTPUT * 4
JOB_ID_LENGTH = 16
ENDED_UNREPORTED = (
    "The command ended without reporting an exit code, as it does when the computer stops "
    "while it runs. Call shell again to run it again."
)

ExecMode = Literal["-i", "-d"]


class ShellError(RuntimeError):
    """A command could not be started or looked at. The message says why, for the model."""


class Job(BaseModel):
    """One command as a bot asked for it: the same three fields are the same job."""

    model_config = ConfigDict(frozen=True)

    command: str
    stdin: str
    cwd: str

    @property
    def folder(self) -> str:
        digest = hashlib.sha256(self.model_dump_json().encode()).hexdigest()
        return f"{JOBS_ROOT}/{digest[:JOB_ID_LENGTH]}"


class NoJob(BaseModel):
    model_config = ConfigDict(frozen=True)

    state: Literal["none"]


class RunningJob(BaseModel):
    model_config = ConfigDict(frozen=True)

    state: Literal["running"]
    seconds: float
    output: str


class FinishedJob(BaseModel):
    model_config = ConfigDict(frozen=True)

    state: Literal["done"]
    seconds: float
    exit_code: int
    output: str


SeenJob = NoJob | RunningJob | FinishedJob
SEEN_JOB: TypeAdapter[SeenJob] = TypeAdapter(Annotated[SeenJob, Field(discriminator="state")])


def last_output(output: str) -> str:
    """At most the last MOST_OUTPUT characters."""
    return output[-MOST_OUTPUT:]


def command_run(seen: RunningJob | FinishedJob) -> CommandRun:
    seconds, output = round(seen.seconds, 1), last_output(seen.output)
    if isinstance(seen, RunningJob):
        return CommandRun(status="running", exit_code=None, seconds=seconds, output=output)
    return CommandRun(status="done", exit_code=seen.exit_code, seconds=seconds, output=output)


def stdout_of(completed: CommandResult, action: str) -> str:
    """`stdout`, or a `ShellError` in the computer's own words."""
    if completed.returncode != 0:
        said = completed.stderr.strip() or f"exit {completed.returncode}"
        raise ShellError(f"{action} failed: {said}")
    return completed.stdout


class Shell:
    """The computer's commands: started once, then waited on for up to WAIT_SECONDS a call."""

    def __init__(
        self, *, docker: Docker, container: str, clock: Clock, variables: Mapping[str, str]
    ) -> None:
        self._docker = docker
        self._container = container
        self._clock = clock
        self._variables = tuple(
            arg for name, value in variables.items() for arg in ("-e", f"{name}={value}")
        )

    async def run(self, job: Job) -> CommandRun:
        """The job's result, once; or, while it still runs after WAIT_SECONDS, how far it got."""
        began = self._clock.now()
        seen = await self._look(job)
        if isinstance(seen, NoJob):
            await self._start(job)
            seen = await self._look_after_a_poll(job)
        while isinstance(seen, RunningJob) and self._clock.now() - began < WAIT_SECONDS:
            seen = await self._look_after_a_poll(job)
        if isinstance(seen, NoJob):
            raise ShellError(ENDED_UNREPORTED)
        return command_run(seen)

    def _exec_arguments(self, mode: ExecMode) -> list[str]:
        """`docker exec` up to the program, with the commands' variables, for every call."""
        return ["exec", mode, *self._variables, self._container]

    async def _start(self, job: Job) -> None:
        written = job.model_dump_json()
        await self._run_python(WRITE_SCRIPT, [job.folder], written, "Starting the command")
        launch = [
            *self._exec_arguments("-d"),
            "sh",
            "-c",
            RUNNER_SCRIPT,
            RUNNER_NAME,
            job.folder,
            job.cwd,
        ]
        stdout_of(
            await self._docker.run(launch, stdin="", timeout_seconds=COMMAND_TIMEOUT_SECONDS),
            "Starting the command",
        )

    async def _look_after_a_poll(self, job: Job) -> SeenJob:
        await self._clock.sleep(POLL_SECONDS)
        return await self._look(job)

    async def _look(self, job: Job) -> SeenJob:
        answer = await self._run_python(
            LOOK_SCRIPT, [job.folder, str(MOST_OUTPUT_BYTES)], "", "Looking at the command"
        )
        try:
            return SEEN_JOB.validate_json(answer)
        except ValidationError as err:
            logger.error("the computer described the job %s as %r: %s", job.folder, answer, err)
            raise ShellError(
                "The computer described the command in a form this server cannot read. "
                "This is a fault in the computer, not in the call: tell the person."
            ) from err

    async def _run_python(self, script: str, args: Sequence[str], stdin: str, action: str) -> str:
        completed = await self._docker.run(
            [*self._exec_arguments("-i"), "python3", "-c", script, *args],
            stdin=stdin,
            timeout_seconds=COMMAND_TIMEOUT_SECONDS,
        )
        return stdout_of(completed, action)
