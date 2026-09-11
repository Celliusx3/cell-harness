"""The skills a person can see and manage.

Read straight off the catalog on every request, the same view the model gets —
so what this lists and what the `skill` tool offers cannot drift, and a problem
reported here is the reason a skill is missing there.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from harness.skills import Catalog


class SkillSummary(BaseModel):
    """One skill as the settings page shows it."""

    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    dir: Path
    root: Path
    model_invocable: bool
    user_invocable: bool


class SkillIssue(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: Path
    problem: str


class SkillList(BaseModel):
    """Every loadable skill, and everything on disk that was not loaded or was
    loaded with a caveat — a person editing files needs the second list more
    than the first."""

    model_config = ConfigDict(frozen=True)

    skills: list[SkillSummary]
    problems: list[SkillIssue]


def build_router(catalog: Catalog) -> APIRouter:
    router = APIRouter(prefix="/api/skills", tags=["skills"])

    @router.get("", response_model=SkillList)
    async def list_skills() -> SkillList:
        snapshot = catalog()
        return SkillList(
            skills=[SkillSummary(**skill.model_dump()) for skill in snapshot.skills],
            problems=[SkillIssue(**problem.model_dump()) for problem in snapshot.problems],
        )

    return router
