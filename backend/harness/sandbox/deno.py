"""A `Runner` backed by a Deno subprocess."""

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

CLOSE_TIMEOUT_SECONDS = 5.0

MAX_FRAME_BYTES = 4 * 1024 * 1024

_SHIM = (resources.files("harness.sandbox") / "js" / "shim.ts").read_text()


class DenoUnavailableError(RuntimeError):
    """The configured Deno binary could not be started."""


@dataclass(frozen=True)
class DenoRunner(Runner):
    """Spawns one sandboxed Deno per script."""

    deno_path: str
    timeout_seconds: float
    _entry_data_url: str = field(
        default_factory=lambda: "data:text/typescript," + urllib.parse.quote(_SHIM),
        repr=False,
    )

    async def run(self, code: str, *, names: Sequence[str], bridge: Bridge) -> Script:
        try:
            process = await asyncio.create_subprocess_exec(
                self.deno_path,
                "run",
                "--no-prompt",
                self._entry_data_url,
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
                        return await self._unanswered(process, frame["name"])
                case "done":
                    return Script(result=frame.get("result"), logs=tuple(frame.get("logs", ())))
                case "failed":
                    return Script(
                        logs=tuple(frame.get("logs", ())),
                        error=frame.get("message", "the script failed"),
                    )

    async def _unanswered(self, process: asyncio.subprocess.Process, name: str) -> Script:
        """Why the child exited mid-call, from what it wrote before it went."""
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
                        "must be awaited all the way up to the script's own return: end the "
                        "body with `return await main();`, or write the steps at the top level"
                    ),
                )
        return Script(error=await self._died(process))

    async def _send(self, process: asyncio.subprocess.Process, frame: dict) -> None:
        assert process.stdin is not None
        process.stdin.write(json.dumps(frame).encode() + b"\n")
        await process.stdin.drain()

    async def _died(self, process: asyncio.subprocess.Process) -> str:
        """Why the child stopped talking."""
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
        except Exception:
            logger.warning("deno pid %s: error while closing", process.pid, exc_info=True)


async def _reply(frame: dict, bridge: Bridge) -> dict:
    """One call's answer."""
    call_id = frame["id"]
    try:
        value = await bridge(frame["name"], frame.get("args") or {})
    except BridgeError as err:
        return {"kind": "result", "id": call_id, "ok": False, "error": str(err)}
    return {"kind": "result", "id": call_id, "ok": True, "value": value}
