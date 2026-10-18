"""The computer sees the chat files read-write and the skills read-only, each at its own path."""

from __future__ import annotations

from pathlib import Path

import pytest

from computer.docker import DockerError
from computer.machine import Machine
from tests.conftest import NAME, Dial, FakeDocker, config, mount_of

MOUNTS = ["inspect", "--type", "container", "--format", "{{json .Mounts}}", NAME]


def folders(tmp_path: Path) -> tuple[Path, Path]:
    files, skills = tmp_path / "files", tmp_path / "skills"
    files.mkdir()
    skills.mkdir()
    return files, skills


async def use(docker: FakeDocker, files: Path, skills: Path) -> None:
    machine = Machine(
        docker=docker, config=config(files_dir=files, skills_dirs=(skills,)), clock=Dial().clock
    )
    async with machine.serving(), machine.in_use():
        pass


async def test_a_new_computer_mounts_files_read_write_and_skills_read_only(tmp_path: Path) -> None:
    files, skills = folders(tmp_path)
    docker = FakeDocker(status="missing")

    await use(docker, files, skills)

    run = next(call for call in docker.calls if call[0] == "run")
    assert f"{files}:{files}" in run
    assert f"{skills}:{skills}:ro" in run


async def test_a_computer_without_the_mounts_is_replaced_keeping_its_home(tmp_path: Path) -> None:
    files, skills = folders(tmp_path)
    docker = FakeDocker(status="running")
    docker.mounts = []

    await use(docker, files, skills)

    verbs = [call[0] for call in docker.calls]
    assert MOUNTS in docker.calls
    assert verbs.index("rm") < verbs.index("run")
    run = next(call for call in docker.calls if call[0] == "run")
    assert f"{NAME}-home:/home/rakazo" in run
    assert f"{files}:{files}" in run


async def test_a_computer_with_the_mounts_is_reused(tmp_path: Path) -> None:
    files, skills = folders(tmp_path)
    docker = FakeDocker(status="running")
    docker.mounts = [
        {"Type": "bind", "Source": str(files), "Destination": str(files), "RW": True},
        {"Type": "bind", "Source": str(skills), "Destination": str(skills), "RW": False},
    ]

    await use(docker, files, skills)

    assert [call[0] for call in docker.calls if call[0] in ("rm", "run")] == []


@pytest.mark.parametrize(
    "volumes",
    [
        ["{files}:{files}", "{skills}:{skills}"],
        ["{files}:{files}:ro", "{skills}:{skills}:ro"],
        ["{files}:/files", "{skills}:{skills}:ro"],
        ["{files}:{files}", "{skills}:{skills}:ro", "/Users/person/old:/Users/person/old"],
    ],
)
async def test_a_computer_whose_mounts_differ_in_any_way_is_replaced(
    tmp_path: Path, volumes: list[str]
) -> None:
    files, skills = folders(tmp_path)
    docker = FakeDocker(status="running")
    docker.mounts = [mount_of(volume.format(files=files, skills=skills)) for volume in volumes]

    await use(docker, files, skills)

    assert [call[0] for call in docker.calls if call[0] in ("rm", "run")] == ["rm", "run"]


async def test_mounts_docker_answers_unreadably_are_refused(tmp_path: Path) -> None:
    files, skills = folders(tmp_path)
    docker = FakeDocker(status="running")
    docker.mounts = [{"Type": "bind", "Source": str(files), "RW": "sometimes"}]

    with pytest.raises(DockerError, match="cannot read"):
        await use(docker, files, skills)

    assert "rm" not in docker.verbs()
