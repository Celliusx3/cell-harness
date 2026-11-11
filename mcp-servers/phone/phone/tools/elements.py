"""The elements tool: the phone's screen read as text, without a screenshot."""

from __future__ import annotations

from mcp.server import MCPServer

from phone.tools import Phone, phone_for_one_call

LIST_ELEMENTS_DESCRIPTION = (
    "List what is on the phone's screen as text: each element with words or a description, its "
    "resource id, whether it can be tapped, and its centre in the pixels of a screenshot. Read "
    "this to find words, prices, links or a target to tap; take a screenshot when you need to see "
    "the picture."
)


def register(server: MCPServer, phone: Phone) -> None:
    @server.tool(name="list_elements", description=LIST_ELEMENTS_DESCRIPTION)
    async def list_elements() -> str:
        async with phone_for_one_call(phone):
            return await phone.elements.listed()
