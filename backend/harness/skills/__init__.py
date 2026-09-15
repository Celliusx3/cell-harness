"""Skills: instructions the model loads when a task matches them.

A skill is a directory with a `SKILL.md` (agentskills.io). The catalog — every
skill's name and one-line description — is rebuilt from disk on every request,
the way the tool list is; the body is read only when a skill is activated.
`SkillService` is the one object the rest of the harness holds.
"""

from harness.skills.invocation import display
from harness.skills.models import (
    InvalidSkill,
    Skill,
    SkillProblem,
    SkillSnapshot,
    UnknownSkill,
    parse,
    valid_name,
)
from harness.skills.service import SkillNotEditable, SkillNotFound, SkillService, SkillShadowed
from harness.skills.tool import SKILL, skill_tool

__all__ = [
    "SKILL",
    "InvalidSkill",
    "Skill",
    "SkillNotEditable",
    "SkillNotFound",
    "SkillProblem",
    "SkillService",
    "SkillShadowed",
    "SkillSnapshot",
    "UnknownSkill",
    "display",
    "parse",
    "skill_tool",
    "valid_name",
]
