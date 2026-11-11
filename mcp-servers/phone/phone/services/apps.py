"""The phone's apps: installed from an APK in the chat's files, opened, listed and managed."""

from __future__ import annotations

import base64
import re
from pathlib import Path
from urllib.parse import urlsplit

from phone.engine import Engine
from phone.models.command import COMMAND_TIMEOUT_SECONDS, CommandResult
from phone.models.phone import android, sh_quoted

INSTALL_TIMEOUT_SECONDS = 180.0
PACKAGE_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+")
PACKAGE_PREFIX = "package:"
LIST_PACKAGES = "pm list packages -3"
SUCCEEDED = "Success"
LAUNCHER = "android.intent.category.LAUNCHER"
START_FAILED = "Error"
WEB_SCHEMES = frozenset({"http", "https"})
PERSONS_SCREEN = "net.christianbeier.droidvnc_ng"
ACTIVITIES = "dumpsys activity activities"
RESUMED_KEYS = ("topResumedActivity", "mResumedActivity")
RESUMED_ACTIVITY = r"{key}=ActivityRecord\{{\S+ \S+ ([A-Za-z0-9_.]+)/"


class AppError(RuntimeError):
    """An app could not be installed or opened. The message says why, in plain words."""


def chat_file(files_dir: Path, path: str) -> Path:
    """`path` resolved, or a refusal unless it is a file inside the chat's files."""
    resolved = Path(path).resolve()
    if not resolved.is_file() or not resolved.is_relative_to(files_dir.resolve()):
        raise AppError(f"{path} is not one of this chat's files")
    return resolved


def package_name(package: str) -> str:
    """`package`, or a refusal unless it reads as an Android package name."""
    if not PACKAGE_PATTERN.fullmatch(package):
        raise AppError(f"{package!r} is not a package name, such as com.example.notes")
    return package


def web_link(url: str) -> str:
    """`url`, or a refusal unless it is an http or https link with a host."""
    parts = urlsplit(url)
    if parts.scheme not in WEB_SCHEMES or not parts.hostname:
        raise AppError(f"{url!r} is not a web link: the phone opens only http and https links")
    return url


def removable(package: str) -> str:
    """`package`, or a refusal when it is the app that gives the person their view of the phone."""
    if package_name(package) == PERSONS_SCREEN:
        raise AppError(
            f"{package} is the person's view of the phone, so it cannot be removed or cleared"
        )
    return package


def resumed_package(activities: str) -> str | None:
    """The package of the activity `dumpsys activity activities` says is on screen, if any."""
    for key in RESUMED_KEYS:
        found = re.search(RESUMED_ACTIVITY.format(key=key), activities)
        if found:
            return found.group(1)
    return None


def words_of(completed: CommandResult) -> str:
    """What Android said, or its exit code when it said nothing."""
    said = f"{completed.stdout.strip()} {completed.stderr.strip()}".strip()
    return said or f"exit {completed.returncode}"


def packages_in(completed: CommandResult) -> frozenset[str]:
    """The package names `pm list packages` printed, one `package:<name>` per line."""
    if completed.returncode != 0:
        raise AppError(f"Listing the phone's apps failed: {words_of(completed)}")
    lines = (line.strip() for line in completed.stdout.splitlines())
    return frozenset(
        line.removeprefix(PACKAGE_PREFIX) for line in lines if line.startswith(PACKAGE_PREFIX)
    )


class Apps:
    """The apps on the phone, worked through Android's package manager."""

    def __init__(self, *, engine: Engine, name: str, files_dir: Path) -> None:
        self._engine = engine
        self._name = name
        self._files_dir = files_dir

    async def install(self, path: str) -> tuple[str, ...]:
        """The packages the APK at `path` added; none when it replaced an app already there."""
        apk = chat_file(self._files_dir, path).read_bytes()
        before = await self._packages()
        completed = await self._engine.run(
            self._name,
            android(f"base64 -d | pm install -S {len(apk)}"),
            stdin=base64.b64encode(apk).decode(),
            timeout_seconds=INSTALL_TIMEOUT_SECONDS,
        )
        if completed.returncode != 0 or SUCCEEDED not in completed.stdout:
            raise AppError(f"Android did not install {path}: {words_of(completed)}")
        return tuple(sorted(await self._packages() - before))

    async def open(self, package: str) -> None:
        """Start the app's launcher activity and wait until Android says it is on screen."""
        activity = await self._launcher_activity(package_name(package))
        started = await self._run(f"am start -W -n {activity}")
        if started.returncode != 0 or START_FAILED in started.stdout:
            raise AppError(f"Android could not open {package}: {words_of(started)}")

    async def open_url(self, url: str) -> None:
        """Hand the link to Android, which opens it in the app that handles it."""
        command = f"am start -W -a android.intent.action.VIEW -d {sh_quoted(web_link(url))}"
        opened = await self._run(command)
        if opened.returncode != 0 or START_FAILED in opened.stdout:
            raise AppError(f"Android could not open {url}: {words_of(opened)}")

    async def listed(self) -> tuple[str, ...]:
        """The apps installed from APK files, sorted, without the person's screen app."""
        return tuple(sorted(await self._packages() - {PERSONS_SCREEN}))

    async def foreground(self) -> str:
        """The package of the app on screen now."""
        completed = await self._run(ACTIVITIES)
        if completed.returncode != 0:
            raise AppError(f"Asking Android which app is open failed: {words_of(completed)}")
        package = resumed_package(completed.stdout)
        if package is None:
            raise AppError("Android says no app is open on the phone's screen")
        return package

    async def terminate(self, package: str) -> None:
        """Force-stop the app; its data stays."""
        stopped = await self._run(f"am force-stop {package_name(package)}")
        if stopped.returncode != 0:
            raise AppError(f"Android could not close {package}: {words_of(stopped)}")

    async def uninstall(self, package: str) -> None:
        await self._succeed(f"pm uninstall {removable(package)}", f"remove {package}")

    async def clear_data(self, package: str) -> None:
        await self._succeed(f"pm clear {removable(package)}", f"clear {package}'s data")

    async def _succeed(self, command: str, action: str) -> None:
        completed = await self._run(command)
        if completed.returncode != 0 or SUCCEEDED not in completed.stdout:
            raise AppError(f"Android could not {action}: {words_of(completed)}")

    async def _launcher_activity(self, package: str) -> str:
        resolved = await self._run(f"cmd package resolve-activity --brief -c {LAUNCHER} {package}")
        lines = resolved.stdout.strip().splitlines()
        activity = lines[-1].strip() if lines else ""
        if resolved.returncode != 0 or not activity.startswith(f"{package}/"):
            raise AppError(
                f"Android could not open {package}: it is not installed, or has no screen "
                f"to open ({words_of(resolved)})"
            )
        return activity

    async def _packages(self) -> frozenset[str]:
        return packages_in(await self._run(LIST_PACKAGES))

    async def _run(self, command: str) -> CommandResult:
        return await self._engine.run(
            self._name, android(command), stdin=None, timeout_seconds=COMMAND_TIMEOUT_SECONDS
        )
