"""`POST /api/conversations/{id}/compact` — the person asks to compact now."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Response, status

from harness.channels.web.channel import WebChannel
from harness.channels.web.routes import chat_router
from harness.runs.service import RunAlreadyActive
from harness.runtime.compaction import CompactionRefused

logger = logging.getLogger("harness.web")


def build_router(web: WebChannel) -> APIRouter:
    router = chat_router(web, tag="compaction")

    @router.post("/{conversation_id}/compact", status_code=status.HTTP_202_ACCEPTED)
    async def compact(conversation_id: str) -> Response:
        if web.runs.active(conversation_id) is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail=f"{conversation_id!r} is running a turn"
            )
        session = await web.sessions.resume(conversation_id)
        try:
            web.gateway.compact(session, ())
        except CompactionRefused as err:
            raise HTTPException(status.HTTP_409_CONFLICT, detail=err.reason) from err
        except RunAlreadyActive as err:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail=f"{conversation_id!r} is running a turn"
            ) from err
        logger.info("conversation %s compacted by the browser", conversation_id)
        return Response(status_code=status.HTTP_202_ACCEPTED)

    return router
