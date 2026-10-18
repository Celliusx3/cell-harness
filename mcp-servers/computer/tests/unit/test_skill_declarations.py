"""What the skills in the mounted folders declare: read, checked, and skipped with a log line."""

from __future__ import annotations

import logging
import shlex
from pathlib import Path

import pytest

from computer.host_services import HostService
from computer.skill_declarations import declared_host_services
from tests.fake_host_service import PROGRAM_NAME, declaring, fake_host_service, write_skill

WORDS = "--port {port} --token-file {token_file} --files={files}"


@pytest.fixture
def program(tmp_path: Path) -> Path:
    return fake_host_service(tmp_path / "bin", "listens")


@pytest.fixture
def skills(tmp_path: Path) -> Path:
    folder = tmp_path / "skills"
    folder.mkdir()
    return folder


@pytest.fixture
def warnings(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    caplog.set_level(logging.WARNING, logger="computer")
    return caplog


def test_a_declared_program_that_is_installed_is_found_with_its_words_and_prefix(
    program: Path, skills: Path, warnings: pytest.LogCaptureFixture
) -> None:
    write_skill(skills, "comic", declaring(f"{shlex.quote(str(program))} {WORDS}", "COMIC"))

    assert declared_host_services([skills], "") == (
        HostService(
            skill="comic",
            env_prefix="COMIC",
            program=program,
            arguments=("--port", "{port}", "--token-file", "{token_file}", "--files={files}"),
        ),
    )
    assert warnings.records == []


def test_a_program_named_bare_is_found_on_the_servers_path(program: Path, skills: Path) -> None:
    write_skill(skills, "comic", declaring(f"{PROGRAM_NAME} {WORDS}"))

    (service,) = declared_host_services([skills], str(program.parent))

    assert service.program == program


def test_a_program_path_from_home_is_expanded(
    program: Path, skills: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    write_skill(skills, "comic", declaring(f"~/bin/{PROGRAM_NAME} {WORDS}"))

    (service,) = declared_host_services([skills], "")

    assert service.program == program


@pytest.mark.parametrize(
    "frontmatter",
    [
        "name: plain\ndescription: Declares nothing.",
        "name: plain\ndescription: Declares nothing.\nmetadata:",
        "name: plain\ndescription: Declares nothing.\nmetadata: {version: 1.0, author: me}",
    ],
)
def test_a_skill_without_a_declaration_declares_nothing_and_logs_nothing(
    skills: Path, frontmatter: str, warnings: pytest.LogCaptureFixture
) -> None:
    write_skill(skills, "plain", frontmatter)

    assert declared_host_services([skills], "") == ()
    assert warnings.records == []


def test_a_program_that_is_not_installed_is_skipped_with_a_warning_naming_skill_and_program(
    skills: Path, tmp_path: Path, warnings: pytest.LogCaptureFixture
) -> None:
    write_skill(skills, "comic", declaring(f"photo-cli {WORDS}"))

    assert declared_host_services([skills], str(tmp_path)) == ()
    assert (
        "the skill comic declares photo-cli, which is not installed, so commands in the computer "
        "run without it"
    ) in warnings.text


@pytest.mark.parametrize(
    ("words", "env_prefix", "reason"),
    [
        (WORDS, "comic", "host-service-env='comic' is not capital letters"),
        (WORDS, "9COMIC", "host-service-env='9COMIC' is not capital letters"),
        (WORDS, "CO-MIC", "host-service-env='CO-MIC' is not capital letters"),
        (WORDS, "COMIC\n", "is not capital letters"),
        ("--root {root}", "COMIC", "'{root}' has a placeholder other than {port}"),
        ("--port={port!r}", "COMIC", "has a placeholder other than"),
        ("--port {port:5}", "COMIC", "has a placeholder other than"),
        ("--port {}", "COMIC", "has a placeholder other than"),
        ("--port {0}", "COMIC", "has a placeholder other than"),
        ("--files {files.parent}", "COMIC", "has a placeholder other than"),
        ("--port {port", "COMIC", "'{port' has a brace out of place"),
        ("--port port}", "COMIC", "has a brace out of place"),
        ("'--port {port}", "COMIC", "host-service does not split into words"),
    ],
)
def test_a_malformed_declaration_is_skipped_with_a_log_line(
    program: Path,
    skills: Path,
    words: str,
    env_prefix: str,
    reason: str,
    warnings: pytest.LogCaptureFixture,
) -> None:
    write_skill(skills, "comic", declaring(f"{shlex.quote(str(program))} {words}", env_prefix))

    assert declared_host_services([skills], "") == ()
    assert "the skill comic declares no program this server can start" in warnings.text
    assert reason in warnings.text


@pytest.mark.parametrize(
    ("frontmatter", "reason"),
    [
        ('metadata: {"host-service": "photo-cli"}', "one of host-service and host-service-env"),
        ('metadata: {"host-service-env": "COMIC"}', "one of host-service and host-service-env"),
        ('metadata: {"host-service": "", "host-service-env": "COMIC"}', "names no program"),
        ('metadata: {"host-service": [a], "host-service-env": "COMIC"}', "metadata.host-service"),
        ("metadata: [host-service, photo-cli]", "its metadata is not usable"),
        ("name: comic\ndescription: [unclosed", "its frontmatter is not valid YAML"),
        ("- a list, not a mapping", "its frontmatter is not usable"),
    ],
)
def test_a_declaration_with_one_key_or_frontmatter_that_does_not_parse_is_skipped_with_a_log_line(
    skills: Path, frontmatter: str, reason: str, warnings: pytest.LogCaptureFixture
) -> None:
    write_skill(skills, "comic", frontmatter)

    assert declared_host_services([skills], "") == ()
    assert "the skill comic declares no program this server can start" in warnings.text
    assert reason in warnings.text


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        (b"# comic\n\nNo frontmatter here.\n", "does not start with a `---` line"),
        (b"---\nname: comic\ndescription: Never closed.\n", "has no closing `---` line"),
        (b"", "does not start with a `---` line"),
        (b"---\nname: comic\ndescription: \xff\xfe\n---\n", "can't decode"),
    ],
)
def test_a_skill_md_that_cannot_be_read_as_frontmatter_is_skipped_with_a_log_line(
    skills: Path, content: bytes, reason: str, warnings: pytest.LogCaptureFixture
) -> None:
    (skills / "comic").mkdir()
    (skills / "comic" / "SKILL.md").write_bytes(content)

    assert declared_host_services([skills], "") == ()
    assert "the skill comic declares no program this server can start" in warnings.text
    assert reason in warnings.text


def test_a_skill_folder_outside_the_skills_folders_is_never_read(
    program: Path, skills: Path, tmp_path: Path, warnings: pytest.LogCaptureFixture
) -> None:
    elsewhere = tmp_path / "elsewhere"
    write_skill(elsewhere, "outside", declaring(f"{shlex.quote(str(program))} {WORDS}"))
    write_skill(elsewhere, "broken", "description: [unclosed")
    write_skill(skills / "comic" / "nested", "deeper", declaring(f"{program} {WORDS}"))
    (skills / "comic" / "SKILL.md").write_text("---\nname: comic\ndescription: Plain.\n---\n")
    (skills / "SKILL.md").write_text(f"---\n{declaring(f'{program} {WORDS}')}\n---\n")

    assert declared_host_services([skills], "") == ()
    assert warnings.records == []


def test_every_skills_folder_is_read_and_a_child_without_a_skill_md_is_passed_over(
    program: Path, tmp_path: Path, warnings: pytest.LogCaptureFixture
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    write_skill(first, "one", declaring(f"{program} {WORDS}", "ONE"))
    write_skill(second, "two", declaring(f"{program} {WORDS}", "TWO"))
    (second / "notes").mkdir()
    (second / "README.md").write_text("not a skill")

    services = declared_host_services([first, second], "")

    assert [(each.skill, each.env_prefix) for each in services] == [("one", "ONE"), ("two", "TWO")]
    assert warnings.records == []


def test_a_second_skill_taking_a_prefix_already_taken_is_skipped_with_a_warning(
    program: Path, skills: Path, warnings: pytest.LogCaptureFixture
) -> None:
    write_skill(skills, "first", declaring(f"{program} {WORDS}", "COMIC"))
    write_skill(skills, "second", declaring(f"{program} {WORDS}", "COMIC"))

    services = declared_host_services([skills], "")

    assert [each.skill for each in services] == ["first"]
    assert "the skill second declares host-service-env COMIC" in warnings.text
    assert "which the skill first already has" in warnings.text


def test_a_skills_folder_that_cannot_be_listed_is_skipped_with_a_log_line(
    program: Path, skills: Path, tmp_path: Path, warnings: pytest.LogCaptureFixture
) -> None:
    locked = tmp_path / "locked"
    write_skill(locked, "hidden", declaring(f"{program} {WORDS}", "HIDDEN"))
    write_skill(skills, "comic", declaring(f"{program} {WORDS}", "COMIC"))
    locked.chmod(0)
    try:
        services = declared_host_services([locked, skills], "")
    finally:
        locked.chmod(0o755)

    assert [each.skill for each in services] == ["comic"]
    assert f"the skill folder {locked} cannot be read, so it declares nothing" in warnings.text
