"""The one image service startup builds: the web channel and the runtime show images through it."""

from __future__ import annotations

from pathlib import Path

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
from tests.unit.helpers import client_tools, no_bots, no_gate, no_skills
from tests.webapp import files_in, images_in, secrets_in


def runtime_over(tmp_path: Path, images: ImageService, *, vision: bool) -> Runtime:
    """The runtime `build_runtime` composes over `images`, for a model that sees or does not."""
    return build_runtime(
        Settings(llm={"model": "m", "api_key": "k", "vision": vision}),
        SessionService(JsonlSessionRepository(tmp_path / "sessions")),
        McpService({}),
        no_skills(),
        client_tools(),
        no_gate(),
        bots=no_bots(SessionService(JsonlSessionRepository(tmp_path / "bot-chats"))),
        subagent_logs=SessionService(JsonlSessionRepository(tmp_path / "subagents")),
        secrets=secrets_in(tmp_path),
        images=images,
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


def test_startup_hands_the_runtime_and_the_web_channel_one_image_service(
    tmp_path: Path, monkeypatch
) -> None:
    settings = Settings(
        llm={"model": "m", "api_key": "k", "vision": True},
        sessions={"root": tmp_path / "sessions"},
        files={"root": tmp_path / "files"},
        bots={"path": tmp_path / "bots.json"},
        secrets={"path": tmp_path / "secrets.json", "encryption_key": "0" * 64},
        approval={"grants_path": tmp_path / "approvals.json"},
        skills={"roots": [tmp_path / "skills"], "editable": tmp_path / "skills"},
        compaction={"context_tokens": 1000},
        telegram={"bot_token": ""},
        discord={"bot_token": ""},
        mcp={"servers": {}},
    )
    handed: list[ImageService] = []
    real_runtime, real_channels = server.build_runtime, server.build_channels

    def runtime_seen(*args, **kwargs) -> Runtime:
        handed.append(kwargs["images"])
        return real_runtime(*args, **kwargs)

    def channels_seen(*args):
        handed.append(args[-1])
        return real_channels(*args)

    monkeypatch.setattr(server, "load", lambda: settings)
    monkeypatch.setattr(server, "configure_logging", lambda: None)
    monkeypatch.setattr(server, "build_runtime", runtime_seen)
    monkeypatch.setattr(server, "build_channels", channels_seen)

    server.create_web_app()

    assert len(handed) == 2
    assert handed[0] is handed[1]
