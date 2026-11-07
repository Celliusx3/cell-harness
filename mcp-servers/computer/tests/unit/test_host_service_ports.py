"""A declared program asks for the same port on every start, so the PC's network rules hold."""

from __future__ import annotations

import socket
import uuid
from pathlib import Path

import pytest

from computer.models.pc import LOOPBACK
from computer.services.host_services import (
    STEADY_PORT_FLOOR,
    STEADY_PORT_SPAN,
    prepared_host_service,
    steady_port,
)
from tests.fake_host_service import declared


@pytest.fixture
def prefix() -> str:
    """A prefix no running program uses, so its steady port is free unless a test takes it."""
    return f"TEST_{uuid.uuid4().hex.upper()}"


def test_the_steady_port_is_the_same_for_a_prefix_and_differs_between_prefixes() -> None:
    assert steady_port("PHOTOCRAFT") == steady_port("PHOTOCRAFT")
    assert steady_port("PHOTOCRAFT") != steady_port("OTHER")


def test_the_steady_port_is_the_one_the_live_app_used_so_no_release_rebuilds_the_pc() -> None:
    assert steady_port("PHOTOCRAFT") == 47028


@pytest.mark.parametrize("env_prefix", ["PHOTOCRAFT", "OTHER", "A", "", "SYSMON_2"])
def test_every_steady_port_lies_in_its_range(env_prefix: str) -> None:
    assert steady_port(env_prefix) in range(STEADY_PORT_FLOOR, STEADY_PORT_FLOOR + STEADY_PORT_SPAN)


def test_two_starts_of_the_same_program_get_the_same_port(tmp_path: Path, prefix: str) -> None:
    program = tmp_path / "program"

    first = prepared_host_service(declared(program, prefix), tmp_path)
    second = prepared_host_service(declared(program, prefix), tmp_path)

    assert first.port == second.port == steady_port(prefix)


def test_a_steady_port_already_taken_falls_back_to_a_free_one(tmp_path: Path, prefix: str) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as taken:
        taken.bind((LOOPBACK, steady_port(prefix)))
        taken.listen()

        prepared = prepared_host_service(declared(tmp_path / "program", prefix), tmp_path)

    assert prepared.port != steady_port(prefix)
