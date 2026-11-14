"""Where the person saves a key the assistant asked for; the model gets back only its name."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import ValidationError

from harness.bots import Bot, BotNotFound
from harness.channels.web.channel import WebChannel
from harness.channels.web.conversation_router import chat_router
from harness.channels.web.secret_card_schemas import EnteredSecret, ModelEntry, SecretEntry
from harness.runs.service.run import RunAlreadyActiveError
from harness.secrets import SECRET_VALUE_RULE, SecretService
from harness.secrets.domain.details import CustomDetails
from harness.secrets.service.credential_effects import CredentialEffects
from harness.session.domain.log import Session
from harness.tools import Ok
from harness.tools.client import ClientToolService
from harness.tools.native.secrets import ASK_FOR_SECRET, SavedName, SecretAsk

logger = logging.getLogger(__name__)


class SecretCardRouter:
    """The card's save: the key is stored by its kind, the waiting call gets its name."""

    def __init__(
        self,
        web: WebChannel,
        client_tools: ClientToolService,
        secrets: SecretService,
        effects: CredentialEffects,
    ) -> None:
        self._web = web
        self._client_tools = client_tools
        self._secrets = secrets
        self._effects = effects
        self.router: APIRouter = chat_router(web, tag="secrets")
        self.router.add_api_route(
            "/{conversation_id}/calls/{call_id}/secret",
            self.save_secret,
            methods=["POST"],
            status_code=status.HTTP_204_NO_CONTENT,
        )

    async def save_secret(self, conversation_id: str, call_id: str, request: Request) -> Response:
        if self._web.runs.active_run(conversation_id) is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail=f"{conversation_id!r} is running a turn"
            )
        session = await self._web.sessions.resume(conversation_id)
        ask = self._waiting_ask(session, call_id)
        entered = _entered_secret(ask, await request.body())
        match entered.details:
            case CustomDetails(destination=destination):
                bot = self._calling_bot(session, call_id)
                self._secrets.save(ask.name, destination, entered.value)
                self._web.bots.allow_secret(bot.id, ask.name)
            case details:
                self._secrets.add_credential(ask.name, details, entered.value)
                await self._effects.react_to_added(ask.name, details, ())
        try:
            saved = SavedName(name=ask.name, kind=ask.kind)
            await self._web.gateway.resume(session, call_id, Ok(content=saved.model_dump_json()))
        except RunAlreadyActiveError as err:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail=f"call {call_id!r} was already answered"
            ) from err
        logger.info("%s key %r for %s saved by the browser", ask.kind, ask.name, conversation_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    def _calling_bot(self, session: Session, call_id: str) -> Bot:
        """The bot whose turn asked for `call_id`, which a website key is tied to; a 409 if none."""
        try:
            return self._web.runs.groups.calling_bot(session, call_id)
        except BotNotFound as err:
            raise HTTPException(status.HTTP_409_CONFLICT, detail=str(err)) from err

    def _waiting_ask(self, session: Session, call_id: str) -> SecretAsk:
        """The `ask_for_secret` call `call_id` still waiting in `session`; a 404 for any other."""
        asked = next(
            (
                pending
                for pending in self._client_tools.answerable_calls(session)
                if pending.call_id == call_id and pending.name == ASK_FOR_SECRET
            ),
            None,
        )
        if asked is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail=f"call {call_id!r} is not waiting for a key"
            )
        return SecretAsk.model_validate_json(asked.arguments)


def _entered_secret(ask: SecretAsk, raw: bytes) -> EnteredSecret:
    """The card's body for `ask`: an LLM's fields as edited, any other kind's as asked; a 422."""
    try:
        if ask.kind == "llm":
            model = ModelEntry.model_validate_json(raw)
            return EnteredSecret(model.details, model.value)
        return EnteredSecret(ask.details, SecretEntry.model_validate_json(raw).value)
    except ValidationError as err:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail=_refusal_detail(err)
        ) from None


def _refusal_detail(err: ValidationError) -> str:
    """The rule each refused field broke, never what was typed in it."""
    errors = err.errors(include_url=False, include_input=False)
    if any(error["loc"][:1] == ("value",) for error in errors):
        return SECRET_VALUE_RULE
    return "; ".join(str(error["msg"]).removeprefix("Value error, ") for error in errors)
