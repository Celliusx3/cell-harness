"""Who may change the harness's setup: a page on this Mac that reached the harness directly."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from urllib.parse import urlsplit

from fastapi import HTTPException, Request, status
from pydantic import BaseModel, ValidationError

from harness.web.errors import STATUS_OF

LOOPBACK_ADDRESSES = frozenset({"127.0.0.1", "::1"})
LOOPBACK_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "::1"})
PROXY_HEADER_NAMES = ("forwarded", "x-real-ip")
PROXY_HEADER_PREFIX = "x-forwarded-"
ALLOWED_METHODS = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
ALLOWED_HEADERS = "content-type"


def permitted_write_headers(request: Request) -> dict[str, str]:
    """The CORS headers for a write from a page on this Mac; a 403 saying why for any other."""
    headers = cors_headers(request)
    refusal = _save_refusal_reason(request)
    if refusal is not None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=refusal, headers=headers)
    return headers


def parsed_body[Body: BaseModel](model: type[Body], raw: bytes, headers: dict[str, str]) -> Body:
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
def refusals_answered_with(
    headers: dict[str, str], refused: tuple[type[Exception], ...]
) -> Iterator[None]:
    """A `refused` write answered with its usual status and the headers the page reads it with."""
    try:
        yield
    except refused as err:
        raise HTTPException(STATUS_OF[type(err)], detail=str(err), headers=headers) from err


def cors_headers(request: Request) -> dict[str, str]:
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
