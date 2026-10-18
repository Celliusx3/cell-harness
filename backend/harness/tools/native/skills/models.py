"""What the three skill tools are called with."""

from __future__ import annotations

from pydantic import BaseModel, Field


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
