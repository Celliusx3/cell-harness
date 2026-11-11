"""Settings from the environment, validated before the server binds."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

NAME = "cell-harness-phone"
IDLE_MINUTES = 10

SANDBOX_NAME_PATTERN = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]+")


class ConfigError(RuntimeError):
    """Startup refused. The message names the variable to set."""


@dataclass(frozen=True)
class Config:
    image: str
    name: str
    kernel: Path
    files_dir: Path
    idle_minutes: int


def required_value(src: Mapping[str, str], variable: str, what: str) -> str:
    """`variable`'s value, stripped, or a refusal saying it is not set and what to name."""
    raw = src.get(variable, "").strip()
    if not raw:
        raise ConfigError(f"{variable} is not set: name {what}")
    return raw


def sandbox_name(raw: str) -> str:
    """`raw` as the phone's microVM name, or a refusal saying what a name may hold."""
    if not SANDBOX_NAME_PATTERN.fullmatch(raw):
        raise ConfigError(
            f"PHONE_NAME={raw!r} is not a name the phone accepts: letters, digits, '_', '.' "
            "and '-', at least two characters, starting with a letter or digit"
        )
    return raw


def existing_file(variable: str, raw: str) -> Path:
    """`raw` as an absolute path to a file that exists, or a refusal naming `variable`."""
    path = Path(raw).expanduser().resolve()
    if not path.is_file():
        raise ConfigError(f"{variable}={raw!r} is not a file that exists")
    return path


def existing_folder(variable: str, raw: str) -> Path:
    """`raw` as an absolute path to a folder that exists, or a refusal naming `variable`."""
    path = Path(raw).expanduser().resolve()
    if not path.is_dir():
        raise ConfigError(f"{variable}={raw!r} is not a folder that exists")
    return path


def idle_minutes(raw: str) -> int:
    """`raw` as the phone's idle minutes, IDLE_MINUTES when unset, or a refusal."""
    try:
        minutes = int(raw) if raw else IDLE_MINUTES
    except ValueError as err:
        raise ConfigError(f"PHONE_IDLE_MINUTES={raw!r} is not a whole number") from err
    if minutes <= 0:
        raise ConfigError(f"PHONE_IDLE_MINUTES={minutes} must be greater than zero")
    return minutes


def load(env: Mapping[str, str] | None = None) -> Config:
    src = os.environ if env is None else env
    image = required_value(src, "PHONE_IMAGE", "the phone's image, pinned by digest")
    kernel = required_value(src, "PHONE_KERNEL", "the libkrunfw.5.dylib built with binder")
    files = required_value(src, "PHONE_FILES_DIR", "the folder the chat files are kept in")
    return Config(
        image=image,
        name=sandbox_name(src.get("PHONE_NAME", "").strip() or NAME),
        kernel=existing_file("PHONE_KERNEL", kernel),
        files_dir=existing_folder("PHONE_FILES_DIR", files),
        idle_minutes=idle_minutes(src.get("PHONE_IDLE_MINUTES", "").strip()),
    )
