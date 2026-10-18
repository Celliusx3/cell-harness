"""FakeDocker whose computer also plays job folders: written, launched, done after N looks."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, replace

from computer.docker import CommandResult
from computer.jobs import LOOK_SCRIPT, RUNNER_SCRIPT, RUNNING_JOBS_SCRIPT, WRITE_SCRIPT
from tests.conftest import FakeDocker

SECONDS_PER_LOOK = 0.5
NOTHING = CommandResult(0, "", "")


@dataclass(frozen=True)
class FakeJob:
    """A job folder as the computer holds it; a runner is alive once `cwd` is set."""

    command: str
    stdin: str
    cwd: str | None = None
    looks: int = 0


class JobDocker(FakeDocker):
    """Plays WRITE_SCRIPT, the runner, LOOK_SCRIPT and RUNNING_JOBS_SCRIPT against `jobs`."""

    def __init__(self, *, status: str = "running", looks_to_finish: int = 1) -> None:
        super().__init__(status=status)
        self.looks_to_finish = looks_to_finish
        self.output = "hi\n"
        self.exit_code = 0
        self.jobs: dict[str, FakeJob] = {}
        self.runner_dies = False
        self.look_answer: str | None = None

    def runner_calls(self) -> list[list[str]]:
        return [call for call in self.calls if RUNNER_SCRIPT in call]

    def look_calls(self) -> list[list[str]]:
        return [call for call in self.calls if LOOK_SCRIPT in call]

    def _answer(self, args: Sequence[str]) -> CommandResult:
        if WRITE_SCRIPT in args:
            job = json.loads(self.stdins[-1])
            self.jobs[args[-1]] = FakeJob(command=job["command"], stdin=job["stdin"])
            return NOTHING
        if RUNNER_SCRIPT in args:
            folder, cwd = args[-2], args[-1]
            if not self.runner_dies:
                self.jobs[folder] = replace(self.jobs[folder], cwd=cwd)
            return NOTHING
        if LOOK_SCRIPT in args:
            return CommandResult(0, self.look_answer or self._look(args[-2]), "")
        if RUNNING_JOBS_SCRIPT in args:
            names = [path.rsplit("/", 1)[1] for path, job in self.jobs.items() if job.cwd]
            return CommandResult(0, "".join(f"{name}\n" for name in names), "")
        return super()._answer(args)

    def _look(self, folder: str) -> str:
        job = self.jobs.pop(folder, None)
        if job is None or job.cwd is None:
            return json.dumps({"state": "none"})
        looked = replace(job, looks=job.looks + 1)
        seconds = looked.looks * SECONDS_PER_LOOK
        if looked.looks >= self.looks_to_finish:
            done = {"exit_code": self.exit_code, "seconds": seconds, "output": self.output}
            return json.dumps({"state": "done", **done})
        self.jobs[folder] = looked
        return json.dumps({"state": "running", "seconds": seconds, "output": self.output})
