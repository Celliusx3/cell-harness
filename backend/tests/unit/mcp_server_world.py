"""The MCP servers screen's routes, over fakes."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
from fastapi import FastAPI

from harness.mcp import DiskSavedServerRepository, McpService, SavedServer, SavedServerService
from harness.mcp.router.mcp_router import McpRouter
from harness.mcp.router.server_router import ServerRouter
from harness.relay import RelayService
from harness.web.http.errors import exception_handlers
from tests.unit.mcp_fakes import FakeFactory, tool

PAGE = "http://127.0.0.1:4887"
THIS_MAC = ("127.0.0.1", 50000)


@dataclass
class BreakableRepository:
    """The servers file on disk, until a test makes every write fail."""

    disk: DiskSavedServerRepository
    broken: bool = False

    def saved_servers(self) -> tuple[SavedServer, ...]:
        return self.disk.saved_servers()

    def replace_all(self, servers: tuple[SavedServer, ...]) -> None:
        if self.broken:
            raise PermissionError(13, "Permission denied", str(self.disk.path))
        self.disk.replace_all(servers)


class ServerWorld:
    """A harness's servers, built from the servers file, behind its routes."""

    def __init__(self, tmp_path: Path, factory: FakeFactory | None = None) -> None:
        self.path = tmp_path / "mcp.json"
        self.factory = factory or FakeFactory()
        self.factory.client.tools = [tool("search")]
        self.repository = BreakableRepository(DiskSavedServerRepository(self.path))
        self.saved = SavedServerService(self.repository)
        self.mcp = McpService(
            {server.id: server.server() for server in self.saved.servers()},
            client_factory=self.factory,
        )
        app = FastAPI(exception_handlers=exception_handlers())
        app.include_router(ServerRouter(self.mcp, self.saved).router)
        app.include_router(McpRouter(self.mcp, RelayService(now=time.monotonic)).router)
        self.app = app

    async def send(
        self,
        method: str,
        url: str,
        body: dict | None = None,
        *,
        client: tuple[str, int] = THIS_MAC,
        origin: str = PAGE,
    ) -> httpx.Response:
        transport = httpx.ASGITransport(app=self.app, client=client)
        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:4886") as http:
            return await http.request(method, url, json=body, headers={"origin": origin})

    def status(self, server_id: str) -> str:
        return next(s.status for s in self.mcp.statuses() if s.id == server_id)

    def tool_names(self) -> set[str]:
        return {t.name for t in self.mcp.tools()}

    async def settled(self) -> None:
        for _ in range(200):
            if all(s.status != "connecting" for s in self.mcp.statuses()):
                return
            await asyncio.sleep(0.01)
        raise AssertionError("never left `connecting`")


def exa(**overrides: object) -> dict:
    """An add-server body, as the screen sends it."""
    return {
        "id": "exa",
        "command": "npx",
        "args": ["-y", "exa-mcp-server"],
        "env": {"EXA_LIMIT": "5"},
        "needs": [],
        "keys": {},
        **overrides,
    }


def draft(body: dict) -> dict:
    """A change-server body: everything an add sends but the id."""
    return {name: value for name, value in body.items() if name != "id"}
