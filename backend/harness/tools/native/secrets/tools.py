"""`ask_for_secret`, declared as a client tool, and `fetch_with_secret`, which sends the key."""

from __future__ import annotations

import json

import httpx

from harness.bots import BotNotFound, BotService
from harness.secrets import Destination, SecretService, UnsealedSecret, redacted
from harness.tools.client import ClientTool
from harness.tools.models.context import ToolContext
from harness.tools.models.outcome import Failure, Ok, ToolOutcome
from harness.tools.models.tool import Tool
from harness.tools.native.secrets.models import FetchArgs, SavedName, SecretAsk

ASK_FOR_SECRET = "ask_for_secret"

ASK_FOR_SECRET_TOOL = ClientTool(
    name=ASK_FOR_SECRET,
    description=(
        "Ask the user for an API key or token on a protected card, and wait while they save "
        "it. Pick the name and label yourself and call this at once; the card is where the "
        "user acts. You never see the key: the result is only the name it was saved under, "
        "which you pass to fetch_with_secret. Never ask the user to paste a key into the chat."
    ),
    args_model=SecretAsk,
    data_model=SavedName,
)


FETCH_WITH_SECRET = "fetch_with_secret"

NO_SECRET = "NO_SECRET"
NOT_ALLOWED = "NOT_ALLOWED"
WRONG_ORIGIN = "WRONG_ORIGIN"
REDIRECTED = "REDIRECTED"
TOO_LARGE = "TOO_LARGE"
REQUEST_FAILED = "REQUEST_FAILED"

MAX_RESPONSE_BYTES = 1024 * 1024
TIMEOUT_SECONDS = 30

_FETCH_DESCRIPTION = (
    "Call an https API with a key the user saved through ask_for_secret. The server adds the "
    "key, so never put one in the url or the body. Redirects are not followed. The result is "
    "the status and the body, with the key blanked as [secret]. If there is no saved key, "
    "call ask_for_secret first."
)


def fetch_with_secret_tool(
    secrets: SecretService, bots: BotService, transport: httpx.AsyncBaseTransport
) -> Tool[FetchArgs]:
    """The tool that sends a saved key the bot may use to its site, and blanks it out after."""

    async def execute(args: FetchArgs, context: ToolContext) -> ToolOutcome:
        saved = secrets.secret_named(args.name)
        if saved is None:
            return Failure(
                NO_SECRET, f"no saved key named {args.name!r}; call ask_for_secret first"
            )
        if not _can_use(bots, context.origin.bot_id, args.name):
            return Failure(
                NOT_ALLOWED,
                f"this bot may not use {args.name!r}; the user can allow it on the bot's page",
            )
        url = _url_on_origin(args.url, saved.destination.origin)
        if url is None:
            return Failure(
                WRONG_ORIGIN,
                f"the url must be https on {saved.destination.origin}, the site key "
                f"{args.name!r} was saved for, with no user or password in it",
            )
        try:
            async with httpx.AsyncClient(
                transport=transport, follow_redirects=False, timeout=TIMEOUT_SECONDS
            ) as client:
                return await _send_request(client, args, url, saved)
        except (httpx.HTTPError, UnicodeError) as err:
            return Failure(REQUEST_FAILED, f"the request failed: {type(err).__name__}")

    return Tool.from_model(
        name=FETCH_WITH_SECRET,
        description=_FETCH_DESCRIPTION,
        args_model=FetchArgs,
        execute=execute,
    )


def _can_use(bots: BotService, bot_id: str, name: str) -> bool:
    try:
        return name in bots.active_bot(bot_id).secret_names
    except BotNotFound:
        return False


def _url_on_origin(url: str, origin: str) -> httpx.URL | None:
    try:
        target = httpx.URL(url)
    except httpx.InvalidURL:
        return None
    site = httpx.URL(origin)
    if target.scheme != "https" or target.userinfo:
        return None
    if (target.scheme, target.host, target.port) != (site.scheme, site.host, site.port):
        return None
    return target


def _auth_headers(destination: Destination, value: str) -> dict[str, str]:
    if destination.header_name is None:
        return {"Authorization": f"Bearer {value}"}
    return {destination.header_name: value}


async def _send_request(
    client: httpx.AsyncClient, args: FetchArgs, url: httpx.URL, secret: UnsealedSecret
) -> ToolOutcome:
    value = secret.value.get_secret_value()
    headers = _auth_headers(secret.destination, value)
    async with client.stream(args.method, url, headers=headers, json=args.body) as response:
        if 300 <= response.status_code < 400:
            return Failure(
                REDIRECTED,
                f"the site answered {response.status_code}; redirects are not followed",
            )
        body = await _body_under_limit(response)
    if body is None:
        return Failure(
            TOO_LARGE, f"the response is over {MAX_RESPONSE_BYTES} bytes, so none of it is shown"
        )
    text = body.decode("utf-8", errors="replace")
    return Ok(content=json.dumps({"status": response.status_code, "body": redacted(text, value)}))


async def _body_under_limit(response: httpx.Response) -> bytes | None:
    chunks: list[bytes] = []
    size = 0
    async for chunk in response.aiter_bytes():
        size += len(chunk)
        if size > MAX_RESPONSE_BYTES:
            return None
        chunks.append(chunk)
    return b"".join(chunks)
