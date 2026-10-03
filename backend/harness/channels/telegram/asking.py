"""How a client tool's ask is put to a Telegram chat."""

from __future__ import annotations

import json

from pydantic import ValidationError
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from harness.channels.protocol import Pushing
from harness.channels.text import split_message
from harness.tools.client import PendingCall
from harness.tools.native.location import LOCATION
from harness.tools.native.question import QUESTION, Question

MAX_MESSAGE_CHARS = 4096
MAX_CALLBACK_BYTES = 64

ASK = {LOCATION: "The assistant needs your location to answer. Share it?"}
SHARE_LABEL = "Share my location"
ASK_BY_LINK = "The assistant needs something from your device. Open the page to answer."
APPROVE_BY_LINK = "The assistant wants to run {label}. Open the page to allow or deny."
NO_ANSWER_PAGE = "(Answering from Telegram needs `web.public_url` to be set.)"

CALLBACK_PREFIX = "ap"
CHOICE_PREFIX = "qa"
BUTTONS: tuple[tuple[str, str], ...] = (
    ("Allow once", "once"),
    ("Allow for this conversation", "conversation"),
    ("Always allow", "always"),
    ("Deny", "deny"),
)


async def ask_client(
    channel: Pushing,
    bot,
    chat_id: str,
    request: PendingCall,
    url: str,
    *,
    gated: frozenset[str],
) -> None:
    """Put `request` to the chat: a location keyboard, options, an approval card, or the page."""
    if request.name == LOCATION:
        await _ask_location(bot, chat_id)
        return
    question = _question(request.arguments) if request.name == QUESTION else None
    if question is not None and _choices_fit(request.call_id, question):
        await _ask_question(bot, chat_id, request.call_id, question)
        return
    if request.name in gated and _buttons_fit(request):
        await _ask_approval(channel, bot, chat_id, request)
        return
    text = (
        APPROVE_BY_LINK.format(label=_label(request.name)) if request.name in gated else ASK_BY_LINK
    )
    if not url:
        await channel.send_message(chat_id, f"{text} {NO_ANSWER_PAGE}")
        return
    await channel.send_link(chat_id, text, url)


def approval_text(request: PendingCall) -> str:
    """The card: who wants to run, and with what."""
    label = _label(request.name)
    server = _server(request.name)
    first = f"{label} ({server}) wants to run with:" if server else f"{label} wants to run with:"
    return "\n".join([first, *_argument_lines(request.arguments)])


def _label(name: str) -> str:
    return name.rsplit("__", 1)[-1].replace("_", " ")


def _server(name: str) -> str:
    return name.rsplit("__", 1)[0].replace("_", " ") if "__" in name else ""


def _argument_lines(arguments: str) -> list[str]:
    try:
        parsed = json.loads(arguments)
    except ValueError:
        return [arguments]
    if not isinstance(parsed, dict):
        return [arguments]
    return [f"{key}: {_render(value)}" for key, value in parsed.items()]


def _render(value: object) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _callback(call_id: str, choice: str) -> str:
    return f"{CALLBACK_PREFIX}:{call_id}:{choice}"


def _buttons_fit(request: PendingCall) -> bool:
    longest = max(len(_callback(request.call_id, choice).encode()) for _, choice in BUTTONS)
    return longest <= MAX_CALLBACK_BYTES


def _keyboard(call_id: str) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(label, callback_data=_callback(call_id, choice))
        for label, choice in BUTTONS
    ]
    return InlineKeyboardMarkup([buttons[:2], buttons[2:]])


async def _ask_approval(channel: Pushing, bot, chat_id: str, request: PendingCall) -> None:
    *earlier, last = split_message(approval_text(request), MAX_MESSAGE_CHARS)
    for part in earlier:
        await channel.send_message(chat_id, part)
    await bot.send_message(chat_id=int(chat_id), text=last, reply_markup=_keyboard(request.call_id))


def _question(arguments: str) -> Question | None:
    try:
        return Question.model_validate_json(arguments)
    except ValidationError:
        return None


def _choice_callback(call_id: str, index: int) -> str:
    return f"{CHOICE_PREFIX}:{call_id}:{index}"


def _choices_fit(call_id: str, question: Question) -> bool:
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


async def _ask_question(bot, chat_id: str, call_id: str, question: Question) -> None:
    await bot.send_message(
        chat_id=int(chat_id),
        text=question.question,
        reply_markup=_choice_keyboard(call_id, question),
    )


async def _ask_location(bot, chat_id: str) -> None:
    button = KeyboardButton(SHARE_LABEL, request_location=True)
    await bot.send_message(
        chat_id=int(chat_id),
        text=ASK[LOCATION],
        reply_markup=ReplyKeyboardMarkup([[button]], one_time_keyboard=True, resize_keyboard=True),
    )
