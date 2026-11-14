"""Each domain error a route lets through, answered with its usual HTTP status."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from types import MappingProxyType

from fastapi import Request, status
from fastapi.responses import JSONResponse

from harness.bots import BotNotFound, BuiltInBotError, EmptyGroupError
from harness.files import FileTooLarge, UnsafeFileName
from harness.mcp import (
    McpConnectionError,
    McpNotConnectedError,
    McpServerNotFound,
    McpServerTaken,
    McpTimeoutError,
)
from harness.schedules import InvalidSchedule, ScheduleBusyError, ScheduleNotFound
from harness.secrets import SecretNotFound, SecretRefused
from harness.session.repository.session_repository import (
    SessionCorruptionError,
    SessionFormatUnsupportedError,
    SessionNotFoundError,
)
from harness.skills import InvalidSkill, SkillNotEditable, SkillShadowed, UnreadableFile
from harness.tickets.domain.models import (
    TicketNotAsking,
    TicketNotFound,
    TicketNotRetryable,
    TicketStopped,
)
from harness.tools import ToolNotApproved

ErrorHandler = Callable[[Request, Exception], Awaitable[JSONResponse]]

STATUS_OF: Mapping[type[Exception], int] = MappingProxyType(
    {
        BotNotFound: status.HTTP_404_NOT_FOUND,
        BuiltInBotError: status.HTTP_409_CONFLICT,
        FileTooLarge: status.HTTP_413_CONTENT_TOO_LARGE,
        EmptyGroupError: status.HTTP_409_CONFLICT,
        InvalidSchedule: status.HTTP_422_UNPROCESSABLE_CONTENT,
        InvalidSkill: status.HTTP_422_UNPROCESSABLE_CONTENT,
        McpConnectionError: status.HTTP_502_BAD_GATEWAY,
        McpNotConnectedError: status.HTTP_503_SERVICE_UNAVAILABLE,
        McpServerNotFound: status.HTTP_404_NOT_FOUND,
        McpServerTaken: status.HTTP_409_CONFLICT,
        McpTimeoutError: status.HTTP_502_BAD_GATEWAY,
        ToolNotApproved: status.HTTP_404_NOT_FOUND,
        ScheduleBusyError: status.HTTP_409_CONFLICT,
        ScheduleNotFound: status.HTTP_404_NOT_FOUND,
        SecretNotFound: status.HTTP_404_NOT_FOUND,
        SecretRefused: status.HTTP_409_CONFLICT,
        SessionCorruptionError: status.HTTP_500_INTERNAL_SERVER_ERROR,
        SessionFormatUnsupportedError: status.HTTP_500_INTERNAL_SERVER_ERROR,
        SessionNotFoundError: status.HTTP_404_NOT_FOUND,
        SkillNotEditable: status.HTTP_409_CONFLICT,
        SkillShadowed: status.HTTP_409_CONFLICT,
        TicketNotAsking: status.HTTP_409_CONFLICT,
        TicketNotFound: status.HTTP_404_NOT_FOUND,
        TicketNotRetryable: status.HTTP_409_CONFLICT,
        TicketStopped: status.HTTP_409_CONFLICT,
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
