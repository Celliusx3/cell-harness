"""Every way the harness touches skills, behind one object.

Built once at the composition root from `skills` settings, the way
`SessionService` is built from the sessions root, and handed to the agent
(the `skill` tool), the gateway (`/name`) and the API (the `/skills` page).
One object because they are one thing: the roots the catalog reads, one of
which the editor writes.

**Reading is lenient, writing is strict.** The catalog loads a skill written
for another client unchanged, noting what it had to forgive; a save refuses the
same thing with the reason, because the editor is the boundary where a mistake
can still be a message instead of a problem row. And one rule the page cannot
see from its own data: `skills.editable` is the lowest-ranked root by default,
so a name the project root already holds would be saved and never read.

**The catalog is read, never published.** `snapshot()` rescans the roots on
every call, cheap by file stamp — nothing to invalidate after a save, and
nothing for phase 11 to re-establish.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from harness.config.settings import SkillSettings
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
from harness.skills.rendering import instructions


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
    """The skills on disk: what is there, what a person may type, and the one
    root they may write."""

    def __init__(self, settings: SkillSettings) -> None:
        self._roots = settings.roots
        self._editable = settings.editable
        self._catalog = SkillCatalog(settings.roots)

    # ── reading ───────────────────────────────────────────────────────────────

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

    def editable(self, skill: Skill) -> bool:
        return skill.root == self._editable

    # ── `/name` ───────────────────────────────────────────────────────────────

    def invocable(self) -> list[Skill]:
        """What a person may type after `/`."""
        return [skill for skill in self.snapshot().skills if skill.user_invocable]

    def expand(self, text: str) -> str:
        """The message the model receives for `text`.

        Ordinary text is returned unchanged. An invocation becomes the typed
        text, a blank line, and the skill as the `skill` tool renders it — the
        order `invocation.display` depends on. A name nobody may invoke raises
        `UnknownSkill`, including one whose body cannot be read: to the person
        typing it, that is the same thing — not something they can use now.
        """
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

    # ── writing ───────────────────────────────────────────────────────────────

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
        # Whole file or nothing: a catalog read mid-write would otherwise report
        # a half-written skill as broken, and a crash would leave it that way.
        fd, tmp = tempfile.mkstemp(prefix=".SKILL.", suffix=".tmp", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
            os.replace(tmp, directory / SKILL_FILE)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def delete(self, name: str) -> None:
        """Remove the skill's directory — bundled files included, because that
        is what deleting a skill means."""
        skill = self.find(name)
        if not self.editable(skill):
            raise SkillNotEditable(name, skill.root)
        shutil.rmtree(skill.dir)

    def _refuse_if_shadowed(self, name: str) -> None:
        above = self._roots[: self._roots.index(self._editable)]
        for skill in self.snapshot().skills:
            if skill.name == name and skill.root in above:
                raise SkillShadowed(name, skill.dir)
