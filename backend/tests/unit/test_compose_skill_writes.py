"""Skill writes through the real object graph: a worker's, never the routing bot's or a script's."""

from __future__ import annotations

import json
from pathlib import Path

from harness.llm import ToolCall
from harness.skills import SKILL
from harness.tools import Ok
from harness.tools.native.code_mode import EXECUTE_TYPESCRIPT, LIST_FUNCTIONS
from harness.tools.native.skills import SKILL_DELETE, SKILL_SAVE, SKILL_WRITE_FILE
from tests.unit.helpers import ORIGIN, new_session, no_progress, skills_at, worker_of
from tests.unit.skills_compose import compose, write_skill

COMMITTED_CONFIG = Path(__file__).parents[2] / "config.json"
__all__ = ["compose"]


def test_every_skill_write_is_offered_to_a_worker_before_any_skill_exists(compose) -> None:
    build, _ = compose
    runtime = worker_of(build())
    assert runtime.tools is not None

    offered = [s.name for s in runtime.tools.specs(sees_images=False)]

    assert {SKILL_SAVE, SKILL_DELETE, SKILL_WRITE_FILE} <= set(offered)


def test_the_bot_that_routes_is_offered_no_skill_write(compose) -> None:
    build, root = compose
    write_skill(root, "pdf")
    runtime = build()
    assert runtime.tools is not None

    offered = {s.name for s in runtime.tools.specs(sees_images=False)}

    assert SKILL in offered
    assert offered.isdisjoint({SKILL_SAVE, SKILL_DELETE, SKILL_WRITE_FILE})


async def test_a_script_cannot_write_a_skill(compose) -> None:
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
    assert isinstance(listed, Ok)
    assert not any(name in listed.text for name in (SKILL_SAVE, SKILL_DELETE, SKILL_WRITE_FILE))

    ran = await runtime.tools.execute(
        ToolCall(
            id="c2",
            name=EXECUTE_TYPESCRIPT,
            arguments=json.dumps(
                {"code": 'return await skill_delete({name: "pdf"});', "description": "try"}
            ),
        ),
        progress=no_progress,
        origin=ORIGIN,
        session=new_session(),
        sees_images=False,
    )
    assert "skill_delete is not defined" in str(ran) or "cannot be called" in str(ran)
    assert (root / "pdf" / "SKILL.md").exists()


def test_the_committed_config_asks_before_any_skill_write() -> None:
    committed = json.loads(COMMITTED_CONFIG.read_text())

    assert {SKILL_SAVE, SKILL_DELETE, SKILL_WRITE_FILE} <= set(committed["approval"]["tools"])


async def test_a_script_written_into_a_skill_runs_as_a_program(compose) -> None:
    build, root = compose
    runtime = worker_of(build())
    assert runtime.tools is not None
    skills_at(root).save("convert", "---\ndescription: Converts km to miles.\n---\nRun it.\n")

    wrote = await runtime.tools.execute(
        ToolCall(
            id="c1",
            name=SKILL_WRITE_FILE,
            arguments=json.dumps(
                {
                    "name": "convert",
                    "path": "scripts/km.ts",
                    "text": "return Math.round(5 * 0.621371 * 1000) / 1000;",
                }
            ),
        ),
        progress=no_progress,
        origin=ORIGIN,
        session=new_session(),
        sees_images=False,
    )
    assert isinstance(wrote, Ok)

    read = await runtime.tools.execute(
        ToolCall(
            id="c2", name=SKILL, arguments=json.dumps({"name": "convert", "path": "scripts/km.ts"})
        ),
        progress=no_progress,
        origin=ORIGIN,
        session=new_session(),
        sees_images=False,
    )
    assert isinstance(read, Ok)
    script = read.text.split("\n", 1)[1].rsplit("\n</skill_file>", 1)[0]
    ran = await runtime.tools.execute(
        ToolCall(
            id="c3",
            name=EXECUTE_TYPESCRIPT,
            arguments=json.dumps({"code": script, "description": "run the skill's script"}),
        ),
        progress=no_progress,
        origin=ORIGIN,
        session=new_session(),
        sees_images=False,
    )
    assert isinstance(ran, Ok) and ran.data == 3.107
