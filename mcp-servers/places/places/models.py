"""What the two tools return."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Candidate(BaseModel):
    """One place Google thinks matches, with nothing extra."""

    place_id: str = Field(description="Stable and storable indefinitely, unlike the rest.")
    name: str
    address: str = ""
    latitude: float | None = None
    longitude: float | None = None
    kind: str = Field(default="", description="Google's own primary type label, e.g. 'Restaurant'.")
    maps_url: str = Field(description="A keyless deep link; tapping it offers Save.")


class SearchResult(BaseModel):
    """Candidates, in Google's relevance order, plus what was actually asked."""

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
