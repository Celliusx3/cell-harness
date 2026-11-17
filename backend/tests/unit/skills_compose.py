"""The real object graph over a skills root in `tmp_path`, for the skill tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.config import Settings
from harness.mcp import McpServer, McpService, open_stdio_client
from harness.runtime.service import Runtime
from harness.session.repository.jsonl_session_repository import JsonlSessionRepository
from harness.session.service.session_service import SessionService
from harness.web.runtime import build_runtime
from tests.unit.helpers import client_tools, no_approvals, no_bots, skills_at
from tests.webapp import files_in, images_in, secrets_in


def write_skill(root: Path, name: str) -> Path:
    (root / name).mkdir(parents=True)
    (root / name / "SKILL.md").write_text(f"---\ndescription: {name} things.\n---\nDo {name}.\n")
    return root / name


@pytest.fixture
def compose(tmp_path: Path):
    root = tmp_path / "skills"
    root.mkdir()

    def build() -> Runtime:
        settings = Settings()
        sessions = SessionService(JsonlSessionRepository(tmp_path / "sessions"))
        mcp = McpService(
            {"stub": McpServer(command="does-not-run")}, client_factory=open_stdio_client
        )
        return build_runtime(
            settings,
            sessions,
            mcp,
            skills_at(root),
            client_tools(),
            no_approvals(),
            bots=no_bots(SessionService(JsonlSessionRepository(tmp_path / "bot-chats"))),
            secrets=secrets_in(tmp_path),
            images=images_in(tmp_path),
            files=files_in(tmp_path),
        )

    return build, root
