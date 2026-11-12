"""The app-wide events: what happened outside any one chat's log."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class TurnStartedAppEvent(BaseModel):
    """A turn began in this chat."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    type: Literal["chat/turn-started"] = "chat/turn-started"
    chat_id: str


class BotsChangedAppEvent(BaseModel):
    """The bots or groups were written."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    type: Literal["bots/changed"] = "bots/changed"


AppEvent = TurnStartedAppEvent | BotsChangedAppEvent
