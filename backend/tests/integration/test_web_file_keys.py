"""A start moves the settings file's keys into the keyring once, or refuses with no Default."""

from __future__ import annotations

import json
from pathlib import Path
from typing import NamedTuple

import httpx
import pytest
from fastapi import FastAPI

from harness.channels.gateway import ChannelGateway
from harness.channels.web.channel import WebChannel
from harness.config.settings import MissingConfigError
from harness.web import server
from tests.webapp import TEST_ENCRYPTION_KEY, startup_settings

MODEL_KEY = "sk-file-model-key-1234"
TELEGRAM_TOKEN = "123456:AAfile-telegram-5678"
DISCORD_TOKEN = "discord-file-token-9012"
ALL_KEYS = {
    "llm": {"api_key": MODEL_KEY, "temperature": 0.5},
    "telegram": {"bot_token": TELEGRAM_TOKEN},
    "discord": {"bot_token": DISCORD_TOKEN},
    "secrets": {"encryption_key": TEST_ENCRYPTION_KEY},
}


class Started(NamedTuple):
    app: FastAPI
    gateway: ChannelGateway


def _start(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Started:
    """`create_web_app` over folders in `tmp_path`, and the gateway it registered channels on."""
    gateways: list[ChannelGateway] = []
    real_channels = server.build_channels

    def channels_seen(*args) -> tuple[ChannelGateway, WebChannel]:
        gateway, web = real_channels(*args)
        gateways.append(gateway)
        return gateway, web

    monkeypatch.setattr(server, "load", lambda: startup_settings(tmp_path))
    monkeypatch.setattr(server, "configure_logging", lambda: None)
    monkeypatch.setattr(server, "build_channels", channels_seen)
    app = server.create_web_app()
    [gateway] = gateways
    return Started(app, gateway)


async def _listed(app: FastAPI) -> list[dict]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://h.test") as http:
        return (await http.get("/api/credentials")).json()["credentials"]


def _write_local(tmp_path: Path, data: dict) -> Path:
    local = tmp_path / "config.local.json"
    local.write_text(json.dumps(data), encoding="utf-8")
    local.chmod(0o600)
    return local


async def test_a_file_holding_all_three_keys_starts_with_three_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    local = _write_local(tmp_path, ALL_KEYS)

    started = _start(tmp_path, monkeypatch)
    listed = await _listed(started.app)
    await started.gateway.aclose()

    assert {entry["name"]: entry["is_default_model"] for entry in listed} == {
        "default_model": True,
        "discord": False,
        "telegram": False,
    }
    assert started.gateway.channels == ["web", "telegram", "discord"]
    text = local.read_text(encoding="utf-8")
    assert all(key not in text for key in (MODEL_KEY, TELEGRAM_TOKEN, DISCORD_TOKEN))
    assert json.loads(text) == {
        "llm": {"temperature": 0.5},
        "secrets": {"encryption_key": TEST_ENCRYPTION_KEY},
    }


async def test_a_second_start_moves_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    local = _write_local(tmp_path, ALL_KEYS)
    await _start(tmp_path, monkeypatch).gateway.aclose()
    file_before = local.read_bytes()
    keyring_before = (tmp_path / "secrets.json").read_bytes()

    await _start(tmp_path, monkeypatch).gateway.aclose()

    assert local.read_bytes() == file_before
    assert (tmp_path / "secrets.json").read_bytes() == keyring_before


def test_with_no_model_key_anywhere_the_harness_refuses_to_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(MissingConfigError, match="no Default model") as refused:
        _start(tmp_path, monkeypatch)

    assert str(tmp_path / "config.local.json") in str(refused.value)
    assert not (tmp_path / "config.local.json").exists()
