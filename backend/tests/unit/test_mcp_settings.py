"""MCP servers as configuration.

A definition that could never spawn is refused when the config loads, so the
failure names the file to edit rather than surfacing as a missing tool later.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from harness.config import settings as settings_module
from harness.config.settings import McpServer, McpSettings, Settings


def test_a_plain_server_is_accepted() -> None:
    server = McpServer(command="npx", args=("-y", "server-fs"))
    assert server.args == ("-y", "server-fs")
    assert server.env == {}


def test_no_servers_is_the_default() -> None:
    assert McpSettings().servers == {}


@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_a_blank_command_is_refused(blank: str) -> None:
    """A blank string in JSON is a paste that went wrong, not a value."""
    with pytest.raises(ValidationError, match="command must not be blank"):
        McpServer(command=blank)


@pytest.mark.parametrize(
    "bad_id",
    [
        "Has-Capitals",
        "has_underscore",  # would make the `{server}__{tool}` split ambiguous
        "has.dot",
        "has/slash",
        "-leading",
        "trailing-",
        "",
        "a" * 40,
    ],
)
def test_an_id_that_could_not_be_half_a_tool_name_is_refused(bad_id: str) -> None:
    with pytest.raises(ValidationError, match="not a usable MCP server id"):
        McpSettings(servers={bad_id: McpServer(command="npx")})


def test_a_server_is_frozen() -> None:
    server = McpServer(command="npx")
    with pytest.raises(ValidationError):
        server.command = "other"


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    """Point the loader at a throwaway config pair — as `test_settings.py` does.

    Patching the module attributes rather than reloading the module: a reload
    replaces the objects `test_settings.py` holds and breaks it from here.
    """
    committed = tmp_path / "config.json"
    local = tmp_path / "config.local.json"
    monkeypatch.setattr(settings_module, "_CONFIG_JSON", committed)
    monkeypatch.setattr(settings_module, "_LOCAL_JSON", local)
    return (
        lambda data: committed.write_text(json.dumps(data)),
        lambda data: local.write_text(json.dumps(data)),
    )


def test_the_two_config_files_merge_per_server(config_file) -> None:
    """The shape is committed; only the secret is gitignored.

    This is what makes a `0600` runtime store unnecessary — `config.local.json`
    is already where secrets live, and it merges *into* a server rather than
    replacing the whole block.
    """
    write_committed, write_local = config_file
    write_committed(
        {
            "mcp": {
                "servers": {
                    "fs": {"command": "npx", "args": ["-y", "srv-fs"]},
                    "gh": {"command": "npx", "args": ["-y", "srv-gh"]},
                }
            }
        }
    )
    write_local({"mcp": {"servers": {"gh": {"env": {"TOKEN": "s3cret"}}}}})

    loaded = Settings()

    assert loaded.mcp.servers["fs"].env == {}
    assert loaded.mcp.servers["gh"].command == "npx"
    assert loaded.mcp.servers["gh"].args == ("-y", "srv-gh")
    assert loaded.mcp.servers["gh"].env == {"TOKEN": "s3cret"}


def test_a_bad_server_in_config_fails_the_load(config_file) -> None:
    """Named at startup, not as a tool that quietly never appears."""
    write_committed, _ = config_file
    write_committed({"mcp": {"servers": {"fs": {"command": ""}}}})

    with pytest.raises(ValidationError, match="command must not be blank"):
        Settings()


def test_servers_can_come_from_the_environment() -> None:
    """`HARNESS_MCP__*` works for free, which is how a container configures one."""
    configured = Settings(mcp={"servers": {"fs": {"command": "npx"}}})
    assert configured.mcp.servers["fs"].command == "npx"
