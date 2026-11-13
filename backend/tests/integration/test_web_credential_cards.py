"""An LLM, Telegram or Discord credential typed into a chat card: saved by kind, never logged."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
from pydantic import SecretStr

from harness.bots import ASSISTANT_ID
from harness.secrets import SecretService
from harness.secrets.domain.details import ChatPlatform, ModelDetails
from harness.tools import ApprovalService
from harness.tools.client import ClientToolService
from harness.tools.native.secrets import ASK_FOR_SECRET, FETCH_WITH_SECRET, fetch_with_secret_tool
from harness.web.runtime import CLIENT_TOOLS
from tests.integration.web_helpers import events_from, settle
from tests.unit.fakes import SteppedClient, calls_tool, completed
from tests.unit.helpers import durable_service, no_skills, run_service
from tests.webapp import bots_in, secrets_in, web_app

KEY = "nvapi-Zq7-secret-9x"
TOKEN = "123456:AAtelegram-card-token"
ASK_LLM = json.dumps(
    {
        "kind": "llm",
        "name": "nvidia",
        "label": "NVIDIA API key",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "model": "meta/llama-3.1-70b-instruct",
        "vision": False,
    }
)
ASK_TELEGRAM = json.dumps({"kind": "telegram", "name": "telegram", "label": "Telegram bot token"})
FETCH = json.dumps(
    {"name": "nvidia", "url": "https://integrate.api.nvidia.com/v1/models", "method": "GET"}
)
OTHER_MODEL = ModelDetails(base_url="https://api.example.com/v1", model="m", vision=False)
EDITED_LLM = {
    "value": KEY,
    "details": {
        "kind": "llm",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "model": "meta/llama-3.3-70b-instruct",
        "vision": True,
    },
}


class ParkedChannel:
    """A chat platform that is only registered, never run."""

    def __init__(self, platform: ChatPlatform) -> None:
        self.channel = platform

    def conversation_for(self, chat_id: str) -> str:
        return ASSISTANT_ID

    async def run(self) -> None:
        return None


class MadePlatforms:
    """Each chat platform the app signed in, with the token it was handed."""

    def __init__(self) -> None:
        self.tokens: list[tuple[ChatPlatform, str]] = []

    def __call__(self, platform: ChatPlatform, token: SecretStr) -> ParkedChannel:
        self.tokens.append((platform, token.get_secret_value()))
        return ParkedChannel(platform)


class CardApp:
    """The app with a scripted model, the keyring, the requests `fetch_with_secret` sent."""

    def __init__(self, tmp_path: Path, model: SteppedClient) -> None:
        approvals = ApprovalService(
            frozenset(), frozenset, tmp_path / "approvals.json", default_mode="ask"
        )
        tools = ClientToolService(CLIENT_TOOLS, approvals)
        self.sent: list[httpx.Request] = []
        self.secrets: SecretService = secrets_in(tmp_path)
        self.platforms = MadePlatforms()
        service = durable_service(tmp_path / "sessions")
        self.bots = bots_in(tmp_path, service)
        transport = httpx.MockTransport(self._answer)
        fetch = fetch_with_secret_tool(self.secrets, self.bots, transport)
        self.runs = run_service(
            service, model, fetch, *tools.tools(), approvals=approvals, bots=self.bots
        )
        app = web_app(
            tmp_path,
            service,
            self.runs,
            skills=no_skills(),
            client_tools=tools,
            approvals=approvals,
            bots=self.bots,
            secrets=self.secrets,
            make_platform=self.platforms,
        )
        self.http = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://h.test"
        )

    def _answer(self, request: httpx.Request) -> httpx.Response:
        self.sent.append(request)
        return httpx.Response(200, text="{}")

    async def post(self, path: str, body: dict) -> httpx.Response:
        response = await self.http.post(f"/api/conversations/{ASSISTANT_ID}{path}", json=body)
        await settle(self.runs, ASSISTANT_ID)
        return response

    async def events(self) -> list[dict]:
        stream = await self.http.get(f"/api/conversations/{ASSISTANT_ID}/events?after=0")
        return events_from(stream.text)

    async def result_of(self, call_id: str) -> dict:
        [result] = [
            event
            for event in await self.events()
            if event["type"] == "tool/result" and event["message"]["tool_call_id"] == call_id
        ]
        return result

    async def waiting(self) -> set[str]:
        events = await self.events()
        called = {e["call"]["id"] for e in events if e["type"] == "tool/call"}
        return called - {e["message"]["tool_call_id"] for e in events if e["type"] == "tool/result"}


def _text(result: dict) -> str:
    return result["message"]["content"][0]["text"]


def _logged(tmp_path: Path) -> str:
    files = (tmp_path / "sessions").rglob("*")
    return "".join(path.read_text(encoding="utf-8") for path in files if path.is_file())


async def test_an_llm_key_saved_on_the_card_is_a_model_credential_the_log_never_holds(
    tmp_path: Path,
) -> None:
    model = SteppedClient(
        calls_tool(ASK_FOR_SECRET, ASK_LLM, id="call_ask"),
        completed("Saved."),
        calls_tool(FETCH_WITH_SECRET, FETCH, id="call_fetch"),
        completed("I cannot send that key."),
    )
    app = CardApp(tmp_path, model)
    async with app.http:
        await app.post("/messages", {"prompt": "add my NVIDIA model"})
        saved = await app.post("/calls/call_ask/secret", EDITED_LLM)
        assert saved.status_code == 204, saved.text

        listed = (await app.http.get("/api/credentials")).json()["credentials"]
        assert [(c["name"], c["details"]) for c in listed] == [
            (
                "nvidia",
                {
                    "kind": "llm",
                    "base_url": "https://integrate.api.nvidia.com/v1",
                    "model": "meta/llama-3.3-70b-instruct",
                    "vision": True,
                },
            )
        ]
        assert json.loads(_text(await app.result_of("call_ask"))) == {
            "name": "nvidia",
            "kind": "llm",
        }
        assistant = app.bots.active_bot(ASSISTANT_ID)
        assert "nvidia" not in assistant.secret_names
        assert assistant.model_credential is None

        await app.post("/messages", {"prompt": "list its models"})
        refused = await app.result_of("call_fetch")
        assert _text(refused).startswith("error:")
        assert app.sent == []

        assert KEY not in json.dumps(await app.events())
    assert KEY not in _logged(tmp_path)


async def test_a_telegram_token_saved_on_the_card_starts_telegram(tmp_path: Path) -> None:
    model = SteppedClient(
        calls_tool(ASK_FOR_SECRET, ASK_TELEGRAM, id="call_ask"), completed("Telegram is on.")
    )
    app = CardApp(tmp_path, model)
    async with app.http:
        await app.post("/messages", {"prompt": "connect my Telegram bot"})
        saved = await app.post("/calls/call_ask/secret", {"value": TOKEN})
        assert saved.status_code == 204, saved.text

        assert app.platforms.tokens == [("telegram", TOKEN)]
        assert app.secrets.chat_platform_token("telegram") == SecretStr(TOKEN)
        assert json.loads(_text(await app.result_of("call_ask"))) == {
            "name": "telegram",
            "kind": "telegram",
        }
        assert TOKEN not in json.dumps(await app.events())
    assert TOKEN not in _logged(tmp_path)


async def test_a_plain_http_endpoint_off_this_computer_is_refused_and_the_card_still_waits(
    tmp_path: Path,
) -> None:
    app = CardApp(tmp_path, SteppedClient(calls_tool(ASK_FOR_SECRET, ASK_LLM, id="call_ask")))
    async with app.http:
        await app.post("/messages", {"prompt": "add my NVIDIA model"})
        refused = await app.post(
            "/calls/call_ask/secret",
            {
                "value": KEY,
                "details": {**EDITED_LLM["details"], "base_url": "http://models.example.com/v1"},
            },
        )

        assert refused.status_code == 422
        assert "plain http:// is only for localhost" in refused.text
        assert KEY not in refused.text
        assert app.secrets.saved_credentials() == ()
        assert await app.waiting() == {"call_ask"}


async def test_a_name_already_saved_is_refused_with_its_reason_and_the_card_still_waits(
    tmp_path: Path,
) -> None:
    app = CardApp(tmp_path, SteppedClient(calls_tool(ASK_FOR_SECRET, ASK_LLM, id="call_ask")))
    async with app.http:
        await app.post("/messages", {"prompt": "add my NVIDIA model"})
        app.secrets.add_credential("nvidia", OTHER_MODEL, SecretStr("sk-older-key"))
        refused = await app.post("/calls/call_ask/secret", EDITED_LLM)

        assert refused.status_code == 409
        assert "already named 'nvidia'" in refused.text
        assert await app.waiting() == {"call_ask"}
