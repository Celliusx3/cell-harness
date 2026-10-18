"""Where a browser answers a client tool — Vercel's `addToolOutput`, as a route."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Response, status

from harness.bots import BotNotFound
from harness.channels.web.channel import WebChannel
from harness.channels.web.routes import chat_router
from harness.runs.service import RunAlreadyActive
from harness.tools.client import ClientToolService, RefusalReason

logger = logging.getLogger(__name__)

STATUS = {
    RefusalReason.NOT_PENDING: status.HTTP_404_NOT_FOUND,
    RefusalReason.DOES_NOT_FIT: status.HTTP_422_UNPROCESSABLE_CONTENT,
}


def build_router(web: WebChannel, client_tools: ClientToolService) -> APIRouter:
    """The browser's answer to a client tool, resumed through the gateway."""
    router = chat_router(web, tag="client-tools")

    @router.post(
        "/{conversation_id}/calls/{call_id}/output", status_code=status.HTTP_204_NO_CONTENT
    )
    async def tool_output(conversation_id: str, call_id: str, body: dict[str, object]) -> Response:
        if web.runs.active(conversation_id) is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail=f"{conversation_id!r} is running a turn"
            )
        session = await web.sessions.resume(conversation_id)
        verdict = client_tools.accept_by_call_id(session, call_id, body)
        if isinstance(verdict, RefusalReason):
            raise HTTPException(STATUS[verdict], detail=f"call {call_id!r}: {verdict.value}")
        try:
            await web.gateway.resume(session, verdict.call_id, verdict.outcome)
        except RunAlreadyActive as err:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail=f"call {call_id!r} was already answered"
            ) from err
        except BotNotFound as err:
            raise HTTPException(status.HTTP_409_CONFLICT, detail=str(err)) from err
        logger.info("call %s in %s answered by the browser", call_id, conversation_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
