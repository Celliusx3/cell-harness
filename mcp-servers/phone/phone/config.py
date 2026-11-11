"""Settings from the environment, validated before the server binds."""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

IMAGE = (
    "ghcr.io/celliusx3/cell-harness/phone"
    "@sha256:f678ec0f58ae66d3baf47b2ac30fef1d1d0c30ebedb0ba82a143d34b3950401c"
)
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


def pinned_kernel(path: Path, pin: str) -> Path:
    """`path`, or a refusal unless its SHA-256 is the one PHONE_KERNEL_SHA256 pins."""
    expected = pin.strip().lower()
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise ConfigError(
            f"PHONE_KERNEL is not the kernel PHONE_KERNEL_SHA256 pins: {path} is {actual}, "
            f"the pin is {expected}"
        )
    return path


def load(env: Mapping[str, str] | None = None) -> Config:
    src = os.environ if env is None else env
    image = src.get("PHONE_IMAGE", "").strip() or IMAGE
    kernel = required_value(src, "PHONE_KERNEL", "the libkrunfw.5.dylib built with binder")
    pin = required_value(src, "PHONE_KERNEL_SHA256", "the SHA-256 of the kernel's release")
    files = required_value(src, "PHONE_FILES_DIR", "the folder the chat files are kept in")
    return Config(
        image=image,
        name=sandbox_name(src.get("PHONE_NAME", "").strip() or NAME),
        kernel=pinned_kernel(existing_file("PHONE_KERNEL", kernel), pin),
        files_dir=existing_folder("PHONE_FILES_DIR", files),
        idle_minutes=idle_minutes(src.get("PHONE_IDLE_MINUTES", "").strip()),
    )
