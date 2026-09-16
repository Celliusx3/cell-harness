"""Where a browser answers a client tool — Vercel's `addToolOutput`, as a route.

One route for every client tool. The page saw the `tool/call` on the stream;
it posts the output to that call's id, and a new turn opens with that output
as the call's result. Nothing was waiting: the conversation was idle with a
pending call in its log, and this is what ends the pending.

Whether the call may be answered, and with what, is the service's to decide
— the same checks a chat's answer goes through; this route turns its answer
into a status code and opens the turn.
"""

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
    """Bound to the browser's channel, like its other routes: the resume goes
    through the gateway so every chat mapped to the conversation is told."""
    router = APIRouter(prefix="/api/conversations", tags=["client-tools"])

    @router.post(
        "/{conversation_id}/calls/{call_id}/output", status_code=status.HTTP_204_NO_CONTENT
    )
    async def tool_output(conversation_id: str, call_id: str, body: dict[str, object]) -> Response:
        # A JSON object and nothing more is asked of FastAPI; the shape is
        # the pending tool's declaration, checked by the service.
        if web.runs.active(conversation_id) is not None:
            # Either this answer is already being carried, or the person
            # typed and the call was skipped. The stream says which.
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail=f"{conversation_id!r} is running a turn"
            )
        try:
            # For writing: the resumed turn appends, and crash repair — which
            # leaves a pending turn's call alone — has to have run.
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
