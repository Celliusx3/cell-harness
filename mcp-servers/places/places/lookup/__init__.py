"""Asking Google about a place — the one outward call this server makes.

**The most important thing here is a documented limitation, not code.** Google
states that Text Search *"is not intended for ambiguous queries"*, and lists the
shapes that fail: *"too many concepts or constraints"* and *"unofficial or vanity
names"*. So a query assembled straight from a reel — "nasi lemak stall Bangsar
blue awning banana leaf" — is bad **by construction**; "blue awning" is in no
index anywhere and its presence actively harms the match.

Verified against the public geocoders too: adding one non-indexed descriptor took
Nominatim and Photon from 2 results to **0**. The pipeline that works is for the
model to normalize the evidence into a clean name-and-area query, get a few
candidates, and re-rank *those* using the visual detail. Descriptors are
disambiguation signal, never search input, and `search_text`'s description says
so because the model is the only thing that can get this right.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from places.config import DETAILS_MASK, SEARCH_MASK
from places.lookup.http import PlacesAuthError, PlacesError, send
from places.lookup.mapping import candidate, details
from places.models import PlaceDetails, SearchResult

__all__ = ["Circle", "PlacesClient", "PlacesAuthError", "PlacesError"]


@dataclass(frozen=True)
class Circle:
    """A location bias. Not a filter — Google may still return results outside it.

    Used rather than `locationRestriction` because restriction only applies to
    categorical queries, and a POI lookup is almost always a name query.
    """

    latitude: float
    longitude: float
    radius_meters: float


class PlacesClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._key = api_key
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def search_text(
        self, query: str, *, near: Circle | None = None, max_results: int
    ) -> SearchResult:
        body: dict[str, object] = {"textQuery": query, "maxResultCount": max_results}
        if near is not None:
            body["locationBias"] = {
                "circle": {
                    "center": {"latitude": near.latitude, "longitude": near.longitude},
                    "radius": near.radius_meters,
                }
            }

        response = await send(
            lambda: self._client.post(
                f"{self._base}/places:searchText", headers=self._headers(SEARCH_MASK), json=body
            )
        )
        places = response.json().get("places") or []
        if not places:
            return SearchResult(
                query_sent=query,
                detail=(
                    "Google returned no matches. Text Search is not built for descriptive "
                    "queries — if this one carried visual detail or several constraints, send "
                    "the venue name and its area alone and re-rank the candidates yourself."
                ),
            )
        return SearchResult(query_sent=query, candidates=[candidate(place) for place in places])

    async def place_details(self, place_id: str) -> PlaceDetails:
        response = await send(
            lambda: self._client.get(
                f"{self._base}/places/{place_id}", headers=self._headers(DETAILS_MASK)
            )
        )
        return details(response.json(), place_id)

    def _headers(self, mask: str) -> dict[str, str]:
        # The field mask is mandatory: "If you omit the field mask, the method
        # returns an error." It is also what sets the price, so it is never
        # defaulted or widened at the call site.
        return {"X-Goog-Api-Key": self._key, "X-Goog-FieldMask": mask}
