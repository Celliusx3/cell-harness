"""The tools through a real MCP client, in-process.

The first test is the reason this server exists: the third-party server it
replaces declares no `outputSchema`, so it cannot populate `structuredContent`
and a code-mode script reading its result gets `undefined`.
"""

from __future__ import annotations

import pytest
from mcp import Client

from tests.conftest import capturing, place, search_reply, server_with


async def call(server, tool: str, args: dict):
    async with Client(server) as client:
        return await client.call_tool(tool, args)


async def test_both_tools_declare_an_output_schema() -> None:
    """The precondition for `structuredContent`, and the thing the server this
    replaces does not do."""
    handler, _ = capturing(search_reply(place()))

    async with Client(server_with(handler)) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}

    assert set(tools) == {"search_text", "place_details"}
    assert tools["search_text"].output_schema is not None
    assert tools["place_details"].output_schema is not None


async def test_a_search_arrives_as_structured_content_a_script_can_index() -> None:
    handler, _ = capturing(search_reply(place(), place("ChIJdef", "Nasi Lemak Tanglin")))

    result = await call(server_with(handler), "search_text", {"query": "Natalina Kuala Lumpur"})

    assert result.structured_content is not None
    candidates = result.structured_content["candidates"]
    assert [c["name"] for c in candidates] == ["Natalina Italian Kitchen", "Nasi Lemak Tanglin"]
    assert candidates[0]["place_id"] == "ChIJabc"


async def test_several_candidates_come_back_so_the_model_can_show_them() -> None:
    """The "say so, show candidates" behaviour depends on getting more than one."""
    handler, seen = capturing(search_reply(place(), place("b", "B"), place("c", "C")))

    result = await call(server_with(handler), "search_text", {"query": "cafe Bangsar"})

    assert len(result.structured_content["candidates"]) == 3
    body = seen[0].read().decode()
    assert '"maxResultCount":3' in body.replace(" ", "")


async def test_coordinates_bias_the_search_only_when_both_are_given() -> None:
    """One coordinate alone is meaningless; silently dropping it would bias
    nothing while appearing to have biased something."""
    handler, seen = capturing(search_reply(place()))
    server = server_with(handler)

    await call(server, "search_text", {"query": "x", "latitude": 3.1})
    assert "locationBias" not in seen[-1].read().decode()

    await call(server, "search_text", {"query": "x", "latitude": 3.1, "longitude": 101.7})
    assert "locationBias" in seen[-1].read().decode()


async def test_a_default_radius_applies_when_coordinates_have_none() -> None:
    handler, seen = capturing(search_reply(place()))

    await call(
        server_with(handler),
        "search_text",
        {"query": "x", "latitude": 3.1, "longitude": 101.7},
    )

    body = seen[0].read().decode()
    assert "5000" in body


async def test_no_matches_returns_advice_rather_than_failing_the_call() -> None:
    handler, _ = capturing(search_reply())

    result = await call(
        server_with(handler), "search_text", {"query": "blue awning banana leaf stall"}
    )

    assert result.structured_content["candidates"] == []
    assert "descriptive queries" in result.structured_content["detail"]
    # An answer, not an error — `is_error` would reach the script as a throw.
    assert not result.is_error


async def test_details_round_trips_as_structured_content() -> None:
    payload = place() | {
        "regularOpeningHours": {"openNow": False, "weekdayDescriptions": ["Monday: Closed"]},
        "nationalPhoneNumber": "03-1234 5678",
    }
    import httpx

    handler, _ = capturing(httpx.Response(200, json=payload))

    result = await call(server_with(handler), "place_details", {"place_id": "ChIJabc"})

    data = result.structured_content
    assert data["opening_hours"]["open_now"] is False
    assert data["phone"] == "03-1234 5678"
    assert "query_place_id=ChIJabc" in data["maps_url"]


async def test_a_rejected_key_reaches_the_model_as_an_error_it_can_report() -> None:
    """Unlike the Instagram server, a failure here is a genuine whole-call
    failure: there is one result, so there are no siblings for a raise to destroy."""
    import httpx

    handler, _ = capturing(httpx.Response(403, text="API key not valid"))

    result = await call(server_with(handler), "search_text", {"query": "x"})

    assert result.is_error
    text = "".join(getattr(block, "text", "") for block in result.content)
    assert "Places API (New) is enabled" in text


@pytest.mark.parametrize("count", [1, 5])
async def test_the_candidate_count_is_operator_config_not_a_model_argument(
    count: int,
) -> None:
    """A knob the model can get wrong for no gain — and one that changes cost."""
    handler, seen = capturing(search_reply(place()))

    await call(server_with(handler, max_results=count), "search_text", {"query": "x"})

    assert f'"maxResultCount":{count}' in seen[0].read().decode().replace(" ", "")
