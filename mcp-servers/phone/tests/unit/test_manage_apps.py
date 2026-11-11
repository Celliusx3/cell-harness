"""Opening links, listing apps, naming the open one, and closing, removing or clearing an app."""

from __future__ import annotations

from pathlib import Path

import pytest

from phone.models.command import CommandResult
from phone.services.apps import ACTIVITIES, PERSONS_SCREEN, AppError, Apps
from tests.fakes import NAME, FakeEngine

PACKAGE = "com.xunmeng.pinduoduo"
VIEW = "am start -W -a android.intent.action.VIEW -d "
SUCCESS = CommandResult(0, "Success\n", "")


def apps_over(engine: FakeEngine, files: Path) -> Apps:
    return Apps(engine=engine, name=NAME, files_dir=files)


@pytest.mark.parametrize(
    ("url", "command"),
    [
        ("http://example.com", f"{VIEW}'http://example.com'"),
        ("https://x.com/a?b=c&d='e'", f"{VIEW}'https://x.com/a?b=c&d='\\''e'\\'''"),
    ],
)
async def test_a_web_link_is_a_view_intent_quoted_for_sh(
    tmp_path: Path, url: str, command: str
) -> None:
    engine = FakeEngine(state="running")

    await apps_over(engine, tmp_path).open_url(url)

    assert engine.commands == [command]


@pytest.mark.parametrize(
    "url", ["file:///data/x", "intent://x", "javascript:alert(1)", "https://", "example.com"]
)
async def test_a_link_that_is_not_http_or_https_with_a_host_is_refused(
    tmp_path: Path, url: str
) -> None:
    engine = FakeEngine(state="running")

    with pytest.raises(AppError, match="only http and https"):
        await apps_over(engine, tmp_path).open_url(url)

    assert engine.commands == []


@pytest.mark.parametrize(
    "answer", [CommandResult(1, "", "am: broken\n"), CommandResult(0, "Error: no activity\n", "")]
)
async def test_a_link_android_cannot_open_says_so(tmp_path: Path, answer: CommandResult) -> None:
    engine = FakeEngine(state="running", answers={f"{VIEW}'https://x.com'": answer})

    with pytest.raises(AppError, match="Android could not open https://x.com: "):
        await apps_over(engine, tmp_path).open_url("https://x.com")


async def test_the_listed_apps_are_sorted_and_leave_out_the_persons_screen(
    tmp_path: Path,
) -> None:
    engine = FakeEngine(state="running", packages=frozenset({PACKAGE, PERSONS_SCREEN, "a.b"}))

    assert await apps_over(engine, tmp_path).listed() == ("a.b", PACKAGE)


@pytest.mark.parametrize(
    "activities",
    [
        f"  topResumedActivity=ActivityRecord{{1a u0 {PACKAGE}/.Main t1}}\n"
        "  mResumedActivity=ActivityRecord{2b u0 org.other/.Main t2}\n",
        f"  mResumedActivity=ActivityRecord{{2b u0 {PACKAGE}/.Main t2}}\n",
    ],
)
async def test_the_foreground_app_is_the_top_resumed_activitys_package(
    tmp_path: Path, activities: str
) -> None:
    engine = FakeEngine(state="running", answers={ACTIVITIES: CommandResult(0, activities, "")})

    assert await apps_over(engine, tmp_path).foreground() == PACKAGE


@pytest.mark.parametrize(
    ("answer", "said"),
    [
        (CommandResult(0, "ACTIVITY MANAGER ACTIVITIES\n", ""), "no app is open"),
        (CommandResult(1, "", "dumpsys: broken\n"), "which app is open failed: dumpsys: broken"),
    ],
)
async def test_no_foreground_app_says_so(tmp_path: Path, answer: CommandResult, said: str) -> None:
    engine = FakeEngine(state="running", answers={ACTIVITIES: answer})

    with pytest.raises(AppError, match=said):
        await apps_over(engine, tmp_path).foreground()


async def test_a_terminated_app_is_force_stopped(tmp_path: Path) -> None:
    engine = FakeEngine(state="running")

    await apps_over(engine, tmp_path).terminate(PACKAGE)

    assert engine.commands == [f"am force-stop {PACKAGE}"]


async def test_an_app_android_cannot_close_says_so(tmp_path: Path) -> None:
    engine = FakeEngine(
        state="running", answers={f"am force-stop {PACKAGE}": CommandResult(1, "", "")}
    )

    with pytest.raises(AppError, match=f"Android could not close {PACKAGE}: exit 1"):
        await apps_over(engine, tmp_path).terminate(PACKAGE)


async def test_an_app_is_uninstalled_and_cleared_through_pm(tmp_path: Path) -> None:
    engine = FakeEngine(
        state="running",
        answers={f"pm uninstall {PACKAGE}": SUCCESS, f"pm clear {PACKAGE}": SUCCESS},
    )
    apps = apps_over(engine, tmp_path)

    await apps.clear_data(PACKAGE)
    await apps.uninstall(PACKAGE)

    assert engine.commands == [f"pm clear {PACKAGE}", f"pm uninstall {PACKAGE}"]


@pytest.mark.parametrize(
    ("command", "said"),
    [(f"pm uninstall {PACKAGE}", f"remove {PACKAGE}"), (f"pm clear {PACKAGE}", "clear")],
)
async def test_a_removal_or_clear_without_success_fails_in_androids_words(
    tmp_path: Path, command: str, said: str
) -> None:
    answer = CommandResult(0, "Failure [DELETE_FAILED_INTERNAL_ERROR]\n", "")
    engine = FakeEngine(state="running", answers={command: answer})
    apps = apps_over(engine, tmp_path)
    act = apps.uninstall if command.startswith("pm uninstall") else apps.clear_data

    with pytest.raises(AppError, match=f"Android could not {said}.*DELETE_FAILED"):
        await act(PACKAGE)


@pytest.mark.parametrize("act", ["uninstall", "clear_data"])
async def test_the_persons_screen_app_is_refused_without_running_anything(
    tmp_path: Path, act: str
) -> None:
    engine = FakeEngine(state="running")

    with pytest.raises(AppError, match="the person's view of the phone"):
        await getattr(apps_over(engine, tmp_path), act)(PERSONS_SCREEN)

    assert engine.commands == []


@pytest.mark.parametrize("act", ["terminate", "uninstall", "clear_data"])
async def test_a_package_name_android_would_not_have_is_refused(tmp_path: Path, act: str) -> None:
    engine = FakeEngine(state="running")

    with pytest.raises(AppError, match="is not a package name"):
        await getattr(apps_over(engine, tmp_path), act)("x; reboot")

    assert engine.commands == []
