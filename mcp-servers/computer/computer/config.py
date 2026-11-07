"""Settings from the environment, validated before the server binds."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, get_args

IMAGE = (
    "ghcr.io/celliusx3/cell-harness/pc"
    "@sha256:50c6c9f7c0aad1fb369f44d532a3c19f62c732a08f12b953b44664f3af21e9e3"
)
NAME = "cell-harness-computer"
IDLE_MINUTES = 10

EngineName = Literal["microsandbox", "docker"]
ENGINE_NAMES: tuple[EngineName, ...] = get_args(EngineName)

DOCKER_NAME_PATTERN = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]+")


class ConfigError(RuntimeError):
    """Startup refused. The message names the variable to set."""


@dataclass(frozen=True)
class Config:
    engine: EngineName
    image: str
    container_name: str
    idle_minutes: int
    files_dir: Path
    skills_dirs: tuple[Path, ...]


def required_value(src: Mapping[str, str], variable: str, what: str) -> str:
    """`variable`'s value, stripped, or a refusal saying it is not set and what to name."""
    raw = src.get(variable, "").strip()
    if not raw:
        raise ConfigError(f"{variable} is not set: name {what}")
    return raw


def engine_name(raw: str) -> EngineName:
    """`raw` as one of the engines, or a refusal naming them all."""
    for name in ENGINE_NAMES:
        if raw == name:
            return name
    choices = " or ".join(repr(name) for name in ENGINE_NAMES)
    raise ConfigError(f"COMPUTER_ENGINE={raw!r} is not {choices}")


def existing_folder(variable: str, raw: str) -> Path:
    """`raw` as an absolute path to a folder that exists, or a refusal naming `variable`."""
    if not raw:
        raise ConfigError(f"{variable} has an empty path in it")
    path = Path(raw).expanduser().resolve()
    if not path.is_dir():
        raise ConfigError(f"{variable}={raw!r} is not a folder that exists")
    return path


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

    files = required_value(src, "COMPUTER_FILES_DIR", "the folder the chat files are kept in")
    skills = required_value(
        src, "COMPUTER_SKILLS_DIRS", f"the skill folders, separated by {os.pathsep!r}"
    )

    engine = engine_name(src.get("COMPUTER_ENGINE", "").strip())

    return Config(
        engine=engine,
        image=image,
        container_name=name,
        idle_minutes=idle_minutes,
        files_dir=existing_folder("COMPUTER_FILES_DIR", files),
        skills_dirs=tuple(
            existing_folder("COMPUTER_SKILLS_DIRS", part.strip())
            for part in skills.split(os.pathsep)
        ),
    )
