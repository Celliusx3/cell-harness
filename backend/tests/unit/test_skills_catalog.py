"""Reading skills off disk: the spec's format, the spec's leniency, ranked roots."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from harness.skills import InvalidSkill, parse
from harness.skills.catalog import SkillCatalog

MINIMAL = (
    "---\nname: pdf\ndescription: Extract text from PDFs. Use when handling PDFs.\n---\n"
    "# PDF\n\nDo the thing.\n"
)


def write_skill(root: Path, name: str, text: str | None = None) -> Path:
    """A skill directory. Without `text`, a valid one named after the directory."""
    directory = root / name
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text(
        text if text is not None else MINIMAL.replace("name: pdf", f"name: {name}")
    )
    return directory


def test_a_spec_skill_parses_into_frontmatter_and_body() -> None:
    parsed = parse(MINIMAL)

    assert parsed.frontmatter.name == "pdf"
    assert parsed.frontmatter.description.startswith("Extract text")
    assert parsed.body == "# PDF\n\nDo the thing."
    assert parsed.frontmatter.disable_model_invocation is False
    assert parsed.frontmatter.user_invocable is True


def test_a_claude_code_skill_with_extra_fields_loads_unchanged() -> None:
    text = (
        "---\n"
        "name: commit\n"
        "description: Stage and commit.\n"
        "disable-model-invocation: true\n"
        "user-invocable: false\n"
        "allowed-tools: Bash(git add *) Bash(git commit *)\n"
        "argument-hint: [message]\n"
        "context: fork\n"
        "agent: Explore\n"
        "paths: src/**\n"
        "hooks:\n  - name: h\n    on: tool-call\n"
        "metadata:\n  version: '1.0'\n"
        "license: MIT\n"
        "---\nbody\n"
    )

    parsed = parse(text)

    assert parsed.frontmatter.disable_model_invocation is True
    assert parsed.frontmatter.user_invocable is False
    assert parsed.body == "body"


def test_booleans_accept_the_words_yaml_and_claude_code_accept() -> None:
    parsed = parse("---\ndescription: d\ndisable-model-invocation: yes\nuser-invocable: off\n---\n")

    assert parsed.frontmatter.disable_model_invocation is True
    assert parsed.frontmatter.user_invocable is False


def test_an_unquoted_colon_in_the_description_is_recovered() -> None:
    parsed = parse(
        "---\nname: x\ndescription: Use this skill when: the user asks about PDFs\n---\n"
    )

    assert parsed.frontmatter.description == "Use this skill when: the user asks about PDFs"


def test_no_fence_is_refused() -> None:
    with pytest.raises(InvalidSkill, match="---"):
        parse("# Just markdown\n")


def test_an_unclosed_fence_is_refused() -> None:
    with pytest.raises(InvalidSkill):
        parse("---\nname: x\ndescription: d\n# no closing fence\n")


def test_a_missing_or_empty_description_is_refused() -> None:
    with pytest.raises(InvalidSkill, match="description"):
        parse("---\nname: x\n---\nbody\n")
    with pytest.raises(InvalidSkill, match="description"):
        parse("---\nname: x\ndescription: '  '\n---\nbody\n")


def test_unparseable_yaml_is_refused_with_the_reason() -> None:
    with pytest.raises(InvalidSkill, match="YAML"):
        parse("---\nname: [unclosed\ndescription: d\n---\n")


def test_a_non_mapping_frontmatter_is_refused() -> None:
    with pytest.raises(InvalidSkill, match="mapping"):
        parse("---\n- just\n- a list\n---\n")


def test_a_skill_directory_is_discovered(tmp_path) -> None:
    root = tmp_path / "skills"
    write_skill(root, "pdf")
    (root / "README.md").write_text("ignored")
    (root / "notes").mkdir()

    snapshot = SkillCatalog([root])()

    (skill,) = snapshot.skills
    assert skill.name == "pdf"
    assert skill.dir == root / "pdf"
    assert skill.root == root
    assert skill.model_invocable and skill.user_invocable
    assert snapshot.problems == ()


def test_the_directory_name_is_the_identity_and_a_mismatch_is_reported(tmp_path) -> None:
    root = tmp_path / "skills"
    write_skill(root, "pdf-tools", MINIMAL)

    snapshot = SkillCatalog([root])()

    assert snapshot.skills[0].name == "pdf-tools"
    (problem,) = snapshot.problems
    assert "differs from the directory" in problem.problem


def test_an_invalid_directory_name_is_skipped_with_a_reason(tmp_path) -> None:
    root = tmp_path / "skills"
    write_skill(root, "PDF_Tools")

    snapshot = SkillCatalog([root])()

    assert snapshot.skills == ()
    assert "not a skill name" in snapshot.problems[0].problem


def test_a_broken_skill_is_a_problem_not_a_crash(tmp_path) -> None:
    root = tmp_path / "skills"
    write_skill(root, "good")
    write_skill(root, "bad", "no frontmatter here\n")

    snapshot = SkillCatalog([root])()

    assert [s.name for s in snapshot.skills] == ["good"]
    (problem,) = snapshot.problems
    assert problem.path == root / "bad" / "SKILL.md"


def test_an_overlong_description_is_truncated_in_the_catalog_and_reported(tmp_path) -> None:
    root = tmp_path / "skills"
    write_skill(root, "long", f"---\ndescription: {'x' * 2000}\n---\nbody\n")

    snapshot = SkillCatalog([root])()

    assert len(snapshot.skills[0].description) == 1024
    assert "truncated" in snapshot.problems[0].problem


def test_the_first_root_wins_and_the_shadowed_copy_is_reported(tmp_path) -> None:
    project, home = tmp_path / "project", tmp_path / "home"
    write_skill(project, "pdf", MINIMAL.replace("Do the thing.", "project version"))
    write_skill(home, "pdf", MINIMAL.replace("Do the thing.", "home version"))

    snapshot = SkillCatalog([project, home])()

    (skill,) = snapshot.skills
    assert skill.root == project
    (problem,) = snapshot.problems
    assert problem.path == home / "pdf" / "SKILL.md"
    assert str(project / "pdf" / "SKILL.md") in problem.problem


def test_an_absent_root_contributes_nothing_silently(tmp_path) -> None:
    snapshot = SkillCatalog([tmp_path / "nowhere"])()

    assert snapshot.skills == () and snapshot.problems == ()


def test_a_body_edit_is_seen_at_the_next_read_and_a_description_edit_at_the_next_call(
    tmp_path,
) -> None:
    root = tmp_path / "skills"
    directory = write_skill(root, "pdf")
    catalog = SkillCatalog([root])
    before = catalog()

    file = directory / "SKILL.md"
    file.write_text(
        MINIMAL.replace("Do the thing.", "Do it differently.").replace("PDFs.", "PDFs!")
    )
    touch_newer(file)

    after = catalog()
    assert before.skills[0].description.endswith("PDFs.")
    assert after.skills[0].description.endswith("PDFs!")
    assert parse(file.read_text()).body == "# PDF\n\nDo it differently."


def test_an_unchanged_file_is_not_reparsed(tmp_path, monkeypatch) -> None:
    root = tmp_path / "skills"
    write_skill(root, "pdf")
    skills = SkillCatalog([root])
    skills()

    from harness.skills import catalog as catalog_module

    def boom(*_args, **_kwargs):
        raise AssertionError("parsed again")

    monkeypatch.setattr(catalog_module, "parse", boom)
    assert skills().skills[0].name == "pdf"


@pytest.mark.skipif(os.geteuid() == 0, reason="root can list anything")
def test_a_root_that_cannot_be_listed_keeps_its_last_good_set(tmp_path, caplog) -> None:
    root = tmp_path / "skills"
    write_skill(root, "pdf")
    catalog = SkillCatalog([root])
    assert [s.name for s in catalog().skills] == ["pdf"]

    root.chmod(0)
    try:
        with caplog.at_level("WARNING", logger="harness.skills"):
            first = catalog()
            second = catalog()
    finally:
        root.chmod(0o755)

    assert [s.name for s in first.skills] == ["pdf"]
    assert [s.name for s in second.skills] == ["pdf"]
    assert sum("keeping its last set" in r.message for r in caplog.records) == 1


def touch_newer(file: Path) -> None:
    os.utime(file, ns=(file.stat().st_atime_ns, file.stat().st_mtime_ns + 1))
