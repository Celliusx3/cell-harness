"""Who answers a message that names nobody: the group's reply setting says, and @names win."""

from __future__ import annotations

import pytest

from harness.groups import Group
from harness.groups.domain.models import ReplySetting
from harness.groups.domain.speaker_queue import SpeakerQueue
from tests.unit.test_speaker_queue import TEAM, E, R, W, opened_by, turn


def desk(reply: ReplySetting, lead_id: str | None = None) -> Group:
    return Group(id="g", name="Desk", member_ids=("r", "w", "e"), lead_id=lead_id, reply=reply)


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
    assert SpeakerQueue.after_message("what now?", TEAM, group).waiting == answering


@pytest.mark.parametrize("reply", ["everyone", "lead", "mentions"])
def test_named_members_answer_whatever_the_setting(reply: ReplySetting) -> None:
    group = desk(reply, "w")

    assert SpeakerQueue.after_message("@Copy Editor then @Researcher", TEAM, group).waiting == (
        R,
        E,
    )
    assert SpeakerQueue.after_message("@everyone what now?", TEAM, group).waiting == TEAM


def test_a_lead_no_longer_active_gives_way_to_the_first_active_member() -> None:
    assert SpeakerQueue.after_message("go", (W, E), desk("lead", "r")).waiting == (W,)


def test_the_replayed_log_follows_the_same_setting() -> None:
    lead_only = opened_by("go", turn(0, W, "Done."))
    named = opened_by("@Writer @Copy Editor", turn(0, W, "Done."))

    assert SpeakerQueue.next_in(lead_only, TEAM, desk("lead", "w")) is None
    assert SpeakerQueue.next_in(named, TEAM, desk("mentions")) == E
    assert SpeakerQueue.next_in(opened_by("go", turn(0, R, "Hi.")), TEAM, desk("everyone")) == W


def test_an_older_groups_file_answers_with_everyone() -> None:
    assert Group(id="g", name="Desk", member_ids=("r", "w")).reply == "everyone"
