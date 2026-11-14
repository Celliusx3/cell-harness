"""The messages that open a turn without the person typing: a bot's, schedules due, a ticket's."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

BotMessageIntent = Literal["request", "result"]
ReportState = Literal["progress", "waiting", "ready", "blocked", "failed", "dropped"]
ReportAsk = Literal["text", "choice", "secret", "location", "takeover"]
TicketAsk = Literal["text", "choice", "secret", "location", "takeover", "approval"]


class BotMessage(BaseModel):
    """What one bot sent another: who from, the text, how many hops it has come, and why."""

    model_config = ConfigDict(frozen=True)

    from_bot_id: str
    from_name: str
    text: str
    hop: int
    intent: BotMessageIntent


class BotMessageEvent(BaseModel):
    """Another bot's message entering this chat, opening the turn that answers it."""

    model_config = ConfigDict(frozen=True)

    type: Literal["bot/message"] = "bot/message"
    turn: int
    message: BotMessage


class ScheduleReminder(BaseModel):
    """One occurrence of a schedule: which one, its title and instruction, and when it was due."""

    model_config = ConfigDict(frozen=True)

    schedule_id: str
    title: str
    prompt: str
    occurrence_at: datetime


class ScheduleReminders(BaseModel):
    """The schedules due together in one bot's chat, in the order they were made."""

    model_config = ConfigDict(frozen=True)

    reminders: tuple[ScheduleReminder, ...] = Field(min_length=1)

    @property
    def text(self) -> str:
        """Their prompts, one per line, as who answers is chosen from."""
        return "\n".join(reminder.prompt for reminder in self.reminders)


class ScheduleReminderEvent(BaseModel):
    """Schedules falling due in their bot's own chat, opening the turn that acts on them."""

    model_config = ConfigDict(frozen=True)

    type: Literal["schedule/reminder"] = "schedule/reminder"
    turn: int
    reminders: tuple[ScheduleReminder, ...] = Field(min_length=1)


class TicketReport(BaseModel):
    """How a ticket's worker ended: which ticket, its title, its state, a summary, a question."""

    model_config = ConfigDict(frozen=True)

    ticket_id: str
    title: str
    state: ReportState
    text: str
    question: str | None
    ask: TicketAsk = "text"
    """How the person answers `question`; reports logged before it was asked are typed."""
    options: tuple[str, ...] | None = None
    secret_name: str | None = None
    approval_call_id: str | None = None
    """The worker's call that waits for the person's approval, when `ask` is `approval`."""
    approval_tool: str | None = None


class TicketReportEvent(BaseModel):
    """A ticket's worker ending, in the chat of the bot that started it, opening the next turn."""

    model_config = ConfigDict(frozen=True)

    type: Literal["ticket/report"] = "ticket/report"
    turn: int
    report: TicketReport


HeardMessage = BotMessage | ScheduleReminders | TicketReport
