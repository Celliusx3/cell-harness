"""The skills page's request and response bodies."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict


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
