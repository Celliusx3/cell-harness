"""Settings from the environment, validated before the server binds."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass

IMAGE = "ghcr.io/elie222/rakazo/computer:edge"
NAME = "cell-harness-computer"
IDLE_MINUTES = 10

DOCKER_NAME_PATTERN = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]+")


class ConfigError(RuntimeError):
    """Startup refused. The message names the variable to set."""


@dataclass(frozen=True)
class Config:
    image: str
    container_name: str
    idle_minutes: int


def load(env: Mapping[str, str] | None = None) -> Config:
    src = os.environ if env is None else env

    image = src.get("COMPUTER_IMAGE", "").strip() or IMAGE

    name = src.get("COMPUTER_NAME", "").strip() or NAME
    if not DOCKER_NAME_PATTERN.fullmatch(name):
        raise ConfigError(
            f"COMPUTER_NAME={name!r} is not a name docker accepts: letters, digits, '_', '.' "
            "and '-', at least two characters, starting with a letter or digit"
        )

    raw = src.get("COMPUTER_IDLE_MINUTES", "").strip()
    try:
        idle_minutes = int(raw) if raw else IDLE_MINUTES
    except ValueError as err:
        raise ConfigError(f"COMPUTER_IDLE_MINUTES={raw!r} is not a whole number") from err
    if idle_minutes <= 0:
        raise ConfigError(f"COMPUTER_IDLE_MINUTES={idle_minutes} must be greater than zero")

    return Config(image=image, container_name=name, idle_minutes=idle_minutes)
