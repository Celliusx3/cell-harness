"""The skills a person can see and manage."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict

from harness.skills import (
    InvalidSkill,
    SkillNotEditable,
    SkillNotFound,
    SkillService,
    SkillShadowed,
    UnreadableFile,
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
    editable: bool


class SkillIssue(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: Path
    problem: str


class SkillList(BaseModel):
    """Every loadable skill, and everything on disk that was not loaded or loaded with a caveat."""

    model_config = ConfigDict(frozen=True)

    skills: list[SkillSummary]
    problems: list[SkillIssue]


class SkillFile(BaseModel):
    """One `SKILL.md`, whole, for the editor, and what the skill bundles beside it."""

    model_config = ConfigDict(frozen=True)

    name: str
    text: str
    editable: bool
    files: list[str]


class BundledFile(BaseModel):
    """One file a skill brought with it, whole."""

    model_config = ConfigDict(frozen=True)

    path: str
    text: str


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
            files = list(skills.files(name))
        except SkillNotFound as err:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail=f"no skill named {err.name!r}"
            ) from err
        return SkillFile(name=name, text=text, editable=skills.editable(skill), files=files)

    @router.get("/{name}/files/{path:path}", response_model=BundledFile)
    async def read_bundled_file(name: str, path: str) -> BundledFile:
        """One of the files the skill brought with it, read by its relative path."""
        try:
            return BundledFile(path=path, text=skills.file(name, path))
        except SkillNotFound as err:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_missing(err)) from err
        except UnreadableFile as err:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(err)) from err

    @router.put("/{name}", status_code=status.HTTP_204_NO_CONTENT)
    async def save_skill(name: str, body: SkillText) -> None:
        """Write a skill, refusing what the catalog would merely flag."""
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

    @router.post("", status_code=status.HTTP_201_CREATED, response_model=SkillSummary)
    async def install_skill(file: UploadFile) -> SkillSummary:
        """Unpack a zipped skill folder into the editable root."""
        try:
            installed = skills.find(skills.install(await file.read()))
            return SkillSummary(**installed.model_dump(), editable=skills.editable(installed))
        except InvalidSkill as err:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(err)) from err
        except SkillShadowed as err:
            raise HTTPException(status.HTTP_409_CONFLICT, detail=str(err)) from err

    return router
