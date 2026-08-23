"""The `run` command — the phase's demo path.

Worth testing despite being a thin driver: the exit code is the contract a script
or CI step depends on, and "printed an error but exited 0" is exactly the failure
a human demo would not notice.
"""

from __future__ import annotations

import pytest

from harness import cli
from harness.llm.stream import Failed, TextChunk
from tests.unit.fakes import (
    ScriptedClient,
    SteppedClient,
    calls_tool,
    completed,
    echo_tool,
    reporting_tool,
)


@pytest.fixture(autouse=True)
def env(monkeypatch) -> None:
    monkeypatch.setenv("HARNESS_LLM_API_KEY", "k")
    monkeypatch.setenv("HARNESS_LLM_MODEL", "m")


def with_script(monkeypatch, script) -> ScriptedClient:
    client = ScriptedClient(script)
    monkeypatch.setattr(cli, "OpenAIClient", lambda settings: client)
    return client


async def test_prints_the_reply_and_exits_zero(monkeypatch, capsys) -> None:
    with_script(monkeypatch, completed("hello there"))

    code = await cli._run("hi")

    assert code == 0
    assert capsys.readouterr().out == "hello there\n"


async def test_failure_goes_to_stderr_and_exits_nonzero(monkeypatch, capsys) -> None:
    with_script(monkeypatch, [TextChunk(text="par"), Failed(reason="502 upstream")])

    code = await cli._run("hi")

    assert code == 1
    captured = capsys.readouterr()
    # The streamed prefix still reached the user; the reason went to stderr in
    # full, untruncated.
    assert captured.out == "par"
    assert "502 upstream" in captured.err


async def test_a_stream_with_no_terminal_is_reported_not_silently_ok(monkeypatch, capsys) -> None:
    """Unreachable while the loop keeps its contract — which is why a silent 0
    here would hide a broken one."""
    with_script(monkeypatch, [TextChunk(text="half")])

    code = await cli._run("hi")

    assert code == 1
    assert "half" in capsys.readouterr().out


async def test_tool_activity_goes_to_stderr_so_stdout_is_the_answer(monkeypatch, capsys) -> None:
    """Piping stdout should give the reply alone — the tool trace is for a human
    watching, not for whatever consumes the output."""
    client = SteppedClient(
        calls_tool("echo", '{"value": "42"}', text="Checking. "),
        completed("It is 42."),
    )
    monkeypatch.setattr(cli, "OpenAIClient", lambda settings: client)
    monkeypatch.setattr(cli, "clock_tool", echo_tool)

    code = await cli._run("what is it?")

    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "Checking. It is 42.\n"
    assert "→ echo" in captured.err
    assert "← 42" in captured.err


async def test_progress_is_rendered_with_and_without_a_percentage(monkeypatch, capsys) -> None:
    client = SteppedClient(calls_tool("slow", '{"value": "done"}'), completed("ok"))
    monkeypatch.setattr(cli, "OpenAIClient", lambda settings: client)
    monkeypatch.setattr(
        cli, "clock_tool", lambda: reporting_tool([(40.0, "working"), (None, "almost")])
    )

    await cli._run("q")

    err = capsys.readouterr().err
    assert "… 40% working" in err
    assert "… almost" in err


def test_run_requires_a_prompt(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["harness", "run"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code != 0


def test_a_command_is_required(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["harness"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code != 0
