"""Which bots a credential serves, and which change when the person ticks a different set."""

from __future__ import annotations

from harness.bots import Bot
from harness.bots.ties import retied_bots, served_bots, untied_bot

CHEF = Bot(id="chef", name="Chef", instructions="Cook.", secret_names=("github", "notion"))
TRADER = Bot(id="trader", name="Trader", instructions="Trade.", model_credential="first_model")


def test_ticking_a_key_adds_it_and_unticking_takes_it_off() -> None:
    retied = retied_bots((CHEF, TRADER), "github", ("trader",))

    assert {bot.id: bot.secret_names for bot in retied} == {
        "chef": ("notion",),
        "trader": ("github",),
    }


def test_a_bot_whose_tie_stays_is_not_among_the_changed() -> None:
    assert retied_bots((CHEF, TRADER), "github", ("chef",)) == ()


def test_an_llm_credential_serves_the_bots_that_answer_on_it() -> None:
    assert served_bots((CHEF, TRADER), "first_model", "llm") == (TRADER,)
    assert served_bots((CHEF, TRADER), "github", "llm") == ()


def test_a_chat_token_serves_no_bot() -> None:
    assert served_bots((CHEF, TRADER), "github", "telegram") == ()


def test_an_untied_bot_loses_the_name_as_a_key_and_as_a_model() -> None:
    both = CHEF.model_copy(update={"model_credential": "github"})

    untied = untied_bot(both, "github")

    assert (untied.secret_names, untied.model_credential) == (("notion",), None)
