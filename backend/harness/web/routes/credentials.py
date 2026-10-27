"""The Credentials page's view of the harness's own keys: listed, never shown in full."""

from __future__ import annotations

from collections.abc import Mapping

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from harness.config.credentials import Credential, credentials
from harness.config.settings import Settings


class CredentialList(BaseModel):
    """Every key the harness holds, masked."""

    model_config = ConfigDict(frozen=True)

    credentials: tuple[Credential, ...]


def build_router(settings: Settings, env: Mapping[str, str]) -> APIRouter:
    router = APIRouter(prefix="/api/credentials", tags=["credentials"])

    @router.get("", response_model=CredentialList)
    async def list_credentials() -> CredentialList:
        """The keys as they were when the harness started."""
        return CredentialList(credentials=credentials(settings, env))

    return router
