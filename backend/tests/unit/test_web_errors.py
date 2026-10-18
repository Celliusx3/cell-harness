"""Each domain error a route lets through answers its usual status, as `HTTPException` did."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI, HTTPException

from harness.bots import ASSISTANT_ID, BotNotFound, BotPermanent, GroupEmpty
from harness.files import FileTooLarge, UnsafeFileName
from harness.mcp.errors import McpConnectionError, McpNotConnectedError, McpTimeoutError
from harness.secrets import SecretNotFound, SecretRefused
from harness.session.repository import (
    SessionCorruptionError,
    SessionFormatUnsupportedError,
    SessionNotFoundError,
)
from harness.skills import InvalidSkill, SkillNotEditable, SkillShadowed, UnreadableFile
from harness.web.errors import STATUS_OF, exception_handlers
from tests.integration.web_helpers import build
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import no_skills
from tests.webapp import web_app

PINNED = [
    pytest.param(BotNotFound("nope"), 404, id="BotNotFound"),
    pytest.param(BotPermanent(ASSISTANT_ID), 409, id="BotPermanent"),
    pytest.param(FileTooLarge("notes.txt", 1024), 413, id="FileTooLarge"),
    pytest.param(GroupEmpty("team"), 409, id="GroupEmpty"),
    pytest.param(InvalidSkill("description is required"), 422, id="InvalidSkill"),
    pytest.param(McpConnectionError("connection refused"), 502, id="McpConnectionError"),
    pytest.param(McpNotConnectedError("stub is not connected"), 503, id="McpNotConnectedError"),
    pytest.param(McpTimeoutError("stub stopped answering"), 502, id="McpTimeoutError"),
    pytest.param(SecretNotFound("GITHUB_TOKEN"), 404, id="SecretNotFound"),
    pytest.param(
        SecretRefused("20 keys are already saved; remove one first"), 409, id="SecretRefused"
    ),
    pytest.param(
        SessionCorruptionError("chat.jsonl: empty log, no header"),
        500,
        id="SessionCorruptionError",
    ),
    pytest.param(
        SessionFormatUnsupportedError("chat.jsonl: format version 0, this build reads 1"),
        500,
        id="SessionFormatUnsupportedError",
    ),
    pytest.param(SessionNotFoundError("no stored session 'nope'"), 404, id="SessionNotFoundError"),
    pytest.param(SkillNotEditable("pdf", Path("/project/skills")), 409, id="SkillNotEditable"),
    pytest.param(SkillShadowed("notes", Path("/project/skills/notes")), 409, id="SkillShadowed"),
    pytest.param(UnreadableFile("'big.txt' is not a text file"), 422, id="UnreadableFile"),
    pytest.param(UnsafeFileName("'..' does not name a file"), 422, id="UnsafeFileName"),
]


def app_raising(err: Exception) -> FastAPI:
    """An app built with the handlers, whose one route raises `err` and catches nothing."""
    app = FastAPI(exception_handlers=exception_handlers())

    @app.get("/")
    async def uncaught() -> None:
        raise err

    return app


async def answer_of(app: FastAPI) -> httpx.Response:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        return await c.get("/")


def test_every_mapped_error_is_pinned() -> None:
    assert {type(param.values[0]) for param in PINNED} == set(STATUS_OF)


@pytest.mark.parametrize(("err", "status_code"), PINNED)
async def test_a_mapped_error_answers_its_status_and_its_message(
    err: Exception, status_code: int
) -> None:
    response = await answer_of(app_raising(err))

    assert response.status_code == status_code
    assert response.json() == {"detail": str(err)}


async def test_a_mapped_error_answers_exactly_as_the_http_exception_it_replaces() -> None:
    err = BotNotFound("nope")

    mapped = await answer_of(app_raising(err))
    replaced = await answer_of(app_raising(HTTPException(404, detail=str(err))))

    assert mapped.status_code == replaced.status_code
    assert mapped.headers == replaced.headers
    assert mapped.content == replaced.content


async def test_a_route_that_does_not_catch_a_mapped_error_answers_its_mapped_status(
    tmp_path,
) -> None:
    service, runs = build(tmp_path, ScriptedClient(completed("hi")))
    app = web_app(tmp_path, service, runs, skills=no_skills())

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        response = await c.post("/api/bots/nope/restore")

    assert response.status_code == 404
    assert response.json() == {"detail": str(BotNotFound("nope"))}
