"""A `Runner` backed by a Deno subprocess.

One process per execution, granted nothing: no `--allow-*` flags, so the bridge
is the script's only route outward. Proved rather than asserted in
`tests/integration/test_sandbox.py`.

No command loop here. `mcp/connection.py` needs one because the MCP SDK is an anyio
context manager bound to its entering task; `create_subprocess_exec` is not.
"""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.parse
from collections.abc import Sequence
from dataclasses import dataclass, field
from importlib import resources

from harness.sandbox.runner import Bridge, BridgeError, Runner, Script

logger = logging.getLogger("harness.sandbox")

# Past this the child is logged and abandoned rather than awaited forever, the
# same trade `mcp/connection.py` makes.
CLOSE_TIMEOUT_SECONDS = 5.0

# A backstop against a script that returns a whole transcript — the case code
# mode exists to prevent — not a normal limit.
MAX_FRAME_BYTES = 4 * 1024 * 1024

# Through the package rather than `__file__`, which breaks under zip import.
_SHIM = (resources.files("harness.sandbox") / "js" / "shim.ts").read_text()


class DenoUnavailableError(RuntimeError):
    """The configured Deno binary could not be started."""


@dataclass(frozen=True)
class DenoRunner(Runner):
    """Spawns one sandboxed Deno per script."""

    # No defaults: `CodeModeSettings` already decides both, and a second copy
    # here is a value that goes stale the first time config.json changes.
    deno_path: str
    timeout_seconds: float
    # On the command line rather than on disk, so the child needs no read
    # permission to load its own entry point.
    _entry: str = field(
        default_factory=lambda: "data:text/typescript," + urllib.parse.quote(_SHIM),
        repr=False,
    )

    async def run(self, code: str, *, names: Sequence[str], bridge: Bridge) -> Script:
        try:
            process = await asyncio.create_subprocess_exec(
                self.deno_path,
                "run",
                "--no-prompt",
                self._entry,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=MAX_FRAME_BYTES,
            )
        except OSError as err:
            raise DenoUnavailableError(f"could not start {self.deno_path!r}: {err}") from err

        try:
            async with asyncio.timeout(self.timeout_seconds):
                return await self._converse(process, code, names, bridge)
        except TimeoutError:
            return Script(error=f"the script did not finish within {self.timeout_seconds:.0f}s")
        finally:
            # Every path, cancellation included. There is no SDK here to reap the
            # child the way MCP's transport does.
            await self._reap(process)

    async def _converse(
        self,
        process: asyncio.subprocess.Process,
        code: str,
        names: Sequence[str],
        bridge: Bridge,
    ) -> Script:
        assert process.stdin is not None and process.stdout is not None
        await self._send(process, {"kind": "run", "code": code, "names": list(names)})

        while True:
            try:
                line = await process.stdout.readline()
            except (ValueError, asyncio.LimitOverrunError):
                return Script(error="the script produced more output than one frame may carry")
            if not line:
                return Script(error=await self._died(process))

            frame = json.loads(line)
            match frame.get("kind"):
                case "call":
                    reply = await _reply(frame, bridge)
                    try:
                        await self._send(process, reply)
                    except (RuntimeError, OSError):
                        # The child is gone. Observed live: a script that
                        # called `main();` without `await` returned at once,
                        # the shim sent `done` and exited, and the reply to the
                        # call `main` had in flight met a closed pipe. What is
                        # left on stdout says which; the message names the
                        # mistake, because "handler is closed" told the model
                        # nothing and it gave up.
                        return await self._unanswered(process, frame["name"])
                case "done":
                    return Script(result=frame.get("result"), logs=tuple(frame.get("logs", ())))
                case "failed":
                    return Script(
                        logs=tuple(frame.get("logs", ())),
                        error=frame.get("message", "the script failed"),
                    )

    async def _unanswered(self, process: asyncio.subprocess.Process, name: str) -> Script:
        """The child exited while a call was being answered — why, from what it
        wrote before it went."""
        assert process.stdout is not None
        rest = (await process.stdout.read()).decode(errors="replace")
        for line in rest.splitlines():
            try:
                frame = json.loads(line)
            except ValueError:
                continue
            if frame.get("kind") in ("done", "failed"):
                return Script(
                    logs=tuple(frame.get("logs", ())),
                    error=(
                        f"the script returned while {name} was still running — every call "
                        "must be awaited all the way up to the script's own return"
                    ),
                )
        return Script(error=await self._died(process))

    async def _send(self, process: asyncio.subprocess.Process, frame: dict) -> None:
        assert process.stdin is not None
        process.stdin.write(json.dumps(frame).encode() + b"\n")
        await process.stdin.drain()

    async def _died(self, process: asyncio.subprocess.Process) -> str:
        """Why the child stopped talking. Deno's diagnostics go to stderr, and
        without them the caller is told only that something went wrong."""
        assert process.stderr is not None
        detail = (await process.stderr.read()).decode(errors="replace").strip()
        if detail:
            return f"the sandbox exited without a result: {detail}"
        return "the sandbox exited without a result"

    async def _reap(self, process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return
        process.kill()
        try:
            await asyncio.wait_for(asyncio.shield(process.wait()), CLOSE_TIMEOUT_SECONDS)
        except TimeoutError:
            logger.error(
                "deno pid %s did not exit within %.0fs", process.pid, CLOSE_TIMEOUT_SECONDS
            )
        except BaseException:  # noqa: BLE001 - teardown must not raise over the real result
            logger.warning("deno pid %s: error while closing", process.pid, exc_info=True)


async def _reply(frame: dict, bridge: Bridge) -> dict:
    """One call's answer. A `BridgeError` becomes a throw inside the script;
    anything else the bridge raises is a bug in the caller, not the script, so it
    propagates and fails the run.

    This loop answers one call before reading the next frame, so the shim can have
    several calls outstanding inside the script but never two here.
    """
    call_id = frame["id"]
    try:
        value = await bridge(frame["name"], frame.get("args") or {})
    except BridgeError as err:
        return {"kind": "result", "id": call_id, "ok": False, "error": str(err)}
    return {"kind": "result", "id": call_id, "ok": True, "value": value}
