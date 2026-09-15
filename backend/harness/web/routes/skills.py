"""The skills a person can see and manage.

Read straight off the catalog on every request, the same view the model gets —
so what this lists and what the `skill` tool offers cannot drift, and a problem
reported here is the reason a skill is missing there.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from harness.skills import (
    InvalidSkill,
    SkillNotEditable,
    SkillNotFound,
    SkillService,
    SkillShadowed,
)


class SkillSummary(BaseModel):
    """One skill as the settings page shows it."""

    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    dir: Path
    root: Path
    model_invocable: bool
    user_invocable: bool
    # Whether this copy is in `skills.editable` — so the page knows what it may
    # change without comparing paths itself.
    editable: bool


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


class SkillFile(BaseModel):
    """One `SKILL.md`, whole, for the editor."""

    model_config = ConfigDict(frozen=True)

    name: str
    text: str
    editable: bool


class SkillText(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str


def _missing(err: SkillNotFound) -> str:
    return f"no skill named {err.name!r}"


def build_router(skills: SkillService) -> APIRouter:
    router = APIRouter(prefix="/api/skills", tags=["skills"])

    @router.get("", response_model=SkillList)
    async def list_skills() -> SkillList:
        snapshot = skills.snapshot()
        return SkillList(
            skills=[
                SkillSummary(**skill.model_dump(), editable=skills.editable(skill))
                for skill in snapshot.skills
            ],
            problems=[SkillIssue(**problem.model_dump()) for problem in snapshot.problems],
        )

    @router.get("/{name}", response_model=SkillFile)
    async def read_skill(name: str) -> SkillFile:
        try:
            skill = skills.find(name)
            text = skills.read(name)
        except SkillNotFound as err:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail=f"no skill named {err.name!r}"
            ) from err
        return SkillFile(name=name, text=text, editable=skills.editable(skill))

    @router.put("/{name}", status_code=status.HTTP_204_NO_CONTENT)
    async def save_skill(name: str, body: SkillText) -> None:
        """Strict where the catalog is lenient — see `SkillService.save`."""
        try:
            skills.save(name, body.text)
        except InvalidSkill as err:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(err)) from err
        except SkillShadowed as err:
            raise HTTPException(status.HTTP_409_CONFLICT, detail=str(err)) from err

    @router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_skill(name: str) -> None:
        try:
            skills.delete(name)
        except SkillNotFound as err:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail=f"no skill named {err.name!r}"
            ) from err
        except SkillNotEditable as err:
            raise HTTPException(status.HTTP_409_CONFLICT, detail=str(err)) from err

    return router
