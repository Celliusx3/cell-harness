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
    """A Demo Key is the fastest path to a first working run, and not obvious."""
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


# --- the masks ------------------------------------------------------------
#
# Billing is per-call at the highest tier any requested field touches, so these
# strings set the price. A test rather than a comment because widening a mask is
# a one-word edit that quietly cuts the free allowance by 80%.

_ENTERPRISE = ("rating", "userRatingCount", "regularOpeningHours", "websiteUri", "priceLevel")
_ATMOSPHERE = ("reviews", "editorialSummary")


@pytest.mark.parametrize("field", _ENTERPRISE + _ATMOSPHERE)
def test_the_search_mask_stays_pro_tier(field: str) -> None:
    """Text Search Pro is 5,000 free calls a month; Enterprise is 1,000.

    This is the specific mistake the third-party server we replaced makes — its
    masks are hardcoded to include these fields, so every search bills at
    Enterprise + Atmosphere.
    """
    assert field not in SEARCH_MASK


def test_the_search_mask_asks_for_what_a_poi_actually_needs() -> None:
    for field in ("places.id", "places.displayName", "places.formattedAddress", "places.location"):
        assert field in SEARCH_MASK


def test_the_details_mask_may_be_enterprise_because_it_is_a_separate_sku() -> None:
    """Hours and a phone number are the point of asking for details, and Place
    Details has its own free allowance — so paying the higher tier here does not
    touch the search budget."""
    for field in ("regularOpeningHours", "nationalPhoneNumber", "websiteUri"):
        assert field in DETAILS_MASK
    # Atmosphere is still excluded: reviews are not worth a tier and would be
    # retained in the session log forever.
    for field in _ATMOSPHERE:
        assert field not in DETAILS_MASK
