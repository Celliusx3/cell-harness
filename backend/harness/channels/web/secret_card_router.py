"""Where the person saves a key the assistant asked for; the model gets back only its name."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import ValidationError

from harness.bots import Bot, BotNotFound
from harness.channels.web.channel import WebChannel
from harness.channels.web.routes import chat_router
from harness.channels.web.secret_card_schemas import Entered, ModelEntry, SecretEntry
from harness.runs.run import RunAlreadyActive
from harness.secrets import SECRET_VALUE_RULE, SecretService
from harness.secrets.domain.details import CustomDetails
from harness.secrets.service.credential_effects import CredentialEffects
from harness.session.log import Session
from harness.tools import Ok
from harness.tools.client import ClientToolService
from harness.tools.native.secrets import ASK_FOR_SECRET, SavedName, SecretAsk

logger = logging.getLogger(__name__)


def build_router(
    web: WebChannel,
    client_tools: ClientToolService,
    secrets: SecretService,
    effects: CredentialEffects,
) -> APIRouter:
    """The card's save: the key is stored by its kind, the waiting call gets its name."""
    router = chat_router(web, tag="secrets")

    @router.post(
        "/{conversation_id}/calls/{call_id}/secret", status_code=status.HTTP_204_NO_CONTENT
    )
    async def save_secret(conversation_id: str, call_id: str, request: Request) -> Response:
        if web.runs.active(conversation_id) is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail=f"{conversation_id!r} is running a turn"
            )
        session = await web.sessions.resume(conversation_id)
        ask = _waiting_ask(client_tools, session, call_id)
        entered = _entered(ask, await request.body())
        match entered.details:
            case CustomDetails(destination=destination):
                bot = _asker(web, session, call_id)
                secrets.save(ask.name, destination, entered.value)
                web.bots.allow_secret(bot.id, ask.name)
            case details:
                secrets.add_credential(ask.name, details, entered.value)
                await effects.added(ask.name, details, ())
        try:
            saved = SavedName(name=ask.name, kind=ask.kind)
            await web.gateway.resume(session, call_id, Ok(content=saved.model_dump_json()))
        except RunAlreadyActive as err:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail=f"call {call_id!r} was already answered"
            ) from err
        logger.info("%s key %r for %s saved by the browser", ask.kind, ask.name, conversation_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router


def _asker(web: WebChannel, session: Session, call_id: str) -> Bot:
    """The bot whose turn asked for `call_id`, which a website key is tied to; a 409 if none."""
    try:
        return web.runs.groups.asker(session, call_id)
    except BotNotFound as err:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(err)) from err


def _waiting_ask(client_tools: ClientToolService, session: Session, call_id: str) -> SecretAsk:
    """The `ask_for_secret` call `call_id` still waiting in `session`; a 404 for any other."""
    asked = next(
        (
            pending
            for pending in client_tools.answerable_calls(session)
            if pending.call_id == call_id and pending.name == ASK_FOR_SECRET
        ),
        None,
    )
    if asked is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"call {call_id!r} is not waiting for a key"
        )
    return SecretAsk.model_validate_json(asked.arguments)


def _entered(ask: SecretAsk, raw: bytes) -> Entered:
    """The card's body for `ask`: an LLM's fields as edited, any other kind's as asked; a 422."""
    try:
        if ask.kind == "llm":
            model = ModelEntry.model_validate_json(raw)
            return Entered(model.details, model.value)
        return Entered(ask.details, SecretEntry.model_validate_json(raw).value)
    except ValidationError as err:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=_refusal(err)) from None


def _refusal(err: ValidationError) -> str:
    """The rule each refused field broke, never what was typed in it."""
    errors = err.errors(include_url=False, include_input=False)
    if any(error["loc"][:1] == ("value",) for error in errors):
        return SECRET_VALUE_RULE
    return "; ".join(str(error["msg"]).removeprefix("Value error, ") for error in errors)
