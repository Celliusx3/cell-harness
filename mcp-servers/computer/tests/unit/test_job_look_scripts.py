"""The look and the running-jobs list the computer runs, run here against real job folders."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from computer.services.jobs import LOOK_SCRIPT, RUNNING_JOBS_SCRIPT

MOST_BYTES = 5

FAKE_PROC_PRELUDE = "\n".join(
    [
        "import builtins, os",
        "fake, real_listdir, real_open = os.environ['FAKE_PROC'], os.listdir, builtins.open",
        "def moved(path):",
        "    return fake + path[len('/proc'):] if str(path).startswith('/proc') else path",
        "os.listdir = lambda path='.': real_listdir(moved(path))",
        "builtins.open = lambda path, *args, **kwargs: real_open(moved(path), *args, **kwargs)",
    ]
)


@pytest.fixture
def proc(tmp_path: Path) -> Path:
    """A stand-in for Linux's /proc, which macOS does not have; it lists no process yet."""
    fake = tmp_path / "proc"
    fake.mkdir()
    return fake


def run_script(script: str, args: list[str], proc: Path) -> str:
    completed = subprocess.run(
        [sys.executable, "-c", f"{FAKE_PROC_PRELUDE}\n{script}", *args],
        capture_output=True,
        text=True,
        env={**os.environ, "FAKE_PROC": str(proc)},
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout


def job_folder(root: Path, name: str, output: str) -> Path:
    folder = root / name
    folder.mkdir(parents=True)
    (folder / "started").write_text(repr(1.0))
    (folder / "out").write_text(output)
    return folder


def running_process(proc: Path, pid: str, folder: Path) -> None:
    (proc / pid).mkdir()
    (proc / pid / "cmdline").write_bytes(b"sh\0-c\0runner\0shell-job\0" + bytes(folder) + b"\0")


def look(folder: Path, proc: Path) -> dict[str, object]:
    return json.loads(run_script(LOOK_SCRIPT, [str(folder), str(MOST_BYTES)], proc))


def test_a_look_at_no_job_says_none(tmp_path: Path, proc: Path) -> None:
    assert look(tmp_path / "jobs" / "missing", proc) == {"state": "none"}


def test_a_look_at_a_job_whose_process_is_gone_and_unfinished_says_none_and_clears_it(
    tmp_path: Path, proc: Path
) -> None:
    folder = job_folder(tmp_path / "jobs", "abandoned", "half")

    assert look(folder, proc) == {"state": "none"}
    assert not folder.exists()


def test_a_look_at_a_running_job_gives_the_tail_of_its_output(tmp_path: Path, proc: Path) -> None:
    folder = job_folder(tmp_path / "jobs", "busy", "0123456789")
    running_process(proc, "4242", folder)

    seen = look(folder, proc)

    assert seen["state"] == "running"
    assert seen["output"] == "56789"
    assert folder.exists()


def test_a_look_at_a_finished_job_gives_its_exit_code_and_clears_it(
    tmp_path: Path, proc: Path
) -> None:
    folder = job_folder(tmp_path / "jobs", "done", "all of it")
    (folder / "exit").write_text("3\n")

    seen = look(folder, proc)

    assert seen["state"] == "done"
    assert seen["exit_code"] == 3
    assert seen["output"] == "of it"
    assert not folder.exists()


def test_no_jobs_folder_lists_no_running_job(tmp_path: Path, proc: Path) -> None:
    assert run_script(RUNNING_JOBS_SCRIPT, [str(tmp_path / "jobs")], proc) == ""


def test_only_a_job_whose_process_runs_and_has_not_finished_is_listed(
    tmp_path: Path, proc: Path
) -> None:
    root = tmp_path / "jobs"
    busy = job_folder(root, "busy", "")
    finished = job_folder(root, "finished", "")
    (finished / "exit").write_text("0\n")
    job_folder(root, "abandoned", "")
    running_process(proc, "41", busy)
    running_process(proc, "42", finished)

    assert run_script(RUNNING_JOBS_SCRIPT, [str(root)], proc) == "busy\n"
