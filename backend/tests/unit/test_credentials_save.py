"""`PUT /api/credentials`: a key saved into the per-machine file, only from a page on this Mac."""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass

import httpx
import pytest
from fastapi import FastAPI

from harness.config import settings as settings_module
from harness.config.settings import Settings
from harness.web.routes.credentials import build_router

PAGE = "http://localhost:4897"
THIS_MAC = ("127.0.0.1", 50000)


@dataclass
class FakeRuns:
    busy: bool = False

    def is_busy(self) -> bool:
        return self.busy


@pytest.fixture
def harness(tmp_path, monkeypatch):
    committed = tmp_path / "config.json"
    local = tmp_path / "config.local.json"
    monkeypatch.setattr(settings_module, "_CONFIG_JSON", committed)
    monkeypatch.setattr(settings_module, "_LOCAL_JSON", local)
    for name in list(os.environ):
        if name.upper().startswith("HARNESS_"):
            monkeypatch.delenv(name)
    committed.write_text(json.dumps({"llm": {"model": "m", "vision": False}}))
    local.write_text(json.dumps({"llm": {"api_key": "sk-old-key-1234"}, "web": {"public_url": ""}}))
    return local, FakeRuns()


def _app(harness, env: dict[str, str] | None = None) -> FastAPI:
    local, runs = harness
    app = FastAPI()
    app.include_router(build_router(Settings(), env or {}, runs, local))
    return app


async def _put(app: FastAPI, body: dict, *, origin: str | None = PAGE, peer=THIS_MAC, **headers):
    sent = {"origin": origin} if origin else {}
    transport = httpx.ASGITransport(app=app, client=peer)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:4896") as http:
        return await http.put("/api/credentials", json=body, headers={**sent, **headers})


def _saved(local) -> dict:
    return json.loads(local.read_text())


async def test_a_new_token_is_saved_and_every_other_value_kept(harness) -> None:
    local, _ = harness

    response = await _put(_app(harness), {"values": {"telegram.bot_token": "123:new-token-wxyz"}})

    assert response.status_code == 200
    assert _saved(local) == {
        "llm": {"api_key": "sk-old-key-1234"},
        "web": {"public_url": ""},
        "telegram": {"bot_token": "123:new-token-wxyz"},
    }


async def test_the_saved_file_is_readable_by_its_owner_only(harness) -> None:
    local, _ = harness

    await _put(_app(harness), {"values": {"telegram.bot_token": "123:new-token-wxyz"}})

    assert stat.S_IMODE(local.stat().st_mode) == 0o600


async def test_null_removes_a_saved_key(harness) -> None:
    local, _ = harness
    await _put(_app(harness), {"values": {"telegram.bot_token": "123:t-abcd"}})

    response = await _put(_app(harness), {"values": {"telegram.bot_token": None}})

    assert response.status_code == 200
    assert _saved(local)["telegram"] == {}


async def test_the_key_the_harness_cannot_start_without_cannot_be_removed(harness) -> None:
    local, _ = harness
    before = local.read_text()

    response = await _put(_app(harness), {"values": {"llm.api_key": None}})

    assert response.status_code == 400
    assert local.read_text() == before


@pytest.mark.parametrize(
    "header", ["x-forwarded-for", "x-forwarded-host", "x-forwarded-proto", "forwarded"]
)
async def test_a_save_that_came_through_a_proxy_is_refused(harness, header) -> None:
    local, _ = harness
    before = local.read_text()

    response = await _put(
        _app(harness), {"values": {"telegram.bot_token": "123:t-abcd"}}, **{header: "x"}
    )

    assert response.status_code == 403
    assert local.read_text() == before


@pytest.mark.parametrize("origin", ["https://evil.example", "http://192.168.1.5:4897", None])
async def test_a_save_from_a_page_that_is_not_on_this_mac_is_refused(harness, origin) -> None:
    response = await _put(_app(harness), {"values": {"telegram.bot_token": "1:t"}}, origin=origin)

    assert response.status_code == 403


async def test_a_save_from_another_device_is_refused(harness) -> None:
    response = await _put(
        _app(harness), {"values": {"telegram.bot_token": "1:t"}}, peer=("192.168.1.5", 50000)
    )

    assert response.status_code == 403


async def test_a_setting_that_is_not_a_listed_credential_is_refused(harness) -> None:
    local, _ = harness
    before = local.read_text()

    for path in ("llm.model", "secrets.encryption_key", "nope.key"):
        response = await _put(_app(harness), {"values": {path: "x"}})
        assert response.status_code == 400, path
    assert local.read_text() == before


async def test_a_key_set_by_the_environment_is_refused(harness) -> None:
    env = {"HARNESS_TELEGRAM__BOT_TOKEN": "from-env"}

    response = await _put(_app(harness, env), {"values": {"telegram.bot_token": "1:t"}})

    assert response.status_code == 400
    assert "HARNESS_TELEGRAM__BOT_TOKEN" in response.json()["detail"]


async def test_the_masked_preview_pasted_back_is_refused_and_not_echoed(harness) -> None:
    response = await _put(_app(harness), {"values": {"llm.api_key": "…1234"}})

    assert response.status_code == 422
    assert "…1234" not in response.text


async def test_a_blank_value_is_refused_since_remove_is_null(harness) -> None:
    response = await _put(_app(harness), {"values": {"llm.api_key": "   "}})

    assert response.status_code == 422


async def test_a_busy_harness_asks_first_and_saves_once_confirmed(harness) -> None:
    local, runs = harness
    runs.busy = True
    before = local.read_text()
    patch = {"values": {"telegram.bot_token": "123:t-abcd"}}

    asked = await _put(_app(harness), patch)
    assert asked.status_code == 409
    assert local.read_text() == before

    confirmed = await _put(_app(harness), {**patch, "may_stop_reply": True})
    assert confirmed.status_code == 200
    assert _saved(local)["telegram"] == {"bot_token": "123:t-abcd"}


async def test_the_list_tells_the_page_the_harness_own_address(harness) -> None:
    transport = httpx.ASGITransport(app=_app(harness), client=THIS_MAC)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:4896") as http:
        response = await http.get("/api/credentials", headers={"origin": PAGE})

    assert response.json()["direct_url"] == "http://127.0.0.1:4896"
    assert response.json()["answering_pid"] == os.getpid()
    assert response.headers["access-control-allow-origin"] == PAGE


async def test_a_page_on_this_mac_may_ask_before_saving(harness) -> None:
    transport = httpx.ASGITransport(app=_app(harness), client=THIS_MAC)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:4896") as http:
        allowed = await http.options("/api/credentials", headers={"origin": PAGE})
        foreign = await http.options("/api/credentials", headers={"origin": "https://evil.example"})

    assert allowed.status_code == 204
    assert allowed.headers["access-control-allow-origin"] == PAGE
    assert "PUT" in allowed.headers["access-control-allow-methods"]
    assert "access-control-allow-origin" not in foreign.headers
