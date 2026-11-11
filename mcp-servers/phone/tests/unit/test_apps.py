"""Installing an APK from the chat's files and opening an app, by Android's package manager."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from phone.models.command import COMMAND_TIMEOUT_SECONDS, CommandResult
from phone.services.apps import INSTALL_TIMEOUT_SECONDS, LIST_PACKAGES, AppError, Apps
from tests.fakes import NAME, FakeEngine

APK = b"PK\x03\x04apk"
PACKAGE = "com.example.notes"
INSTALL = f"base64 -d | pm install -S {len(APK)}"
ACTIVITY = f"{PACKAGE}/.MainActivity"
RESOLVE = f"cmd package resolve-activity --brief -c android.intent.category.LAUNCHER {PACKAGE}"
RESOLVED = CommandResult(0, f"priority=0 preferredOrder=0\n{ACTIVITY}\n", "")
START = f"am start -W -n {ACTIVITY}"


def apps_over(engine: FakeEngine, files: Path) -> Apps:
    return Apps(engine=engine, name=NAME, files_dir=files)


def chat_apk(files: Path) -> Path:
    apk = files / "notes.apk"
    apk.write_bytes(APK)
    return apk


async def test_the_apk_is_piped_as_base64_between_two_package_listings(tmp_path: Path) -> None:
    engine = FakeEngine(state="running", installs=PACKAGE, packages=frozenset({"org.other"}))

    added = await apps_over(engine, tmp_path).install(str(chat_apk(tmp_path)))

    assert added == (PACKAGE,)
    assert engine.commands == [LIST_PACKAGES, INSTALL, LIST_PACKAGES]
    assert engine.stdins == [None, base64.b64encode(APK).decode(), None]
    assert engine.timeouts == [
        COMMAND_TIMEOUT_SECONDS,
        INSTALL_TIMEOUT_SECONDS,
        COMMAND_TIMEOUT_SECONDS,
    ]


async def test_an_apk_already_installed_adds_no_package(tmp_path: Path) -> None:
    engine = FakeEngine(state="running", installs=PACKAGE, packages=frozenset({PACKAGE}))

    assert await apps_over(engine, tmp_path).install(str(chat_apk(tmp_path))) == ()


async def test_a_path_outside_the_chat_files_is_refused_without_running_anything(
    tmp_path: Path,
) -> None:
    files = tmp_path / "files"
    files.mkdir()
    outside = chat_apk(tmp_path)
    engine = FakeEngine(state="running")

    with pytest.raises(AppError, match=f"^{outside} is not one of this chat's files$"):
        await apps_over(engine, files).install(str(outside))

    assert engine.commands == []


async def test_a_symlink_in_the_chat_files_to_a_file_outside_is_refused(tmp_path: Path) -> None:
    files = tmp_path / "files"
    files.mkdir()
    link = files / "notes.apk"
    link.symlink_to(chat_apk(tmp_path))

    with pytest.raises(AppError, match="is not one of this chat's files"):
        await apps_over(FakeEngine(state="running"), files).install(str(link))


async def test_a_dotdot_path_out_of_the_chat_files_is_refused(tmp_path: Path) -> None:
    files = tmp_path / "files"
    files.mkdir()
    chat_apk(tmp_path)

    with pytest.raises(AppError, match="is not one of this chat's files"):
        await apps_over(FakeEngine(state="running"), files).install(f"{files}/../notes.apk")


@pytest.mark.parametrize("name", ["missing.apk", "."])
async def test_a_path_that_is_not_a_file_is_refused(tmp_path: Path, name: str) -> None:
    with pytest.raises(AppError, match="is not one of this chat's files"):
        await apps_over(FakeEngine(state="running"), tmp_path).install(str(tmp_path / name))


@pytest.mark.parametrize(
    ("answer", "said"),
    [
        (CommandResult(1, "Failure [INSTALL_FAILED_INVALID_APK]\n", ""), "INSTALL_FAILED_INVALID"),
        (CommandResult(0, "Failure [INSTALL_FAILED_OLDER_SDK]\n", ""), "INSTALL_FAILED_OLDER_SDK"),
        (CommandResult(0, "", ""), "exit 0"),
    ],
)
async def test_an_install_android_refuses_fails_in_its_words(
    tmp_path: Path, answer: CommandResult, said: str
) -> None:
    engine = FakeEngine(state="running", answers={INSTALL: answer})
    apk = chat_apk(tmp_path)

    with pytest.raises(AppError, match=f"Android did not install {apk}: .*{said}"):
        await apps_over(engine, tmp_path).install(str(apk))


async def test_an_app_is_opened_by_its_launcher_activity(tmp_path: Path) -> None:
    engine = FakeEngine(state="running", answers={RESOLVE: RESOLVED})

    await apps_over(engine, tmp_path).open(PACKAGE)

    assert engine.commands == [RESOLVE, START]


@pytest.mark.parametrize("package", ["notes", "com..notes", "1com.notes", "com.notes; reboot"])
async def test_a_package_name_android_would_not_have_is_refused(
    tmp_path: Path, package: str
) -> None:
    engine = FakeEngine(state="running")

    with pytest.raises(AppError, match="is not a package name, such as com.example.notes"):
        await apps_over(engine, tmp_path).open(package)

    assert engine.commands == []


@pytest.mark.parametrize(
    "answers",
    [
        {RESOLVE: CommandResult(0, "No activity found\n", "")},
        {RESOLVE: CommandResult(255, "", "Error: unknown package\n")},
        {RESOLVE: RESOLVED, START: CommandResult(0, "Error: Activity class does not exist.\n", "")},
        {RESOLVE: RESOLVED, START: CommandResult(1, "", "am: broken\n")},
    ],
)
async def test_an_app_android_cannot_open_says_so(
    tmp_path: Path, answers: dict[str, CommandResult]
) -> None:
    engine = FakeEngine(state="running", answers=answers)

    with pytest.raises(AppError, match=f"Android could not open {PACKAGE}: "):
        await apps_over(engine, tmp_path).open(PACKAGE)
