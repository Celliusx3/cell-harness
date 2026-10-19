"""`ask_user` — the question, the answer, and the declaration."""

from __future__ import annotations

import re

import pytest
from pydantic import ValidationError

from harness.tools import Ok
from harness.tools.client import ClientTools, ClientToolService
from harness.tools.native.question import ASK_USER, ASK_USER_TOOL, Answer, Question
from tests.unit.helpers import no_approvals

LONGEST_LABEL = "x" * 80
LONGEST_QUESTION = "q" * 240


def test_a_question_offers_two_to_four_short_distinct_options() -> None:
    assert Question(question="Which shop?", options=("Lazada", "Shopee")).options == (
        "Lazada",
        "Shopee",
    )
    Question(question=LONGEST_QUESTION, options=("a", "b", "c", LONGEST_LABEL))
    for bad in (
        {"question": "Which shop?", "options": ["Lazada"]},
        {"question": "Which shop?", "options": ["a", "b", "c", "d", "e"]},
        {"question": "Which shop?", "options": ["Lazada", "Lazada"]},
        {"question": "Which shop?", "options": ["Lazada", ""]},
        {"question": "Which shop?", "options": ["Lazada", LONGEST_LABEL + "x"]},
        {"question": LONGEST_QUESTION + "q", "options": ["Lazada", "Shopee"]},
        {"question": "", "options": ["Lazada", "Shopee"]},
        {"question": "Which shop?", "options": ["Lazada", "Shopee"], "header": "Shop"},
    ):
        with pytest.raises(ValidationError):
            Question.model_validate(bad)


def test_an_answer_names_a_choice_and_nothing_else() -> None:
    assert Answer(choice="Amazon").choice == "Amazon"
    for bad in ({"choice": ""}, {}, {"choice": "Shopee", "index": 1}):
        with pytest.raises(ValidationError):
            Answer.model_validate(bad)


def test_the_example_in_the_description_is_a_call_the_tool_accepts() -> None:
    (tool,) = ClientToolService(ClientTools((ASK_USER_TOOL,)), no_approvals()).tools()
    spec = tool.spec()
    assert spec.name == ASK_USER
    example = re.search(rf"{ASK_USER}\((\{{.*?\}})\)", spec.description)
    assert example is not None
    Question.model_validate_json(example.group(1))
    assert "Other" in spec.description


def test_a_tap_reaches_the_model_as_the_chosen_label() -> None:
    tools = ClientTools((ASK_USER_TOOL,))
    tapped = tools.parse(ASK_USER, {"kind": "shared", "data": {"choice": "Shopee"}})
    assert tools.outcome(tapped) == Ok(content='{"choice":"Shopee"}')
