"""What the two tools return.

Pydantic models so the server emits an `outputSchema` and populates
`structuredContent` — the thing the third-party server this replaces does not do,
and without which a code-mode script reads `undefined`.

`maps_url` is on every candidate and is **built locally, not requested**:
`https://www.google.com/maps/search/?api=1&query=…&query_place_id=…` is
officially documented, needs no API key, and opens natively in the mobile app
where one tap saves it. That matters because there is no API that writes to a
Google Maps saved list — the My Maps write API died in January 2011, `place/add`
in June 2018, and the feature request has been open since 2010. A link the person
taps is not a workaround; it is the only compliant path.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Candidate(BaseModel):
    """One place Google thinks matches, with nothing extra.

    Deliberately no rating, no reviews, no photos. Every one of those promotes
    the call to a more expensive SKU, and a tool result is retained in the
    session log forever — so a field nobody reads is a field stored forever for
    nothing.
    """

    place_id: str = Field(description="Stable and storable indefinitely, unlike the rest.")
    name: str
    address: str = ""
    latitude: float | None = None
    longitude: float | None = None
    kind: str = Field(default="", description="Google's own primary type label, e.g. 'Restaurant'.")
    maps_url: str = Field(description="A keyless deep link; tapping it offers Save.")


class SearchResult(BaseModel):
    """Candidates, in Google's relevance order, plus what was actually asked.

    `query_sent` is echoed because the model is expected to *normalize* a reel's
    messy evidence into a clean query, and seeing what was sent is how it learns
    a search returned nothing because the query was wrong rather than because the
    place does not exist.
    """

    query_sent: str
    candidates: list[Candidate] = Field(default_factory=list)
    detail: str = Field(default="", description="Why there are no candidates, when there are none.")


class OpeningHours(BaseModel):
    open_now: bool | None = None
    weekly: list[str] = Field(default_factory=list)


class PlaceDetails(BaseModel):
    """The things worth knowing before going somewhere."""

    place_id: str
    name: str
    address: str = ""
    latitude: float | None = None
    longitude: float | None = None
    maps_url: str
    opening_hours: OpeningHours = Field(default_factory=OpeningHours)
    rating: float | None = None
    rating_count: int | None = None
    website: str = ""
    phone: str = ""
