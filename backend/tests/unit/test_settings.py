"""Settings: where each value comes from, and which are unguessable."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.config import settings as settings_module
from harness.config.sections import LLMSettings
from harness.config.settings import MissingConfigError, Settings, load


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    """Point the loader at a throwaway config pair."""
    committed = tmp_path / "config.json"
    local = tmp_path / "config.local.json"
    monkeypatch.setattr(settings_module, "_CONFIG_JSON", committed)
    monkeypatch.setattr(settings_module, "_LOCAL_JSON", local)
    for name in ("HARNESS_LLM__MODEL", "HARNESS_LLM__API_KEY", "HARNESS_SESSIONS__ROOT"):
        monkeypatch.delenv(name, raising=False)

    return (
        lambda data: committed.write_text(json.dumps(data)),
        lambda data: local.write_text(json.dumps(data)),
    )


def test_config_json_supplies_defaults(config_file) -> None:
    write_committed, _ = config_file
    write_committed({"llm": {"model": "from-json", "temperature": 0.2}})

    settings = Settings()

    assert settings.llm.model == "from-json"
    assert settings.llm.temperature == 0.2


def test_the_environment_beats_config_json(config_file, monkeypatch) -> None:
    write_committed, _ = config_file
    write_committed({"llm": {"model": "from-json"}})
    monkeypatch.setenv("HARNESS_LLM__MODEL", "from-env")

    assert Settings().llm.model == "from-env"


def test_constructor_arguments_beat_everything(config_file, monkeypatch) -> None:
    write_committed, _ = config_file
    write_committed({"llm": {"model": "from-json"}})
    monkeypatch.setenv("HARNESS_LLM__MODEL", "from-env")

    assert Settings(llm=LLMSettings(model="explicit")).llm.model == "explicit"


def test_a_value_in_neither_falls_back_to_the_field_default(config_file) -> None:
    write_committed, _ = config_file
    write_committed({"llm": {"model": "m"}})

    assert Settings().llm.base_url == "https://api.openai.com/v1"


def test_nesting_uses_a_double_underscore(config_file, monkeypatch) -> None:
    write_committed, _ = config_file
    """`HARNESS_LLM__API_KEY`, matching config.json's structure. The prefix is
    deliberate: picking up a bare `LLM__API_KEY` from a shell would surprise."""
    write_committed({})
    monkeypatch.setenv("HARNESS_LLM__API_KEY", "sk-from-env")

    assert Settings().llm.api_key == "sk-from-env"


@pytest.mark.parametrize("missing", ["model", "api_key"])
def test_load_refuses_when_an_unguessable_value_is_absent(config_file, missing) -> None:
    write_committed, _ = config_file
    """A default API key cannot exist, and a default *model* is a behavioral
    choice — it decides what answers cost and how good they are."""
    values = {"model": "m", "api_key": "k"}
    del values[missing]
    write_committed({"llm": values})

    with pytest.raises(MissingConfigError, match=f"llm.{missing}"):
        load()


def test_the_refusal_names_the_files_to_edit(config_file) -> None:
    write_committed, _ = config_file
    """The error a caller wants tells them what to do, not a pydantic path."""
    write_committed({})

    with pytest.raises(MissingConfigError, match="config.json"):
        load()


def test_load_returns_settings_when_both_are_present(config_file) -> None:
    write_committed, _ = config_file
    write_committed({"llm": {"model": "m", "api_key": "k"}})

    assert load().llm.model == "m"


@pytest.mark.parametrize("blank", ["", "   "])
def test_a_blank_value_counts_as_absent(config_file, blank) -> None:
    write_committed, _ = config_file
    """An empty string in config.json is someone who has not filled it in yet."""
    write_committed({"llm": {"model": blank, "api_key": "k"}})

    with pytest.raises(MissingConfigError):
        load()


def test_temperature_is_pinned_not_inherited() -> None:
    assert LLMSettings().temperature == 1.0


@pytest.mark.parametrize("bad", [-0.1, 2.1])
def test_temperature_is_bounded(bad: float) -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        LLMSettings(temperature=bad)


def test_the_sessions_root_expands_a_tilde() -> None:
    from harness.config.sections import SessionSettings

    root = SessionSettings(root="~/somewhere").root

    assert "~" not in str(root)
    assert str(root).startswith("/")


def test_config_local_json_beats_config_json(config_file) -> None:
    write_committed, write_local = config_file
    write_committed({"llm": {"model": "committed", "base_url": "https://committed"}})
    write_local({"llm": {"model": "local"}})

    settings = Settings()

    assert settings.llm.model == "local"
    assert settings.llm.base_url == "https://committed"


def test_the_environment_beats_config_local_json(config_file, monkeypatch) -> None:
    write_committed, write_local = config_file
    write_committed({"llm": {"model": "committed"}})
    write_local({"llm": {"model": "local"}})
    monkeypatch.setenv("HARNESS_LLM__MODEL", "from-env")

    assert Settings().llm.model == "from-env"


def test_a_missing_local_file_is_normal(config_file) -> None:
    write_committed, _ = config_file
    write_committed({"llm": {"model": "m", "api_key": "k"}})

    assert load().llm.model == "m"


def test_the_refusal_points_at_the_local_file_for_the_key(config_file) -> None:
    write_committed, _ = config_file
    write_committed({"llm": {"model": "m"}})

    with pytest.raises(MissingConfigError, match="config.local.json"):
        load()


def test_skill_roots_resolve_relative_paths_against_the_project(config_file, tmp_path) -> None:
    write_committed, _ = config_file
    (tmp_path / ".git").mkdir()
    write_committed({"skills": {"roots": [".agents/skills", "~/x"], "editable": "~/x"}})

    settings = Settings()

    assert settings.skills.roots == (tmp_path / ".agents" / "skills", Path.home() / "x")
    assert settings.skills.editable == Path.home() / "x"


def test_the_editable_root_must_be_read_from(config_file) -> None:
    write_committed, _ = config_file
    write_committed({"skills": {"roots": ["/a"], "editable": "/b"}})

    with pytest.raises(ValueError, match="must be one of skills.roots"):
        Settings()


def test_skill_roots_can_come_from_the_environment(config_file, monkeypatch) -> None:
    monkeypatch.setenv("HARNESS_SKILLS__ROOTS", '["/only"]')
    monkeypatch.setenv("HARNESS_SKILLS__EDITABLE", "/only")

    assert Settings().skills.roots == (Path("/only"),)


def test_the_public_url_is_off_by_default(config_file) -> None:
    assert Settings().web.public_url == ""


def test_a_trailing_slash_on_the_public_url_is_dropped(config_file) -> None:
    write_committed, _ = config_file
    write_committed({"web": {"public_url": "https://h.example/"}})

    assert Settings().web.public_url == "https://h.example"
