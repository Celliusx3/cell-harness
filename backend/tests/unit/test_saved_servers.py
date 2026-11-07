"""The person's MCP servers, kept with their keys in their own file, an id taken refused."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from harness.config.sections import BotSettings, McpSettings
from harness.mcp import (
    DiskSavedServerRepository,
    McpServerBuiltIn,
    McpServerNotFound,
    McpServerTaken,
    SavedServer,
    SavedServerService,
    ServerDraft,
)

EXA = SavedServer(
    id="exa", command="npx", args=("-y", "exa-mcp-server"), env={}, needs=("EXA_API_KEY",)
)
NO_KEYS: dict[str, SecretStr] = {}


def saved_in(tmp_path: Path, *built_in: str) -> SavedServerService:
    return SavedServerService(
        DiskSavedServerRepository(tmp_path / "mcp.json"), built_in_ids=frozenset(built_in)
    )


def test_no_file_is_no_server(tmp_path: Path) -> None:
    assert saved_in(tmp_path).servers() == ()


def test_a_server_added_is_read_back_by_another_service_over_the_same_file(tmp_path) -> None:
    saved_in(tmp_path).add(EXA)

    assert saved_in(tmp_path).servers() == (EXA,)


def test_an_id_a_built_in_server_uses_is_refused_unsaved(tmp_path: Path) -> None:
    service = saved_in(tmp_path, "exa")

    with pytest.raises(McpServerTaken, match="built-in"):
        service.add(EXA)

    assert service.servers() == ()


def test_an_id_another_saved_server_uses_is_refused(tmp_path: Path) -> None:
    service = saved_in(tmp_path)
    service.add(EXA)

    with pytest.raises(McpServerTaken, match="already"):
        service.add(EXA.model_copy(update={"command": "uvx"}))

    assert service.servers() == (EXA,)


def test_a_change_keeps_the_id_and_the_place_in_the_list(tmp_path: Path) -> None:
    service = saved_in(tmp_path)
    service.add(EXA)
    service.add(EXA.model_copy(update={"id": "maps"}))
    draft = ServerDraft(command="uvx", args=("exa",), env={"LIMIT": "3"}, needs=(), keys=NO_KEYS)

    changed = service.change("exa", draft)

    assert changed == SavedServer(
        id="exa", command="uvx", args=("exa",), env={"LIMIT": "3"}, needs=()
    )
    assert [s.id for s in saved_in(tmp_path).servers()] == ["exa", "maps"]
    assert saved_in(tmp_path).servers()[0] == changed


def test_a_removed_server_is_gone_from_the_file(tmp_path: Path) -> None:
    service = saved_in(tmp_path)
    service.add(EXA)

    service.remove("exa")

    assert saved_in(tmp_path).servers() == ()


def test_a_built_in_server_cannot_be_changed_or_removed(tmp_path: Path) -> None:
    service = saved_in(tmp_path, "fs")
    draft = ServerDraft(command="npx", args=(), env={}, needs=(), keys=NO_KEYS)

    with pytest.raises(McpServerBuiltIn):
        service.change("fs", draft)
    with pytest.raises(McpServerBuiltIn):
        service.remove("fs")


def test_an_unknown_server_is_not_found(tmp_path: Path) -> None:
    service = saved_in(tmp_path)

    with pytest.raises(McpServerNotFound):
        service.remove("nowhere")
    with pytest.raises(McpServerNotFound):
        service.change(
            "nowhere", ServerDraft(command="npx", args=(), env={}, needs=(), keys=NO_KEYS)
        )


def test_the_ids_follow_the_rule_config_ids_follow() -> None:
    with pytest.raises(ValidationError, match="not a usable MCP server id"):
        SavedServer(id="my-server", command="npx", args=(), env={}, needs=())


@pytest.mark.parametrize("blank", ["", "  "])
def test_a_blank_command_is_refused(blank: str) -> None:
    with pytest.raises(ValidationError, match="command must not be blank"):
        ServerDraft(command=blank, args=(), env={}, needs=(), keys=NO_KEYS)


def test_a_key_the_server_needs_is_refused_as_a_plain_setting() -> None:
    with pytest.raises(ValidationError, match="type it as a key, not as a setting"):
        ServerDraft(
            command="npx", args=(), env={"EXA_API_KEY": "x"}, needs=("EXA_API_KEY",), keys=NO_KEYS
        )


def test_a_blank_needed_key_name_is_refused() -> None:
    with pytest.raises(ValidationError, match="needs must name env variables"):
        ServerDraft(command="npx", args=(), env={}, needs=(" ",), keys=NO_KEYS)


def test_a_draft_runs_as_a_server_that_is_never_required() -> None:
    server = EXA.server()

    assert (server.command, server.args, server.needs, server.required) == (
        "npx",
        ("-y", "exa-mcp-server"),
        ("EXA_API_KEY",),
        False,
    )


def test_every_field_is_asked_for_and_nothing_else() -> None:
    with pytest.raises(ValidationError):
        ServerDraft.model_validate({"command": "npx"})
    with pytest.raises(ValidationError):
        ServerDraft.model_validate(
            {"command": "npx", "args": [], "env": {}, "needs": [], "keys": {}, "required": True}
        )


def test_a_change_keeps_a_key_not_typed_again_and_takes_one_typed(tmp_path: Path) -> None:
    service = saved_in(tmp_path)
    service.add(EXA.model_copy(update={"env": {"EXA_API_KEY": "first", "LIMIT": "3"}}))
    needs = ("EXA_API_KEY", "OTHER_KEY")

    kept = service.change(
        "exa", ServerDraft(command="npx", args=(), env={}, needs=needs, keys=NO_KEYS)
    )
    typed = service.change(
        "exa",
        ServerDraft(
            command="npx", args=(), env={}, needs=needs, keys={"OTHER_KEY": SecretStr("second")}
        ),
    )

    assert kept.env == {"EXA_API_KEY": "first"}
    assert typed.env == {"EXA_API_KEY": "first", "OTHER_KEY": "second"}
    assert saved_in(tmp_path).servers() == (typed,)


def test_the_file_is_readable_by_its_owner_alone(tmp_path: Path) -> None:
    saved_in(tmp_path).add(EXA)

    assert stat.S_IMODE((tmp_path / "mcp.json").stat().st_mode) == 0o600


def test_the_default_file_sits_beside_the_bots_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    assert McpSettings().path == BotSettings().path.with_name("mcp.json")
    assert McpSettings(path="~/elsewhere/mcp.json").path == tmp_path / "elsewhere" / "mcp.json"
