"""A turn is told its workspace, logged once and again only when it changes; a group names both."""

from __future__ import annotations

from dataclasses import replace

from harness.session.domain.models import WorkspaceEvent
from tests.unit.fakes import SteppedClient, completed
from tests.unit.helpers import drain, new_session, runtime_over
from tests.webapp import files_in


async def test_a_bots_own_chat_logs_its_workspace_once_and_tells_it(tmp_path) -> None:
    files = files_in(tmp_path)
    client = SteppedClient(completed("one"), completed("two"))
    runtime = replace(runtime_over(client), files=files, own_chat_of=lambda bot_id: bot_id)
    session = new_session("translator")

    await drain(runtime.run("q", session=session, bot_id="translator"))
    await drain(runtime.run("q", session=session, bot_id="translator"))

    logged = [e for e in session.events() if isinstance(e, WorkspaceEvent)]
    workspace = str(files.workspace("translator"))
    assert logged == [WorkspaceEvent(bot_id="translator", workspace=workspace, own_workspace=None)]
    system = runtime.request_messages(session, sees_images=False)[0].content
    assert workspace in system


async def test_a_group_turn_is_told_the_groups_workspace_and_its_own(tmp_path) -> None:
    files = files_in(tmp_path)
    client = SteppedClient(completed("hi"))
    runtime = replace(runtime_over(client), files=files, own_chat_of=lambda bot_id: bot_id)
    session = new_session("group-1")

    await drain(runtime.run("q", session=session, bot_id="translator"))

    system = runtime.request_messages(session, sees_images=False)[0].content
    assert str(files.workspace("group-1")) in system
    assert str(files.workspace("translator")) in system


async def test_a_runtime_without_files_tells_no_workspace(tmp_path) -> None:
    session = new_session("translator")

    await drain(runtime_over(SteppedClient(completed("hi"))).run("q", session=session, bot_id="b"))

    assert not [e for e in session.events() if isinstance(e, WorkspaceEvent)]
