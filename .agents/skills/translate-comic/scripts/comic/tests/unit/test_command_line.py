"""Each command prints one JSON object and exits 0, or one `error:` line and exits 1."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from comic.cli import main
from comic.steps.write import PhotoCraftAccess
from comic.tests.unit.one_bubble import BOX_2D

ITEM = {"part": 1, "box_2d": list(BOX_2D), "original": "ABCDEFGHIJ", "english": "It's me!"}


def run(argv: list[str], env: dict[str, str], stdin: str = "") -> tuple[int, list[str]]:
    out = io.StringIO()
    code = main(argv, env, io.StringIO(stdin), out)
    return code, out.getvalue().splitlines()


def env_of(access: PhotoCraftAccess) -> dict[str, str]:
    return {
        "PHOTOCRAFT_ADDR": access.addr,
        "PHOTOCRAFT_TOKEN": access.token,
        "HOME": str(access.lock.parent),
    }


def test_pages_then_write_twice_print_the_work_and_the_attempt(
    bubble_comic: Path, access: PhotoCraftAccess
) -> None:
    code, [line] = run(["pages", str(bubble_comic)], {})
    listed = json.loads(line)
    [page] = listed["pages"]
    assert (code, page["page"], page["parts"]) == (0, "001.png", 1)

    written = [
        run(["write", listed["work"], "001.png"], env_of(access), json.dumps([ITEM]))
        for _ in range(2)
    ]

    assert [(code, json.loads(line)["attempt"]) for code, [line] in written] == [(0, 1), (0, 2)]


def test_cleanup_prints_what_it_kept(bubble_comic: Path) -> None:
    _, [line] = run(["pages", str(bubble_comic)], {})
    archive = Path(json.loads(line)["work"]) / "ch1-english.cbz"
    archive.write_bytes(b"archive")

    code, [kept] = run(["cleanup", str(archive.parent), str(archive)], {})

    assert (code, json.loads(kept)["kept"]) == (0, str(archive))


def test_a_command_it_does_not_have_is_refused_with_the_usage() -> None:
    assert run(["view", "/tmp/ch1-english"], {}) == (
        1,
        [
            "error: usage: run.py pages <file> | run.py write <work> <page> "
            "(the items as JSON on stdin) | run.py cleanup <work> <keep>"
        ],
    )


def test_a_write_names_each_photocraft_setting_it_lacks(tmp_path: Path) -> None:
    code, [line] = run(["write", str(tmp_path), "001.png"], {"PHOTOCRAFT_ADDR": "127.0.0.1:9"})

    assert code == 1
    assert line.startswith("error: PHOTOCRAFT_TOKEN not set;")
    assert "install photocraft-cli on the Mac" in line


def test_items_that_are_not_valid_are_refused_naming_the_field(
    bubble_comic: Path, access: PhotoCraftAccess
) -> None:
    _, [line] = run(["pages", str(bubble_comic)], {})
    five = {**ITEM, "box_2d": [1, 2, 3, 4, 5]}

    code, [refused] = run(
        ["write", json.loads(line)["work"], "001.png"], env_of(access), json.dumps([five])
    )

    assert code == 1
    assert refused.startswith("error: the items on stdin are not valid: 0.box_2d: Tuple should")


def test_no_items_keep_the_page_as_it_is(bubble_comic: Path, access: PhotoCraftAccess) -> None:
    _, [line] = run(["pages", str(bubble_comic)], {})

    code, [written] = run(["write", json.loads(line)["work"], "001.png"], env_of(access), "[]")

    assert code == 0
    assert Path(json.loads(written)["english"]).is_file()


def test_an_archive_that_is_not_a_zip_is_one_error_line(tmp_path: Path) -> None:
    (tmp_path / "ch1.cbz").write_bytes(b"not a zip")

    assert run(["pages", str(tmp_path / "ch1.cbz")], {}) == (1, ["error: File is not a zip file"])


def test_a_work_file_the_scripts_did_not_write_is_one_error_line(bubble_comic: Path) -> None:
    _, [line] = run(["pages", str(bubble_comic)], {})
    (Path(json.loads(line)["work"]) / "pages.json").write_text('[{"page": "001.png"}]')

    code, [refused] = run(["pages", str(bubble_comic)], {})

    assert code == 1
    assert refused.startswith("error: list[Page] is not as the scripts wrote it: 0.size: Field")


def test_an_archive_with_a_page_that_is_not_an_image_is_one_error_line(tmp_path: Path) -> None:
    with zipfile.ZipFile(tmp_path / "ch1.cbz", "w") as archive:
        archive.writestr("001.png", b"not a png")

    code, [refused] = run(["pages", str(tmp_path / "ch1.cbz")], {})

    assert code == 1
    assert refused.startswith("error: cannot identify image file")
