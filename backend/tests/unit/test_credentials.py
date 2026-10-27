"""The harness's own keys as the Credentials page lists them: masked, and never in full."""

from __future__ import annotations

import json
import os
from typing import get_args

import httpx
import pytest
from fastapi import FastAPI
from pydantic import BaseModel

from harness.config import settings as settings_module
from harness.config.credentials import credentials
from harness.config.settings import Settings
from harness.web.routes.credentials import build_router

API_KEY = "sk-abcdefgh1234"


class NotBusy:
    def is_busy(self) -> bool:
        return False


@pytest.fixture
def settings_with(tmp_path, monkeypatch):
    committed = tmp_path / "config.json"
    local = tmp_path / "config.local.json"
    monkeypatch.setattr(settings_module, "_CONFIG_JSON", committed)
    monkeypatch.setattr(settings_module, "_LOCAL_JSON", local)
    for name in list(os.environ):
        if name.upper().startswith("HARNESS_"):
            monkeypatch.delenv(name)
    committed.write_text(json.dumps({"llm": {"model": "m", "vision": False}}))

    def build(local_values: dict) -> Settings:
        local.write_text(json.dumps(local_values))
        return Settings()

    return build


def test_the_list_is_the_api_key_then_each_bot_token(settings_with) -> None:
    listed = credentials(settings_with({}), env={})

    assert [c.path for c in listed] == ["llm.api_key", "telegram.bot_token", "discord.bot_token"]


def test_a_saved_key_shows_only_its_last_four_characters(settings_with) -> None:
    api_key = credentials(settings_with({"llm": {"api_key": API_KEY}}), env={})[0]

    assert api_key.is_set
    assert api_key.last_four == "1234"
    assert API_KEY not in api_key.model_dump_json()


def test_a_key_too_short_to_mask_shows_as_set_with_no_characters(settings_with) -> None:
    api_key = credentials(settings_with({"llm": {"api_key": "abc123"}}), env={})[0]

    assert api_key.is_set
    assert api_key.last_four is None


def test_an_unset_key_shows_as_not_set(settings_with) -> None:
    telegram = credentials(settings_with({}), env={})[1]

    assert not telegram.is_set
    assert telegram.last_four is None


def test_a_key_given_by_the_environment_names_its_variable(settings_with) -> None:
    listed = credentials(settings_with({}), env={"harness_telegram__bot_token": "t-1"})

    assert listed[1].env_variable == "harness_telegram__bot_token"
    assert listed[0].env_variable is None


def test_only_the_model_api_key_is_required(settings_with) -> None:
    listed = credentials(settings_with({}), env={})

    assert [c.path for c in listed if c.is_required] == ["llm.api_key"]


def test_the_settings_read_their_variables_in_any_case_as_the_list_does() -> None:
    assert Settings.model_config["case_sensitive"] is False


def test_every_credential_says_what_it_is(settings_with) -> None:
    assert all(c.description.strip() for c in credentials(settings_with({}), env={}))


def _text_fields(model: type[BaseModel], prefix: str = "") -> list[tuple[str, dict]]:
    found = []
    for name, field in model.model_fields.items():
        nested = [a for a in (field.annotation, *get_args(field.annotation)) if isinstance(a, type)]
        models = [a for a in nested if issubclass(a, BaseModel)]
        for sub in models:
            found += _text_fields(sub, f"{prefix}{name}.")
        if field.annotation is str:
            found.append((f"{prefix}{name}", field.json_schema_extra or {}))
    return found


def test_every_text_setting_named_like_a_key_or_token_is_marked_secret() -> None:
    unmarked = [
        path
        for path, extra in _text_fields(Settings)
        if path.endswith(("key", "token")) and not extra.get("x-secret")
    ]

    assert unmarked == []


async def test_the_page_reads_the_list_with_no_key_in_full(settings_with) -> None:
    app = FastAPI()
    settings = settings_with({"llm": {"api_key": API_KEY}})
    app.include_router(build_router(settings, {}, NotBusy(), settings_module.local_settings_path()))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://t"
    ) as http:
        response = await http.get("/api/credentials")

    assert response.status_code == 200
    assert [c["path"] for c in response.json()["credentials"]][0] == "llm.api_key"
    assert API_KEY not in response.text
