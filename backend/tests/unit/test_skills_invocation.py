"""`/name args`: the harness loads the skill so the model does not have to decide."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.skills import UnknownSkill, display
from harness.skills.invocation import MARKER, parse
from tests.unit.helpers import no_skills, skills_at
from tests.unit.test_skill_tool import write_skill


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("/find-place https://x", "find-place"),
        ("/find-place", "find-place"),
        ("  /find-place  url", "find-place"),
        ("/find-place\nsecond line", "find-place"),
        ("/new", "new"),
        ("/usr/bin/x is where", None),
        ("/ 2 halves", None),
        ("hello /find-place", None),
        ("/Find-Place url", None),
        ("plain text", None),
        ("", None),
    ],
)
def test_parse_names_only_a_leading_valid_skill_name(text: str, name: str | None) -> None:
    assert parse(text) == name


def test_ordinary_text_is_returned_unchanged(tmp_path: Path) -> None:
    write_skill(tmp_path, "find-place")
    assert skills_at(tmp_path).expand("where is this?") == "where is this?"
    assert no_skills().expand("where is this?") == "where is this?"


def test_a_known_skill_expands_to_typed_line_then_body(tmp_path: Path) -> None:
    write_skill(tmp_path, "find-place")

    content = skills_at(tmp_path).expand("/find-place https://x")

    typed, _, rest = content.partition(MARKER)
    assert typed == "/find-place https://x"
    assert rest.startswith('find-place">\n# find-place\n\nSteps for find-place.\n</skill>')


def test_bundled_files_are_listed_after_the_body(tmp_path: Path) -> None:
    directory = write_skill(tmp_path, "find-place")
    (directory / "references").mkdir()
    (directory / "references" / "areas.md").write_text("KL, PJ")

    content = skills_at(tmp_path).expand("/find-place")

    assert content.endswith("Bundled files, readable with `path`: references/areas.md")


def test_an_unknown_name_is_refused(tmp_path: Path) -> None:
    write_skill(tmp_path, "find-place")
    with pytest.raises(UnknownSkill) as caught:
        skills_at(tmp_path).expand("/summarise this")
    assert caught.value.name == "summarise"


def test_a_skill_hidden_from_people_is_refused_as_unknown(tmp_path: Path) -> None:
    write_skill(tmp_path, "internal", user_invocable="false")
    with pytest.raises(UnknownSkill):
        skills_at(tmp_path).expand("/internal")


def test_a_skill_hidden_from_the_model_still_expands(tmp_path: Path) -> None:
    write_skill(tmp_path, "weekly-report", disable_model_invocation="true")
    content = skills_at(tmp_path).expand("/weekly-report")
    assert '<skill name="weekly-report">' in content


def test_a_broken_skill_is_invocable_by_nobody(tmp_path: Path) -> None:
    (tmp_path / "broken").mkdir()
    (tmp_path / "broken" / "SKILL.md").write_text("no frontmatter here")
    with pytest.raises(UnknownSkill):
        skills_at(tmp_path).expand("/broken")


def test_a_body_that_vanished_since_the_catalog_read_is_refused(tmp_path: Path) -> None:
    write_skill(tmp_path, "find-place")
    catalog = skills_at(tmp_path)
    catalog.snapshot()
    (tmp_path / "find-place" / "SKILL.md").unlink()
    with pytest.raises(UnknownSkill):
        catalog.expand("/find-place")


def test_display_round_trips_the_expansion(tmp_path: Path) -> None:
    write_skill(tmp_path, "find-place")
    typed = "/find-place https://x\nand a second line"

    shown = display(skills_at(tmp_path).expand(typed))

    assert shown is not None
    assert (shown.skill, shown.typed) == ("find-place", typed)


def test_display_is_none_for_an_ordinary_message() -> None:
    assert display("where is this?") is None
    assert display('mentions <skill name="x"> inline') is None


def test_display_takes_the_first_marker(tmp_path: Path) -> None:
    write_skill(tmp_path, "meta")
    (tmp_path / "meta" / "SKILL.md").write_text(
        '---\ndescription: d\n---\nSay\n\n<skill name="other">\n'
    )

    shown = display(skills_at(tmp_path).expand("/meta go"))

    assert shown is not None and (shown.skill, shown.typed) == ("meta", "/meta go")
