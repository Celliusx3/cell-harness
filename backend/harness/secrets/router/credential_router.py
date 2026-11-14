"""The Credentials page: every credential with its bots, added, changed or removed from this Mac."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request, Response, status

from harness.bots import Bot, BotNotFound, BotService
from harness.channels.service.platforms import PlatformChannels
from harness.secrets import SavedCredential, SecretNotFound, SecretRefused, SecretService
from harness.secrets.router.credential_schemas import (
    BotRef,
    CredentialChange,
    CredentialEntry,
    CredentialList,
    NewCredential,
)
from harness.secrets.service.credential_effects import CredentialEffects
from harness.web.http.this_mac import (
    cors_headers,
    parsed_body,
    permitted_write_headers,
    refusals_answered_with,
)

logger = logging.getLogger(__name__)

REFUSED = (BotNotFound, SecretNotFound, SecretRefused)


class CredentialRouter:
    """List the keyring's credentials with their bots; add, change and remove one from this Mac."""

    def __init__(
        self,
        secrets: SecretService,
        bots: BotService,
        platforms: PlatformChannels,
    ) -> None:
        self._secrets = secrets
        self._bots = bots
        self._effects = CredentialEffects(bots, platforms)
        self.router: APIRouter = APIRouter(prefix="/api/credentials", tags=["credentials"])
        self._add_reading_routes()
        self._add_writing_routes()

    def _add_reading_routes(self) -> None:
        """Listing the credentials, and answering a write's preflight."""
        self.router.add_api_route(
            "", self.list_credentials, methods=["GET"], response_model=CredentialList
        )
        self.router.add_api_route("/{name}", self.answer_preflight, methods=["OPTIONS"])
        self.router.add_api_route("", self.answer_preflight, methods=["OPTIONS"])

    def _add_writing_routes(self) -> None:
        """Adding, changing and removing a credential."""
        self.router.add_api_route(
            "", self.add_credential, methods=["POST"], status_code=status.HTTP_201_CREATED
        )
        self.router.add_api_route("/{name}", self.change_credential, methods=["PATCH"])
        self.router.add_api_route(
            "/{name}",
            self.remove_credential,
            methods=["DELETE"],
            status_code=status.HTTP_204_NO_CONTENT,
        )

    async def list_credentials(self, request: Request, response: Response) -> CredentialList:
        response.headers.update(cors_headers(request))
        saved = await asyncio.to_thread(self._secrets.saved_credentials)
        active = await self._bots.open_active_bots()
        return CredentialList(
            credentials=tuple(_credential_entry(credential, active) for credential in saved),
            direct_url=_direct_url(request),
        )

    async def answer_preflight(self, request: Request) -> Response:
        """A page on this Mac may write here; any other page gets no permission."""
        return Response(status_code=status.HTTP_204_NO_CONTENT, headers=cors_headers(request))

    async def add_credential(self, request: Request) -> Response:
        headers = permitted_write_headers(request)
        body = parsed_body(NewCredential, await request.body(), headers)
        with refusals_answered_with(headers, REFUSED):
            self._refuse_inactive_bots(body.bot_ids)
            await asyncio.to_thread(
                self._secrets.add_credential, body.name, body.details, body.value
            )
        await self._effects.added(body.name, body.details, body.bot_ids)
        logger.info("credential %r added for bots %s", body.name, list(body.bot_ids))
        return Response(status_code=status.HTTP_201_CREATED, headers=headers)

    async def change_credential(self, name: str, request: Request) -> Response:
        headers = permitted_write_headers(request)
        body = parsed_body(CredentialChange, await request.body(), headers)
        with refusals_answered_with(headers, REFUSED):
            self._refuse_inactive_bots(body.bot_ids)
            await asyncio.to_thread(self._secrets.change_credential, name, body.details, body.value)
        await self._effects.changed(
            name, body.details, bot_ids=body.bot_ids, is_new_key=body.value is not None
        )
        logger.info("credential %r changed for bots %s", name, list(body.bot_ids))
        return Response(status_code=status.HTTP_200_OK, headers=headers)

    async def remove_credential(self, name: str, request: Request) -> Response:
        headers = permitted_write_headers(request)
        with refusals_answered_with(headers, REFUSED):
            removed = self._secrets.delete(name)
        await self._effects.removed(name, removed)
        logger.info("credential %r removed from the keyring and every bot", name)
        return Response(status_code=status.HTTP_204_NO_CONTENT, headers=headers)

    def _refuse_inactive_bots(self, bot_ids: tuple[str, ...]) -> None:
        """`BotNotFound` for a ticked bot that is not active, before anything is saved."""
        for bot_id in bot_ids:
            self._bots.active_bot(bot_id)


def _credential_entry(credential: SavedCredential, active: tuple[Bot, ...]) -> CredentialEntry:
    served = tuple(
        bot for bot in active if bot.has_credential(credential.name, credential.details.kind)
    )
    return CredentialEntry(
        name=credential.name,
        details=credential.details,
        last_four=credential.last_four,
        bots=tuple(BotRef(id=bot.id, name=bot.name) for bot in served),
    )


def _direct_url(request: Request) -> str:
    """The address the harness itself listens on."""
    server = request.scope.get("server")
    if server is None:
        return str(request.base_url).rstrip("/")
    host, port = server
    return f"http://{f'[{host}]' if ':' in host else host}:{port}"
