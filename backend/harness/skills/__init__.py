"""Skills: instructions the model loads when a task matches them.

A skill is a directory with a `SKILL.md` (agentskills.io). The catalog — every
skill's name and one-line description — is rebuilt from disk on every request,
the way the tool list is; the body is read only when a skill is activated.
"""

from harness.skills.catalog import SkillCatalog, read_body
from harness.skills.models import (
    Catalog,
    InvalidSkill,
    Skill,
    SkillProblem,
    SkillSnapshot,
    parse,
    valid_name,
)
from harness.skills.tool import SKILL, skill_tool

__all__ = [
    "SKILL",
    "Catalog",
    "SkillCatalog",
    "InvalidSkill",
    "Skill",
    "SkillProblem",
    "SkillSnapshot",
    "parse",
    "read_body",
    "skill_tool",
    "valid_name",
]
