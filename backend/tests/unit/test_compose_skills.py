"""Skills and bot_create through the real object graph: offered while one exists."""

from __future__ import annotations

import json
from pathlib import Path

from harness.llm import Message, SystemMessage, ToolCall, UserMessage
from harness.runtime.service import Runtime
from harness.session.domain.models import TurnStart, UserMessageEvent
from harness.skills import SKILL
from harness.tickets.domain.prompts import ORCHESTRATOR_INTRO
from harness.tools import Ok
from harness.tools.native.bots import BOT_CREATE, MESSAGE_BOT
from harness.tools.native.code_mode import EXECUTE_TYPESCRIPT, LIST_FUNCTIONS
from harness.tools.native.tickets import TICKET_NOTE, TICKET_ROUTE
from harness.web.runtime import DEFAULT_TOOLS, SCHEDULE_TOOLS
from tests.unit.helpers import (
    ORIGIN,
    new_session,
    no_progress,
    skills_at,
)
from tests.unit.skills_compose import compose, write_skill
from tests.unit.worker_helpers import worker_of
from tests.webapp import MODEL_CREDENTIAL, a_model_saved_in

__all__ = ["compose"]


def test_the_tool_is_offered_exactly_while_a_skill_exists(compose) -> None:
    build, root = compose
    runtime = build()
    assert runtime.tools is not None

    assert SKILL not in [s.name for s in runtime.tools.specs(sees_images=False)]

    directory = write_skill(root, "pdf")
    offered = [s.name for s in runtime.tools.specs(sees_images=True)]
    assert SKILL in offered
    attached_later = (MESSAGE_BOT, *SCHEDULE_TOOLS, BOT_CREATE, TICKET_ROUTE, TICKET_NOTE)
    assert offered == [name for name in DEFAULT_TOOLS if name not in attached_later]

    (directory / "SKILL.md").unlink()
    assert SKILL not in [s.name for s in runtime.tools.specs(sees_images=False)]


def test_bot_create_is_offered_exactly_while_an_llm_credential_is_saved(
    compose, tmp_path: Path
) -> None:
    build, _ = compose
    runtime = build()
    assert runtime.tools is not None

    assert BOT_CREATE not in [s.name for s in runtime.tools.specs(sees_images=False)]

    saved = a_model_saved_in(tmp_path)
    assert BOT_CREATE in [s.name for s in runtime.tools.specs(sees_images=False)]

    saved.delete(MODEL_CREDENTIAL)
    assert BOT_CREATE not in [s.name for s in runtime.tools.specs(sees_images=False)]


async def test_the_first_user_message_lists_the_skills_exactly_while_one_exists(compose) -> None:
    build, root = compose
    runtime = build()
    alone = [SystemMessage(content=ORCHESTRATOR_INTRO), UserMessage(content="hi")]

    assert await request_of(runtime) == alone

    directory = write_skill(root, "pdf")
    system, user = await request_of(runtime)
    assert system == SystemMessage(content=ORCHESTRATOR_INTRO)
    assert user.content.startswith("hi\n\n<system-reminder>\n")
    assert "\n- pdf: pdf things.\n</system-reminder>" in user.content

    (directory / "SKILL.md").unlink()
    assert await request_of(runtime) == alone


async def request_of(runtime: Runtime) -> list[Message]:
    """The request a step would send for one message, "hi"."""
    session = new_session()
    session.append(TurnStart(turn=0, bot_id="b"))
    session.append(UserMessageEvent(turn=0, message=UserMessage(content="hi")))
    return runtime.request_messages(
        session, await runtime.hooks.start_of_step(None), sees_images=False
    )


async def test_the_tool_dispatches_and_returns_the_body(compose) -> None:
    build, root = compose
    write_skill(root, "pdf")
    runtime = build()
    assert runtime.tools is not None

    outcome = await runtime.tools.execute(
        ToolCall(id="c1", name=SKILL, arguments=json.dumps({"name": "pdf"})),
        progress=no_progress,
        origin=ORIGIN,
        session=new_session(),
        sees_images=False,
    )

    assert isinstance(outcome, Ok) and "Do pdf." in outcome.text


async def test_a_script_cannot_reach_it(compose) -> None:
    build, root = compose
    write_skill(root, "pdf")
    runtime = worker_of(build())
    assert runtime.tools is not None

    listed = await runtime.tools.execute(
        ToolCall(id="c1", name=LIST_FUNCTIONS, arguments="{}"),
        progress=no_progress,
        origin=ORIGIN,
        session=new_session(),
        sees_images=False,
    )
    assert isinstance(listed, Ok) and "skill" not in listed.text

    ran = await runtime.tools.execute(
        ToolCall(
            id="c2",
            name=EXECUTE_TYPESCRIPT,
            arguments=json.dumps(
                {"code": 'return await skill({name: "pdf"});', "description": "try"}
            ),
        ),
        progress=no_progress,
        origin=ORIGIN,
        session=new_session(),
        sees_images=False,
    )
    assert "skill is not defined" in str(ran).lower() or "cannot be called" in str(ran)


def test_a_skill_saved_through_the_editor_is_offered_next_request(compose) -> None:
    build, root = compose
    runtime = build()
    assert runtime.tools is not None
    assert SKILL not in [s.name for s in runtime.tools.specs(sees_images=False)]

    skills_at(root).save("notes", "---\ndescription: Notes.\n---\nWrite them.\n")

    (spec,) = [s for s in runtime.tools.specs(sees_images=False) if s.name == SKILL]
    assert spec.input_schema["properties"]["name"]["enum"] == ["notes"]

    skills_at(root).delete("notes")
    assert SKILL not in [s.name for s in runtime.tools.specs(sees_images=False)]
