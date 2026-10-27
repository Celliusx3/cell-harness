"""The Discord channel wired into the app: present with a keyring token, absent without."""

from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr

from harness.channels.gateway import ChannelGateway
from harness.config.settings import Settings
from harness.runs.service import RunService
from harness.runtime.service import Runtime
from harness.secrets import Destination, SecretService
from harness.secrets.models.details import DiscordDetails, TelegramDetails
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.web.server import build_channels
from tests.unit.fakes import OneModel, ScriptedClient
from tests.unit.helpers import no_bots
from tests.webapp import channel_services, secrets_in


def _services(tmp_path: Path) -> tuple[SessionService, RunService]:
    sessions = SessionService(JsonlSessionRepository(tmp_path / "sessions"))
    runtime = Runtime(models=OneModel(ScriptedClient([])), images=None)
    return sessions, RunService(sessions, runtime, no_bots(sessions))


def _channels(tmp_path: Path, keyring: SecretService) -> ChannelGateway:
    sessions, runs = _services(tmp_path)
    settings = Settings(local_settings_path=tmp_path / "config.local.json")
    return build_channels(settings, channel_services(tmp_path, sessions, runs), keyring)[0]


async def test_no_token_means_no_channel(tmp_path) -> None:
    assert _channels(tmp_path, secrets_in(tmp_path)).channels == ["web"]


async def test_a_custom_key_named_discord_is_not_a_token(tmp_path) -> None:
    keyring = secrets_in(tmp_path)
    site = Destination(origin="https://discord.example", auth="bearer")
    keyring.save("discord", site, SecretStr("custom-key-not-a-token"))

    assert _channels(tmp_path, keyring).channels == ["web"]


async def test_a_token_builds_a_channel(tmp_path) -> None:
    keyring = secrets_in(tmp_path)
    keyring.add_credential("discord", DiscordDetails(), SecretStr("discord-token-abc"))

    built = _channels(tmp_path, keyring)

    assert built.channels == ["web", "discord"]
    await built.aclose()


async def test_both_bots_share_one_gateway(tmp_path) -> None:
    keyring = secrets_in(tmp_path)
    keyring.add_credential("telegram", TelegramDetails(), SecretStr("123:abc-telegram"))
    keyring.add_credential("discord", DiscordDetails(), SecretStr("discord-token-abc"))

    built = _channels(tmp_path, keyring)

    assert built.channels == ["web", "telegram", "discord"]
    await built.aclose()
