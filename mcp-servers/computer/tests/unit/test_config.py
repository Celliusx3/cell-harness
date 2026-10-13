"""Startup refusals, and the defaults the live computer runs with."""

from __future__ import annotations

import pytest

from computer.config import ConfigError, load


def test_an_empty_environment_loads_rakazos_image_and_the_shared_name() -> None:
    config = load({})

    assert config.image == "ghcr.io/elie222/rakazo/computer:edge"
    assert config.container_name == "cell-harness-computer"
    assert config.idle_minutes == 10


def test_every_setting_can_be_overridden() -> None:
    config = load(
        {
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
