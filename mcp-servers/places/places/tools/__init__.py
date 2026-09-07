"""The MCP surface: two tools over one lookup client.

Unlike the Instagram server, these return **one** result rather than a list of
per-item outcomes — so a failure here is a genuine whole-call failure, which is
correct: there is no sibling result for a raise to destroy. An empty candidate
list is still a success with a `detail`, because "Google knows of no such place"
is an answer, not an error.

**Failures are raised as `ToolError`, and that specific type matters.**
`MCPServer.call_tool` passes a `ToolError`'s message through but wraps anything
else in `UnexpectedToolError` with a generic string — so a rejected API key
raised as a plain exception reaches the model as `Error executing tool
search_text`, indistinguishable from any other fault and impossible to act on.
"""

from __future__ import annotations

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from places.config import Config
from places.lookup import Circle, PlacesClient, PlacesError
from places.models import PlaceDetails, SearchResult
from places.tools.descriptions import DETAILS_DESCRIPTION, SEARCH_DESCRIPTION

DEFAULT_RADIUS_METERS = 5000.0


def register(server: MCPServer, *, config: Config, client: PlacesClient) -> MCPServer:
    @server.tool(name="search_text", description=SEARCH_DESCRIPTION)
    async def search_text(
        query: str,
        latitude: float | None = None,
        longitude: float | None = None,
        radius_meters: float | None = None,
    ) -> SearchResult:
        # Both or neither. One coordinate alone is meaningless, and silently
        # dropping it would bias nothing while looking like it had.
        near = None
        if latitude is not None and longitude is not None:
            near = Circle(
                latitude=latitude,
                longitude=longitude,
                radius_meters=radius_meters or DEFAULT_RADIUS_METERS,
            )
        try:
            return await client.search_text(query, near=near, max_results=config.max_results)
        except PlacesError as err:
            raise ToolError(str(err)) from err

    @server.tool(name="place_details", description=DETAILS_DESCRIPTION)
    async def place_details(place_id: str) -> PlaceDetails:
        try:
            return await client.place_details(place_id)
        except PlacesError as err:
            raise ToolError(str(err)) from err

    return server
