"""Each domain error a route lets through, answered with its usual HTTP status."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from types import MappingProxyType

from fastapi import Request, status
from fastapi.responses import JSONResponse

from harness.bots import BotNotFound, BotPermanent, GroupEmpty
from harness.files import FileTooLarge, UnsafeFileName
from harness.mcp.errors import McpConnectionError, McpNotConnectedError, McpTimeoutError
from harness.secrets import SecretNotFound, SecretRefused
from harness.session.repository import (
    SessionCorruptionError,
    SessionFormatUnsupportedError,
    SessionNotFoundError,
)
from harness.skills import InvalidSkill, SkillNotEditable, SkillShadowed, UnreadableFile
from harness.tools import NotGranted

ErrorHandler = Callable[[Request, Exception], Awaitable[JSONResponse]]

STATUS_OF: Mapping[type[Exception], int] = MappingProxyType(
    {
        BotNotFound: status.HTTP_404_NOT_FOUND,
        BotPermanent: status.HTTP_409_CONFLICT,
        FileTooLarge: status.HTTP_413_CONTENT_TOO_LARGE,
        GroupEmpty: status.HTTP_409_CONFLICT,
        InvalidSkill: status.HTTP_422_UNPROCESSABLE_CONTENT,
        McpConnectionError: status.HTTP_502_BAD_GATEWAY,
        McpNotConnectedError: status.HTTP_503_SERVICE_UNAVAILABLE,
        McpTimeoutError: status.HTTP_502_BAD_GATEWAY,
        NotGranted: status.HTTP_404_NOT_FOUND,
        SecretNotFound: status.HTTP_404_NOT_FOUND,
        SecretRefused: status.HTTP_409_CONFLICT,
        SessionCorruptionError: status.HTTP_500_INTERNAL_SERVER_ERROR,
        SessionFormatUnsupportedError: status.HTTP_500_INTERNAL_SERVER_ERROR,
        SessionNotFoundError: status.HTTP_404_NOT_FOUND,
        SkillNotEditable: status.HTTP_409_CONFLICT,
        SkillShadowed: status.HTTP_409_CONFLICT,
        UnreadableFile: status.HTTP_422_UNPROCESSABLE_CONTENT,
        UnsafeFileName: status.HTTP_422_UNPROCESSABLE_CONTENT,
    }
)


def _answer_with(status_code: int) -> ErrorHandler:
    """A handler answering an error's message with `status_code`, the body `HTTPException` has."""

    async def answer(request: Request, err: Exception) -> JSONResponse:
        return JSONResponse({"detail": str(err)}, status_code=status_code)

    return answer


def exception_handlers() -> dict[type[Exception], ErrorHandler]:
    """What `FastAPI(exception_handlers=...)` takes: one handler per error in `STATUS_OF`."""
    return {error: _answer_with(status_code) for error, status_code in STATUS_OF.items()}
