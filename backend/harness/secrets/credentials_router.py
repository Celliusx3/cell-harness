"""The Credentials page: every credential with its bots, added, changed or removed from this Mac."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request, Response, status

from harness.bots import Bot, BotNotFound, BotService
from harness.channels.platforms import PlatformChannels
from harness.secrets import SavedCredential, SecretNotFound, SecretRefused, SecretService
from harness.secrets.credential_effects import CredentialEffects
from harness.secrets.credentials_schemas import (
    BotRef,
    CredentialChange,
    CredentialEntry,
    CredentialList,
    NewCredential,
)
from harness.web.http.this_mac import (
    cors_headers,
    parsed_body,
    permitted_write_headers,
    refusals_answered_with,
)

logger = logging.getLogger(__name__)

REFUSED = (BotNotFound, SecretNotFound, SecretRefused)


def build_router(
    secrets: SecretService,
    bots: BotService,
    platforms: PlatformChannels,
) -> APIRouter:
    """List the keyring's credentials with their bots; add, change and remove one from this Mac."""
    router = APIRouter(prefix="/api/credentials", tags=["credentials"])
    effects = CredentialEffects(bots, platforms)

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
        with refusals_answered_with(headers, REFUSED):
            _refuse_inactive_bots(bots, body.bot_ids)
            await asyncio.to_thread(secrets.change_credential, name, body.details, body.value)
        await effects.changed(
            name, body.details, bot_ids=body.bot_ids, is_new_key=body.value is not None
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


def _credential_entry(credential: SavedCredential, active: tuple[Bot, ...]) -> CredentialEntry:
    served = tuple(bot for bot in active if bot.serves(credential.name, credential.details.kind))
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
