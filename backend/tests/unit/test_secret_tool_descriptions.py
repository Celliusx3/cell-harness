"""What `ask_for_secret` and `fetch_with_secret` tell the model, and where each rule is said."""

from __future__ import annotations

import httpx
import pytest
from pydantic import ValidationError

from harness.tools.native.secrets import ASK_FOR_SECRET_TOOL, fetch_with_secret_tool
from harness.tools.native.secrets.models import FetchArgs, SecretAsk
from tests.unit.helpers import durable_service
from tests.webapp import bots_in, secrets_in

NAME_RULE = "lowercase letters, digits and underscores"


def _fetch_description(tmp_path) -> str:
    bots = bots_in(tmp_path, durable_service(tmp_path / "sessions"))
    transport = httpx.MockTransport(lambda request: httpx.Response(200))
    return fetch_with_secret_tool(secrets_in(tmp_path), bots, transport).description


def test_ask_for_secret_says_what_a_name_may_be() -> None:
    assert NAME_RULE in SecretAsk.model_json_schema()["properties"]["name"]["description"]
    with pytest.raises(ValidationError):
        SecretAsk.model_validate(
            {
                "name": "httpbinToken",
                "origin": "https://httpbin.org",
                "auth": "bearer",
                "label": "HTTPBin Token",
            }
        )


def test_fetch_with_secret_says_to_leave_the_body_out_for_get() -> None:
    assert (
        "Leave it out for GET" in FetchArgs.model_json_schema()["properties"]["body"]["description"]
    )


def test_neither_description_carries_an_example_call(tmp_path) -> None:
    for description in (ASK_FOR_SECRET_TOOL.description, _fetch_description(tmp_path)):
        assert "ask_for_secret({" not in description
        assert "fetch_with_secret({" not in description


def test_ask_for_secret_says_the_model_picks_the_name_and_label_itself() -> None:
    assert "Pick the name and label yourself" in ASK_FOR_SECRET_TOOL.description
