"""The PC in its own terms: what it is made with, the programs run in it, and its state."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

PcState = Literal["running", "stopped", "missing"]


@dataclass(frozen=True)
class SharedFolder:
    """A folder on the Mac the PC sees at the same path, writable or read-only."""

    path: Path
    writable: bool


@dataclass(frozen=True)
class HomeVolume:
    """The engine's own named volume that holds the PC's home folder across new PCs."""

    name: str
    guest_path: str


@dataclass(frozen=True)
class PcSpec:
    """Everything the PC is made with; each published guest port is reached on loopback only."""

    name: str
    image: str
    env: Mapping[str, str]
    home: HomeVolume
    shared_folders: tuple[SharedFolder, ...]
    published_ports: tuple[int, ...]
    host_service_ports: tuple[int, ...]
    shm_megabytes: int


@dataclass(frozen=True)
class Program:
    """A program to run in the PC: its words, and the variables it runs with."""

    argv: tuple[str, ...]
    env: Mapping[str, str]
