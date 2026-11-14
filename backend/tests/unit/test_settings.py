"""Settings: where each value comes from, and which are unguessable."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from harness.config import settings as settings_module
from harness.config.sections import FileSettings, LLMSettings
from harness.config.settings import MissingConfigError, Settings, load_settings


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    """Point the loader at a throwaway config pair."""
    committed = tmp_path / "config.json"
    local = tmp_path / "config.local.json"
    monkeypatch.setattr(settings_module, "_CONFIG_JSON", committed)
    monkeypatch.setattr(settings_module, "_LOCAL_JSON", local)
    for name in ("HARNESS_LLM__TEMPERATURE", "HARNESS_SESSIONS__ROOT"):
        monkeypatch.delenv(name, raising=False)

    return (
        lambda data: committed.write_text(json.dumps(data)),
        lambda data: local.write_text(json.dumps(data)),
    )


def settings_in(tmp_path: Path) -> Settings:
    """Settings as the throwaway files and the environment give them."""
    return Settings()


def test_config_json_supplies_defaults(tmp_path, config_file) -> None:
    write_committed, _ = config_file
    write_committed({"llm": {"temperature": 0.2, "timeout_seconds": 30}})

    settings = settings_in(tmp_path)

    assert settings.llm.temperature == 0.2
    assert settings.llm.timeout_seconds == 30


def test_the_environment_beats_config_json(tmp_path, config_file, monkeypatch) -> None:
    write_committed, _ = config_file
    write_committed({"llm": {"temperature": 0.2}})
    monkeypatch.setenv("HARNESS_LLM__TEMPERATURE", "0.7")

    assert settings_in(tmp_path).llm.temperature == 0.7


def test_constructor_arguments_beat_everything(tmp_path, config_file, monkeypatch) -> None:
    write_committed, _ = config_file
    write_committed({"llm": {"temperature": 0.2}})
    monkeypatch.setenv("HARNESS_LLM__TEMPERATURE", "0.7")

    assert Settings(llm=LLMSettings(temperature=1.5)).llm.temperature == 1.5


def test_a_value_in_neither_falls_back_to_the_field_default(tmp_path, config_file) -> None:
    write_committed, _ = config_file
    write_committed({"llm": {"temperature": 0.2}})

    assert settings_in(tmp_path).llm.timeout_seconds == 600.0


@pytest.mark.parametrize(
    ("section", "field"),
    [
        ("llm", "api_key"),
        ("llm", "model"),
        ("llm", "base_url"),
        ("telegram", "bot_token"),
        ("discord", "bot_token"),
    ],
)
def test_a_key_in_the_settings_files_is_refused(tmp_path, config_file, section, field) -> None:
    """Every key is a credential, saved on Credentials; one left in a file stops the start."""
    _, write_local = config_file
    write_local({section: {field: "sk-left-in-the-file"}})

    with pytest.raises(ValidationError, match=section) as refused:
        settings_in(tmp_path)

    assert "sk-left-in-the-file" not in str(refused.value)


def test_load_needs_no_model_now_each_bot_has_its_own(config_file) -> None:
    write_committed, _ = config_file
    write_committed({"secrets": {"encryption_key": "e"}})

    assert load_settings().llm == LLMSettings()


def test_temperature_is_pinned_not_inherited() -> None:
    assert LLMSettings().temperature == 1.0


@pytest.mark.parametrize("bad", [-0.1, 2.1])
def test_temperature_is_bounded(bad: float) -> None:
    with pytest.raises(ValidationError):
        LLMSettings(temperature=bad)


def test_the_sessions_root_expands_a_tilde() -> None:
    from harness.config.sections import SessionSettings

    root = SessionSettings(root="~/somewhere").root

    assert "~" not in str(root)
    assert str(root).startswith("/")


def test_the_bots_file_path_expands_a_tilde() -> None:
    from harness.config.sections import BotSettings

    path = BotSettings(path="~/bots.json").path

    assert "~" not in str(path)
    assert str(path).startswith("/")


def test_config_local_json_beats_config_json(tmp_path, config_file) -> None:
    write_committed, write_local = config_file
    write_committed({"llm": {"temperature": 0.2, "timeout_seconds": 30}})
    write_local({"llm": {"temperature": 0.5}})

    settings = settings_in(tmp_path)

    assert settings.llm.temperature == 0.5
    assert settings.llm.timeout_seconds == 30


def test_the_environment_beats_config_local_json(tmp_path, config_file, monkeypatch) -> None:
    write_committed, write_local = config_file
    write_committed({"llm": {"temperature": 0.2}})
    write_local({"llm": {"temperature": 0.5}})
    monkeypatch.setenv("HARNESS_LLM__TEMPERATURE", "0.7")

    assert settings_in(tmp_path).llm.temperature == 0.7


def test_a_missing_local_file_is_normal(config_file) -> None:
    write_committed, _ = config_file
    write_committed({"llm": {"temperature": 0.2}, "secrets": {"encryption_key": "e"}})

    assert load_settings().llm.temperature == 0.2


@pytest.mark.parametrize("secrets", [{}, {"encryption_key": ""}, {"encryption_key": "   "}])
def test_load_refuses_a_blank_encryption_key_and_points_at_the_local_file(
    config_file, monkeypatch, secrets
) -> None:
    write_committed, _ = config_file
    monkeypatch.delenv("HARNESS_SECRETS__ENCRYPTION_KEY", raising=False)
    write_committed({"secrets": secrets})

    with pytest.raises(MissingConfigError, match="config.local.json") as refused:
        load_settings()

    assert "secrets.encryption_key" in str(refused.value)


def test_skill_roots_resolve_relative_paths_against_the_project(config_file, tmp_path) -> None:
    write_committed, _ = config_file
    (tmp_path / ".git").mkdir()
    write_committed({"skills": {"roots": [".agents/skills", "~/x"], "editable": "~/x"}})

    settings = settings_in(tmp_path)

    assert settings.skills.roots == (tmp_path / ".agents" / "skills", Path.home() / "x")
    assert settings.skills.editable == Path.home() / "x"


def test_the_editable_root_must_be_read_from(tmp_path, config_file) -> None:
    write_committed, _ = config_file
    write_committed({"skills": {"roots": ["/a"], "editable": "/b"}})

    with pytest.raises(ValueError, match="must be one of skills.roots"):
        settings_in(tmp_path)


def test_skill_roots_can_come_from_the_environment(tmp_path, config_file, monkeypatch) -> None:
    monkeypatch.setenv("HARNESS_SKILLS__ROOTS", '["/only"]')
    monkeypatch.setenv("HARNESS_SKILLS__EDITABLE", "/only")

    assert settings_in(tmp_path).skills.roots == (Path("/only"),)


def test_the_public_url_is_off_by_default(tmp_path, config_file) -> None:
    assert settings_in(tmp_path).web.public_url == ""


def test_a_trailing_slash_on_the_public_url_is_dropped(tmp_path, config_file) -> None:
    write_committed, _ = config_file
    write_committed({"web": {"public_url": "https://h.example/"}})

    assert settings_in(tmp_path).web.public_url == "https://h.example"


def test_the_files_root_expands_a_tilde() -> None:
    root = FileSettings(root="~/files").root

    assert "~" not in str(root)
    assert str(root).startswith("/")


def test_an_upload_limit_of_nothing_is_refused() -> None:
    with pytest.raises(ValidationError):
        FileSettings(max_bytes=0)


def test_the_committed_config_sets_where_files_go_and_how_big_one_may_be(config_file) -> None:
    committed = json.loads((Path(__file__).parents[2] / "config.json").read_text())

    assert committed["files"] == {"root": "~/.harness/files", "max_bytes": 209715200}


def test_the_committed_config_names_no_model_only_how_every_model_is_asked() -> None:
    committed = json.loads((Path(__file__).parents[2] / "config.json").read_text())

    assert set(committed["llm"]) == {"temperature", "timeout_seconds"}
