"""What the tools are sent is refused before it reaches the computer when it does not fit."""

from __future__ import annotations

import base64

import pytest
from pydantic import ValidationError

from computer.models import (
    TRANSFER_LIMIT_BYTES,
    Action,
    HomePath,
    checked_file_path,
    checked_upload,
    home_path,
)


@pytest.mark.parametrize(
    "action",
    [
        {"kind": "click", "ref": "e1"},
        {"kind": "fill", "ref": "e1", "text": "Ada"},
        {"kind": "fill", "ref": "e1", "text": ""},
        {"kind": "type", "ref": "e1", "text": " Lovelace"},
    ],
)
def test_an_action_that_fits_its_kind_is_accepted(action: dict[str, str]) -> None:
    assert Action.model_validate(action).model_dump(exclude_none=True) == action


@pytest.mark.parametrize(
    ("action", "because"),
    [
        ({"kind": "click", "ref": "e1", "text": "x"}, "click takes no text"),
        ({"kind": "fill", "ref": "e1"}, "fill needs text"),
        ({"kind": "type", "ref": "e1"}, "type needs text"),
        ({"kind": "click", "ref": ""}, "at least 1 character"),
        ({"kind": "press", "ref": "e1"}, "'click', 'fill' or 'type'"),
    ],
)
def test_an_action_that_does_not_fit_is_refused(action: dict[str, str], because: str) -> None:
    with pytest.raises(ValidationError, match=because):
        Action.model_validate(action)


@pytest.mark.parametrize(
    ("given", "relative", "absolute"),
    [
        ("", "", "/home/rakazo"),
        ("/", "", "/home/rakazo"),
        ("notes", "notes", "/home/rakazo/notes"),
        ("notes/", "notes", "/home/rakazo/notes"),
        ("/notes//hello.txt", "notes/hello.txt", "/home/rakazo/notes/hello.txt"),
        ("notes\\hello.txt", "notes/hello.txt", "/home/rakazo/notes/hello.txt"),
        ("/etc/passwd", "etc/passwd", "/home/rakazo/etc/passwd"),
        (".bashrc", ".bashrc", "/home/rakazo/.bashrc"),
        ("a..b/...", "a..b/...", "/home/rakazo/a..b/..."),
    ],
)
def test_a_path_is_read_as_rakazo_reads_it_under_the_home_folder(
    given: str, relative: str, absolute: str
) -> None:
    path = home_path(given)

    assert path.relative == relative
    assert path.absolute == absolute


@pytest.mark.parametrize(
    ("given", "because"),
    [
        ("..", "no . or .. segments"),
        ("../etc/passwd", "no . or .. segments"),
        ("notes/../../etc", "no . or .. segments"),
        ("/home/rakazo/../../etc", "no . or .. segments"),
        ("./notes", "no . or .. segments"),
        ("a/./b", "no . or .. segments"),
        ("..\\etc", "no . or .. segments"),
        ("a\x00b", "NUL"),
    ],
)
def test_a_path_that_could_leave_the_home_folder_is_refused(given: str, because: str) -> None:
    with pytest.raises(ValueError, match=because):
        home_path(given)


def test_a_file_path_must_name_a_file_not_the_home_folder() -> None:
    hello = HomePath(relative="notes/hello.txt")

    assert checked_file_path(hello) == hello
    with pytest.raises(ValueError, match="not the folder itself"):
        checked_file_path(HomePath(relative=""))


def test_an_upload_of_up_to_ten_mebibytes_is_accepted() -> None:
    content = base64.b64encode(bytes(TRANSFER_LIMIT_BYTES)).decode()

    assert checked_upload(content) == content


@pytest.mark.parametrize(
    ("content", "because"),
    [
        (base64.b64encode(bytes(TRANSFER_LIMIT_BYTES + 1)).decode(), "at most 10 MiB"),
        ("not base64!", "not base64"),
        ("aGk=\n", "not base64"),
        ("aGk", "not base64"),
    ],
)
def test_an_upload_too_large_or_not_base64_is_refused(content: str, because: str) -> None:
    with pytest.raises(ValueError, match=because):
        checked_upload(content)
