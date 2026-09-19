"""The subprocess seam: no shell, and we reap what we spawn."""

from __future__ import annotations

import pytest

from instagram.command import run_command


async def test_output_and_exit_code_come_back() -> None:
    result = await run_command(["/bin/echo", "hello"], 5.0)

    assert result.code == 0
    assert result.stdout.strip() == b"hello"


async def test_stderr_is_captured_as_text_for_an_error_message() -> None:
    result = await run_command(["/bin/sh", "-c", "echo boom >&2; exit 3"], 5.0)

    assert result.code == 3
    assert "boom" in result.stderr


async def test_arguments_are_never_reinterpreted_by_a_shell() -> None:
    result = await run_command(["/bin/echo", "; rm -rf /"], 5.0)

    assert result.stdout.strip() == b"; rm -rf /"


async def test_a_hung_process_is_killed_rather_than_left_behind() -> None:
    with pytest.raises(TimeoutError):
        await run_command(["/bin/sleep", "30"], 0.2)
