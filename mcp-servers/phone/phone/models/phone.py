"""The phone in its own terms: what it is made with, its programs and its state."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

LABEL = "cell-harness.phone"
LOOPBACK = "127.0.0.1"

PhoneState = Literal["running", "stopped", "missing"]


@dataclass(frozen=True)
class PhoneSpec:
    """Everything the phone is made with."""

    name: str
    image: str
    published_ports: tuple[int, ...]


@dataclass(frozen=True)
class Program:
    """A program to run in the phone's microVM: its words, and the variables it runs with."""

    argv: tuple[str, ...]
    env: Mapping[str, str]


def android(command: str) -> Program:
    """`command` run in Android's root shell, through the image's `android` helper."""
    return Program(argv=("android", command), env={})
