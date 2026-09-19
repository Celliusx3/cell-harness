"""What a skill is, and how one is read off a `SKILL.md`."""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_NAME_CHARS = 64
MAX_DESCRIPTION_CHARS = 1024
SKILL_FILE = "SKILL.md"

_FENCE = "---"


class InvalidSkill(ValueError):
    """A `SKILL.md` that cannot be loaded. The message says why, for a person."""


class UnknownSkill(LookupError):
    """`/name` named no skill a person may invoke."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name


class Frontmatter(BaseModel):
    """The fields we act on. Everything else is accepted and ignored."""

    model_config = ConfigDict(frozen=True, extra="ignore", populate_by_name=True)

    name: str | None = None
    description: str
    disable_model_invocation: bool = Field(default=False, alias="disable-model-invocation")
    user_invocable: bool = Field(default=True, alias="user-invocable")


class Parsed(NamedTuple):
    frontmatter: Frontmatter
    body: str


class Skill(BaseModel):
    """One loadable skill: where it is and how it may be reached."""

    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    dir: Path
    root: Path
    model_invocable: bool
    user_invocable: bool


class SkillProblem(BaseModel):
    """Something on disk that was not loaded, or was loaded with a caveat."""

    model_config = ConfigDict(frozen=True)

    path: Path
    problem: str


class SkillSnapshot(BaseModel):
    """What the roots hold right now."""

    model_config = ConfigDict(frozen=True)

    skills: tuple[Skill, ...] = ()
    problems: tuple[SkillProblem, ...] = ()


def valid_name(name: str) -> bool:
    return len(name) <= MAX_NAME_CHARS and NAME.match(name) is not None


def parse(text: str) -> Parsed:
    """The frontmatter and body of one `SKILL.md`, or `InvalidSkill`."""
    parts = _split(text)
    if parts is None:
        raise InvalidSkill(f"{SKILL_FILE} must start with a `---` YAML frontmatter block")
    raw, body = parts
    try:
        data = _load_yaml(raw)
    except yaml.YAMLError as err:
        raise InvalidSkill(f"frontmatter is not valid YAML: {err}") from err
    if not isinstance(data, dict):
        raise InvalidSkill("frontmatter must be a YAML mapping")
    if "description" not in data:
        raise InvalidSkill("description is required")
    try:
        frontmatter = Frontmatter.model_validate(data)
    except ValidationError as err:
        first = err.errors()[0]
        field = ".".join(str(part) for part in first["loc"]) or "frontmatter"
        raise InvalidSkill(f"{field}: {first['msg']}") from err
    if not frontmatter.description.strip():
        raise InvalidSkill("description must not be empty")
    return Parsed(frontmatter, body)


def _split(text: str) -> tuple[str, str] | None:
    """`(yaml, body)` — or `None` when there is no leading fence."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != _FENCE:
        return None
    for at, line in enumerate(lines[1:], start=1):
        if line.strip() == _FENCE:
            return "".join(lines[1:at]), "".join(lines[at + 1 :]).strip()
    return None


def _load_yaml(raw: str) -> object:
    try:
        return yaml.safe_load(raw)
    except yaml.YAMLError:
        return yaml.safe_load(_quote_colons(raw))


_UNQUOTED = re.compile(r"^(?P<key>[\w-]+):[ \t]+(?P<value>[^\"'#|>\[{].*?: .*)$")


def _quote_colons(raw: str) -> str:
    def quote(match: re.Match[str]) -> str:
        value = match.group("value").replace("\\", "\\\\").replace('"', '\\"')
        return f'{match.group("key")}: "{value}"'

    return "\n".join(_UNQUOTED.sub(quote, line) for line in raw.splitlines())
