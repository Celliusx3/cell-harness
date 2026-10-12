"""Where the person saves a key the assistant asked for; the model gets back only its name."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, ValidationError

from harness.bots import BotNotFound
from harness.channels.web.channel import WebChannel
from harness.channels.web.routes import chat_router
from harness.runs.service import RunAlreadyActive
from harness.secrets import SECRET_VALUE_RULE, SecretRefused, SecretService, SecretValue
from harness.session.repository import SessionNotFoundError
from harness.tools.client import ClientToolService
from harness.tools.definition import Ok
from harness.tools.native.secrets import ASK_FOR_SECRET, SavedName, SecretAsk

logger = logging.getLogger(__name__)


class SecretEntry(BaseModel):
    """The key the person typed on the card."""

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    value: SecretValue


def build_router(
    web: WebChannel, client_tools: ClientToolService, secrets: SecretService
) -> APIRouter:
    """The card's save: the key is sealed, the bot may use it, the waiting call gets its name."""
    router = chat_router(web, tag="secrets")

    @router.post(
        "/{conversation_id}/calls/{call_id}/secret", status_code=status.HTTP_204_NO_CONTENT
    )
    async def save_secret(conversation_id: str, call_id: str, request: Request) -> Response:
        try:
            entry = SecretEntry.model_validate_json(await request.body())
        except ValidationError:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, detail=SECRET_VALUE_RULE
            ) from None
        if web.runs.active(conversation_id) is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail=f"{conversation_id!r} is running a turn"
            )
        try:
            session = await web.sessions.resume(conversation_id)
        except SessionNotFoundError as err:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(err)) from err
        asked = next(
            (
                pending
                for pending in client_tools.pending(session)
                if pending.call_id == call_id and pending.name == ASK_FOR_SECRET
            ),
            None,
        )
        if asked is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail=f"call {call_id!r} is not waiting for a key"
            )
        ask = SecretAsk.model_validate_json(asked.arguments)
        try:
            bot = web.bots.asker(session, call_id)
        except BotNotFound as err:
            raise HTTPException(status.HTTP_409_CONFLICT, detail=str(err)) from err
        try:
            secrets.save(ask.name, ask.destination, entry.value)
        except SecretRefused as err:
            raise HTTPException(status.HTTP_409_CONFLICT, detail=str(err)) from err
        web.bots.allow_secret(bot.id, ask.name)
        try:
            await web.gateway.resume(
                session, call_id, Ok(content=SavedName(name=ask.name).model_dump_json())
            )
        except RunAlreadyActive as err:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail=f"call {call_id!r} was already answered"
            ) from err
        logger.info("key %r for %s saved by the browser", ask.name, conversation_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
