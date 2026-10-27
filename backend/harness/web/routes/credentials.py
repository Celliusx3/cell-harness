"""The Credentials page: every credential in the keyring, with its bots, never a key in full."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from harness.bots import Bot, BotService
from harness.secrets import SavedCredential, SecretService


class BotRef(BaseModel):
    """A bot a credential serves: its id and the name the sidebar shows."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    name: str


class CredentialEntry(SavedCredential):
    """One credential as the Credentials page lists it, with the bots it serves."""

    bots: tuple[BotRef, ...]


class CredentialList(BaseModel):
    """Every credential in the keyring, by name."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    credentials: tuple[CredentialEntry, ...]


def build_router(secrets: SecretService, bots: BotService) -> APIRouter:
    """List the keyring's credentials, each with the bots it serves."""
    router = APIRouter(prefix="/api/credentials", tags=["credentials"])

    @router.get("", response_model=CredentialList)
    async def list_credentials() -> CredentialList:
        saved = await asyncio.to_thread(secrets.saved_credentials)
        active = await bots.active_bots()
        return CredentialList(
            credentials=tuple(_credential_entry(credential, active) for credential in saved)
        )

    return router


def _credential_entry(credential: SavedCredential, active: tuple[Bot, ...]) -> CredentialEntry:
    return CredentialEntry(
        name=credential.name,
        details=credential.details,
        last_four=credential.last_four,
        bots=_bots_served(credential, active),
    )


def _bots_served(credential: SavedCredential, active: tuple[Bot, ...]) -> tuple[BotRef, ...]:
    if credential.details.kind != "custom":
        return ()
    return tuple(
        BotRef(id=bot.id, name=bot.name) for bot in active if credential.name in bot.secret_names
    )
