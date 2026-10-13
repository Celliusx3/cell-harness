"""The Python the computer runs for files, run here against a real folder."""

from __future__ import annotations

import base64
import json
import stat
import subprocess
import sys
from pathlib import Path

from computer.files import LIST_SCRIPT, READ_SCRIPT, TOO_LARGE_EXIT_CODE, WRITE_SCRIPT


def run(script: str, *args: str, stdin: bytes = b"") -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-c", script, *args], input=stdin, capture_output=True, check=False
    )


def test_the_list_skips_symlinks_and_sorts_by_path(tmp_path: Path) -> None:
    (tmp_path / "b.txt").write_bytes(b"hi")
    (tmp_path / "a").mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "b.txt")
    (tmp_path / "loop").symlink_to(tmp_path / "a")

    listed = run(LIST_SCRIPT, str(tmp_path), str(tmp_path), "notes")

    assert listed.returncode == 0, listed.stderr
    entries = json.loads(listed.stdout)
    assert [(entry["path"], entry["kind"]) for entry in entries] == [
        ("notes/a", "dir"),
        ("notes/b.txt", "file"),
    ]
    assert entries[1] == {"path": "notes/b.txt", "kind": "file", "size": 2}


def test_the_home_folder_lists_bare_names(tmp_path: Path) -> None:
    (tmp_path / "x").write_text("x")

    listed = run(LIST_SCRIPT, str(tmp_path), str(tmp_path), "")

    assert [entry["path"] for entry in json.loads(listed.stdout)] == ["x"]


def test_a_missing_folder_fails_with_the_reason(tmp_path: Path) -> None:
    listed = run(LIST_SCRIPT, str(tmp_path), str(tmp_path / "nope"), "nope")

    assert listed.returncode == 1
    assert b"No such file or directory" in listed.stderr


def test_a_read_within_its_limit_is_base64_and_past_it_exits_42(tmp_path: Path) -> None:
    (tmp_path / "f").write_bytes(b"abcd")

    within = run(READ_SCRIPT, str(tmp_path), str(tmp_path / "f"), "4")
    past = run(READ_SCRIPT, str(tmp_path), str(tmp_path / "f"), "3")

    assert base64.b64decode(within.stdout, validate=True) == b"abcd"
    assert (past.returncode, past.stdout) == (TOO_LARGE_EXIT_CODE, b"")


def test_a_read_of_a_missing_file_fails_with_the_reason(tmp_path: Path) -> None:
    read = run(READ_SCRIPT, str(tmp_path), str(tmp_path / "nope"), "4")

    assert read.returncode == 1
    assert b"No such file or directory" in read.stderr


def test_the_write_makes_its_folders_and_a_file_only_its_owner_reads(tmp_path: Path) -> None:
    target = tmp_path / "notes" / "deep" / "hello.txt"

    wrote = run(WRITE_SCRIPT, str(tmp_path), str(target), stdin=base64.b64encode(b"hi there"))

    assert wrote.returncode == 0, wrote.stderr
    assert target.read_bytes() == b"hi there"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_a_write_over_a_folder_fails_with_the_reason(tmp_path: Path) -> None:
    wrote = run(WRITE_SCRIPT, str(tmp_path), str(tmp_path), stdin=b"aGk=")

    assert wrote.returncode == 1
    assert b"Is a directory" in wrote.stderr


def outside_and_home(tmp_path: Path) -> tuple[Path, Path]:
    outside, home = tmp_path / "outside", tmp_path / "home"
    outside.mkdir()
    home.mkdir()
    (outside / "secret").write_bytes(b"not yours")
    return outside, home


def test_a_read_through_a_link_that_leaves_home_is_refused(tmp_path: Path) -> None:
    outside, home = outside_and_home(tmp_path)
    (home / "link").symlink_to(outside / "secret")

    read = run(READ_SCRIPT, str(home), str(home / "link"), "100")

    assert read.returncode != 0
    assert b"outside the home folder" in read.stderr
    assert read.stdout == b""


def test_a_list_of_a_linked_folder_that_leaves_home_is_refused(tmp_path: Path) -> None:
    outside, home = outside_and_home(tmp_path)
    (home / "away").symlink_to(outside)

    listed = run(LIST_SCRIPT, str(home), str(home / "away"), "away")

    assert listed.returncode != 0
    assert b"outside the home folder" in listed.stderr


def test_a_write_through_a_linked_folder_that_leaves_home_is_refused(tmp_path: Path) -> None:
    outside, home = outside_and_home(tmp_path)
    (home / "away").symlink_to(outside)

    written = run(
        WRITE_SCRIPT, str(home), str(home / "away" / "planted"), stdin=base64.b64encode(b"x")
    )

    assert written.returncode != 0
    assert b"outside the home folder" in written.stderr
    assert not (outside / "planted").exists()


def test_a_link_that_stays_in_home_still_reads(tmp_path: Path) -> None:
    _, home = outside_and_home(tmp_path)
    (home / "real.txt").write_bytes(b"mine")
    (home / "alias").symlink_to(home / "real.txt")

    read = run(READ_SCRIPT, str(home), str(home / "alias"), "100")

    assert read.returncode == 0, read.stderr
    assert base64.b64decode(read.stdout) == b"mine"
