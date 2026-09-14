"""A server with a scripted provider, and one call through a real MCP client."""

from __future__ import annotations

from pathlib import Path

from mcp import Client

from tests.conftest import asr_reply, chat_reply, recording_runner, scripted, server_with

VISION = chat_reply(
    "ON-SCREEN TEXT:\nBEST NASI LEMAK\n@warung.mak.cik\n\nSCENE:\nA roadside stall in Bangsar."
)
SPOKEN = asr_reply("The best nasi lemak in Bangsar, on Telawi.")


def server_for(work_dir: Path, **overrides):
    runner, _ = recording_runner(touch="x")
    handler = scripted({"/chat/completions": VISION, "/audio/transcriptions": SPOKEN})
    return server_with(work_dir, handler, runner, **overrides)


async def call(server, tool: str, args: dict):
    async with Client(server) as client:
        return await client.call_tool(tool, args)
