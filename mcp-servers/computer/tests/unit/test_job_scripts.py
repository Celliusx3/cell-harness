"""The writer and the runner the computer runs for a job, run here against a real folder."""

from __future__ import annotations

import json
import stat
import subprocess
import sys
from pathlib import Path

from computer.jobs import RUNNER_NAME, RUNNER_SCRIPT, WRITE_SCRIPT

QUOTED = 'it\'s "here" $HOME\n'


def write(folder: Path, command: str, stdin: str) -> subprocess.CompletedProcess[bytes]:
    job = json.dumps({"command": command, "stdin": stdin, "cwd": "/"}).encode()
    return subprocess.run(
        [sys.executable, "-c", WRITE_SCRIPT, str(folder)], input=job, capture_output=True
    )


def run(folder: Path, cwd: Path) -> None:
    subprocess.run(["sh", "-c", RUNNER_SCRIPT, RUNNER_NAME, str(folder), str(cwd)], check=True)


def test_the_write_keeps_the_command_and_its_input_verbatim_in_a_private_folder(
    tmp_path: Path,
) -> None:
    folder = tmp_path / ".shell" / "0123456789abcdef"

    wrote = write(folder, "cat | tr a-z A-Z", QUOTED)

    assert wrote.returncode == 0, wrote.stderr
    assert (folder / "cmd").read_text() == "cat | tr a-z A-Z"
    assert (folder / "in").read_text() == QUOTED
    assert float((folder / "started").read_text()) > 0
    assert stat.S_IMODE(folder.stat().st_mode) == 0o700


def test_the_write_refuses_a_job_folder_that_already_exists(tmp_path: Path) -> None:
    wrote = write(tmp_path, "ls", "")

    assert wrote.returncode != 0
    assert b"FileExistsError" in wrote.stderr


def test_the_runner_runs_in_its_folder_on_its_input_and_writes_the_exit_code(
    tmp_path: Path,
) -> None:
    folder, cwd = tmp_path / "job", tmp_path / "work"
    cwd.mkdir()
    write(folder, "pwd; cat; echo oops >&2; exit 3", QUOTED)

    run(folder, cwd)

    assert (folder / "out").read_text() == f"{cwd}\n{QUOTED}oops\n"
    assert (folder / "exit").read_text() == "3\n"
    assert not (folder / "exit.tmp").exists()


def test_a_folder_that_is_missing_fails_the_job_with_the_reason_as_its_output(
    tmp_path: Path,
) -> None:
    folder = tmp_path / "job"
    write(folder, "echo never", "")

    run(folder, tmp_path / "nope")

    assert str(tmp_path / "nope") in (folder / "out").read_text()
    assert "never" not in (folder / "out").read_text()
    assert (folder / "exit").read_text().strip() != "0"
