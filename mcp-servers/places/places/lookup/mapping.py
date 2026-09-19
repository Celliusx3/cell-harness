"""Google's payload shapes to ours, and the link we build ourselves."""

from __future__ import annotations

from urllib.parse import quote_plus

from places.models import Candidate, OpeningHours, PlaceDetails

_DEEP_LINK = "https://www.google.com/maps/search/?api=1&query={query}&query_place_id={place_id}"


def candidate(place: dict) -> Candidate:
    place_id = place.get("id", "")
    name = display(place)
    location = place.get("location") or {}
    return Candidate(
        place_id=place_id,
        name=name,
        address=place.get("formattedAddress", ""),
        latitude=location.get("latitude"),
        longitude=location.get("longitude"),
        kind=(place.get("primaryTypeDisplayName") or {}).get("text", ""),
        maps_url=deep_link(name, place_id),
    )


def display(place: dict) -> str:
    """`displayName.text`, or the empty string."""
    return (place.get("displayName") or {}).get("text", "")


def deep_link(name: str, place_id: str) -> str:
    return _DEEP_LINK.format(query=quote_plus(name or place_id), place_id=quote_plus(place_id))


def details(payload: dict, place_id: str) -> PlaceDetails:
    """One place's details, flattened."""
    hours = payload.get("regularOpeningHours") or {}
    resolved = payload.get("id", place_id)
    name = display(payload)
    return PlaceDetails(
        place_id=resolved,
        name=name,
        address=payload.get("formattedAddress", ""),
        latitude=(payload.get("location") or {}).get("latitude"),
        longitude=(payload.get("location") or {}).get("longitude"),
        maps_url=deep_link(name, resolved),
        opening_hours=OpeningHours(
            open_now=hours.get("openNow"),
            weekly=list(hours.get("weekdayDescriptions") or []),
        ),
        rating=payload.get("rating"),
        rating_count=payload.get("userRatingCount"),
        website=payload.get("websiteUri", ""),
        phone=payload.get("nationalPhoneNumber", ""),
    )
