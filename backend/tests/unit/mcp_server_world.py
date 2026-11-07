"""The MCP servers screen's routes, the credentials routes and the keyring, over fakes."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
from fastapi import FastAPI

from harness.bots import BotService
from harness.config.sections import McpServer
from harness.mcp import DiskSavedServerRepository, McpService, SavedServer, SavedServerService
from harness.relay import RelayService
from harness.secrets import DiskSecretRepository, SecretService
from harness.web.errors import exception_handlers
from harness.web.routes.credentials import build_router as build_credentials_router
from harness.web.routes.mcp import build_router as build_mcp_router
from harness.web.routes.mcp_servers import build_router
from tests.unit.helpers import durable_service
from tests.unit.mcp_fakes import FakeFactory, tool
from tests.webapp import no_platforms

KEY = "0123456789abcdef0123456789abcdef"
PAGE = "http://127.0.0.1:4887"
THIS_MAC = ("127.0.0.1", 50000)


def built_ins() -> dict[str, McpServer]:
    return {"computer": McpServer(command="uv", args=("run", "computer"))}


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
    """A harness's servers, built from config and the saved file, behind its routes."""

    def __init__(self, tmp_path: Path, factory: FakeFactory | None = None) -> None:
        self.path = tmp_path / "mcp.json"
        self.secrets = SecretService(
            DiskSecretRepository(tmp_path / "secrets.json"), encryption_key=KEY
        )
        self.factory = factory or FakeFactory()
        self.factory.client.tools = [tool("search")]
        self.repository = BreakableRepository(DiskSavedServerRepository(self.path))
        self.saved = SavedServerService(self.repository, built_in_ids=frozenset(built_ins()))
        self.mcp = McpService(
            built_ins(),
            saved={server.id: server.server() for server in self.saved.servers()},
            keys=self.secrets,
            client_factory=self.factory,
        )
        bots = BotService(
            tmp_path / "bots.json",
            durable_service(tmp_path / "sessions"),
            assistant_instructions="Be kind.",
        )
        app = FastAPI(exception_handlers=exception_handlers())
        app.include_router(build_router(self.mcp, self.saved))
        app.include_router(build_mcp_router(self.mcp, RelayService(now=time.monotonic)))
        app.include_router(
            build_credentials_router(self.secrets, bots, no_platforms(self.secrets), self.mcp)
        )
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
        **overrides,
    }


def draft(body: dict) -> dict:
    """A change-server body: everything an add sends but the id."""
    return {name: value for name, value in body.items() if name != "id"}
