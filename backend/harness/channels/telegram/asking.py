"""How a client tool's ask is put to a Telegram chat."""

from __future__ import annotations

import json
from typing import Literal, TypeIs

from pydantic import ValidationError
from telegram import (
    Bot,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from harness.channels.domain.protocol import PushChannel
from harness.channels.domain.text import split_message
from harness.tools.client import PendingCall
from harness.tools.domain.decision import Scope
from harness.tools.native.location import GET_LOCATION
from harness.tools.native.question import ASK_USER, Question

MAX_MESSAGE_CHARS = 4096
MAX_CALLBACK_BYTES = 64

LOCATION_ASK = "The assistant needs your location to answer. Share it?"
SHARE_LABEL = "Share my location"
ASK_BY_LINK = (
    "The assistant needs an answer from you. Open the page to give it there; "
    "never paste a key or password into this chat."
)
APPROVE_BY_LINK = "The assistant wants to run {label}. Open the page to allow or deny."
NO_ANSWER_PAGE = "(Answering from Telegram needs `web.public_url` to be set.)"

APPROVAL_CALLBACK_PREFIX = "ap"
CHOICE_PREFIX = "qa"
ApprovalChoice = Literal[Scope, "deny"]
APPROVAL_BUTTONS: tuple[tuple[str, ApprovalChoice], ...] = (
    ("Allow once", "once"),
    ("Allow for this conversation", "conversation"),
    ("Always allow", "always"),
    ("Deny", "deny"),
)
APPROVAL_CHOICES = frozenset(choice for _, choice in APPROVAL_BUTTONS)


def is_approval_choice(word: str) -> TypeIs[ApprovalChoice]:
    """Whether `word` is what one of the approval card's buttons answers."""
    return word in APPROVAL_CHOICES


async def ask_client(
    channel: PushChannel,
    bot: Bot,
    chat_id: str,
    request: PendingCall,
    url: str,
    *,
    protected_tools: frozenset[str],
) -> None:
    """Put `request` to the chat: a location keyboard, options, an approval card, or the page."""
    if request.name == GET_LOCATION:
        await _ask_location(bot, chat_id)
        return
    question = _question(request.arguments) if request.name == ASK_USER else None
    if question is not None and _has_room_for_choices(request.call_id, question):
        await _ask_question(bot, chat_id, request.call_id, question)
        return
    if request.name in protected_tools and _has_room_for_buttons(request):
        await _ask_approval(channel, bot, chat_id, request)
        return
    text = (
        APPROVE_BY_LINK.format(label=_tool_label(request.name))
        if request.name in protected_tools
        else ASK_BY_LINK
    )
    if not url:
        await channel.send_message(chat_id, f"{text} {NO_ANSWER_PAGE}")
        return
    await channel.send_link(chat_id, text, url)


def approval_text(request: PendingCall) -> str:
    """The card: who wants to run, and with what."""
    label = _tool_label(request.name)
    server = _server_label(request.name)
    first = f"{label} ({server}) wants to run with:" if server else f"{label} wants to run with:"
    return "\n".join([first, *_argument_lines(request.arguments)])


def _tool_label(name: str) -> str:
    return name.rsplit("__", 1)[-1].replace("_", " ")


def _server_label(name: str) -> str:
    return name.rsplit("__", 1)[0].replace("_", " ") if "__" in name else ""


def _argument_lines(arguments: str) -> list[str]:
    try:
        parsed = json.loads(arguments)
    except ValueError:
        return [arguments]
    if not isinstance(parsed, dict):
        return [arguments]
    return [f"{key}: {_argument_text(value)}" for key, value in parsed.items()]


def _argument_text(value: object) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _approval_callback_data(call_id: str, choice: str) -> str:
    return f"{APPROVAL_CALLBACK_PREFIX}:{call_id}:{choice}"


def _has_room_for_buttons(request: PendingCall) -> bool:
    longest = max(
        len(_approval_callback_data(request.call_id, choice).encode())
        for _, choice in APPROVAL_BUTTONS
    )
    return longest <= MAX_CALLBACK_BYTES


def _approval_keyboard(call_id: str) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(label, callback_data=_approval_callback_data(call_id, choice))
        for label, choice in APPROVAL_BUTTONS
    ]
    return InlineKeyboardMarkup([buttons[:2], buttons[2:]])


async def _ask_approval(channel: PushChannel, bot: Bot, chat_id: str, request: PendingCall) -> None:
    *earlier, last = split_message(approval_text(request), MAX_MESSAGE_CHARS)
    for part in earlier:
        await channel.send_message(chat_id, part)
    await bot.send_message(
        chat_id=int(chat_id), text=last, reply_markup=_approval_keyboard(request.call_id)
    )


def _question(arguments: str) -> Question | None:
    try:
        return Question.model_validate_json(arguments)
    except ValidationError:
        return None


def _choice_callback(call_id: str, index: int) -> str:
    return f"{CHOICE_PREFIX}:{call_id}:{index}"


def _has_room_for_choices(call_id: str, question: Question) -> bool:
    longest = max(
        len(_choice_callback(call_id, index).encode()) for index in range(len(question.options))
    )
    return longest <= MAX_CALLBACK_BYTES


def _choice_keyboard(call_id: str, question: Question) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(option, callback_data=_choice_callback(call_id, index))]
            for index, option in enumerate(question.options)
        ]
    )


async def _ask_question(bot: Bot, chat_id: str, call_id: str, question: Question) -> None:
    await bot.send_message(
        chat_id=int(chat_id),
        text=question.question,
        reply_markup=_choice_keyboard(call_id, question),
    )


async def _ask_location(bot: Bot, chat_id: str) -> None:
    button = KeyboardButton(SHARE_LABEL, request_location=True)
    await bot.send_message(
        chat_id=int(chat_id),
        text=LOCATION_ASK,
        reply_markup=ReplyKeyboardMarkup([[button]], one_time_keyboard=True, resize_keyboard=True),
    )
