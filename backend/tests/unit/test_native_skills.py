"""`skill_save`, `skill_delete` and `skill_write_file`: the Skills page's writes, as tools."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.tools.definition import Failure, Ok
from harness.tools.native.skills import skill_delete_tool, skill_save_tool, skill_write_file_tool
from tests.unit.helpers import context_for, skills_at

VALID = "---\nname: notes\ndescription: Take notes.\n---\n# Notes\n\nWrite them down.\n"


def write_skill(root: Path, name: str) -> Path:
    (root / name).mkdir(parents=True)
    (root / name / "SKILL.md").write_text(f"---\ndescription: {name} things.\n---\nDo {name}.\n")
    return root / name


async def call(tool, **arguments):
    return await tool.invoke(json.dumps(arguments), context=context_for())


@pytest.fixture
def roots(tmp_path: Path) -> tuple[Path, Path]:
    """A project root that outranks the editable home root, as in config.json."""
    project, home = tmp_path / "project", tmp_path / "home"
    write_skill(project, "pdf")
    home.mkdir()
    return project, home


async def test_saving_writes_where_the_page_writes(roots) -> None:
    project, home = roots

    outcome = await call(skill_save_tool(skills_at(project, home)), name="notes", text=VALID)

    assert isinstance(outcome, Ok) and "notes" in outcome.text
    assert (home / "notes" / "SKILL.md").read_text() == VALID


@pytest.mark.parametrize(
    ("name", "text", "reason"),
    [
        ("Bad Name", VALID, "name"),
        ("notes", "no frontmatter\n", "---"),
        ("notes", "---\nname: other\ndescription: d\n---\nbody\n", "'other'"),
    ],
)
async def test_a_skill_the_page_would_refuse_comes_back_as_its_message(
    roots, name, text, reason
) -> None:
    project, home = roots

    outcome = await call(skill_save_tool(skills_at(project, home)), name=name, text=text)

    assert isinstance(outcome, Failure) and reason in outcome.message
    assert not (home / name).exists()


async def test_saving_a_name_the_project_root_owns_is_refused_naming_it(roots) -> None:
    project, home = roots

    outcome = await call(
        skill_save_tool(skills_at(project, home)),
        name="pdf",
        text="---\ndescription: mine now\n---\nbody\n",
    )

    assert isinstance(outcome, Failure) and str(project / "pdf") in outcome.message
    assert not (home / "pdf").exists()


async def test_deleting_removes_the_folder_with_what_it_bundles(roots) -> None:
    project, home = roots
    directory = write_skill(home, "mine")
    (directory / "references").mkdir()
    (directory / "references" / "x.md").write_text("bundled")

    outcome = await call(skill_delete_tool(skills_at(project, home)), name="mine")

    assert isinstance(outcome, Ok) and "mine" in outcome.text
    assert not directory.exists()


async def test_deleting_a_project_skill_is_refused_naming_its_root(roots) -> None:
    project, home = roots

    outcome = await call(skill_delete_tool(skills_at(project, home)), name="pdf")

    assert isinstance(outcome, Failure) and str(project) in outcome.message
    assert (project / "pdf" / "SKILL.md").exists()


async def test_deleting_an_unknown_skill_says_so_as_the_page_does(roots) -> None:
    project, home = roots

    outcome = await call(skill_delete_tool(skills_at(project, home)), name="nope")

    assert isinstance(outcome, Failure) and outcome.message == "no skill named 'nope'"


async def test_writing_a_file_puts_it_beside_the_skill_where_the_page_lists_it(roots) -> None:
    project, home = roots
    skills = skills_at(project, home)
    skills.save("notes", VALID)

    outcome = await call(
        skill_write_file_tool(skills), name="notes", path="references/style.md", text="Short.\n"
    )

    assert isinstance(outcome, Ok) and "references/style.md" in outcome.text
    assert (home / "notes" / "references" / "style.md").read_text() == "Short.\n"
    assert skills.files("notes") == ("references/style.md",)


@pytest.mark.parametrize(
    ("path", "reason"),
    [
        ("../escape.md", "escape"),
        ("/tmp/absolute.md", "escape"),
        ("references\\x.md", "escape"),
        (".hidden/x.md", "hidden"),
        ("__pycache__/x.md", "hidden"),
        ("SKILL.md", "SKILL.md"),
        ("skill.md", "SKILL.md"),
        ("a/b/c/d.md", "deeper"),
        ("", "names no file"),
    ],
)
async def test_a_path_the_page_would_never_list_is_refused(roots, path, reason) -> None:
    project, home = roots
    skills = skills_at(project, home)
    skills.save("notes", VALID)

    outcome = await call(skill_write_file_tool(skills), name="notes", path=path, text="x")

    assert isinstance(outcome, Failure) and reason in outcome.message
    assert skills.files("notes") == ()
    assert (home / "notes" / "SKILL.md").read_text() == VALID


async def test_a_file_too_large_to_read_back_is_refused(roots) -> None:
    project, home = roots
    skills = skills_at(project, home)
    skills.save("notes", VALID)

    outcome = await call(
        skill_write_file_tool(skills),
        name="notes",
        path="references/big.md",
        text="x" * (64 * 1024 + 1),
    )

    assert isinstance(outcome, Failure) and "64 KiB" in outcome.message
    assert skills.files("notes") == ()


async def test_writing_into_a_project_skill_is_refused_naming_its_root(roots) -> None:
    project, home = roots

    outcome = await call(
        skill_write_file_tool(skills_at(project, home)),
        name="pdf",
        path="references/x.md",
        text="x",
    )

    assert isinstance(outcome, Failure) and str(project) in outcome.message
    assert not (project / "pdf" / "references").exists()


async def test_writing_into_an_unknown_skill_says_so_as_the_page_does(roots) -> None:
    project, home = roots

    outcome = await call(
        skill_write_file_tool(skills_at(project, home)),
        name="nope",
        path="references/x.md",
        text="x",
    )

    assert isinstance(outcome, Failure) and outcome.message == "no skill named 'nope'"


async def test_a_folder_that_links_outside_the_skill_is_refused(roots, tmp_path) -> None:
    project, home = roots
    skills = skills_at(project, home)
    skills.save("notes", VALID)
    outside = tmp_path / "outside"
    outside.mkdir()
    (home / "notes" / "references").symlink_to(outside, target_is_directory=True)

    outcome = await call(
        skill_write_file_tool(skills), name="notes", path="references/x.md", text="x"
    )

    assert isinstance(outcome, Failure) and "escape" in outcome.message
    assert list(outside.iterdir()) == []
