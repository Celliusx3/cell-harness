"""The sandbox against a real Deno.

Its own contracts only: a script runs, it cannot reach anything we did not hand
it, and it always dies. The bridge here is a plain callable — no registry, no
pipeline, no `ToolOutcome` — which is the proof that `harness/sandbox` really is
independent of the tool domain rather than merely filed separately.
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess

import pytest

from harness.sandbox import BridgeError, DenoRunner, Script

deno = pytest.mark.skipif(shutil.which("deno") is None, reason="deno is not installed")

# Reports its pid through the bridge, then never finishes — so a test can prove
# the process really died rather than assuming it.
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
    """`DenoRunner` takes both values because `CodeModeSettings` is the only place
    they are decided. Tests say the binary once, here."""
    return DenoRunner(deno_path="deno", timeout_seconds=timeout)


def alive(pid: int) -> bool:
    return subprocess.run(["ps", "-p", str(pid)], capture_output=True).returncode == 0  # noqa: S603,S607


@deno
async def test_a_script_runs_and_returns() -> None:
    """Type annotations included — the script is imported as a data: module,
    which is what strips them."""
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
    """The one inversion the sandbox owns: callers may represent failure however
    they like, and TypeScript expects a throw."""
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
    """The security argument for running model-written code at all: the bridge is
    the script's only route outward."""
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
    """Proved by pid, the same standard `test_mcp_stdio.py` holds MCP to. There is
    no SDK here to reap the child for us."""
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
    """A turn the user stopped must not leave a sandbox holding a pipe."""
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
