"""Settings from the environment, validated before the server binds."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

BASE_URL = "https://places.googleapis.com/v1"

SEARCH_MASK = (
    "places.id,"
    "places.displayName,"
    "places.formattedAddress,"
    "places.location,"
    "places.primaryTypeDisplayName"
)

DETAILS_MASK = (
    "id,displayName,formattedAddress,location,"
    "regularOpeningHours,rating,userRatingCount,websiteUri,nationalPhoneNumber"
)


class ConfigError(RuntimeError):
    """Startup refused. The message names the variable to set."""


@dataclass(frozen=True)
class Config:
    api_key: str
    base_url: str
    max_results: int
    timeout_seconds: float


def load(env: Mapping[str, str] | None = None) -> Config:
    src = os.environ if env is None else env

    key = src.get("GOOGLE_MAPS_API_KEY", "").strip()
    if not key:
        raise ConfigError(
            "GOOGLE_MAPS_API_KEY is not set — a GCP project with Places API (New) "
            "enabled, or a Maps Demo Key for prototyping without billing"
        )

    raw = src.get("PLACES_MAX_RESULTS", "").strip()
    try:
        max_results = int(raw) if raw else 3
    except ValueError as err:
        raise ConfigError(f"PLACES_MAX_RESULTS={raw!r} is not an integer") from err
    if not 1 <= max_results <= 20:
        raise ConfigError(f"PLACES_MAX_RESULTS={max_results} must be between 1 and 20")

    raw = src.get("PLACES_TIMEOUT_SECONDS", "").strip()
    try:
        timeout = float(raw) if raw else 30.0
    except ValueError as err:
        raise ConfigError(f"PLACES_TIMEOUT_SECONDS={raw!r} is not a number") from err
    if timeout <= 0:
        raise ConfigError(f"PLACES_TIMEOUT_SECONDS={timeout} must be greater than zero")

    base_url = src.get("PLACES_BASE_URL", "").strip()
    if not base_url:
        base_url = BASE_URL

    return Config(
        api_key=key,
        base_url=base_url,
        max_results=max_results,
        timeout_seconds=timeout,
    )
