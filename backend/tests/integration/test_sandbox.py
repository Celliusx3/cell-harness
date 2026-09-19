"""The sandbox against a real Deno."""

from __future__ import annotations

import asyncio
import shutil
import subprocess

import pytest

from harness.sandbox import BridgeError, DenoRunner, Script

deno = pytest.mark.skipif(shutil.which("deno") is None, reason="deno is not installed")

HANG = (
    "await report({ pid: Deno.pid });\n"
    "while (true) { await new Promise((r) => setTimeout(r, 20)); }"
)


async def echo(name: str, args: dict) -> object:
    if name == "boom":
        raise BridgeError("it exploded")
    if name == "rows":
        return {"rows": [{"n": 1}, {"n": 2}, {"n": 3}]}
    return f"{name} got {sorted(args)}"


def runner(timeout: float) -> DenoRunner:
    """A `DenoRunner` with the given timeout."""
    return DenoRunner(deno_path="deno", timeout_seconds=timeout)


def alive(pid: int) -> bool:
    return subprocess.run(["ps", "-p", str(pid)], capture_output=True).returncode == 0


@deno
async def test_a_script_runs_and_returns() -> None:
    result = await runner(30).run("const n: number = 41; return n + 1;", names=[], bridge=echo)

    assert result == Script(result=42)


@deno
async def test_a_bridge_value_arrives_as_an_object() -> None:
    result = await runner(30).run(
        "const r = await rows({}); console.log('saw', r.rows.length); return r.rows.length;",
        names=["rows"],
        bridge=echo,
    )

    assert result.result == 3
    assert result.logs == ("saw 3",)


@deno
async def test_a_bridge_error_is_catchable_in_the_script() -> None:
    result = await runner(30).run(
        "try { await boom({}); return 'no'; }\ncatch (e) { return 'caught: ' + e.message; }",
        names=["boom"],
        bridge=echo,
    )

    assert result.result == "caught: it exploded"


@deno
async def test_a_script_that_throws_is_reported_not_raised() -> None:
    result = await runner(30).run("throw new Error('nope');", names=[], bridge=echo)

    assert result.error == "nope"
    assert result.result is None


@deno
async def test_the_sandbox_cannot_reach_the_network() -> None:
    result = await runner(30).run(
        "try { await fetch('https://example.com'); return 'REACHED'; } catch { return 'blocked'; }",
        names=[],
        bridge=echo,
    )

    assert result.result == "blocked"


@deno
async def test_the_sandbox_cannot_read_the_filesystem() -> None:
    result = await runner(30).run(
        "try { Deno.readTextFileSync('/etc/hosts'); return 'READ'; } catch { return 'blocked'; }",
        names=[],
        bridge=echo,
    )

    assert result.result == "blocked"


@deno
async def test_a_runaway_script_is_killed_and_the_process_is_gone() -> None:
    seen: list[int] = []

    async def report(name: str, args: dict) -> object:
        seen.append(int(args["pid"]))
        return "noted"

    result = await runner(2).run(HANG, names=["report"], bridge=report)

    assert result.error is not None
    assert "did not finish" in result.error
    for _ in range(50):
        if not alive(seen[0]):
            return
        await asyncio.sleep(0.1)
    raise AssertionError(f"deno pid {seen[0]} survived the timeout")


@deno
async def test_cancelling_the_caller_kills_the_process() -> None:
    seen: list[int] = []
    started = asyncio.Event()

    async def report(name: str, args: dict) -> object:
        seen.append(int(args["pid"]))
        started.set()
        return "noted"

    task = asyncio.create_task(runner(60).run(HANG, names=["report"], bridge=report))
    await asyncio.wait_for(started.wait(), 30)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    for _ in range(50):
        if not alive(seen[0]):
            return
        await asyncio.sleep(0.1)
    raise AssertionError(f"deno pid {seen[0]} survived cancellation")


@deno
async def test_a_script_that_returns_with_a_call_in_flight_is_told_so() -> None:

    async def slow(name: str, args: dict) -> object:
        await asyncio.sleep(0.3)
        return "late"

    script = await runner(5).run(
        'async function main() { console.log("in"); await tool({}); console.log("never"); }\n'
        "main();\nreturn 1;",
        names=["tool"],
        bridge=slow,
    )

    assert script.error is not None
    assert "tool was still running" in script.error
    assert "return await main();" in script.error
    assert script.logs == ("in",)
