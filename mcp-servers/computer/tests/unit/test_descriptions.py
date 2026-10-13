"""The tool descriptions."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

import computer.tools.descriptions
from computer.models import (
    Acted,
    FileBytes,
    FileEntry,
    FileText,
    Listing,
    Opened,
    Page,
    ScreenSession,
    Uploaded,
)
from computer.tools.descriptions import (
    ACT_DESCRIPTION,
    FILE_DOWNLOAD_DESCRIPTION,
    FILE_LIST_DESCRIPTION,
    FILE_READ_DESCRIPTION,
    FILE_UPLOAD_DESCRIPTION,
    HELD_BY_PERSON,
    KEEP_AWAKE_DESCRIPTION,
    NAVIGATE_DESCRIPTION,
    READ_PAGE_DESCRIPTION,
    RELEASE_CONTROL_DESCRIPTION,
    SCREEN_SESSION_DESCRIPTION,
    SCREENSHOT_DESCRIPTION,
    TERMINAL_SESSION_DESCRIPTION,
)

ALL = {
    "browser_navigate": NAVIGATE_DESCRIPTION,
    "browser_read_page": READ_PAGE_DESCRIPTION,
    "browser_act": ACT_DESCRIPTION,
    "screenshot": SCREENSHOT_DESCRIPTION,
    "screen_session": SCREEN_SESSION_DESCRIPTION,
    "release_control": RELEASE_CONTROL_DESCRIPTION,
    "terminal_session": TERMINAL_SESSION_DESCRIPTION,
    "file_list": FILE_LIST_DESCRIPTION,
    "file_read": FILE_READ_DESCRIPTION,
    "file_download": FILE_DOWNLOAD_DESCRIPTION,
    "file_upload": FILE_UPLOAD_DESCRIPTION,
    "keep_awake": KEEP_AWAKE_DESCRIPTION,
}
APP_ONLY_TOOLS = (
    "screenshot",
    "screen_session",
    "release_control",
    "terminal_session",
    "file_list",
    "file_read",
    "file_download",
    "file_upload",
    "keep_awake",
)


@pytest.mark.parametrize("name", sorted(ALL))
def test_a_description_survives_being_collapsed_to_one_line(name: str) -> None:
    text = ALL[name]

    assert " ".join(text.split()) == text


@pytest.mark.parametrize("name", sorted(ALL))
def test_a_description_cannot_end_its_own_comment_block(name: str) -> None:
    assert "*/" not in ALL[name]


@pytest.mark.parametrize("name", sorted(ALL))
def test_a_description_names_its_arguments(name: str) -> None:
    assert "args: {" in ALL[name]


@pytest.mark.parametrize(
    ("name", "model"),
    [
        ("browser_navigate", Opened),
        ("browser_read_page", Page),
        ("browser_act", Acted),
        ("screen_session", ScreenSession),
        ("release_control", ScreenSession),
        ("file_list", Listing),
        ("file_list", FileEntry),
        ("file_read", FileText),
        ("file_download", FileBytes),
        ("file_upload", Uploaded),
    ],
)
def test_every_returned_field_is_named_in_the_prose(name: str, model: type[BaseModel]) -> None:
    missing = [field for field in model.model_fields if field not in ALL[name]]

    assert missing == []


@pytest.mark.parametrize("name", sorted(ALL))
def test_a_description_never_hardcodes_its_own_namespace(name: str) -> None:
    assert "__" not in ALL[name]


@pytest.mark.parametrize("name", sorted(ALL))
def test_a_description_never_names_rakazos_fallback(name: str) -> None:
    assert "computer_act" not in ALL[name]
    assert "fallback" not in ALL[name]


@pytest.mark.parametrize("name", APP_ONLY_TOOLS)
def test_an_app_only_tool_tells_the_model_not_to_call_it(name: str) -> None:
    assert ALL[name].startswith("App-only:")
    assert "do not call it" in ALL[name]


def test_act_states_the_limit_the_schema_enforces() -> None:
    assert "1 to 24 actions" in ACT_DESCRIPTION


def test_a_held_screen_tells_the_bot_to_wait_for_the_person() -> None:
    assert "taken control" in HELD_BY_PERSON
    assert " ".join(HELD_BY_PERSON.split()) == HELD_BY_PERSON


def test_the_screenshot_control_path_is_gone() -> None:
    assert not hasattr(computer.tools.descriptions, "CONTROL_DESCRIPTION")


@pytest.mark.parametrize("name", ["file_upload", "terminal_session"])
def test_a_tool_that_needs_control_says_so(name: str) -> None:
    assert "while they hold control" in ALL[name]


def test_the_folder_listing_says_an_empty_path_is_the_home_folder() -> None:
    assert "empty for the home folder itself" in FILE_LIST_DESCRIPTION
