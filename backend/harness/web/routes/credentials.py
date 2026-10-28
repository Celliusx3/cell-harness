"""The Credentials page: every credential with its bots, added, changed or removed from this Mac."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from harness.bots import Bot, BotNotFound, BotService, served_bots
from harness.secrets import (
    SavedCredential,
    SecretName,
    SecretNotFound,
    SecretRefused,
    SecretService,
    SecretValue,
)
from harness.secrets.models.details import ChatPlatform, ChatPlatformDetails, CredentialDetails
from harness.web.errors import STATUS_OF
from harness.web.platforms import PlatformChannels

logger = logging.getLogger(__name__)

LOOPBACK_ADDRESSES = frozenset({"127.0.0.1", "::1"})
LOOPBACK_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "::1"})
PROXY_HEADER_NAMES = ("forwarded", "x-real-ip")
PROXY_HEADER_PREFIX = "x-forwarded-"
ALLOWED_METHODS = "GET, POST, PATCH, DELETE, OPTIONS"
ALLOWED_HEADERS = "content-type"
PLATFORM_SERVES_NO_BOTS = "a Telegram or Discord credential serves no bots; tick none"


class BotRef(BaseModel):
    """A bot a credential serves: its id and the name the sidebar shows."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    name: str


class CredentialEntry(SavedCredential):
    """One credential as the Credentials page lists it, with the bots it serves."""

    bots: tuple[BotRef, ...]


class CredentialList(BaseModel):
    """Every credential in the keyring, by name, and the harness's own address to save at."""

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
    def _platform_serves_no_bots(self) -> NewCredential:
        _refuse_bots_for_a_platform(self.details, self.bot_ids)
        return self


class CredentialChange(BaseModel):
    """An edit from the dialog: what it is for, a new key or `None` to keep it, and its bots."""

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    details: CredentialDetails
    value: SecretValue | None
    bot_ids: tuple[str, ...]

    @model_validator(mode="after")
    def _platform_serves_no_bots(self) -> CredentialChange:
        _refuse_bots_for_a_platform(self.details, self.bot_ids)
        return self


def build_router(
    secrets: SecretService, bots: BotService, platforms: PlatformChannels
) -> APIRouter:
    """List the keyring's credentials with their bots; add, change and remove one from this Mac."""
    router = APIRouter(prefix="/api/credentials", tags=["credentials"])

    @router.get("", response_model=CredentialList)
    async def list_credentials(request: Request, response: Response) -> CredentialList:
        response.headers.update(_cors_headers(request))
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
        return Response(status_code=status.HTTP_204_NO_CONTENT, headers=_cors_headers(request))

    @router.post("", status_code=status.HTTP_201_CREATED)
    async def add_credential(request: Request) -> Response:
        headers = _permitted_write_headers(request)
        body = _parsed_body(NewCredential, await request.body(), headers)
        with _refusals_answered_with(headers):
            _refuse_inactive_bots(bots, body.bot_ids)
            await asyncio.to_thread(secrets.add_credential, body.name, body.details, body.value)
        platform = _platform_of(body.details)
        if platform is None:
            bots.tie_credential(body.name, body.details.kind, body.bot_ids)
        else:
            await platforms.restart(platform)
        logger.info("credential %r added for bots %s", body.name, list(body.bot_ids))
        return Response(status_code=status.HTTP_201_CREATED, headers=headers)

    @router.patch("/{name}")
    async def change_credential(name: str, request: Request) -> Response:
        headers = _permitted_write_headers(request)
        body = _parsed_body(CredentialChange, await request.body(), headers)
        with _refusals_answered_with(headers):
            _refuse_inactive_bots(bots, body.bot_ids)
            await asyncio.to_thread(secrets.change_credential, name, body.details, body.value)
        platform = _platform_of(body.details)
        if platform is None:
            bots.tie_credential(name, body.details.kind, body.bot_ids)
        elif body.value is not None:
            await platforms.restart(platform)
        logger.info("credential %r changed for bots %s", name, list(body.bot_ids))
        return Response(status_code=status.HTTP_200_OK, headers=headers)

    @router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
    async def remove_credential(name: str, request: Request) -> Response:
        headers = _permitted_write_headers(request)
        with _refusals_answered_with(headers):
            removed = secrets.delete(name)
        bots.forget_secret(name)
        platform = _platform_of(removed)
        if platform is not None:
            await platforms.restart(platform)
        logger.info("credential %r removed from the keyring and every bot", name)
        return Response(status_code=status.HTTP_204_NO_CONTENT, headers=headers)

    return router


def _refuse_bots_for_a_platform(details: CredentialDetails, bot_ids: tuple[str, ...]) -> None:
    if isinstance(details, ChatPlatformDetails) and bot_ids:
        raise ValueError(PLATFORM_SERVES_NO_BOTS)


def _platform_of(details: CredentialDetails) -> ChatPlatform | None:
    """The chat platform a credential signs in, or `None` for a key that serves bots."""
    return details.kind if isinstance(details, ChatPlatformDetails) else None


def _credential_entry(credential: SavedCredential, active: tuple[Bot, ...]) -> CredentialEntry:
    served = served_bots(active, credential.name, credential.details.kind)
    return CredentialEntry(
        name=credential.name,
        details=credential.details,
        last_four=credential.last_four,
        is_default_model=credential.is_default_model,
        bots=tuple(BotRef(id=bot.id, name=bot.name) for bot in served),
    )


def _permitted_write_headers(request: Request) -> dict[str, str]:
    """The CORS headers for a write from a page on this Mac; a 403 saying why for any other."""
    headers = _cors_headers(request)
    refusal = _save_refusal_reason(request)
    if refusal is not None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=refusal, headers=headers)
    return headers


def _parsed_body[Body: BaseModel](model: type[Body], raw: bytes, headers: dict[str, str]) -> Body:
    """`raw` parsed as `model`; a 422 naming each refused field, never what was typed in it."""
    try:
        return model.model_validate_json(raw)
    except ValidationError as err:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=err.errors(include_url=False, include_context=False, include_input=False),
            headers=headers,
        ) from None


@contextmanager
def _refusals_answered_with(headers: dict[str, str]) -> Iterator[None]:
    """A refused write answered with its usual status, and the headers that let the page read it."""
    try:
        yield
    except (BotNotFound, SecretNotFound, SecretRefused) as err:
        raise HTTPException(STATUS_OF[type(err)], detail=str(err), headers=headers) from err


def _refuse_inactive_bots(bots: BotService, bot_ids: tuple[str, ...]) -> None:
    """`BotNotFound` for a ticked bot that is not active, before anything is saved."""
    for bot_id in bot_ids:
        bots.active_bot(bot_id)


def _save_refusal_reason(request: Request) -> str | None:
    """Why a save is refused, or None for a page on this Mac that reached the harness directly."""
    if any(_is_proxy_header(name) for name in request.headers):
        return "Saving through a proxy is refused; open the page on the Mac that runs the harness."
    if request.client is None or request.client.host not in LOOPBACK_ADDRESSES:
        return "Saving is refused from another device."
    if not _is_page_on_this_mac(request.headers.get("origin")):
        return "Saving is refused from a page that is not this harness's own."
    return None


def _is_proxy_header(name: str) -> bool:
    lowered = name.lower()
    return lowered.startswith(PROXY_HEADER_PREFIX) or lowered in PROXY_HEADER_NAMES


def _is_page_on_this_mac(origin: str | None) -> bool:
    if origin is None:
        return False
    parts = urlsplit(origin)
    return parts.scheme == "http" and parts.hostname in LOOPBACK_HOSTNAMES


def _cors_headers(request: Request) -> dict[str, str]:
    """Cross-origin permission for a page served from this Mac, and none for any other page."""
    origin = request.headers.get("origin")
    if not _is_page_on_this_mac(origin):
        return {}
    return {
        "access-control-allow-origin": str(origin),
        "access-control-allow-methods": ALLOWED_METHODS,
        "access-control-allow-headers": ALLOWED_HEADERS,
        "vary": "Origin",
    }


def _direct_url(request: Request) -> str:
    """The address the harness itself listens on."""
    server = request.scope.get("server")
    if server is None:
        return str(request.base_url).rstrip("/")
    host, port = server
    return f"http://{f'[{host}]' if ':' in host else host}:{port}"
