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
    monkeypatch.setenv("HARNESS_LLM__API_KEY", "k")
    monkeypatch.setenv("HARNESS_LLM__MODEL", "m")
    # Session storage is redirected for the whole suite — see tests/conftest.py.


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


async def test_run_reports_the_session_id_on_stderr(monkeypatch, capsys) -> None:
    """It is the id `resume` needs, so it must be visible — but on stderr, so a
    piped answer stays clean."""
    with_script(monkeypatch, completed("hi"))

    await cli._run("hello")

    assert "session " in capsys.readouterr().err


async def test_list_shows_stored_conversations_newest_first(monkeypatch, capsys) -> None:
    with_script(monkeypatch, completed("one"))
    await cli._run("first question")
    with_script(monkeypatch, completed("two"))
    await cli._run("second question")
    capsys.readouterr()

    await cli._list()

    rows = capsys.readouterr().out.strip().splitlines()
    assert len(rows) == 2
    assert "second question" in rows[0]
    assert "first question" in rows[1]


async def test_resume_continues_a_stored_conversation(monkeypatch, capsys) -> None:
    client = with_script(monkeypatch, completed("blue"))
    await cli._run("what colour is the sky?")
    session_id = capsys.readouterr().err.split("session ")[1].strip()

    client._script = completed("I said blue")
    code = await cli._resume(session_id, "what did you just say?")

    assert code == 0
    # The resumed turn saw the whole prior exchange, derived from the log.
    assert [(m.role, m.content) for m in client.seen][1:] == [
        ("user", "what colour is the sky?"),
        ("assistant", "blue"),
        ("user", "what did you just say?"),
    ]


async def test_resuming_an_unknown_session_reports_and_exits_nonzero(monkeypatch, capsys) -> None:
    with_script(monkeypatch, completed("x"))

    code = await cli._resume("no-such-session", "hi")

    assert code == 1
    assert "no stored session" in capsys.readouterr().err


async def test_a_finished_turn_is_durable_without_another_request(monkeypatch, capsys) -> None:
    """The loop checkpoints before work, so the final answer needs the flush in
    `_drive`'s `finally` or it would sit unwritten."""
    with_script(monkeypatch, completed("the answer"))
    await cli._run("a question")
    session_id = capsys.readouterr().err.split("session ")[1].strip()

    session = await cli.build_store(cli.Settings()).resume(session_id)

    from harness.session.derive import derive_messages

    assert [m.content for m in derive_messages(session.events())] == ["a question", "the answer"]


async def test_the_suite_never_writes_to_the_real_sessions_directory(monkeypatch) -> None:
    """A regression test for a bug that shipped: an earlier version of the CLI
    fixture set the pre-`config.json` variable name, the override silently
    missed, and a test run left real conversation files in a developer's home.
    """
    from harness.config.settings import Settings

    root = str(Settings().sessions.root)

    assert ".harness/sessions" not in root, f"tests would write to {root}"
