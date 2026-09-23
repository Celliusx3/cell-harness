"""Every way the harness touches skills, behind one object."""

from __future__ import annotations

import io
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from harness.config.settings import SkillSettings
from harness.skills import archive, resources
from harness.skills.archive import ArchivePlan
from harness.skills.catalog import SkillCatalog
from harness.skills.invocation import parse
from harness.skills.models import (
    SKILL_FILE,
    InvalidSkill,
    Skill,
    SkillSnapshot,
    UnknownSkill,
    valid_name,
)
from harness.skills.models import (
    parse as parse_file,
)
from harness.skills.prompt import instructions


class SkillNotFound(LookupError):
    """No skill of that name is in the catalog."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name


class SkillNotEditable(PermissionError):
    """The skill lives in a root the editor does not write to."""

    def __init__(self, name: str, root: Path) -> None:
        super().__init__(f"{name!r} lives in {root}, which is not the editable root")
        self.name = name
        self.root = root


class SkillShadowed(FileExistsError):
    """A higher-ranked root already holds this name; a save would never be read."""

    def __init__(self, name: str, winner: Path) -> None:
        super().__init__(f"{name!r} is shadowed by {winner}; saved here it would never load")
        self.name = name
        self.winner = winner


class SkillService:
    """The skills on disk, what a person may type, and the one root they may write."""

    def __init__(self, settings: SkillSettings) -> None:
        self._roots = settings.roots
        self._editable = settings.editable
        self._catalog = SkillCatalog(settings.roots)

    def snapshot(self) -> SkillSnapshot:
        """Every loadable skill and every problem, as of now."""
        return self._catalog()

    def find(self, name: str) -> Skill:
        for skill in self.snapshot().skills:
            if skill.name == name:
                return skill
        raise SkillNotFound(name)

    def read(self, name: str) -> str:
        """The `SKILL.md` as it is on disk, for the editor to show."""
        return (self.find(name).dir / SKILL_FILE).read_text(encoding="utf-8")

    def files(self, name: str) -> tuple[str, ...]:
        """Every file the named skill bundles beside its `SKILL.md`."""
        return resources.listing(self.find(name))

    def file(self, name: str, path: str) -> str:
        """One bundled file of the named skill, or `UnreadableFile` saying why not."""
        return resources.read(self.find(name), path)

    def editable(self, skill: Skill) -> bool:
        return skill.root == self._editable

    def invocable(self) -> list[Skill]:
        """What a person may type after `/`."""
        return [skill for skill in self.snapshot().skills if skill.user_invocable]

    def expand(self, text: str) -> str:
        """The message the model receives for `text`."""
        name = parse(text)
        if name is None:
            return text
        skill = next((s for s in self.invocable() if s.name == name), None)
        if skill is None:
            raise UnknownSkill(name)
        try:
            loaded = instructions(skill)
        except (OSError, ValueError) as err:
            raise UnknownSkill(name) from err
        return f"{text}\n\n{loaded}"

    def save(self, name: str, text: str) -> None:
        """Write `text` as `<editable>/<name>/SKILL.md`, or refuse with the reason."""
        if not valid_name(name):
            raise InvalidSkill(
                f"name {name!r} must be lowercase letters, digits and single hyphens, 64 at most"
            )
        declared = parse_file(text).frontmatter.name
        if declared is not None and declared != name:
            raise InvalidSkill(f"frontmatter name {declared!r} does not match {name!r}")
        self._refuse_if_shadowed(name)

        directory = self._editable / name
        directory.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".SKILL.", suffix=".tmp", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
            os.replace(tmp, directory / SKILL_FILE)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def install(self, data: bytes) -> str:
        """Unpack a zipped skill folder into the editable root; return the skill's name."""
        if len(data) > archive.MAX_ARCHIVE_BYTES:
            raise InvalidSkill(
                f"the upload is {len(data)} bytes, larger than the "
                f"{archive.MAX_ARCHIVE_BYTES} allowed"
            )
        try:
            zipped = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as err:
            raise InvalidSkill(f"the upload is not a readable zip archive: {err}") from err
        with zipped:
            plan = archive.plan(archive.members_of(zipped))
            self._refuse_if_shadowed(plan.name)
            self._editable.mkdir(parents=True, exist_ok=True)
            staged = Path(tempfile.mkdtemp(dir=self._editable.parent))
            try:
                _extract(zipped, plan, staged)
                _refuse_mismatched_name(staged / SKILL_FILE, plan.name)
                _replace_whole_directory(staged, self._editable / plan.name)
            finally:
                shutil.rmtree(staged, ignore_errors=True)
        return plan.name

    def delete(self, name: str) -> None:
        """Remove the skill's directory, bundled files included."""
        skill = self.find(name)
        if not self.editable(skill):
            raise SkillNotEditable(name, skill.root)
        shutil.rmtree(skill.dir)

    def _refuse_if_shadowed(self, name: str) -> None:
        above = self._roots[: self._roots.index(self._editable)]
        for skill in self.snapshot().skills:
            if skill.name == name and skill.root in above:
                raise SkillShadowed(name, skill.dir)


def _refuse_mismatched_name(file: Path, name: str) -> None:
    """Raise unless the staged `SKILL.md` parses and agrees with the folder it came in."""
    try:
        text = file.read_text(encoding="utf-8")
    except UnicodeDecodeError as err:
        raise InvalidSkill(f"{SKILL_FILE} is not a UTF-8 text file") from err
    declared = parse_file(text).frontmatter.name
    if declared is not None and declared != name:
        raise InvalidSkill(f"frontmatter name {declared!r} does not match the folder {name!r}")


def _replace_whole_directory(staged: Path, destination: Path) -> None:
    """Put `staged` where `destination` is, leaving no file of what was there."""
    if not destination.exists():
        os.replace(staged, destination)
        return
    aside = staged.with_name(staged.name + ".replaced")
    os.replace(destination, aside)
    os.replace(staged, destination)
    shutil.rmtree(aside)


def _extract(zipped: zipfile.ZipFile, plan: ArchivePlan, staged: Path) -> None:
    for planned in plan.files:
        target = staged / planned.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(zipped.read(planned.member))
