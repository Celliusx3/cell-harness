"""Startup refusals, and the defaults the live computer runs with."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from computer.config import ConfigError, load


def folders(tmp_path: Path) -> dict[str, str]:
    for name in ("files", "skills", "more-skills"):
        (tmp_path / name).mkdir()
    return {
        "COMPUTER_FILES_DIR": str(tmp_path / "files"),
        "COMPUTER_SKILLS_DIRS": f"{tmp_path / 'skills'}{os.pathsep}{tmp_path / 'more-skills'}",
    }


def test_only_the_folders_set_loads_rakazos_image_and_the_shared_name(tmp_path: Path) -> None:
    config = load(folders(tmp_path))

    assert config.image == "ghcr.io/elie222/rakazo/computer:edge"
    assert config.container_name == "cell-harness-computer"
    assert config.idle_minutes == 10


def test_every_setting_can_be_overridden(tmp_path: Path) -> None:
    config = load(
        {
            **folders(tmp_path),
            "COMPUTER_IMAGE": "example/computer:1",
            "COMPUTER_NAME": "cell-harness-computer-test",
            "COMPUTER_IDLE_MINUTES": "3",
        }
    )

    assert (config.image, config.container_name, config.idle_minutes) == (
        "example/computer:1",
        "cell-harness-computer-test",
        3,
    )


@pytest.mark.parametrize(
    ("value", "because"),
    [("soon", "not a whole number"), ("0", "greater than zero"), ("-5", "greater than zero")],
)
def test_an_unusable_idle_time_refuses(value: str, because: str) -> None:
    with pytest.raises(ConfigError, match=because):
        load({"COMPUTER_IDLE_MINUTES": value})


@pytest.mark.parametrize("name", ["has space", "-leading-dash", "semi;colon", "a"])
def test_a_name_docker_would_refuse_is_refused_at_startup(name: str) -> None:
    with pytest.raises(ConfigError, match="COMPUTER_NAME"):
        load({"COMPUTER_NAME": name})


def test_the_files_folder_and_every_skills_folder_load_as_absolute_paths(tmp_path: Path) -> None:
    config = load(folders(tmp_path))

    assert config.files_dir == tmp_path / "files"
    assert config.skills_dirs == (tmp_path / "skills", tmp_path / "more-skills")


def test_a_folder_is_expanded_from_home_and_resolved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = folders(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))

    config = load({**env, "COMPUTER_FILES_DIR": "~/skills/../files"})

    assert config.files_dir == tmp_path.resolve() / "files"


@pytest.mark.parametrize("variable", ["COMPUTER_FILES_DIR", "COMPUTER_SKILLS_DIRS"])
def test_a_folder_not_set_is_refused_at_startup(tmp_path: Path, variable: str) -> None:
    env = folders(tmp_path)

    with pytest.raises(ConfigError, match=f"{variable} is not set"):
        load({**env, variable: " "})
    with pytest.raises(ConfigError, match=f"{variable} is not set"):
        load({key: value for key, value in env.items() if key != variable})


@pytest.mark.parametrize("variable", ["COMPUTER_FILES_DIR", "COMPUTER_SKILLS_DIRS"])
def test_a_folder_that_does_not_exist_is_refused_naming_its_variable(
    tmp_path: Path, variable: str
) -> None:
    env = folders(tmp_path)
    (tmp_path / "a-file").write_text("")

    for missing in (tmp_path / "missing", tmp_path / "a-file"):
        with pytest.raises(ConfigError, match=f"{variable}=.* is not a folder that exists"):
            load({**env, variable: str(missing)})


def test_every_entry_in_the_skills_folders_is_checked(tmp_path: Path) -> None:
    env = folders(tmp_path)
    skills = env["COMPUTER_SKILLS_DIRS"]

    with pytest.raises(ConfigError, match="COMPUTER_SKILLS_DIRS has an empty path"):
        load({**env, "COMPUTER_SKILLS_DIRS": f"{skills}{os.pathsep}"})
    with pytest.raises(ConfigError, match="COMPUTER_SKILLS_DIRS=.* is not a folder that exists"):
        load({**env, "COMPUTER_SKILLS_DIRS": f"{skills}{os.pathsep}{tmp_path / 'missing'}"})
