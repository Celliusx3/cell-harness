"""`POST /api/conversations/{id}/compact` — the person asks to compact now."""

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
            session = await web.sessions.resume(conversation_id)
        except SessionNotFoundError as err:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(err)) from err
        try:
            await web.gateway.compact(session)
        except CompactionRefused as err:
            raise HTTPException(status.HTTP_409_CONFLICT, detail=err.reason) from err
        except RunAlreadyActive as err:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail=f"{conversation_id!r} is running a turn"
            ) from err
        logger.info("conversation %s compacted by the browser", conversation_id)
        return Response(status_code=status.HTTP_202_ACCEPTED)

    return router
