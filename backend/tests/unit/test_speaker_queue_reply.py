"""Who answers a message that names nobody: the group's reply setting says, and @names win."""

from __future__ import annotations

import pytest

from harness.groups import Group
from harness.groups.domain.models import ReplySetting
from harness.groups.domain.speaker_queue import SpeakerQueue, picks_by_auto
from harness.session.domain.models import GoalStartEvent, GroupAutoPickEvent
from tests.unit.test_speaker_queue import TEAM, E, R, W, opened_by, turn


def desk(reply: ReplySetting, lead_id: str | None = None) -> Group:
    model = "m" if reply == "auto" else None
    return Group(
        id="g",
        name="Desk",
        member_ids=("r", "w", "e"),
        lead_id=lead_id,
        reply=reply,
        auto_model=model,
    )


def picked(bot_id: str | None, *, at: int = 0, fallback: bool = False) -> GroupAutoPickEvent:
    return GroupAutoPickEvent(turn=at, bot_id=bot_id, confidence=0.9, fallback=fallback)


@pytest.mark.parametrize(
    ("group", "answering"),
    [
        (desk("everyone"), TEAM),
        (desk("lead", "w"), (W,)),
        (desk("lead"), (R,)),
        (desk("lead", "gone"), (R,)),
        (desk("mentions", "w"), ()),
    ],
)
def test_a_plain_message_is_answered_by_the_reply_setting(group, answering) -> None:
    assert SpeakerQueue.after_message("what now?", TEAM, group, None).waiting == answering


@pytest.mark.parametrize("reply", ["everyone", "lead", "mentions", "auto"])
def test_named_members_answer_whatever_the_setting(reply: ReplySetting) -> None:
    group = desk(reply, "w")

    assert SpeakerQueue.after_message(
        "@Copy Editor then @Researcher", TEAM, group, None
    ).waiting == (
        R,
        E,
    )
    assert SpeakerQueue.after_message("@everyone what now?", TEAM, group, None).waiting == TEAM


def test_a_lead_no_longer_active_gives_way_to_the_first_active_member() -> None:
    assert SpeakerQueue.after_message("go", (W, E), desk("lead", "r"), None).waiting == (W,)


def test_the_replayed_log_follows_the_same_setting() -> None:
    lead_only = opened_by("go", turn(0, W, "Done."))
    named = opened_by("@Writer @Copy Editor", turn(0, W, "Done."))

    assert SpeakerQueue.next_in(lead_only, TEAM, desk("lead", "w")) is None
    assert SpeakerQueue.next_in(named, TEAM, desk("mentions")) == E
    assert SpeakerQueue.next_in(opened_by("go", turn(0, R, "Hi.")), TEAM, desk("everyone")) == W


def test_an_older_groups_file_answers_with_everyone() -> None:
    assert Group(id="g", name="Desk", member_ids=("r", "w")).reply == "everyone"


@pytest.mark.parametrize(
    ("pick", "answering"),
    [
        (picked("e"), (E,)),
        (picked(None), TEAM),
        (picked("w", fallback=True), (W,)),
        (picked("gone"), (W,)),
        (None, (W,)),
    ],
)
def test_auto_answers_with_its_pick_and_else_the_lead(pick, answering) -> None:
    assert (
        SpeakerQueue.after_message("what now?", TEAM, desk("auto", "w"), pick).waiting == answering
    )


@pytest.mark.parametrize(
    ("text", "reply", "asks"),
    [
        ("what is NVDA's price?", "auto", True),
        ("@Writer, the price?", "auto", False),
        ("@everyone, the price?", "auto", False),
        ("what is NVDA's price?", "lead", False),
    ],
)
def test_only_an_auto_group_s_message_naming_nobody_asks_the_model(text, reply, asks) -> None:
    assert picks_by_auto(text, TEAM, desk(reply)) is asks


def test_the_replayed_log_follows_the_pick_logged_for_the_message_s_turn() -> None:
    everyone = [picked(None), *opened_by("go", turn(0, R, "Sources."))]
    researcher = [picked("r"), *opened_by("go", turn(0, R, "Sources."))]
    stale = [*researcher, *opened_by("again", turn(1, W, "Draft."))]

    assert SpeakerQueue.next_in(everyone, TEAM, desk("auto", "w")) == W
    assert SpeakerQueue.next_in(researcher, TEAM, desk("auto", "w")) is None
    assert SpeakerQueue.next_in(stale, TEAM, desk("auto", "w")) is None


def test_nobody_the_goal_or_a_reply_names_is_queued_after_a_goal_message() -> None:
    start = GoalStartEvent(turn=0, goal="@Writer ship it", lead_id="r", max_turns=13)
    events = [start, *opened_by("/goal @Writer ship it", turn(0, R, "@Copy Editor go."))]

    assert SpeakerQueue.next_in(events, TEAM, desk("everyone")) is None
