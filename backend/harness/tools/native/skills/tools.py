"""The Skills page's save and delete, and a bundled file's write, offered to the model as tools."""

from __future__ import annotations

from pydantic import BaseModel, Field

from harness.skills.models import InvalidSkill
from harness.skills.service import SkillNotEditable, SkillNotFound, SkillService, SkillShadowed
from harness.tools.context import ToolContext
from harness.tools.definition import (
    INVALID_ARGUMENTS,
    REFUSED,
    Failure,
    Ok,
    ToolDefinition,
    ToolOutcome,
)

SKILL_SAVE = "skill_save"
SKILL_DELETE = "skill_delete"
SKILL_WRITE_FILE = "skill_write_file"

_SAVE_DESCRIPTION = (
    "Write the whole SKILL.md for `name` into the skills folder the Skills page "
    "writes to. `text` starts with YAML frontmatter between `---` lines holding "
    "at least `description` (a `name` there, if given, must equal `name`), then "
    "the instructions. Saving a name that already exists there replaces its SKILL.md."
)

_DELETE_DESCRIPTION = (
    "Delete a skill the Skills page could delete, together with every file it bundles."
)

_WRITE_FILE_DESCRIPTION = (
    "Write one file inside a skill already saved with skill_save, by its path relative to "
    "the skill's folder: a reference under references/, a script under scripts/, an asset "
    "under assets/, e.g. 'references/factors.md'. A script under scripts/ is TypeScript "
    "written like execute_typescript's code: the body of an async function that calls tools "
    "by their exact name and ends with `return`, with no imports or exports. It runs when the "
    "skill tool reads it and its text is passed to execute_typescript as the code. Writing a "
    "path that already exists replaces it."
)


def skill_save_tool(skills: SkillService) -> ToolDefinition[SaveArgs]:
    """The tool that writes a skill through the Skills page's own save."""

    async def execute(args: SaveArgs, _context: ToolContext) -> ToolOutcome:
        try:
            skills.save(args.name, args.text)
        except InvalidSkill as err:
            return Failure(INVALID_ARGUMENTS, str(err))
        except SkillShadowed as err:
            return Failure(REFUSED, str(err))
        return Ok(f"saved skill {args.name!r}")

    return ToolDefinition.from_model(
        name=SKILL_SAVE, description=_SAVE_DESCRIPTION, args_model=SaveArgs, execute=execute
    )


def skill_delete_tool(skills: SkillService) -> ToolDefinition[DeleteArgs]:
    """The tool that removes a skill through the Skills page's own delete."""

    async def execute(args: DeleteArgs, _context: ToolContext) -> ToolOutcome:
        try:
            skills.delete(args.name)
        except SkillNotFound as err:
            return Failure(INVALID_ARGUMENTS, f"no skill named {err.name!r}")
        except SkillNotEditable as err:
            return Failure(REFUSED, str(err))
        return Ok(f"deleted skill {args.name!r}")

    return ToolDefinition.from_model(
        name=SKILL_DELETE, description=_DELETE_DESCRIPTION, args_model=DeleteArgs, execute=execute
    )


def skill_write_file_tool(skills: SkillService) -> ToolDefinition[WriteFileArgs]:
    """The tool that writes one file a skill bundles, into a skill the Skills page could edit."""

    async def execute(args: WriteFileArgs, _context: ToolContext) -> ToolOutcome:
        try:
            skills.write_file(args.name, args.path, args.text)
        except SkillNotFound as err:
            return Failure(INVALID_ARGUMENTS, f"no skill named {err.name!r}")
        except SkillNotEditable as err:
            return Failure(REFUSED, str(err))
        except InvalidSkill as err:
            return Failure(INVALID_ARGUMENTS, str(err))
        return Ok(f"wrote {args.path!r} in skill {args.name!r}")

    return ToolDefinition.from_model(
        name=SKILL_WRITE_FILE,
        description=_WRITE_FILE_DESCRIPTION,
        args_model=WriteFileArgs,
        execute=execute,
    )


class SaveArgs(BaseModel):
    """What the model passes to `skill_save`."""

    name: str = Field(description="The skill to write, e.g. 'meeting-notes'.")
    text: str = Field(description="The whole SKILL.md: the frontmatter, then the instructions.")


class DeleteArgs(BaseModel):
    """What the model passes to `skill_delete`."""

    name: str = Field(description="The skill to delete.")


class WriteFileArgs(BaseModel):
    """What the model passes to `skill_write_file`."""

    name: str = Field(description="The skill to write into, e.g. 'meeting-notes'.")
    path: str = Field(
        description="Where the file goes, relative to the skill's folder, "
        "e.g. 'references/factors.md'."
    )
    text: str = Field(description="The whole file.")
