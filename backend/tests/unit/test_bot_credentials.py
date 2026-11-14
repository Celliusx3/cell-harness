"""Which credentials a bot is tied to, and how a key is put on or taken off it."""

from __future__ import annotations

from harness.bots import Bot

CHEF = Bot(id="chef", name="Chef", instructions="Cook.", secret_names=("github", "notion"))
TRADER = Bot(id="trader", name="Trader", instructions="Trade.", model_credential="first_model")


def test_ticking_a_key_adds_it_last_and_unticking_takes_it_off() -> None:
    assert CHEF.with_secret("github", allowed=False).secret_names == ("notion",)
    assert TRADER.with_secret("github", allowed=True).secret_names == ("github",)
    assert CHEF.with_secret("github", allowed=True).secret_names == ("notion", "github")


def test_a_key_serves_the_bots_that_hold_it() -> None:
    assert CHEF.has_credential("github", "custom")
    assert not TRADER.has_credential("github", "custom")


def test_an_llm_credential_serves_the_bots_that_answer_on_it() -> None:
    assert TRADER.has_credential("first_model", "llm")
    assert not CHEF.has_credential("github", "llm")


def test_a_chat_token_serves_no_bot() -> None:
    assert not CHEF.has_credential("github", "telegram")


def test_a_bot_without_a_credential_loses_it_as_a_key_and_as_a_model() -> None:
    both = CHEF.model_copy(update={"model_credential": "github"})

    untied = both.without_credential("github")

    assert (untied.secret_names, untied.model_credential) == (("notion",), None)
