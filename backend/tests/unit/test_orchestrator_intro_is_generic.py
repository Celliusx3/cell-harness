"""The bot's routing rules name no skill's own roles: a skill says what to start, and when."""

from __future__ import annotations

import re

import pytest

from harness.tickets.domain.prompts import ORCHESTRATOR_INTRO


@pytest.mark.parametrize("word", ["part", "combine", "page", "pack", "chapter", "comic"])
def test_the_routing_rules_name_no_word_of_one_skill(word: str) -> None:
    assert not re.search(rf"\b{word}s?\b", ORCHESTRATOR_INTRO, re.IGNORECASE)


def test_the_routing_rules_start_tasks_now_or_after_others_and_send_blocked_work_back() -> None:
    assert "start now" in ORCHESTRATOR_INTRO
    assert "only after" in ORCHESTRATOR_INTRO
    assert "attach to the ticket that holds that work" in ORCHESTRATOR_INTRO
