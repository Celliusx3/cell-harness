"""The skills a person can see and manage."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile, status

from harness.skills import SkillNotFound, SkillService
from harness.skills.router.schemas import (
    BundledFile,
    SkillFile,
    SkillIssue,
    SkillList,
    SkillSummary,
    SkillText,
)


def _missing(err: SkillNotFound) -> str:
    return f"no skill named {err.name!r}"


class SkillRouter:
    """List, read, save, delete and install the skills a person can see."""

    def __init__(self, skills: SkillService) -> None:
        self._skills = skills
        self.router: APIRouter = APIRouter(prefix="/api/skills", tags=["skills"])
        self._add_reading_routes()
        self._add_writing_routes()

    def _add_reading_routes(self) -> None:
        """Listing the skills, and reading one and the files it brought."""
        self.router.add_api_route("", self.list_skills, methods=["GET"], response_model=SkillList)
        self.router.add_api_route(
            "/{name}", self.read_skill, methods=["GET"], response_model=SkillFile
        )
        self.router.add_api_route(
            "/{name}/files/{path:path}",
            self.read_bundled_file,
            methods=["GET"],
            response_model=BundledFile,
        )

    def _add_writing_routes(self) -> None:
        """Saving, deleting and installing a skill."""
        no_content = status.HTTP_204_NO_CONTENT
        self.router.add_api_route(
            "/{name}", self.save_skill, methods=["PUT"], status_code=no_content
        )
        self.router.add_api_route(
            "/{name}", self.delete_skill, methods=["DELETE"], status_code=no_content
        )
        self.router.add_api_route(
            "",
            self.install_skill,
            methods=["POST"],
            status_code=status.HTTP_201_CREATED,
            response_model=SkillSummary,
        )

    async def list_skills(self) -> SkillList:
        snapshot = self._skills.snapshot()
        return SkillList(
            skills=[
                SkillSummary(**skill.model_dump(), editable=self._skills.editable(skill))
                for skill in snapshot.skills
            ],
            problems=[SkillIssue(**problem.model_dump()) for problem in snapshot.problems],
        )

    async def read_skill(self, name: str) -> SkillFile:
        try:
            skill = self._skills.find(name)
            text = self._skills.read(name)
            files = list(self._skills.files(name))
        except SkillNotFound as err:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail=f"no skill named {err.name!r}"
            ) from err
        return SkillFile(name=name, text=text, editable=self._skills.editable(skill), files=files)

    async def read_bundled_file(self, name: str, path: str) -> BundledFile:
        """One of the files the skill brought with it, read by its relative path."""
        try:
            return BundledFile(path=path, text=self._skills.file(name, path))
        except SkillNotFound as err:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_missing(err)) from err

    async def save_skill(self, name: str, body: SkillText) -> None:
        """Write a skill, refusing what the catalog would merely flag."""
        self._skills.save(name, body.text)

    async def delete_skill(self, name: str) -> None:
        try:
            self._skills.delete(name)
        except SkillNotFound as err:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail=f"no skill named {err.name!r}"
            ) from err

    async def install_skill(self, file: UploadFile) -> SkillSummary:
        """Unpack a zipped skill folder into the editable root."""
        installed = self._skills.find(self._skills.install(await file.read()))
        return SkillSummary(**installed.model_dump(), editable=self._skills.editable(installed))
