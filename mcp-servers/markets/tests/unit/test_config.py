"""Startup refusals: the two required strings, and the numbers."""

from __future__ import annotations

import pytest

from markets.config import DEFAULT_MAX_ROWS, ConfigError, load

BASE = {"SEC_USER_AGENT": "tests tests@example.com", "COINGECKO_API_KEY": "CG-x"}


def test_a_complete_environment_loads_with_defaults() -> None:
    config = load(BASE)

    assert config.max_rows == DEFAULT_MAX_ROWS
    assert config.edgar_data_url == "https://data.sec.gov"
    assert config.coingecko_base_url.startswith("https://api.coingecko.com")


def test_a_missing_user_agent_refuses_and_says_what_edgar_wants() -> None:
    with pytest.raises(ConfigError, match="Name email"):
        load({"COINGECKO_API_KEY": "CG-x"})


def test_a_missing_coingecko_key_refuses_and_names_the_free_route() -> None:
    with pytest.raises(ConfigError, match="Demo key"):
        load({"SEC_USER_AGENT": "tests tests@example.com"})


def test_the_refusal_goes_to_the_agent_first() -> None:
    with pytest.raises(ConfigError, match="SEC_USER_AGENT"):
        load({})


@pytest.mark.parametrize("value", ["9", "1001", "-1"])
def test_an_out_of_range_row_cap_refuses(value: str) -> None:
    with pytest.raises(ConfigError, match="between 10 and 1000"):
        load(BASE | {"MARKETS_MAX_ROWS": value})


@pytest.mark.parametrize(
    ("name", "value", "because"),
    [
        ("MARKETS_MAX_ROWS", "many", "not an integer"),
        ("MARKETS_MAX_IDS", "0", "between 1 and 50"),
        ("MARKETS_TIMEOUT_SECONDS", "soon", "not a number"),
        ("MARKETS_CALL_BUDGET_SECONDS", "0", "greater than zero"),
    ],
)
def test_an_unusable_number_refuses(name: str, value: str, because: str) -> None:
    with pytest.raises(ConfigError, match=because):
        load(BASE | {name: value})


def test_urls_can_be_overridden_for_tests() -> None:
    config = load(
        BASE
        | {
            "MARKETS_EDGAR_DATA_URL": "http://127.0.0.1:1",
            "MARKETS_EDGAR_WWW_URL": "http://127.0.0.1:2",
            "MARKETS_COINGECKO_BASE_URL": "http://127.0.0.1:3",
        }
    )

    assert (config.edgar_data_url, config.edgar_www_url, config.coingecko_base_url) == (
        "http://127.0.0.1:1",
        "http://127.0.0.1:2",
        "http://127.0.0.1:3",
    )
