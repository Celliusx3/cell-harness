"""The secrets page's request and response bodies."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from harness.secrets import Destination


class AllowedBot(BaseModel):
    """A bot that may use a key: its id and the name the sidebar shows."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str


class SavedKey(Destination):
    """One saved key as the bot page lists it: its name, its site and its bots, never its value."""

    name: str
    bots: tuple[AllowedBot, ...]
