"""The Mac programs the skills in the mounted folders declare in their SKILL.md metadata."""

from __future__ import annotations

import logging
import os
import re
import shlex
import shutil
import string
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from computer.host_services import HostService

logger = logging.getLogger("computer")

SKILL_FILE = "SKILL.md"
FENCE = "---"
ENV_PREFIX_PATTERN = re.compile(r"[A-Z][A-Z0-9_]*")
PLACEHOLDERS = ("port", "token_file", "files")


class MalformedDeclaration(ValueError):
    """A SKILL.md whose frontmatter or program declaration cannot be used. The message says why."""


class Declaration(BaseModel):
    """The two metadata keys a skill declares a program with; its other keys are its own."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    command_line: str | None = Field(default=None, alias="host-service")
    env_prefix: str | None = Field(default=None, alias="host-service-env")


class Frontmatter(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    metadata: Declaration | None = None


@dataclass(frozen=True)
class DeclaredCommand:
    """A skill's declaration, parsed: the program as written, its words, its variables' prefix."""

    program: str
    arguments: tuple[str, ...]
    env_prefix: str


def frontmatter_of(skill_text: str) -> Frontmatter:
    """The frontmatter a SKILL.md opens with between `---` lines, or a `MalformedDeclaration`."""
    lines = skill_text.splitlines()
    if not lines or lines[0].strip() != FENCE:
        raise MalformedDeclaration(f"{SKILL_FILE} does not start with a `---` line")
    closing = next((at for at, line in enumerate(lines[1:], 1) if line.strip() == FENCE), None)
    if closing is None:
        raise MalformedDeclaration(f"{SKILL_FILE}'s frontmatter has no closing `---` line")
    try:
        return Frontmatter.model_validate(yaml.safe_load("\n".join(lines[1:closing])))
    except yaml.YAMLError as err:
        raise MalformedDeclaration(f"its frontmatter is not valid YAML: {err}") from err
    except ValidationError as err:
        first = err.errors()[0]
        where = ".".join(str(part) for part in first["loc"]) or "frontmatter"
        raise MalformedDeclaration(f"its {where} is not usable: {first['msg']}") from err


def placeholder_problem(word: str) -> str | None:
    """Why `word` cannot be filled in, or None when each `{…}` in it is a bare placeholder."""
    try:
        fields = [
            (name, spec, conversion)
            for _, name, spec, conversion in string.Formatter().parse(word)
            if name is not None
        ]
    except ValueError as err:
        return f"{word!r} has a brace out of place: {err}"
    if all(
        name in PLACEHOLDERS and not spec and conversion is None
        for name, spec, conversion in fields
    ):
        return None
    return f"{word!r} has a placeholder other than {{port}}, {{token_file}} and {{files}}"


def declared_command(skill_text: str) -> DeclaredCommand | None:
    """The program a SKILL.md's metadata declares; None when it sets neither key."""
    declaration = frontmatter_of(skill_text).metadata
    if declaration is None or (declaration.command_line, declaration.env_prefix) == (None, None):
        return None
    if declaration.command_line is None or declaration.env_prefix is None:
        raise MalformedDeclaration("it sets one of host-service and host-service-env but not both")
    if not ENV_PREFIX_PATTERN.fullmatch(declaration.env_prefix):
        raise MalformedDeclaration(
            f"host-service-env={declaration.env_prefix!r} is not capital letters, digits and "
            "'_', starting with a letter"
        )
    try:
        words = shlex.split(declaration.command_line)
    except ValueError as err:
        raise MalformedDeclaration(f"host-service does not split into words: {err}") from err
    if not words:
        raise MalformedDeclaration("host-service names no program")
    program, *arguments = words
    problem = next(filter(None, map(placeholder_problem, arguments)), None)
    if problem is not None:
        raise MalformedDeclaration(f"host-service word {problem}")
    return DeclaredCommand(
        program=program, arguments=tuple(arguments), env_prefix=declaration.env_prefix
    )


def declared_host_service(skill_dir: Path, search_path: str) -> HostService | None:
    """The installed program the skill in `skill_dir` declares; None, logged unless it has none."""
    skill = skill_dir.name
    try:
        command = declared_command((skill_dir / SKILL_FILE).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, MalformedDeclaration) as err:
        logger.warning("the skill %s declares no program this server can start: %s", skill, err)
        return None
    if command is None:
        return None
    found = shutil.which(os.path.expanduser(command.program), path=search_path)
    if found is None:
        logger.warning(
            "the skill %s declares %s, which is not installed, so commands in the computer run "
            "without it",
            skill,
            command.program,
        )
        return None
    return HostService(
        skill=skill,
        env_prefix=command.env_prefix,
        program=Path(found).absolute(),
        arguments=command.arguments,
    )


def skill_folders(skills_dirs: Sequence[Path]) -> tuple[Path, ...]:
    """Each child of these folders that holds a SKILL.md, by name within each folder."""
    found: list[Path] = []
    for skills_dir in skills_dirs:
        try:
            children = sorted(skills_dir.iterdir())
        except OSError as err:
            logger.warning(
                "the skill folder %s cannot be read, so it declares nothing: %s", skills_dir, err
            )
            continue
        found.extend(child for child in children if (child / SKILL_FILE).is_file())
    return tuple(found)


def declared_host_services(
    skills_dirs: Sequence[Path], search_path: str
) -> tuple[HostService, ...]:
    """Every installed program the skills in these folders declare, one per variables' prefix."""
    services: dict[str, HostService] = {}
    for skill_dir in skill_folders(skills_dirs):
        service = declared_host_service(skill_dir, search_path)
        if service is None:
            continue
        taken = services.get(service.env_prefix)
        if taken is not None:
            logger.warning(
                "the skill %s declares host-service-env %s, which the skill %s already has, so "
                "commands in the computer run without its program",
                service.skill,
                service.env_prefix,
                taken.skill,
            )
            continue
        services[service.env_prefix] = service
    return tuple(services.values())
