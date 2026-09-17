"""`POST /api/conversations/{id}/compact` — the person asks to compact now.

Bound to the browser's channel like the client-answer route, and for the same
reason it goes through the gateway: every chat mapped to the conversation is
told, and the busy check and the stream come with being a run. The compaction service
refuses out loud when there is nothing to do or a client request is still
open; those become a `409`, not an empty bracket in the log.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Response, status

from harness.agent.compaction import CompactionRefused
from harness.channels.web.channel import WebChannel
from harness.runs.store import RunAlreadyActive
from harness.session.repository import SessionNotFoundError

logger = logging.getLogger("harness.web")


def build_router(web: WebChannel) -> APIRouter:
    router = APIRouter(prefix="/api/conversations", tags=["compaction"])

    @router.post("/{conversation_id}/compact", status_code=status.HTTP_202_ACCEPTED)
    async def compact(conversation_id: str) -> Response:
        if web.runs.active(conversation_id) is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail=f"{conversation_id!r} is running a turn"
            )
        try:
            # For writing: the compaction appends, so crash repair must have run.
            session = await web.sessions.resume(conversation_id)
        except SessionNotFoundError as err:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(err)) from err
        try:
            await web.gateway.compact(session)
        except CompactionRefused as err:
            # `nothing to compact` / a pending client call: nothing changed and
            # the caller asked for a change, so a 409 with the reason.
            raise HTTPException(status.HTTP_409_CONFLICT, detail=err.reason) from err
        except RunAlreadyActive as err:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail=f"{conversation_id!r} is running a turn"
            ) from err
        logger.info("conversation %s compacted by the browser", conversation_id)
        return Response(status_code=status.HTTP_202_ACCEPTED)

    return router
