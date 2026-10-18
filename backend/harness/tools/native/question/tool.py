"""`ask_user`, declared as a client tool."""

from __future__ import annotations

from harness.tools.client import ClientTool
from harness.tools.native.question.models import Answer, Question

ASK_USER = "ask_user"

ASK_USER_TOOL = ClientTool(
    name=ASK_USER,
    description=(
        "Ask the user one short multiple-choice question with tappable answers, then "
        "wait for their tap. Use this instead of asking them to type when a few short "
        "choices are enough. Give two to four options, never more: "
        'ask_user({"question": "Which shop should I search?", "options": ["Lazada", "Shopee"]}). '
        'The result is their answer, as {"choice": "Shopee"}. Do not add an "Other" '
        "option: they can always type their own answer instead, and then their message "
        "is the answer, so do not ask the same question again."
    ),
    args_model=Question,
    data_model=Answer,
)
