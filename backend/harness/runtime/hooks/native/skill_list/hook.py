"""The skills the model may load, listed on every request."""

from __future__ import annotations

from dataclasses import dataclass

from harness.runtime.hooks.service import StepHook
from harness.skills import SkillService
from harness.skills.prompt import available_skills


@dataclass(frozen=True)
class SkillListHook(StepHook):
    """The skill list, read from disk at the start of every step."""

    skills: SkillService

    async def start_of_step(self) -> str | None:
        return available_skills(self.skills.model_invocable()) or None
