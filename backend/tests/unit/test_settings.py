"""Settings: where each value comes from, and which are unguessable."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.config import settings as settings_module
from harness.config.sections import FileSettings, LLMSettings
from harness.config.settings import MissingConfigError, Settings, load


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    """Point the loader at a throwaway config pair; `llm.vision` is set."""
    committed = tmp_path / "config.json"
    local = tmp_path / "config.local.json"
    monkeypatch.setattr(settings_module, "_CONFIG_JSON", committed)
    monkeypatch.setattr(settings_module, "_LOCAL_JSON", local)
    for name in ("HARNESS_LLM__MODEL", "HARNESS_LLM__API_KEY", "HARNESS_SESSIONS__ROOT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HARNESS_LLM__VISION", "false")

    return (
        lambda data: committed.write_text(json.dumps(data)),
        lambda data: local.write_text(json.dumps(data)),
    )


def settings_in(tmp_path: Path) -> Settings:
    """Settings as the throwaway files and the environment give them."""
    return Settings(local_settings_path=tmp_path / "config.local.json")


def test_config_json_supplies_defaults(tmp_path, config_file) -> None:
    write_committed, _ = config_file
    write_committed({"llm": {"model": "from-json", "temperature": 0.2}})

    settings = settings_in(tmp_path)

    assert settings.llm.model == "from-json"
    assert settings.llm.temperature == 0.2


def test_the_environment_beats_config_json(tmp_path, config_file, monkeypatch) -> None:
    write_committed, _ = config_file
    write_committed({"llm": {"model": "from-json"}})
    monkeypatch.setenv("HARNESS_LLM__MODEL", "from-env")

    assert settings_in(tmp_path).llm.model == "from-env"


def test_constructor_arguments_beat_everything(tmp_path, config_file, monkeypatch) -> None:
    write_committed, _ = config_file
    write_committed({"llm": {"model": "from-json"}})
    monkeypatch.setenv("HARNESS_LLM__MODEL", "from-env")

    assert (
        Settings(
            local_settings_path=tmp_path / "config.local.json",
            llm=LLMSettings(model="explicit", vision=False),
        ).llm.model
        == "explicit"
    )


def test_a_value_in_neither_falls_back_to_the_field_default(tmp_path, config_file) -> None:
    write_committed, _ = config_file
    write_committed({"llm": {"model": "m"}})

    assert settings_in(tmp_path).llm.base_url == "https://api.openai.com/v1"


def test_nesting_uses_a_double_underscore(tmp_path, config_file, monkeypatch) -> None:
    write_committed, _ = config_file
    """`HARNESS_LLM__API_KEY`, matching config.json's structure. The prefix is
    deliberate: picking up a bare `LLM__API_KEY` from a shell would surprise."""
    write_committed({})
    monkeypatch.setenv("HARNESS_LLM__API_KEY", "sk-from-env")

    assert settings_in(tmp_path).llm.api_key == "sk-from-env"


def test_load_refuses_when_the_model_is_absent(config_file) -> None:
    write_committed, _ = config_file
    write_committed({"llm": {"api_key": "k"}, "secrets": {"encryption_key": "e"}})

    with pytest.raises(MissingConfigError, match="llm.model") as refused:
        load()

    assert "HARNESS_LLM__API_KEY" not in str(refused.value)


def test_the_refusal_names_the_files_to_edit(config_file) -> None:
    write_committed, _ = config_file
    """The error a caller wants tells them what to do, not a pydantic path."""
    write_committed({})

    with pytest.raises(MissingConfigError, match="config.json"):
        load()


def test_load_returns_settings_when_both_are_present(config_file) -> None:
    write_committed, _ = config_file
    write_committed({"llm": {"model": "m", "api_key": "k"}, "secrets": {"encryption_key": "e"}})

    assert load().llm.model == "m"


@pytest.mark.parametrize("blank", ["", "   "])
def test_a_blank_value_counts_as_absent(config_file, blank) -> None:
    write_committed, _ = config_file
    """An empty string in config.json is someone who has not filled it in yet."""
    write_committed({"llm": {"model": blank, "api_key": "k"}})

    with pytest.raises(MissingConfigError):
        load()


def test_temperature_is_pinned_not_inherited() -> None:
    assert LLMSettings(vision=False).temperature == 1.0


@pytest.mark.parametrize("bad", [-0.1, 2.1])
def test_temperature_is_bounded(bad: float) -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        LLMSettings(vision=False, temperature=bad)


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
    write_committed({"llm": {"model": "committed", "base_url": "https://committed"}})
    write_local({"llm": {"model": "local"}})

    settings = settings_in(tmp_path)

    assert settings.llm.model == "local"
    assert settings.llm.base_url == "https://committed"


def test_the_environment_beats_config_local_json(tmp_path, config_file, monkeypatch) -> None:
    write_committed, write_local = config_file
    write_committed({"llm": {"model": "committed"}})
    write_local({"llm": {"model": "local"}})
    monkeypatch.setenv("HARNESS_LLM__MODEL", "from-env")

    assert settings_in(tmp_path).llm.model == "from-env"


def test_a_missing_local_file_is_normal(config_file) -> None:
    write_committed, _ = config_file
    write_committed({"llm": {"model": "m", "api_key": "k"}, "secrets": {"encryption_key": "e"}})

    assert load().llm.model == "m"


def test_load_needs_no_model_key_now_the_keyring_holds_it(config_file) -> None:
    write_committed, _ = config_file
    write_committed({"llm": {"model": "m"}, "secrets": {"encryption_key": "e"}})

    assert load().llm.model == "m"


def test_load_names_the_settings_file_it_read(tmp_path, config_file) -> None:
    write_committed, _ = config_file
    write_committed({"llm": {"model": "m"}, "secrets": {"encryption_key": "e"}})

    assert load().local_settings_path == tmp_path / "config.local.json"


def test_settings_that_do_not_name_the_settings_file_are_refused(config_file) -> None:
    from pydantic import ValidationError

    write_committed, _ = config_file
    write_committed({"llm": {"model": "m"}})

    with pytest.raises(ValidationError, match="local_settings_path"):
        Settings()


@pytest.mark.parametrize("secrets", [{}, {"encryption_key": ""}, {"encryption_key": "   "}])
def test_load_refuses_a_blank_encryption_key_and_points_at_the_local_file(
    config_file, monkeypatch, secrets
) -> None:
    write_committed, _ = config_file
    monkeypatch.delenv("HARNESS_SECRETS__ENCRYPTION_KEY", raising=False)
    write_committed({"llm": {"model": "m", "api_key": "k"}, "secrets": secrets})

    with pytest.raises(MissingConfigError, match="config.local.json") as refused:
        load()

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
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        FileSettings(max_bytes=0)


def test_the_committed_config_sets_where_files_go_and_how_big_one_may_be(config_file) -> None:
    committed = json.loads((Path(__file__).parents[2] / "config.json").read_text())

    assert committed["files"] == {"root": "~/.harness/files", "max_bytes": 209715200}


def test_a_config_that_does_not_say_whether_the_model_can_see_is_refused(
    tmp_path, config_file, monkeypatch
) -> None:
    from pydantic import ValidationError

    write_committed, _ = config_file
    monkeypatch.delenv("HARNESS_LLM__VISION")
    write_committed({"llm": {"model": "m", "api_key": "k"}})

    with pytest.raises(ValidationError, match="llm.vision"):
        settings_in(tmp_path)


def test_the_committed_config_shows_the_model_images(config_file) -> None:
    committed = json.loads((Path(__file__).parents[2] / "config.json").read_text())

    assert committed["llm"]["vision"] is True
