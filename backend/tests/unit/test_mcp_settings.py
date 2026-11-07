"""An MCP server as it is run, and the ids a server may have."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from harness.config.sections import McpServer, usable_server_id


def test_a_plain_server_is_accepted() -> None:
    server = McpServer(command="npx", args=("-y", "server-fs"))
    assert server.args == ("-y", "server-fs")
    assert server.env == {}


@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_a_blank_command_is_refused(blank: str) -> None:
    with pytest.raises(ValidationError, match="command must not be blank"):
        McpServer(command=blank)


@pytest.mark.parametrize(
    "bad_id",
    [
        "Has-Capitals",
        "has_underscore",
        "has.dot",
        "has/slash",
        "-leading",
        "trailing-",
        "",
        "a" * 40,
        "has-hyphen",
        "instagram-poi",
        "3d",
        "9lives",
    ],
)
def test_an_id_that_could_not_be_half_a_tool_name_is_refused(bad_id: str) -> None:
    with pytest.raises(ValueError, match="not a usable MCP server id"):
        usable_server_id(bad_id)


def test_the_refusal_says_why_a_hyphen_is_not_allowed() -> None:
    with pytest.raises(ValueError, match="TypeScript identifier"):
        usable_server_id("my-server")


@pytest.mark.parametrize(
    "good_id", ["yt", "igpoi", "instagram", "places", "jobs", "a", "s3", "maps2"]
)
def test_a_plain_lowercase_id_is_accepted(good_id: str) -> None:
    assert usable_server_id(good_id) == good_id


def test_a_server_is_frozen() -> None:
    server = McpServer(command="npx")
    with pytest.raises(ValidationError):
        server.command = "other"


def test_a_server_setting_under_the_home_folder_is_read_from_it(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    server = McpServer(command="uvx", env={"NOTES": "~/notes", "AGENT": "x ~/y", "BARE": "~"})

    assert server.env == {"NOTES": f"{tmp_path}/notes", "AGENT": "x ~/y", "BARE": "~"}
