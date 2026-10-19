"""The image and chat file services startup builds once, for the web channel and the runtime."""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import pytest

from harness.channels.gateway import ChannelGateway
from harness.channels.web.channel import WebChannel
from harness.config.settings import Settings
from harness.images import ImageService
from harness.mcp.service import McpService
from harness.runtime.service import Runtime
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.web import server
from harness.web.runtime import build_runtime
from harness.web.server import build_channels
from tests.integration.web_helpers import build
from tests.unit.fakes import ScriptedClient
from tests.unit.helpers import client_tools, no_approvals, no_bots, no_skills
from tests.webapp import files_in, images_in, secrets_in, startup_settings


def runtime_over(tmp_path: Path, images: ImageService, *, vision: bool) -> Runtime:
    """The runtime `build_runtime` composes over `images`, for a model that sees or does not."""
    return build_runtime(
        Settings(llm={"model": "m", "api_key": "k", "vision": vision}),
        SessionService(JsonlSessionRepository(tmp_path / "sessions")),
        McpService({}),
        no_skills(),
        client_tools(),
        no_approvals(),
        bots=no_bots(SessionService(JsonlSessionRepository(tmp_path / "bot-chats"))),
        subagent_logs=SessionService(JsonlSessionRepository(tmp_path / "subagents")),
        secrets=secrets_in(tmp_path),
        images=images,
        files=files_in(tmp_path),
    )


def test_the_web_channel_keeps_images_in_the_service_it_is_built_with(tmp_path) -> None:
    sessions, runs = build(tmp_path, ScriptedClient([]))
    images = images_in(tmp_path)
    settings = Settings(telegram={"bot_token": ""}, discord={"bot_token": ""})

    _, web = build_channels(
        settings,
        sessions,
        runs,
        no_skills(),
        client_tools(),
        no_bots(sessions),
        files_in(tmp_path),
        images,
    )

    assert web.images is images


def test_a_runtime_for_a_model_that_sees_shows_images_through_the_service_it_is_built_with(
    tmp_path,
) -> None:
    images = images_in(tmp_path)

    assert runtime_over(tmp_path, images, vision=True).images is images


def test_a_runtime_for_a_model_that_cannot_see_holds_no_images(tmp_path) -> None:
    assert runtime_over(tmp_path, images_in(tmp_path), vision=False).images is None


class Started(NamedTuple):
    runtime: Runtime
    web: WebChannel


def started(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Started:
    """The runtime and the web channel `create_web_app` builds, over folders in `tmp_path`."""
    settings = startup_settings(tmp_path)
    runtimes: list[Runtime] = []
    webs: list[WebChannel] = []
    real_runtime, real_channels = server.build_runtime, server.build_channels

    def runtime_seen(*args, **kwargs) -> Runtime:
        runtimes.append(real_runtime(*args, **kwargs))
        return runtimes[-1]

    def channels_seen(*args) -> tuple[ChannelGateway, WebChannel]:
        gateway, web = real_channels(*args)
        webs.append(web)
        return gateway, web

    monkeypatch.setattr(server, "load", lambda: settings)
    monkeypatch.setattr(server, "configure_logging", lambda: None)
    monkeypatch.setattr(server, "build_runtime", runtime_seen)
    monkeypatch.setattr(server, "build_channels", channels_seen)

    server.create_web_app()

    [runtime], [web] = runtimes, webs
    return Started(runtime, web)


def test_startup_hands_the_runtime_and_the_web_channel_one_image_service(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = started(tmp_path, monkeypatch)

    assert app.runtime.images is app.web.images


def test_startup_hands_the_runtime_and_the_web_channel_one_chat_file_service(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = started(tmp_path, monkeypatch)

    assert app.runtime.files is app.web.files
