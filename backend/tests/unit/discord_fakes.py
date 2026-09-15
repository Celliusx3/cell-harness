"""Stand-ins for discord.py's client, messages and interactions.

Faking at the library's boundary, as `telegram_fakes.py` does: the library owns
the websocket and the REST wire, and a test that re-implemented Discord's JSON
would be testing discord.py. What is ours is what we do with a `Message` or an
`Interaction`, and what we ask the client to send.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

from harness.agent.loop import LoopAgent
from harness.channels.discord.channel import DiscordChannel
from harness.channels.gateway import ChannelGateway
from harness.channels.repositories.jsonl import JsonlChatRepository
from harness.llm.client import LLMClient
from harness.runs.store import RunStore
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import no_skills

BOT_ID = 900


class FakeMessageable:
    """One DM, channel or thread. Records what was sent to it."""

    def __init__(self) -> None:
        self.sent: list[str] = []
        # (text, the view) for every send that carried buttons.
        self.linked: list[tuple[str, object]] = []
        self.typing_count = 0
        # Set to raise on the next call, for the failure paths.
        self.fail_next: Exception | None = None

    async def send(self, text: str, view: object = None, **_: object) -> None:
        self._maybe_fail()
        if view is not None:
            self.linked.append((text, view))
        else:
            self.sent.append(text)

    async def typing(self) -> None:
        self._maybe_fail()
        self.typing_count += 1

    def _maybe_fail(self) -> None:
        if self.fail_next is not None:
            error, self.fail_next = self.fail_next, None
            raise error


class FakeClient:
    """Stands in for `discord.Client`: a user, and channels by id.

    `cached` answers `get_channel`; anything else is only reachable through
    `fetch_channel`, which is the restart path.
    """

    def __init__(self) -> None:
        self.user = SimpleNamespace(id=BOT_ID, bot=True)
        self.cached: dict[int, FakeMessageable] = {}
        self.fetchable: dict[int, FakeMessageable] = {}
        self.fetched: list[int] = []

    def get_channel(self, channel_id: int) -> FakeMessageable | None:
        return self.cached.get(channel_id)

    async def fetch_channel(self, channel_id: int) -> FakeMessageable:
        self.fetched.append(channel_id)
        return self.fetchable[channel_id]

    def chat(self, chat_id: str) -> FakeMessageable:
        """A cached channel for `chat_id`, created on first use."""
        return self.cached.setdefault(int(chat_id), FakeMessageable())


def discord_channel(gateway: ChannelGateway) -> tuple[DiscordChannel, FakeClient]:
    """A real `DiscordChannel` whose discord.py client is a fake.

    The channel is genuine — its gating, stripping, splitting and command
    handling are what the tests are for. Constructing `discord.Client` opens no
    connection, so the real one is built and then replaced.
    """
    channel = DiscordChannel("fake-token", gateway)
    client = FakeClient()
    channel._client = client  # type: ignore[assignment]
    return channel, client


def message(
    chat_id: str,
    text: str,
    *,
    guild: bool = False,
    mentions: tuple[int, ...] = (),
    bot: bool = False,
) -> SimpleNamespace:
    """The shape of a `discord.Message` that the handler reads."""
    return SimpleNamespace(
        author=SimpleNamespace(id=1, bot=bot),
        guild=SimpleNamespace(id=5) if guild else None,
        mentions=[SimpleNamespace(id=user_id) for user_id in mentions],
        content=text,
        channel=SimpleNamespace(id=int(chat_id)),
    )


class FakeInteraction:
    """A slash command in one chat. Records the acknowledgement and the reply."""

    def __init__(self, chat_id: str) -> None:
        self.channel_id = int(chat_id)
        self.deferred = False
        self.replies: list[str] = []
        self.response = SimpleNamespace(defer=self._defer)
        self.followup = SimpleNamespace(send=self._send)

    async def _defer(self, **_: object) -> None:
        self.deferred = True

    async def _send(self, text: str, **_: object) -> None:
        if not self.deferred:
            raise AssertionError("a follow-up before the deferral is a Discord error")
        self.replies.append(text)


def build(tmp_path, client: LLMClient | None = None):
    """A gateway over real stores with the Discord channel registered."""
    ids = iter(f"c{n}" for n in range(100))
    sessions = SessionService(
        JsonlSessionRepository(tmp_path / "sessions"),
        now=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        new_id=lambda: next(ids),
    )
    agent = LoopAgent(
        name="t",
        model="m",
        client=client or ScriptedClient(completed("ok")),
        checkpoint=sessions.flush,
    )
    runs = RunStore(sessions, agent)
    chats = JsonlChatRepository(tmp_path / "chats")
    gateway = ChannelGateway(chats, runs, sessions, no_skills(), public_url="http://t")
    channel, fake = discord_channel(gateway)
    gateway.register(channel)
    return channel, fake, gateway, runs, chats, sessions


async def settle(gateway: ChannelGateway, runs: RunStore) -> None:
    """Wait for every turn and its delivery to finish."""
    for _ in range(300):
        busy = gateway._tasks.running()
        if not busy and not runs._runs:
            return
        await asyncio.sleep(0.01)
    raise AssertionError("channel never went idle")
