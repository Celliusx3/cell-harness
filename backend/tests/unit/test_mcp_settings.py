"""MCP servers as configuration."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from harness.config import settings as settings_module
from harness.config.sections import McpServer, McpSettings
from harness.config.settings import Settings, SkillSettings


def test_a_plain_server_is_accepted() -> None:
    server = McpServer(command="npx", args=("-y", "server-fs"))
    assert server.args == ("-y", "server-fs")
    assert server.env == {}


def test_no_servers_is_the_default() -> None:
    assert McpSettings().servers == {}


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
    with pytest.raises(ValidationError, match="not a usable MCP server id"):
        McpSettings(servers={bad_id: McpServer(command="npx")})


def test_the_refusal_says_why_a_hyphen_is_not_allowed() -> None:
    with pytest.raises(ValidationError, match="TypeScript identifier"):
        McpSettings(servers={"my-server": McpServer(command="npx")})


@pytest.mark.parametrize(
    "good_id", ["yt", "igpoi", "instagram", "places", "jobs", "a", "s3", "maps2"]
)
def test_a_plain_lowercase_id_is_accepted(good_id: str) -> None:
    assert good_id in McpSettings(servers={good_id: McpServer(command="npx")}).servers


def test_a_server_is_frozen() -> None:
    server = McpServer(command="npx")
    with pytest.raises(ValidationError):
        server.command = "other"


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    """Point the loader at a throwaway config pair — as `test_settings.py` does."""
    committed = tmp_path / "config.json"
    local = tmp_path / "config.local.json"
    monkeypatch.setattr(settings_module, "_CONFIG_JSON", committed)
    monkeypatch.setattr(settings_module, "_LOCAL_JSON", local)
    monkeypatch.setenv("HARNESS_LLM__VISION", "false")
    return (
        lambda data: committed.write_text(json.dumps(data)),
        lambda data: local.write_text(json.dumps(data)),
    )


def settings_in(tmp_path: Path) -> Settings:
    """Settings as the throwaway files and the environment give them."""
    return Settings(local_settings_path=tmp_path / "config.local.json")


def test_the_two_config_files_merge_per_server(tmp_path, config_file) -> None:
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

    loaded = settings_in(tmp_path)

    assert loaded.mcp.servers["fs"].env == {}
    assert loaded.mcp.servers["gh"].command == "npx"
    assert loaded.mcp.servers["gh"].args == ("-y", "srv-gh")
    assert loaded.mcp.servers["gh"].env == {"TOKEN": "s3cret"}


def test_a_bad_server_in_config_fails_the_load(tmp_path, config_file) -> None:
    write_committed, _ = config_file
    write_committed({"mcp": {"servers": {"fs": {"command": ""}}}})

    with pytest.raises(ValidationError, match="command must not be blank"):
        settings_in(tmp_path)


def test_servers_can_come_from_the_environment(tmp_path) -> None:
    configured = Settings(
        local_settings_path=tmp_path / "config.local.json",
        mcp={"servers": {"fs": {"command": "npx"}}},
    )
    assert configured.mcp.servers["fs"].command == "npx"


def test_the_computer_mounts_exactly_the_skills_bots_cannot_change() -> None:
    backend = Path(__file__).parents[2]
    committed = json.loads((backend / "config.json").read_text())
    skills = SkillSettings.model_validate(committed["skills"])
    shipped = {root.resolve() for root in skills.roots if root != skills.editable}
    mounted = committed["mcp"]["servers"]["computer"]["env"]["COMPUTER_SKILLS_DIRS"]

    assert {(backend / folder).resolve() for folder in mounted.split(os.pathsep)} == shipped
