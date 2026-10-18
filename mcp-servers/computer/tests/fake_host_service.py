"""A stand-in for a skill's Mac program: it writes how it started, then listens, hangs or exits."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from computer.host_services import HostService

Behaviour = Literal["listens", "hangs", "exits"]
EXIT_CODE = 3
PROGRAM_NAME = "fake-host-service"
STARTED_FILE = "started.json"
MOST_WAITS = 1000
ARGUMENTS = ("--port", "{port}", "--token-file", "{token_file}", "--files={files}")

SCRIPT = f"""
import json, os, socket, stat, sys, time
from pathlib import Path
args = sys.argv[1:]
token_file = Path(args[args.index("--token-file") + 1])
said = {{
    "pid": os.getpid(),
    "args": args,
    "token": token_file.read_text(),
    "token_mode": stat.S_IMODE(token_file.stat().st_mode),
    "folder_mode": stat.S_IMODE(token_file.parent.stat().st_mode),
}}
writing = Path(sys.argv[0]).with_name("{STARTED_FILE}.part")
writing.write_text(json.dumps(said))
writing.rename(writing.with_name("{STARTED_FILE}"))
if BEHAVIOUR == "exits":
    sys.exit({EXIT_CODE})
if BEHAVIOUR == "listens":
    server = socket.create_server(("127.0.0.1", int(args[args.index("--port") + 1])))
    while True:
        server.accept()[0].close()
while True:
    time.sleep(60)
"""


@dataclass(frozen=True)
class Started:
    """What the stand-in saw when it started: its pid, its arguments and its token file."""

    pid: int
    args: tuple[str, ...]
    token: str
    token_mode: int
    folder_mode: int

    @property
    def token_file(self) -> Path:
        return Path(self.args[self.args.index("--token-file") + 1])


def fake_host_service(folder: Path, behaviour: Behaviour) -> Path:
    """An executable stand-in in `folder`, its own, that behaves as asked once it has started."""
    folder.mkdir(parents=True, exist_ok=True)
    program = folder / PROGRAM_NAME
    program.write_text(f"#!{sys.executable}\nBEHAVIOUR = {behaviour!r}\n{SCRIPT}")
    program.chmod(0o755)
    return program


def declared(program: Path, env_prefix: str = "FAKE") -> HostService:
    """`program` as a skill named `fake` declares it, with ARGUMENTS for its words."""
    return HostService(skill="fake", env_prefix=env_prefix, program=program, arguments=ARGUMENTS)


def write_skill(skills_dir: Path, name: str, frontmatter: str) -> Path:
    """A skill folder `name` in `skills_dir` whose SKILL.md opens with `frontmatter`."""
    folder = skills_dir / name
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n\n# {name}\n", encoding="utf-8")
    return folder


def declaring(command_line: str, env_prefix: str = "FAKE") -> str:
    """Frontmatter whose metadata declares `command_line` under `env_prefix`."""
    metadata = {"host-service": command_line, "host-service-env": env_prefix}
    return f"name: fake\ndescription: Declares a program.\nmetadata: {json.dumps(metadata)}"


def started(program: Path) -> Started:
    said = json.loads(program.with_name(STARTED_FILE).read_text())
    return Started(**{**said, "args": tuple(said["args"])})


async def until_started(program: Path) -> Started:
    for _ in range(MOST_WAITS):
        if program.with_name(STARTED_FILE).exists():
            return started(program)
        await asyncio.sleep(0.01)
    raise AssertionError(f"{program} never started")


def is_gone(pid: int) -> bool:
    """Whether no process, not even an unreaped one, has this pid."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False
