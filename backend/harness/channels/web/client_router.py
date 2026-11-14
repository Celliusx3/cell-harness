"""Where a browser answers a client tool — Vercel's `addToolOutput`, as a route."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Response, status

from harness.bots import BotNotFound
from harness.channels.web.channel import WebChannel
from harness.channels.web.conversation_router import chat_router
from harness.runs.service.run import RunAlreadyActiveError
from harness.tools.client import ClientToolService, RefusalReason

logger = logging.getLogger(__name__)

REFUSAL_STATUS = {
    RefusalReason.NOT_PENDING: status.HTTP_404_NOT_FOUND,
    RefusalReason.DOES_NOT_FIT: status.HTTP_422_UNPROCESSABLE_CONTENT,
}


class ClientToolRouter:
    """The browser's answer to a client tool, resumed through the gateway."""

    def __init__(self, web: WebChannel, client_tools: ClientToolService) -> None:
        self._web = web
        self._client_tools = client_tools
        self.router: APIRouter = chat_router(web, tag="client-tools")
        self.router.add_api_route(
            "/{conversation_id}/calls/{call_id}/output",
            self.tool_output,
            methods=["POST"],
            status_code=status.HTTP_204_NO_CONTENT,
        )

    async def tool_output(
        self, conversation_id: str, call_id: str, body: dict[str, object]
    ) -> Response:
        if self._web.runs.active_run(conversation_id) is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail=f"{conversation_id!r} is running a turn"
            )
        session = await self._web.sessions.resume(conversation_id)
        verdict = self._client_tools.accept_by_call_id(session, call_id, body)
        if isinstance(verdict, RefusalReason):
            raise HTTPException(
                REFUSAL_STATUS[verdict], detail=f"call {call_id!r}: {verdict.value}"
            )
        try:
            await self._web.gateway.resume(session, verdict.call_id, verdict.outcome)
        except RunAlreadyActiveError as err:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail=f"call {call_id!r} was already answered"
            ) from err
        except BotNotFound as err:
            raise HTTPException(status.HTTP_409_CONFLICT, detail=str(err)) from err
        logger.info("call %s in %s answered by the browser", call_id, conversation_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
