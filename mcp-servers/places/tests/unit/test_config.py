"""Startup refusals, and the field masks — which are the price."""

from __future__ import annotations

import pytest

from places.config import DETAILS_MASK, SEARCH_MASK, ConfigError, load

BASE = {"GOOGLE_MAPS_API_KEY": "AIza-test"}


def test_a_complete_environment_loads() -> None:
    config = load(BASE)

    assert config.max_results == 3
    assert config.base_url.startswith("https://places.googleapis.com")


def test_a_missing_key_refuses_and_says_what_is_needed() -> None:
    with pytest.raises(ConfigError, match="Places API \\(New\\)"):
        load({})


def test_the_refusal_mentions_the_no_billing_route() -> None:
    with pytest.raises(ConfigError, match="Demo Key"):
        load({})


@pytest.mark.parametrize("value", ["0", "21", "-1"])
def test_an_out_of_range_result_count_refuses(value: str) -> None:
    with pytest.raises(ConfigError, match="between 1 and 20"):
        load(BASE | {"PLACES_MAX_RESULTS": value})


@pytest.mark.parametrize(
    ("name", "value", "because"),
    [
        ("PLACES_MAX_RESULTS", "three", "not an integer"),
        ("PLACES_TIMEOUT_SECONDS", "soon", "not a number"),
        ("PLACES_TIMEOUT_SECONDS", "0", "greater than zero"),
    ],
)
def test_an_unusable_number_refuses(name: str, value: str, because: str) -> None:
    with pytest.raises(ConfigError, match=because):
        load(BASE | {name: value})


_ENTERPRISE = ("rating", "userRatingCount", "regularOpeningHours", "websiteUri", "priceLevel")
_ATMOSPHERE = ("reviews", "editorialSummary")


@pytest.mark.parametrize("field", _ENTERPRISE + _ATMOSPHERE)
def test_the_search_mask_stays_pro_tier(field: str) -> None:
    assert field not in SEARCH_MASK


def test_the_search_mask_asks_for_what_a_poi_actually_needs() -> None:
    for field in ("places.id", "places.displayName", "places.formattedAddress", "places.location"):
        assert field in SEARCH_MASK


def test_the_details_mask_may_be_enterprise_because_it_is_a_separate_sku() -> None:
    for field in ("regularOpeningHours", "nationalPhoneNumber", "websiteUri"):
        assert field in DETAILS_MASK
    for field in _ATMOSPHERE:
        assert field not in DETAILS_MASK
