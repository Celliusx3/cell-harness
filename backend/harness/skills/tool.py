"""The one tool through which the model loads a skill.

Built fresh from the catalog on every request, because its schema *is* the
catalog: `name` is a `Literal` of the skills that exist right now, so an
invented name is a schema violation before any code runs, and the description
carries the `<available_skills>` index the model reads to decide. Index and
enum come from the same list in the same call, so they cannot disagree.

**No skills, no tool.** The factory returns `None` and the registry provider
yields nothing, so the model is never shown an enum with no members — the spec's
client guide is explicit that an empty catalog confuses the model more than an
absent one.

The catalog is the description; the body is the *result*. That is progressive
disclosure: every request pays for one line per skill, and a body costs nothing
until the model asks for it. The body is read from disk at that moment, so an
edit shows at the next activation with no change to the tool's schema.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, create_model

from harness.skills.models import Skill
from harness.skills.rendering import instructions
from harness.skills.service import SkillService
from harness.tools.definition import INVALID_ARGUMENTS, Failure, Ok, ToolDefinition, ToolOutcome
from harness.tools.progress import ToolProgressReporter

SKILL = "skill"

# A bundled file the model asks for by `path`. Bounded because it lands in the
# conversation whole: a 2 MB data file would cost the turn its context.
MAX_RESOURCE_BYTES = 64 * 1024

# Prompt text is code. "before starting" exists because a model shown the tool
# would otherwise use it after it had already answered from general knowledge —
# the whole point is that the skill changes how the task is done, not the
# reply's afterword. The last sentence exists because a public skill's body may
# say "run scripts/extract.py", and a model with no shell must be told that the
# instructions, not the scripts, are what it has.
_DESCRIPTION = (
    "Load a skill's instructions before starting a task that matches its "
    "description. When one matches, call this first and follow what it "
    "returns. A skill may name bundled files; read one by passing its relative "
    "`path`. You cannot run a skill's scripts — follow its instructions with "
    "the capabilities you have.\n\n"
)


def skill_tool(skills: SkillService) -> ToolDefinition[BaseModel] | None:
    """The tool over the skills the model may load, or `None` when there are none."""
    offered = [skill for skill in skills.snapshot().skills if skill.model_invocable]
    if not offered:
        return None
    by_name = {skill.name: skill for skill in offered}

    async def execute(args: BaseModel, _progress: ToolProgressReporter) -> ToolOutcome:
        name: str = args.name  # type: ignore[attr-defined]
        path: str | None = args.path  # type: ignore[attr-defined]
        skill = by_name[name]
        if path is not None:
            return _resource(skill, path)
        return _instructions(skill)

    return ToolDefinition.from_model(
        name=SKILL,
        description=_DESCRIPTION + _index(offered),
        args_model=_args_model(tuple(by_name)),
        execute=execute,
    )


def _args_model(names: tuple[str, ...]) -> type[BaseModel]:
    """`name` as an enum of what exists. Generated per call, because the set
    changes as files do, and a stale enum would refuse a skill that exists."""
    return create_model(
        "SkillArgs",
        name=(
            Literal[names],
            Field(description="The skill to load.", json_schema_extra=_always_enum(names)),
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
    """Pydantic prints a one-member `Literal` as `const`, not `enum`. One skill
    is the common case, and the model should see one shape however many."""

    def fix(schema: dict) -> None:
        schema.pop("const", None)
        schema["enum"] = list(names)

    return fix


def _index(skills: list[Skill]) -> str:
    lines = ["<available_skills>"]
    for skill in skills:
        lines.append(
            f"  <skill><name>{skill.name}</name>"
            f"<description>{_escape(skill.description)}</description></skill>"
        )
    lines.append("</available_skills>")
    return "\n".join(lines)


def _escape(text: str) -> str:
    """A description containing `<` would otherwise read as markup."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _instructions(skill: Skill) -> ToolOutcome:
    try:
        return Ok(instructions(skill))
    except (OSError, ValueError) as err:
        # Present when the catalog was built, gone or broken now. Reported as a
        # failure the model can react to; the catalog will drop it next call.
        return Failure(INVALID_ARGUMENTS, f"skill {skill.name!r} could not be read: {err}")


def _resource(skill: Skill, path: str) -> ToolOutcome:
    """One bundled file, confined to the skill's directory."""
    base = skill.dir.resolve()
    target = (skill.dir / path).resolve()
    if not target.is_relative_to(base) or target == base:
        return Failure(INVALID_ARGUMENTS, f"{path!r} is not inside skill {skill.name!r}")
    if not target.is_file():
        return Failure(INVALID_ARGUMENTS, f"skill {skill.name!r} has no file {path!r}")
    if target.stat().st_size > MAX_RESOURCE_BYTES:
        return Failure(
            INVALID_ARGUMENTS,
            f"{path!r} is larger than {MAX_RESOURCE_BYTES // 1024} KiB and cannot be loaded whole",
        )
    try:
        text = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return Failure(INVALID_ARGUMENTS, f"{path!r} is not a text file")
    except OSError as err:
        return Failure(INVALID_ARGUMENTS, f"{path!r} could not be read: {err}")
    return Ok(f'<skill_file name="{skill.name}" path="{path}">\n{text}\n</skill_file>')
