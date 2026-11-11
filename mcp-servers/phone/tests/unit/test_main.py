"""Startup: a refusal exits 2, and the binder kernel is set before the server runs."""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

import pytest
from mcp.server import MCPServer

from phone import server


def test_a_refused_config_exits_two_and_says_why(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.delenv("PHONE_KERNEL", raising=False)

    with caplog.at_level(logging.ERROR, logger="phone"), pytest.raises(SystemExit) as exit:
        server.main()

    assert exit.value.code == 2
    assert "phone refusing to start: PHONE_KERNEL is not set" in caplog.text


def test_the_kernel_is_set_and_then_the_server_runs_on_stdio(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    kernel = tmp_path / "libkrunfw.5.dylib"
    kernel.write_bytes(b"\x00")
    monkeypatch.setenv("PHONE_IMAGE", "example/phone:1")
    monkeypatch.setenv("PHONE_KERNEL", str(kernel))
    monkeypatch.setenv("PHONE_KERNEL_SHA256", hashlib.sha256(b"\x00").hexdigest())
    monkeypatch.setenv("PHONE_FILES_DIR", str(tmp_path))
    monkeypatch.delenv(server.KERNEL_VARIABLE, raising=False)
    monkeypatch.delenv(server.MSB_VARIABLE, raising=False)
    seen: list[tuple[str | None, str | None]] = []
    monkeypatch.setattr(
        MCPServer,
        "run",
        lambda _self, transport: seen.append(
            (os.environ.get(server.KERNEL_VARIABLE), os.environ.get(server.MSB_VARIABLE))
        ),
    )

    server.main()

    assert seen == [(str(kernel.resolve()), server.packaged_msb())]
    assert Path(server.packaged_msb()).is_file()
