"""The API client: the mask that is sent, the shapes that come back, the failures."""

from __future__ import annotations

import httpx
import pytest

from places.config import SEARCH_MASK
from places.lookup import Circle, PlacesAuthError, PlacesError
from tests.conftest import capturing, client_with, place, search_reply


async def test_the_field_mask_is_sent_because_the_api_requires_it() -> None:
    """ "If you omit the field mask, the method returns an error." It is also
    what sets the price, so it is asserted rather than assumed."""
    handler, seen = capturing(search_reply(place()))

    await client_with(handler).search_text("Natalina Bangsar", max_results=3)

    assert seen[0].headers["X-Goog-FieldMask"] == SEARCH_MASK
    assert seen[0].headers["X-Goog-Api-Key"] == "test-key"


async def test_a_candidate_is_flattened_from_the_shape_google_returns() -> None:
    handler, _ = capturing(search_reply(place()))

    result = await client_with(handler).search_text("Natalina", max_results=3)

    candidate = result.candidates[0]
    # `displayName` is {text, languageCode} — read as a string it yields "".
    assert candidate.name == "Natalina Italian Kitchen"
    assert candidate.kind == "Italian restaurant"
    assert candidate.latitude == pytest.approx(3.1595)
    assert candidate.place_id == "ChIJabc"


async def test_the_maps_link_is_built_locally_and_needs_no_key() -> None:
    """Officially documented, keyless, and opens the native app where one tap
    saves it — which matters because no API can write to a saved list."""
    handler, _ = capturing(search_reply(place()))

    result = await client_with(handler).search_text("Natalina", max_results=3)

    url = result.candidates[0].maps_url
    assert url.startswith("https://www.google.com/maps/search/?api=1&query=")
    assert "query_place_id=ChIJabc" in url
    # URL-encoded, so a venue name with spaces or punctuation cannot break it.
    assert " " not in url


async def test_location_bias_is_sent_as_a_circle_when_given() -> None:
    handler, seen = capturing(search_reply(place()))

    await client_with(handler).search_text(
        "nasi lemak",
        near=Circle(latitude=3.13, longitude=101.67, radius_meters=2000),
        max_results=3,
    )

    body = seen[0].read().decode()
    assert '"locationBias"' in body
    assert '"radius": 2000' in body or '"radius":2000' in body


async def test_no_bias_means_no_location_key_at_all() -> None:
    handler, seen = capturing(search_reply(place()))

    await client_with(handler).search_text("nasi lemak", max_results=3)

    assert "locationBias" not in seen[0].read().decode()


async def test_no_matches_is_an_answer_with_advice_not_an_error() -> None:
    """ "Google knows of no such place" is a result. And the advice matters: the
    usual cause is a descriptive query, which this endpoint is documented as not
    supporting."""
    handler, _ = capturing(search_reply())

    result = await client_with(handler).search_text("blue awning stall", max_results=3)

    assert result.candidates == []
    assert "not built for descriptive queries" in result.detail
    assert result.query_sent == "blue awning stall"


@pytest.mark.parametrize("status", [401, 403])
async def test_a_rejected_key_is_its_own_error_because_retrying_cannot_help(
    status: int,
) -> None:
    handler, _ = capturing(httpx.Response(status, text="API key not valid"))

    with pytest.raises(PlacesAuthError, match="Places API \\(New\\) is enabled"):
        await client_with(handler).search_text("x", max_results=3)


async def test_a_429_is_retried_exactly_once() -> None:
    """One retry, not a loop: this runs inside a 60s MCP deadline it cannot extend."""
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(429, text="quota")

    with pytest.raises(PlacesError, match="rate-limited"):
        await client_with(handler).search_text("x", max_results=3)

    assert len(calls) == 2


async def test_a_429_that_clears_on_retry_succeeds() -> None:
    responses = [httpx.Response(429, text="quota"), search_reply(place())]

    def handler(request: httpx.Request) -> httpx.Response:
        return responses.pop(0)

    result = await client_with(handler).search_text("x", max_results=3)

    assert len(result.candidates) == 1


async def test_a_server_error_carries_googles_own_message() -> None:
    handler, _ = capturing(httpx.Response(500, text="internal"))

    with pytest.raises(PlacesError, match="internal"):
        await client_with(handler).search_text("x", max_results=3)


async def test_place_details_flattens_hours_and_contact() -> None:
    payload = place() | {
        "regularOpeningHours": {
            "openNow": True,
            "weekdayDescriptions": ["Monday: 11:00 – 22:00", "Tuesday: Closed"],
        },
        "rating": 4.6,
        "userRatingCount": 812,
        "websiteUri": "https://natalina.example",
        "nationalPhoneNumber": "03-1234 5678",
    }
    handler, seen = capturing(httpx.Response(200, json=payload))

    details = await client_with(handler).place_details("ChIJabc")

    assert seen[0].url.path.endswith("/places/ChIJabc")
    assert details.opening_hours.open_now is True
    assert details.opening_hours.weekly[1] == "Tuesday: Closed"
    assert (details.rating, details.rating_count) == (4.6, 812)
    assert details.phone == "03-1234 5678"
    assert "query_place_id=ChIJabc" in details.maps_url


async def test_details_for_a_place_with_no_hours_is_still_usable() -> None:
    handler, _ = capturing(httpx.Response(200, json=place()))

    details = await client_with(handler).place_details("ChIJabc")

    assert details.opening_hours.open_now is None
    assert details.opening_hours.weekly == []
    assert details.name == "Natalina Italian Kitchen"


# --- how Google actually reports a key problem ----------------------------
#
# Found by calling the live API with a deliberately invalid key: it answers
# **400 API_KEY_INVALID**, not 401 or 403. Keying only on status missed the most
# common auth failure entirely and reported it through the generic branch,
# without the hint that helps.


async def test_an_invalid_key_is_recognised_despite_arriving_as_a_400() -> None:
    body = {
        "error": {
            "code": 400,
            "message": "API key not valid. Please pass a valid API key.",
            "status": "INVALID_ARGUMENT",
            "details": [{"reason": "API_KEY_INVALID"}],
        }
    }
    handler, _ = capturing(httpx.Response(400, json=body))

    with pytest.raises(PlacesAuthError, match="Places API \\(New\\) is enabled"):
        await client_with(handler).search_text("x", max_results=3)


async def test_an_unenabled_api_is_recognised_from_its_403_reason() -> None:
    handler, _ = capturing(
        httpx.Response(
            403, json={"error": {"status": "PERMISSION_DENIED", "message": "SERVICE_DISABLED"}}
        )
    )

    with pytest.raises(PlacesAuthError):
        await client_with(handler).search_text("x", max_results=3)


async def test_an_ordinary_400_is_not_mistaken_for_a_key_problem() -> None:
    """A malformed request is our bug. Blaming the user's key for it would send
    them to the Cloud console over a field mask typo."""
    handler, _ = capturing(
        httpx.Response(
            400, json={"error": {"message": "Invalid field mask", "status": "INVALID_ARGUMENT"}}
        )
    )

    with pytest.raises(PlacesError, match="Invalid field mask") as caught:
        await client_with(handler).search_text("x", max_results=3)
    assert not isinstance(caught.value, PlacesAuthError)
