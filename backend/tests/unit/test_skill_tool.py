"""The `skill` tool: an enum of what exists, the index in its description, the
body as its result — and nothing at all when there is nothing to load."""

from __future__ import annotations

import json
from pathlib import Path

from harness.skills import SKILL, skill_tool
from harness.tools.definition import INVALID_ARGUMENTS, Failure, Ok
from tests.unit.helpers import no_progress, no_skills, skills_at


def write_skill(root: Path, name: str, description: str = "Does X. Use when Y.", **front) -> Path:
    directory = root / name
    directory.mkdir(parents=True, exist_ok=True)
    extra = "".join(f"{key.replace('_', '-')}: {value}\n" for key, value in front.items())
    (directory / "SKILL.md").write_text(
        f"---\ndescription: {description}\n{extra}---\n# {name}\n\nSteps for {name}.\n"
    )
    return directory


async def call(tool, **arguments):
    return await tool.invoke(json.dumps(arguments), progress=no_progress)


def test_no_skills_means_no_tool() -> None:
    assert skill_tool(no_skills()) is None


def test_the_enum_and_the_index_come_from_the_same_subset(tmp_path) -> None:
    write_skill(tmp_path, "pdf", "PDF work.")
    write_skill(tmp_path, "deploy", "Ship it.", disable_model_invocation="true")

    tool = skill_tool(skills_at(tmp_path))

    assert tool is not None and tool.name == SKILL
    spec = tool.spec()
    assert spec.input_schema["properties"]["name"]["enum"] == ["pdf"]
    assert "<name>pdf</name><description>PDF work.</description>" in spec.description
    assert "deploy" not in spec.description


def test_only_hidden_skills_means_no_tool(tmp_path) -> None:
    write_skill(tmp_path, "deploy", disable_model_invocation="true")

    assert skill_tool(skills_at(tmp_path)) is None


def test_the_schema_is_an_allowlist_of_three_fields(tmp_path) -> None:
    write_skill(tmp_path, "pdf")
    spec = skill_tool(skills_at(tmp_path)).spec()

    assert set(spec.input_schema["properties"]) == {"name", "path"}
    assert spec.input_schema["required"] == ["name"]


async def test_an_invented_name_is_a_schema_violation(tmp_path) -> None:
    write_skill(tmp_path, "pdf")
    tool = skill_tool(skills_at(tmp_path))

    outcome = await call(tool, name="xlsx")

    assert isinstance(outcome, Failure) and outcome.code == INVALID_ARGUMENTS


async def test_activation_returns_the_body_without_frontmatter(tmp_path) -> None:
    write_skill(tmp_path, "pdf")
    tool = skill_tool(skills_at(tmp_path))

    outcome = await call(tool, name="pdf")

    assert isinstance(outcome, Ok)
    assert outcome.text == '<skill name="pdf">\n# pdf\n\nSteps for pdf.\n</skill>'
    assert "description:" not in outcome.text


async def test_a_body_edit_shows_at_the_next_call_with_the_spec_unchanged(tmp_path) -> None:
    directory = write_skill(tmp_path, "pdf")
    catalog = skills_at(tmp_path)
    before = skill_tool(catalog)

    (directory / "SKILL.md").write_text("---\ndescription: Does X. Use when Y.\n---\nNew steps.\n")

    after = skill_tool(catalog)
    assert after.spec() == before.spec()
    assert "New steps." in (await call(after, name="pdf")).text


async def test_bundled_files_are_listed_not_read(tmp_path) -> None:
    directory = write_skill(tmp_path, "pdf")
    (directory / "references").mkdir()
    (directory / "references" / "forms.md").write_text("FORMS " * 100)
    (directory / "scripts").mkdir()
    (directory / "scripts" / "fill.py").write_text("print(1)")
    (directory / ".hidden").write_text("no")
    tool = skill_tool(skills_at(tmp_path))

    outcome = await call(tool, name="pdf")

    assert outcome.text.endswith(
        "Bundled files, readable with `path`: references/forms.md, scripts/fill.py"
    )
    assert "FORMS" not in outcome.text


async def test_the_listing_is_capped(tmp_path) -> None:
    directory = write_skill(tmp_path, "pdf")
    (directory / "assets").mkdir()
    for n in range(25):
        (directory / "assets" / f"f{n:02}.txt").write_text("x")
    tool = skill_tool(skills_at(tmp_path))

    outcome = await call(tool, name="pdf")

    assert outcome.text.count("assets/") == 20
    assert outcome.text.endswith(", and 5 more")


async def test_a_bundled_file_is_read_by_path(tmp_path) -> None:
    directory = write_skill(tmp_path, "pdf")
    (directory / "references").mkdir()
    (directory / "references" / "forms.md").write_text("Fill the form.")
    tool = skill_tool(skills_at(tmp_path))

    outcome = await call(tool, name="pdf", path="references/forms.md")

    assert isinstance(outcome, Ok)
    assert outcome.text == (
        '<skill_file name="pdf" path="references/forms.md">\nFill the form.\n</skill_file>'
    )


async def test_a_path_cannot_escape_the_skill(tmp_path) -> None:
    write_skill(tmp_path, "pdf")
    write_skill(tmp_path, "other")
    (tmp_path / "secret.txt").write_text("no")
    tool = skill_tool(skills_at(tmp_path))

    for path in ("../secret.txt", "../other/SKILL.md", "/etc/hosts", ".", ""):
        outcome = await call(tool, name="pdf", path=path)
        assert isinstance(outcome, Failure), path
        assert outcome.code == INVALID_ARGUMENTS


async def test_missing_binary_and_oversize_files_are_refused(tmp_path) -> None:
    directory = write_skill(tmp_path, "pdf")
    (directory / "big.txt").write_text("x" * (64 * 1024 + 1))
    (directory / "img.png").write_bytes(b"\x89PNG\xff\xfe\x00")
    tool = skill_tool(skills_at(tmp_path))

    for path, reason in (("nope.md", "no file"), ("big.txt", "KiB"), ("img.png", "not a text")):
        outcome = await call(tool, name="pdf", path=path)
        assert isinstance(outcome, Failure) and reason in outcome.message, path


async def test_a_skill_deleted_after_the_tool_was_built_fails_softly(tmp_path) -> None:
    directory = write_skill(tmp_path, "pdf")
    tool = skill_tool(skills_at(tmp_path))
    (directory / "SKILL.md").unlink()

    outcome = await call(tool, name="pdf")

    assert isinstance(outcome, Failure) and "could not be read" in outcome.message


def test_markup_in_a_description_is_escaped(tmp_path) -> None:
    write_skill(tmp_path, "pdf", "Handles <b>PDF</b> & forms.")

    spec = skill_tool(skills_at(tmp_path)).spec()

    assert "Handles &lt;b&gt;PDF&lt;/b&gt; &amp; forms." in spec.description
