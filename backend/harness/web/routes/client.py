"""Where a browser answers a client tool — Vercel's `addToolOutput`, as a route."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Response, status

from harness.channels.web.channel import WebChannel
from harness.runs.store import RunAlreadyActive
from harness.session.repository import SessionNotFoundError
from harness.tools.client import ClientToolService, Refused

logger = logging.getLogger(__name__)

STATUS = {
    Refused.NOT_PENDING: status.HTTP_404_NOT_FOUND,
    Refused.DOES_NOT_FIT: status.HTTP_422_UNPROCESSABLE_CONTENT,
}


def build_router(web: WebChannel, client_tools: ClientToolService) -> APIRouter:
    """The browser's answer to a client tool, resumed through the gateway."""
    router = APIRouter(prefix="/api/conversations", tags=["client-tools"])

    @router.post(
        "/{conversation_id}/calls/{call_id}/output", status_code=status.HTTP_204_NO_CONTENT
    )
    async def tool_output(conversation_id: str, call_id: str, body: dict[str, object]) -> Response:
        if web.runs.active(conversation_id) is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail=f"{conversation_id!r} is running a turn"
            )
        try:
            session = await web.sessions.resume(conversation_id)
        except SessionNotFoundError as err:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(err)) from err
        accepted = client_tools.accept_call(session, call_id, body)
        if isinstance(accepted, Refused):
            raise HTTPException(STATUS[accepted], detail=f"call {call_id!r}: {accepted.value}")
        try:
            await web.gateway.resume(session, accepted.call_id, accepted.outcome)
        except RunAlreadyActive as err:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail=f"call {call_id!r} was already answered"
            ) from err
        logger.info("call %s in %s answered by the browser", call_id, conversation_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
