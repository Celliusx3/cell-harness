"""Which bots a credential serves: a site's key is one of a bot's keys, a model is its one model."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from types import MappingProxyType

from harness.bots.models import Bot


def _holds_key(bot: Bot, name: str) -> bool:
    return name in bot.secret_names


def _answers_with_model(bot: Bot, name: str) -> bool:
    return bot.model_credential == name


SERVED_BY: Mapping[str, Callable[[Bot, str], bool]] = MappingProxyType(
    {"custom": _holds_key, "llm": _answers_with_model}
)


def _with_key(bot: Bot, name: str, is_ticked: bool) -> Bot:
    kept = tuple(held for held in bot.secret_names if held != name)
    return bot.model_copy(update={"secret_names": (*kept, name) if is_ticked else kept})


def retied_bots(active: tuple[Bot, ...], name: str, ticked_ids: tuple[str, ...]) -> tuple[Bot, ...]:
    """The bots in `active` whose hold on the key `name` changes when only `ticked_ids` hold it."""
    return tuple(
        _with_key(bot, name, bot.id in ticked_ids)
        for bot in active
        if _holds_key(bot, name) != (bot.id in ticked_ids)
    )


def served_bots(bots: tuple[Bot, ...], name: str, kind: str) -> tuple[Bot, ...]:
    """The bots in `bots` the credential `name` of `kind` serves; none for a kind no bot holds."""
    serves = SERVED_BY.get(kind)
    return tuple(bot for bot in bots if serves is not None and serves(bot, name))


def untied_bot(bot: Bot, name: str) -> Bot:
    """`bot` with the credential `name` off its keys and off its model."""
    return bot.model_copy(
        update={
            "secret_names": tuple(held for held in bot.secret_names if held != name),
            "model_credential": None if bot.model_credential == name else bot.model_credential,
        }
    )
