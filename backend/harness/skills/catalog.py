"""Skills read from ranked directories on disk.

Every call rescans the roots. That sounds expensive and is not: a root's listing
plus one `stat` per `SKILL.md`, and a file whose `(mtime, size)` has not moved
is served from the last parse. It is what makes a skill copied into a root
appear at the next step with no watcher, no debounce, and no "a directory
created after startup needs a restart" hole — the limitation Claude Code
documents for its watcher-based design.

Ranked: the first root to hold a name wins, and the shadowed copy is reported
rather than silently dropped. A root that cannot be listed keeps contributing
whatever it last held — incomplete is not empty, and one unmounted directory
must not take every other root's skills out of the catalog with it.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

from harness.skills.models import (
    MAX_DESCRIPTION_CHARS,
    SKILL_FILE,
    InvalidSkill,
    Skill,
    SkillProblem,
    SkillSnapshot,
    parse,
    valid_name,
)

logger = logging.getLogger("harness.skills")


class SkillCatalog:
    """Every skill under a ranked list of roots, read afresh on each call.

    Not a skill: the thing that finds them. Built once with the roots at
    startup; called on every request to get the current `SkillSnapshot`.

    A `SkillSnapshot` is the unit at every level — one file yields one with zero or
    one skill, one root yields one with many, and the call merges them.
    """

    def __init__(self, roots: Sequence[Path]) -> None:
        self._roots = tuple(roots)
        # Per file: the (mtime_ns, size) it was parsed at, and what it yielded.
        self._parsed: dict[Path, tuple[tuple[int, int], SkillSnapshot]] = {}
        self._last_good: dict[Path, SkillSnapshot] = {}
        self._failing: set[Path] = set()

    @property
    def roots(self) -> tuple[Path, ...]:
        return self._roots

    def __call__(self) -> SkillSnapshot:
        skills: dict[str, Skill] = {}
        problems: list[SkillProblem] = []
        for root in self._roots:
            scanned = self._scan(root)
            problems.extend(scanned.problems)
            for skill in scanned.skills:
                if skill.name in skills:
                    problems.append(
                        SkillProblem(
                            path=skill.dir / SKILL_FILE,
                            problem=f"shadowed by {skills[skill.name].dir / SKILL_FILE}",
                        )
                    )
                    continue
                skills[skill.name] = skill
        return SkillSnapshot(skills=tuple(skills.values()), problems=tuple(problems))

    def _scan(self, root: Path) -> SkillSnapshot:
        if not root.is_dir():
            # `~/.agents/skills` usually does not exist. Nothing to say.
            return SkillSnapshot()
        try:
            entries = sorted(entry for entry in root.iterdir() if entry.is_dir())
        except OSError as err:
            if root not in self._failing:
                logger.warning("cannot list skills root %s: %s; keeping its last set", root, err)
                self._failing.add(root)
            return self._last_good.get(root, SkillSnapshot())
        self._failing.discard(root)

        skills: list[Skill] = []
        problems: list[SkillProblem] = []
        for entry in entries:
            if not (entry / SKILL_FILE).is_file():
                continue
            loaded = self._load(root, entry)
            skills.extend(loaded.skills)
            problems.extend(loaded.problems)
        scanned = SkillSnapshot(skills=tuple(skills), problems=tuple(problems))
        self._last_good[root] = scanned
        return scanned

    def _load(self, root: Path, entry: Path) -> SkillSnapshot:
        file = entry / SKILL_FILE
        try:
            stat = file.stat()
        except OSError as err:
            return _problem(file, str(err))
        stamp = (stat.st_mtime_ns, stat.st_size)
        cached = self._parsed.get(file)
        if cached is not None and cached[0] == stamp:
            return cached[1]
        loaded = _read(root, entry)
        self._parsed[file] = (stamp, loaded)
        return loaded


def _read(root: Path, entry: Path) -> SkillSnapshot:
    """One `SKILL.md`: a skill with zero or more caveats, or none with one problem."""
    file = entry / SKILL_FILE
    if not valid_name(entry.name):
        return _problem(
            file,
            f"directory name {entry.name!r} is not a skill name: lowercase letters, digits "
            "and single hyphens, at most 64",
        )
    try:
        parsed = parse(file.read_text(encoding="utf-8"))
    except (InvalidSkill, OSError, UnicodeDecodeError) as err:
        return _problem(file, str(err))

    front = parsed.frontmatter
    notes: list[SkillProblem] = []
    if front.name is not None and front.name != entry.name:
        # Loaded anyway, under the directory's name — the spec's lenient rule.
        notes.append(
            SkillProblem(
                path=file,
                problem=(
                    f"frontmatter name {front.name!r} differs from the directory; "
                    "the directory name is used"
                ),
            )
        )
    description = front.description.strip()
    if len(description) > MAX_DESCRIPTION_CHARS:
        notes.append(
            SkillProblem(
                path=file, problem=f"description truncated to {MAX_DESCRIPTION_CHARS} characters"
            )
        )
    skill = Skill(
        name=entry.name,
        description=description[:MAX_DESCRIPTION_CHARS],
        dir=entry,
        root=root,
        model_invocable=not front.disable_model_invocation,
        user_invocable=front.user_invocable,
    )
    return SkillSnapshot(skills=(skill,), problems=tuple(notes))


def _problem(file: Path, problem: str) -> SkillSnapshot:
    return SkillSnapshot(problems=(SkillProblem(path=file, problem=problem),))
