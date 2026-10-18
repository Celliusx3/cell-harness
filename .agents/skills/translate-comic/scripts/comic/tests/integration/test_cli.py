"""The scripts end to end with the real PhotoCraft: pages, then write, then cleanup."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

RUN = Path(__file__).parents[3] / "run.py"
PAGE = (600, 800)
LETTER_ROWS = (420, 452)
LETTERS_FROM, LETTERS_TO = 220, 380
TEXT_BOX = (215, 415, 385, 475)
MOST_VIEW_BYTES = 5 * 1024 * 1024

pytestmark = pytest.mark.skipif(
    shutil.which("photocraft-cli") is None, reason="needs PhotoCraft on PATH"
)


def bubble_page() -> Image.Image:
    """A white page holding one outlined bubble with two lines of black letters in it."""
    page = Image.new("RGB", PAGE, "white")
    pen = ImageDraw.Draw(page)
    pen.ellipse((100, 300, 500, 600), outline="black", width=3)
    for top in LETTER_ROWS:
        for x in range(LETTERS_FROM, LETTERS_TO, 16):
            pen.rectangle((x, top, x + 9, top + 17), fill="black")
    return page


def box_2d() -> list[int]:
    x0, y0, x1, y1 = TEXT_BOX
    width, height = PAGE
    return [round(y0 / height * 1000), round(x0 / width * 1000)] + [
        round(y1 / height * 1000),
        round(x1 / width * 1000),
    ]


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture
def photocraft(tmp_path: Path) -> Iterator[dict[str, str]]:
    files, token = tmp_path / "files", tmp_path / "token"
    files.mkdir()
    token.write_text(secrets.token_hex(32))
    token.chmod(0o600)
    port = free_port()
    serve = subprocess.Popen(
        ["photocraft-cli", "serve", "--port", str(port), "--control-token-file", str(token)]
        + ["--automation-read-root", str(files), "--automation-write-root", str(files)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(100):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=1).close()
                break
            except OSError:
                time.sleep(0.1)
        yield {
            "PHOTOCRAFT_ADDR": f"127.0.0.1:{port}",
            "PHOTOCRAFT_TOKEN": token.read_text(),
            "HOME": str(tmp_path),
        }
    finally:
        serve.terminate()
        serve.wait(timeout=10)


def run(args: list[str], env: dict[str, str], stdin: str = "") -> dict:
    done = subprocess.run(
        [sys.executable, str(RUN), *args],
        input=stdin,
        capture_output=True,
        text=True,
        env={**os.environ, **env},
        timeout=180,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    return json.loads(done.stdout)


def test_pages_then_write_then_cleanup_leave_only_the_archive(
    tmp_path: Path, photocraft: dict[str, str]
) -> None:
    chat = tmp_path / "files" / "chat" / "token"
    chat.mkdir(parents=True)
    archive = chat / "comic.cbz"
    bubble_page().save(chat / "page.png")
    with zipfile.ZipFile(archive, "w") as packed:
        packed.write(chat / "page.png", "page.png")
    (chat / "page.png").unlink()

    listed = run(["pages", str(archive)], photocraft)
    [entry] = listed["pages"]
    assert entry["parts"] == 1
    assert all(
        Path(view).is_file() and Path(view).stat().st_size <= MOST_VIEW_BYTES
        for view in entry["views"]
    )

    items = [{"part": 1, "box_2d": box_2d(), "original": "ABCDEFGHIJ", "english": "Hi!"}]
    written = run(["write", listed["work"], entry["page"]], photocraft, json.dumps(items))
    assert (written["cut_off"], written["spills"], written["left_over"]) == ([], [], [])
    assert written["attempt"] == 1
    assert Image.open(written["english"]).size == PAGE
    assert all(Path(view).is_file() for view in written["views"])

    again = run(["write", listed["work"], entry["page"]], photocraft, json.dumps(items))
    assert again["attempt"] == 2

    keep = Path(written["english"]).parent / "comic-english.cbz"
    with zipfile.ZipFile(keep, "w") as packed:
        packed.write(written["english"], "001.png")
    cleaned = run(["cleanup", listed["work"], str(keep)], {})
    assert cleaned["kept"] == str(keep)
    assert [path for path in Path(listed["work"]).rglob("*") if path.is_file()] == [keep]


def test_a_write_without_photocraft_settings_says_which_is_missing(tmp_path: Path) -> None:
    done = subprocess.run(
        [sys.executable, str(RUN), "write", str(tmp_path), "001.png"],
        input="[]",
        capture_output=True,
        text=True,
        env={key: value for key, value in os.environ.items() if not key.startswith("PHOTOCRAFT")},
        timeout=60,
    )

    assert done.returncode != 0
    assert "PHOTOCRAFT_ADDR" in done.stdout + done.stderr
