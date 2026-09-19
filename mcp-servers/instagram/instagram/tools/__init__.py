"""The MCP surface: two tools, and the batching that makes them affordable."""

from __future__ import annotations

from mcp.server import MCPServer

from instagram.media.fetch import Fetcher, fetch_reel
from instagram.models import FetchedReel, FetchReels, ReadReel, ReadReels
from instagram.read import Reader, read_reel
from instagram.reel import NotAReelUrl, ReelRef, parse
from instagram.tools.budget import with_budget
from instagram.tools.descriptions import FETCH_DESCRIPTION, READ_DESCRIPTION


def register(server: MCPServer, *, fetcher: Fetcher, reader: Reader) -> MCPServer:
    """Add both tools to `server`, bound to the two dependency bundles."""

    @server.tool(name="fetch_reels", description=FETCH_DESCRIPTION)
    async def fetch_reels(urls: list[str]) -> FetchReels:
        entries: list[ReelRef | FetchedReel] = []
        for url in urls:
            try:
                entries.append(parse(url))
            except NotAReelUrl as err:
                entries.append(
                    FetchedReel(url=url, shortcode="", status="unsupported_url", detail=str(err))
                )

        async def one(entry: ReelRef | FetchedReel) -> FetchedReel:
            if isinstance(entry, FetchedReel):
                return entry
            return await fetch_reel(entry, fetcher)

        items = await with_budget(
            entries,
            one,
            seconds=fetcher.config.call_budget_seconds,
            concurrency=fetcher.config.fetch_concurrency,
            on_timeout=_fetch_timeout,
        )
        return FetchReels(items=items)

    @server.tool(name="read_reels", description=READ_DESCRIPTION)
    async def read_reels(shortcodes: list[str], want: list[str]) -> ReadReels:
        wanted = set(want)
        budget = reader.config.call_budget_seconds

        async def one(shortcode: str) -> ReadReel:
            return await read_reel(shortcode, wanted, reader)

        items = await with_budget(
            shortcodes,
            one,
            seconds=budget,
            concurrency=reader.config.read_concurrency,
            on_timeout=lambda code: ReadReel(
                shortcode=code,
                status="timeout",
                detail=(
                    f"{code} was not read within this call's {budget:.0f}s budget; call "
                    "read_reels again with just this shortcode — nothing already done is lost"
                ),
            ),
        )
        return ReadReels(items=items)

    return server


def _fetch_timeout(entry: ReelRef | FetchedReel) -> FetchedReel:
    if isinstance(entry, FetchedReel):
        return entry
    return FetchedReel(
        url=entry.url,
        shortcode=entry.shortcode,
        status="error",
        detail="the fetch did not finish within this call's budget; try it on its own",
    )
