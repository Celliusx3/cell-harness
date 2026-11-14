"""The one tool through which the model loads a skill."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, create_model

from harness.skills.domain.models import Skill
from harness.skills.service import resources
from harness.skills.service.prompt import instructions
from harness.skills.service.skill_service import SkillService
from harness.tools import INVALID_ARGUMENTS, Failure, Ok, Tool, ToolContext, ToolOutcome

SKILL = "skill"

_DESCRIPTION = (
    "Load a skill's instructions before starting a task that matches its "
    "description. Available skills appear in a system-reminder listing with one-line "
    "descriptions. When one matches, call this first and follow what it returns. A skill "
    "may name bundled files; read one by passing its relative `path`. A TypeScript file "
    "under a skill's scripts/ is a program, not a function "
    "you can call by name: when you are offered execute_typescript, read it by `path`, then "
    "pass its text as the code to execute_typescript. A script in another language runs "
    "only through a tool for "
    "running commands, when you are offered one: from the folder the skill names, where its "
    "scripts already are; only when that folder is not in your computer, read the script by "
    "`path` and write it there yourself. Without the tool a script needs, follow the "
    "instructions with the capabilities you have."
)


def skill_tool(skills: SkillService) -> Tool[SkillArgs] | None:
    """The tool over the skills the model may load, or `None` when there are none."""
    offered = skills.model_invocable_skills()
    if not offered:
        return None
    by_name = {skill.name: skill for skill in offered}

    async def execute(args: SkillArgs, _context: ToolContext) -> ToolOutcome:
        skill = by_name[args.name]
        if args.path is not None:
            return _bundled_file_outcome(skill, args.path)
        return _instructions_outcome(skill)

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
                json_schema_extra=_enum_schema_hook(names),
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


def _enum_schema_hook(names: tuple[str, ...]):
    """A schema hook that forces `enum` for `name`."""
    # Pydantic prints a one-member `Literal` as `const`, not `enum`.

    def force_enum(schema: dict) -> None:
        schema.pop("const", None)
        schema["enum"] = list(names)

    return force_enum


def _instructions_outcome(skill: Skill) -> ToolOutcome:
    try:
        return Ok(instructions(skill))
    except (OSError, ValueError) as err:
        return Failure(INVALID_ARGUMENTS, f"skill {skill.name!r} could not be read: {err}")


def _bundled_file_outcome(skill: Skill, path: str) -> ToolOutcome:
    """One bundled file, confined to the skill's directory."""
    try:
        text = resources.read(skill, path)
    except resources.UnreadableFile as err:
        return Failure(INVALID_ARGUMENTS, str(err))
    return Ok(f'<skill_file name="{skill.name}" path="{path}">\n{text}\n</skill_file>')
