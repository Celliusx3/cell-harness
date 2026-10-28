"""Which bots a credential serves: a site's key is one of a bot's keys, a model is its one model."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from harness.bots.models import Bot

TiedKind = Literal["custom", "llm"]


@dataclass(frozen=True)
class Tie:
    """How one kind of credential is tied to a bot: whether it is, and the bot tied or untied."""

    is_tied: Callable[[Bot, str], bool]
    retied: Callable[[Bot, str, bool], Bot]


def _holds_key(bot: Bot, name: str) -> bool:
    return name in bot.secret_names


def _with_key(bot: Bot, name: str, is_ticked: bool) -> Bot:
    kept = tuple(held for held in bot.secret_names if held != name)
    return bot.model_copy(update={"secret_names": (*kept, name) if is_ticked else kept})


def _answers_with_model(bot: Bot, name: str) -> bool:
    return bot.model_credential == name


def _with_model(bot: Bot, name: str, is_ticked: bool) -> Bot:
    return bot.model_copy(update={"model_credential": name if is_ticked else None})


TIES: Mapping[str, Tie] = MappingProxyType(
    {
        "custom": Tie(is_tied=_holds_key, retied=_with_key),
        "llm": Tie(is_tied=_answers_with_model, retied=_with_model),
    }
)


def retied_bots(
    active: tuple[Bot, ...], name: str, kind: TiedKind, ticked_ids: tuple[str, ...]
) -> tuple[Bot, ...]:
    """The bots in `active` whose tie to `name` changes when it serves exactly `ticked_ids`."""
    tie = TIES[kind]
    return tuple(
        tie.retied(bot, name, bot.id in ticked_ids)
        for bot in active
        if tie.is_tied(bot, name) != (bot.id in ticked_ids)
    )


def served_bots(bots: tuple[Bot, ...], name: str, kind: str) -> tuple[Bot, ...]:
    """The bots in `bots` the credential `name` of `kind` serves; none for a kind no bot holds."""
    tie = TIES.get(kind)
    return tuple(bot for bot in bots if tie is not None and tie.is_tied(bot, name))


def untied_bot(bot: Bot, name: str) -> Bot:
    """`bot` with the credential `name` off its keys and off its model."""
    return bot.model_copy(
        update={
            "secret_names": tuple(held for held in bot.secret_names if held != name),
            "model_credential": None if bot.model_credential == name else bot.model_credential,
        }
    )
