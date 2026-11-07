"""The Credentials page: every credential with its bots, added, changed or removed from this Mac."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, model_validator

from harness.bots import Bot, BotNotFound, BotService, served_bots
from harness.mcp import McpService
from harness.secrets import (
    SavedCredential,
    SecretName,
    SecretNotFound,
    SecretRefused,
    SecretService,
    SecretValue,
)
from harness.secrets.models.details import (
    CapabilityDetails,
    ChatPlatformDetails,
    CredentialDetails,
    ModelDetails,
)
from harness.web.credential_effects import CredentialEffects
from harness.web.platforms import PlatformChannels
from harness.web.this_mac import (
    cors_headers,
    parsed_body,
    permitted_write_headers,
    refusals_answered_with,
)

logger = logging.getLogger(__name__)

REFUSED = (BotNotFound, SecretNotFound, SecretRefused)
PLATFORM_SERVES_NO_BOTS = "a Telegram or Discord credential serves no bots; tick none"
CAPABILITY_SERVES_NO_BOTS = "a capability key serves its capability, not bots; tick none"
MODEL_PICKED_IN_EDIT_BOT = "a bot's model is picked in Edit bot; tick none"


class BotRef(BaseModel):
    """A bot a credential serves: its id and the name the sidebar shows."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    name: str


class CredentialEntry(SavedCredential):
    """One credential as the Credentials page lists it, with the bots it serves."""

    bots: tuple[BotRef, ...]


class CredentialList(BaseModel):
    """Every credential by name, and the address to save at."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    credentials: tuple[CredentialEntry, ...]
    direct_url: str


class NewCredential(BaseModel):
    """A credential typed into the dialog: its name, what it is for, its key, and its bots."""

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    name: SecretName
    details: CredentialDetails
    value: SecretValue
    bot_ids: tuple[str, ...]

    @model_validator(mode="after")
    def _serves_bots_only_if_a_key_for_them(self) -> NewCredential:
        _refuse_bots_where_none_served(self.details, self.bot_ids)
        return self


class CredentialChange(BaseModel):
    """An edit from the dialog: what it is for, a new key or `None` to keep it, and its bots."""

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    details: CredentialDetails
    value: SecretValue | None
    bot_ids: tuple[str, ...]

    @model_validator(mode="after")
    def _serves_bots_only_if_a_key_for_them(self) -> CredentialChange:
        _refuse_bots_where_none_served(self.details, self.bot_ids)
        return self


def build_router(
    secrets: SecretService,
    bots: BotService,
    platforms: PlatformChannels,
    mcp: McpService,
) -> APIRouter:
    """List the keyring's credentials with their bots; add, change and remove one from this Mac."""
    router = APIRouter(prefix="/api/credentials", tags=["credentials"])
    effects = CredentialEffects(bots, platforms, mcp)

    @router.get("", response_model=CredentialList)
    async def list_credentials(request: Request, response: Response) -> CredentialList:
        response.headers.update(cors_headers(request))
        saved = await asyncio.to_thread(secrets.saved_credentials)
        active = await bots.active_bots()
        return CredentialList(
            credentials=tuple(_credential_entry(credential, active) for credential in saved),
            direct_url=_direct_url(request),
        )

    @router.options("")
    @router.options("/{name}")
    async def answer_preflight(request: Request) -> Response:
        """A page on this Mac may write here; any other page gets no permission."""
        return Response(status_code=status.HTTP_204_NO_CONTENT, headers=cors_headers(request))

    @router.post("", status_code=status.HTTP_201_CREATED)
    async def add_credential(request: Request) -> Response:
        headers = permitted_write_headers(request)
        body = parsed_body(NewCredential, await request.body(), headers)
        _refuse_unneeded_capability_key(effects, body.details, headers)
        with refusals_answered_with(headers, REFUSED):
            _refuse_inactive_bots(bots, body.bot_ids)
            await asyncio.to_thread(secrets.add_credential, body.name, body.details, body.value)
        await effects.added(body.name, body.details, body.bot_ids)
        logger.info("credential %r added for bots %s", body.name, list(body.bot_ids))
        return Response(status_code=status.HTTP_201_CREATED, headers=headers)

    @router.patch("/{name}")
    async def change_credential(name: str, request: Request) -> Response:
        headers = permitted_write_headers(request)
        body = parsed_body(CredentialChange, await request.body(), headers)
        _refuse_unneeded_capability_key(effects, body.details, headers)
        with refusals_answered_with(headers, REFUSED):
            _refuse_inactive_bots(bots, body.bot_ids)
            replaced = await asyncio.to_thread(
                secrets.change_credential, name, body.details, body.value
            )
        await effects.changed(
            name, replaced, body.details, bot_ids=body.bot_ids, is_new_key=body.value is not None
        )
        logger.info("credential %r changed for bots %s", name, list(body.bot_ids))
        return Response(status_code=status.HTTP_200_OK, headers=headers)

    @router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
    async def remove_credential(name: str, request: Request) -> Response:
        headers = permitted_write_headers(request)
        with refusals_answered_with(headers, REFUSED):
            removed = secrets.delete(name)
        await effects.removed(name, removed)
        logger.info("credential %r removed from the keyring and every bot", name)
        return Response(status_code=status.HTTP_204_NO_CONTENT, headers=headers)

    return router


def _refuse_bots_where_none_served(details: CredentialDetails, bot_ids: tuple[str, ...]) -> None:
    if not bot_ids:
        return
    if isinstance(details, ChatPlatformDetails):
        raise ValueError(PLATFORM_SERVES_NO_BOTS)
    if isinstance(details, CapabilityDetails):
        raise ValueError(CAPABILITY_SERVES_NO_BOTS)
    if isinstance(details, ModelDetails):
        raise ValueError(MODEL_PICKED_IN_EDIT_BOT)


def _refuse_unneeded_capability_key(
    effects: CredentialEffects, details: CredentialDetails, headers: dict[str, str]
) -> None:
    """A 422 for a capability key its server is not configured to need, before anything is saved."""
    refusal = effects.capability_refusal(details)
    if refusal is not None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=refusal, headers=headers)


def _credential_entry(credential: SavedCredential, active: tuple[Bot, ...]) -> CredentialEntry:
    served = served_bots(active, credential.name, credential.details.kind)
    return CredentialEntry(
        name=credential.name,
        details=credential.details,
        last_four=credential.last_four,
        bots=tuple(BotRef(id=bot.id, name=bot.name) for bot in served),
    )


def _refuse_inactive_bots(bots: BotService, bot_ids: tuple[str, ...]) -> None:
    """`BotNotFound` for a ticked bot that is not active, before anything is saved."""
    for bot_id in bot_ids:
        bots.active_bot(bot_id)


def _direct_url(request: Request) -> str:
    """The address the harness itself listens on."""
    server = request.scope.get("server")
    if server is None:
        return str(request.base_url).rstrip("/")
    host, port = server
    return f"http://{f'[{host}]' if ':' in host else host}:{port}"
