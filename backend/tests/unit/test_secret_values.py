"""What the person may type as a key, where a key may be sent, and how it is redacted."""

from __future__ import annotations

import base64
import json
from urllib.parse import quote

import pytest

from harness.secrets import Destination, redacted
from harness.tools.native.secrets import SecretAsk
from harness.web.routes.secret_card import SecretEntry

MARK = "Q7xZ"
ORIGIN = "https://api.example.com"
TRANSPORT_HEADERS = ("Host", "Content-Length", "Transfer-Encoding", "Connection", "Cookie")
CASES = (str, str.lower, str.upper, str.swapcase)


def _destination(**fields: str) -> Destination:
    return Destination.model_validate({"origin": ORIGIN, **fields})


@pytest.mark.parametrize("value", ["tok-9Zx=", "Ab3$ x" * 2730 + "Ab3$"], ids=["8", "16384"])
def test_a_typed_key_of_8_to_16384_printable_characters_is_taken(value: str) -> None:
    entry = SecretEntry.model_validate({"value": value})

    assert entry.value.get_secret_value() == value


@pytest.mark.parametrize(
    "value",
    [
        f"{MARK}-ab",
        MARK + "k" * 16381,
        f" {MARK}-abcd",
        f"{MARK}-abcd ",
        f"{MARK}\nabcd",
        f"{MARK}-abcdé",
    ],
    ids=["7", "16385", "leading space", "trailing space", "newline", "non-ascii"],
)
def test_a_typed_key_that_breaks_the_rule_is_refused_without_showing_it(value: str) -> None:
    with pytest.raises(ValueError) as refused:
        SecretEntry.model_validate({"value": value})

    assert MARK not in str(refused.value)
    assert MARK not in repr(refused.value)


@pytest.mark.parametrize(
    "origin",
    [
        "http://api.example.com",
        "https://api.example.com/v1",
        "https://api.example.com?key=1",
        "https://api.example.com#top",
        "https://user:pw@api.example.com",
    ],
    ids=["http", "path", "query", "fragment", "userinfo"],
)
def test_a_destination_is_an_https_origin_and_nothing_more(origin: str) -> None:
    with pytest.raises(ValueError):
        _destination(origin=origin, auth="bearer")


@pytest.mark.parametrize("origin", [ORIGIN, "https://api.example.com:8443"])
def test_an_https_origin_with_or_without_a_port_is_a_destination(origin: str) -> None:
    assert _destination(origin=origin, auth="bearer").origin == origin


def test_header_auth_needs_a_header_name_and_bearer_refuses_one() -> None:
    assert _destination(auth="header", header_name="X-Api-Key").header_name == "X-Api-Key"
    with pytest.raises(ValueError):
        _destination(auth="header")
    with pytest.raises(ValueError):
        _destination(auth="bearer", header_name="X-Api-Key")


@pytest.mark.parametrize("header", [case(name) for name in TRANSPORT_HEADERS for case in CASES])
def test_a_header_the_transport_owns_cannot_carry_a_key(header: str) -> None:
    with pytest.raises(ValueError):
        _destination(auth="header", header_name=header)


@pytest.mark.parametrize("auth", [{"auth": "bearer"}, {"auth": "header", "header_name": "X-Key"}])
def test_an_ask_saves_its_site_and_how_it_takes_the_key(auth: dict[str, str]) -> None:
    ask = SecretAsk.model_validate({"name": "api", "label": "API key", "origin": ORIGIN, **auth})

    assert ask.destination == _destination(**auth)


def test_redact_blanks_the_key_as_is_json_escaped_url_quoted_and_base64() -> None:
    value = 'tok-"q/+9Zx=7Lm'
    forms = (
        value,
        json.dumps(value)[1:-1],
        quote(value, safe=""),
        base64.b64encode(value.encode()).decode(),
    )
    echoed = " | ".join(f"<{form}>" for form in forms)

    assert redacted(echoed, value) == " | ".join("<[secret]>" for _ in forms)


def test_redact_leaves_text_without_the_key_alone() -> None:
    text = 'status ok: "tok", 9Zx=7Lm and q/+ are not the key'

    assert redacted(text, 'tok-"q/+9Zx=7Lm') == text
