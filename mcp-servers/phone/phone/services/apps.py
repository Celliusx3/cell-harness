"""The phone's apps: installed from an APK in the chat's files, and opened by package name."""

from __future__ import annotations

import base64
import re
from pathlib import Path

from phone.engine import Engine
from phone.models.command import COMMAND_TIMEOUT_SECONDS, CommandResult
from phone.models.phone import android

INSTALL_TIMEOUT_SECONDS = 180.0
PACKAGE_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+")
PACKAGE_PREFIX = "package:"
LIST_PACKAGES = "pm list packages -3"
INSTALLED = "Success"
LAUNCHER = "android.intent.category.LAUNCHER"
START_FAILED = "Error"


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
        if completed.returncode != 0 or INSTALLED not in completed.stdout:
            raise AppError(f"Android did not install {path}: {words_of(completed)}")
        return tuple(sorted(await self._packages() - before))

    async def open(self, package: str) -> None:
        """Start the app's launcher activity and wait until Android says it is on screen."""
        activity = await self._launcher_activity(package_name(package))
        started = await self._run(f"am start -W -n {activity}")
        if started.returncode != 0 or START_FAILED in started.stdout:
            raise AppError(f"Android could not open {package}: {words_of(started)}")

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
