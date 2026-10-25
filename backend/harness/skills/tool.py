"""The one tool through which the model loads a skill."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, create_model

from harness.skills import resources
from harness.skills.models import Skill
from harness.skills.prompt import instructions
from harness.skills.service import SkillService
from harness.tools import INVALID_ARGUMENTS, Failure, Ok, Tool, ToolContext, ToolOutcome

SKILL = "skill"

_DESCRIPTION = (
    "Load a skill's instructions before starting a task that matches its "
    "description. Available skills appear in a system-reminder listing with one-line "
    "descriptions. When one matches, call this first and follow what it returns. A skill "
    "may name bundled files; read one by passing its relative `path`. A TypeScript file "
    "under a skill's scripts/ is a program, not a function "
    "you can call by name: read it by `path`, then pass its text as the code to "
    "execute_typescript. A script in another language runs only through a tool for "
    "running commands, when you are offered one: from the skill's folder when the skill "
    "names one, and otherwise after you read it by `path` and write it into the computer "
    "yourself. Without such a tool, follow the instructions with the capabilities you "
    "have."
)


def skill_tool(skills: SkillService) -> Tool[SkillArgs] | None:
    """The tool over the skills the model may load, or `None` when there are none."""
    offered = skills.model_invocable()
    if not offered:
        return None
    by_name = {skill.name: skill for skill in offered}

    async def execute(args: SkillArgs, _context: ToolContext) -> ToolOutcome:
        skill = by_name[args.name]
        if args.path is not None:
            return _resource(skill, args.path)
        return _instructions(skill, shipped=not skills.editable(skill))

    return Tool.from_model(
        name=SKILL,
        description=_DESCRIPTION,
        args_model=_args_model(tuple(by_name)),
        execute=execute,
    )


class SkillArgs(BaseModel):
    """What the model passes to `skill`."""

    name: str
    path: str | None = None


def _args_model(names: tuple[str, ...]) -> type[SkillArgs]:
    """`SkillArgs` with `name` as an enum of what exists."""
    return create_model(
        "SkillArgs",
        __base__=SkillArgs,
        name=(
            Literal[names],
            Field(
                description=(
                    "The name of a skill from the available-skills list. Do not guess names."
                ),
                json_schema_extra=_always_enum(names),
            ),
        ),
        path=(
            str | None,
            Field(
                default=None,
                description=(
                    "A bundled file to read instead of the instructions, relative to the "
                    "skill's directory, e.g. 'references/forms.md'."
                ),
            ),
        ),
    )


def _always_enum(names: tuple[str, ...]):
    """A schema hook that forces `enum` for `name`."""
    # Pydantic prints a one-member `Literal` as `const`, not `enum`.

    def fix(schema: dict) -> None:
        schema.pop("const", None)
        schema["enum"] = list(names)

    return fix


def _instructions(skill: Skill, *, shipped: bool) -> ToolOutcome:
    try:
        return Ok(instructions(skill, shipped=shipped))
    except (OSError, ValueError) as err:
        return Failure(INVALID_ARGUMENTS, f"skill {skill.name!r} could not be read: {err}")


def _resource(skill: Skill, path: str) -> ToolOutcome:
    """One bundled file, confined to the skill's directory."""
    try:
        text = resources.read(skill, path)
    except resources.UnreadableFile as err:
        return Failure(INVALID_ARGUMENTS, str(err))
    return Ok(f'<skill_file name="{skill.name}" path="{path}">\n{text}\n</skill_file>')
