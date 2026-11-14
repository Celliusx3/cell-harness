"""`POST /api/conversations/{id}/compact` — the person asks to compact now."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Response, status

from harness.channels.web.channel import WebChannel
from harness.channels.web.conversation_router import chat_router
from harness.runs.service.run import RunAlreadyActive
from harness.runtime.compaction import CompactionRefused

logger = logging.getLogger("harness.web")


class CompactRouter:
    """The person's ask to compact a chat now, refused while it runs a turn."""

    def __init__(self, web: WebChannel) -> None:
        self._web = web
        self.router: APIRouter = chat_router(web, tag="compaction")
        self.router.add_api_route(
            "/{conversation_id}/compact",
            self.compact,
            methods=["POST"],
            status_code=status.HTTP_202_ACCEPTED,
        )

    async def compact(self, conversation_id: str) -> Response:
        if self._web.runs.active(conversation_id) is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail=f"{conversation_id!r} is running a turn"
            )
        session = await self._web.sessions.resume(conversation_id)
        try:
            self._web.gateway.compact(session, ())
        except CompactionRefused as err:
            raise HTTPException(status.HTTP_409_CONFLICT, detail=err.reason) from err
        except RunAlreadyActive as err:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail=f"{conversation_id!r} is running a turn"
            ) from err
        logger.info("conversation %s compacted by the browser", conversation_id)
        return Response(status_code=status.HTTP_202_ACCEPTED)
