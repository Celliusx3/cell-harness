"""The Credentials page's view of the harness's own keys: masked, saved only from this Mac."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict

from harness.config.credentials import (
    Credential,
    NotSettable,
    RefusedValue,
    check_values,
    credentials,
)
from harness.config.credentials_file import read_saved, with_values, write_saved
from harness.config.settings import Settings

LOOPBACK_PEERS = frozenset({"127.0.0.1", "::1"})
LOOPBACK_PAGES = frozenset({"localhost", "127.0.0.1", "::1"})
PROXY_HEADERS = ("forwarded", "x-real-ip")
PROXY_HEADER_PREFIX = "x-forwarded-"
SAVE_METHODS = "GET, PUT, OPTIONS"
SAVE_HEADERS = "content-type"


class Busyness(Protocol):
    def is_busy(self) -> bool: ...


class CredentialList(BaseModel):
    """Every key masked, the harness's own address to save at, and which process answered."""

    model_config = ConfigDict(frozen=True)

    credentials: tuple[Credential, ...]
    direct_url: str
    harness_pid: int


class CredentialValues(BaseModel):
    """New keys by path, None to remove one, and whether a reply in progress may stop."""

    model_config = ConfigDict(frozen=True)

    values: dict[str, str | None]
    confirm: bool = False


class Saved(BaseModel):
    model_config = ConfigDict(frozen=True)

    saved: tuple[str, ...]


def build_router(
    settings: Settings, env: Mapping[str, str], runs: Busyness, local: Path
) -> APIRouter:
    router = APIRouter(prefix="/api/credentials", tags=["credentials"])

    @router.get("", response_model=CredentialList)
    async def list_credentials(request: Request, response: Response) -> CredentialList:
        """The keys as they were when the harness started."""
        response.headers.update(_page_headers(request))
        return CredentialList(
            credentials=credentials(settings, env),
            direct_url=_own_url(request),
            harness_pid=os.getpid(),
        )

    @router.options("")
    async def ask_before_saving(request: Request) -> Response:
        """A page on this Mac may save here; any other page gets no permission."""
        return Response(status_code=status.HTTP_204_NO_CONTENT, headers=_page_headers(request))

    @router.put("", response_model=Saved)
    async def save(request: Request, response: Response, body: CredentialValues) -> Saved:
        """Writes the keys into the per-machine settings file."""
        headers = _page_headers(request)
        refusal = _save_refusal(request)
        if refusal is not None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail=refusal, headers=headers)
        _check(settings, env, body, headers)
        if runs.is_busy() and not body.confirm:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail="A reply will stop.", headers=headers
            )
        write_saved(local, with_values(read_saved(local), body.values))
        response.headers.update(headers)
        return Saved(saved=tuple(body.values))

    return router


def _check(
    settings: Settings, env: Mapping[str, str], body: CredentialValues, headers: dict[str, str]
) -> None:
    try:
        check_values(settings, env, body.values)
    except NotSettable as err:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(err), headers=headers) from err
    except RefusedValue as err:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(err), headers=headers
        ) from err


def _save_refusal(request: Request) -> str | None:
    """Why a save is refused, or None for a page on this Mac that reached the harness directly."""
    if any(_is_proxy_header(name) for name in request.headers):
        return "Saving through a proxy is refused; open the page on the Mac that runs the harness."
    if request.client is None or request.client.host not in LOOPBACK_PEERS:
        return "Saving is refused from another device."
    if not _is_page_on_this_mac(request.headers.get("origin")):
        return "Saving is refused from a page that is not this harness's own."
    return None


def _is_proxy_header(name: str) -> bool:
    lowered = name.lower()
    return lowered.startswith(PROXY_HEADER_PREFIX) or lowered in PROXY_HEADERS


def _is_page_on_this_mac(origin: str | None) -> bool:
    if origin is None:
        return False
    parts = urlsplit(origin)
    return parts.scheme == "http" and parts.hostname in LOOPBACK_PAGES


def _page_headers(request: Request) -> dict[str, str]:
    """Cross-origin permission for a page served from this Mac, and none for any other page."""
    origin = request.headers.get("origin")
    if not _is_page_on_this_mac(origin):
        return {}
    return {
        "access-control-allow-origin": str(origin),
        "access-control-allow-methods": SAVE_METHODS,
        "access-control-allow-headers": SAVE_HEADERS,
        "vary": "Origin",
    }


def _own_url(request: Request) -> str:
    """The address the harness itself listens on."""
    server = request.scope.get("server")
    if server is None:
        return str(request.base_url).rstrip("/")
    host, port = server
    return f"http://{f'[{host}]' if ':' in host else host}:{port}"
