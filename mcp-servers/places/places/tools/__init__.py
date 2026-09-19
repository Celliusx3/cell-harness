"""The MCP surface: two tools over one lookup client."""

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
