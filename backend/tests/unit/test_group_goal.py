"""A goal run's pure parts: the `/goal` text, the lead's decision block, and who it names."""

from __future__ import annotations

import pytest

from harness.groups import Group
from harness.groups.domain.goal import (
    GoalContinue,
    GoalFinish,
    goal_decision,
    goal_lead,
    goal_member,
    goal_text,
)
from harness.groups.domain.prompts import GOAL_LEAD
from tests.unit.test_speaker_queue import TEAM, E, R, W

DESK = Group(id="g", name="Desk", member_ids=("r", "w", "e"), lead_id="w")


@pytest.mark.parametrize(
    ("text", "goal"),
    [
        ("/goal ship it", "ship it"),
        ("/goal   ship it  ", "ship it"),
        ("/goal @Writer ship it", "@Writer ship it"),
        ("/goal ", None),
        ("/goal    ", None),
        ("/goal", None),
        ("/goals ship it", None),
        ("ship it /goal now", None),
    ],
)
def test_only_goal_and_some_text_starts_a_goal(text, goal) -> None:
    assert goal_text(text) == goal


def test_a_continue_block_names_the_next_member_and_task() -> None:
    reply = 'Over to you.\n<goal>{"status":"continue","next":"Writer","task":"Draft it"}</goal>'

    assert goal_decision(reply) == GoalContinue(status="continue", next="Writer", task="Draft it")


def test_the_last_complete_block_wins() -> None:
    reply = (
        'For example <goal>{"status":"done","detail":"x"}</goal> is how it ends.\n'
        '<goal>{"status":"blocked","detail":"No data."}</goal>'
    )

    assert goal_decision(reply) == GoalFinish(status="blocked", detail="No data.")


@pytest.mark.parametrize(
    "reply",
    [
        "No block at all.",
        "<goal>{not json}</goal>",
        '<goal>{"status":"continue","next":"Writer"}</goal>',
        '<goal>{"status":"continue","next":" ","task":"Draft"}</goal>',
        '<goal>{"status":"done"}</goal>',
        '<goal>{"status":"done","detail":"  "}</goal>',
        '<goal>{"status":"maybe","detail":"x"}</goal>',
        '<goal>{"status":"done","detail":"x"}',
    ],
)
def test_a_missing_or_broken_block_is_no_decision(reply) -> None:
    assert goal_decision(reply) is None


def test_the_first_member_named_in_the_goal_leads() -> None:
    assert goal_lead("ask @Copy Editor then @Researcher", TEAM, DESK) == E


def test_with_nobody_named_the_group_s_lead_leads_else_the_first_member() -> None:
    assert goal_lead("ship it", TEAM, DESK) == W
    assert goal_lead("ship it", (R, E), DESK) == R


@pytest.mark.parametrize(
    ("reference", "member"),
    [("w", W), ("Writer", W), ("@writer", W), (" COPY EDITOR ", E), ("Researcher", None)],
)
def test_a_member_is_named_by_id_or_name_and_never_the_lead(reference, member) -> None:
    assert goal_member(reference, TEAM, lead_id="r") == member


def test_a_name_two_members_share_names_nobody() -> None:
    twin = W.model_copy(update={"id": "w2"})

    assert goal_member("Writer", (R, W, twin), lead_id="r") is None
    assert goal_member("w2", (R, W, twin), lead_id="r") == twin


def test_a_member_outside_the_active_ones_is_nobody() -> None:
    assert goal_member("Copy Editor", (R, W), lead_id="r") is None


def test_the_lead_is_told_the_block_is_the_only_way_to_hand_over_a_turn() -> None:
    assert "only through the block; message_bot does not reach a member" in GOAL_LEAD.replace(
        "\n", " "
    )
