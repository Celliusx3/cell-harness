"""Prompt text is code."""

from __future__ import annotations

import pytest

from markets import models as m
from markets.tools import descriptions as d

ALL = {
    "search_symbol": d.SEARCH,
    "get_quote": d.QUOTE,
    "get_price_history": d.HISTORY,
    "get_company_profile": d.PROFILE,
    "get_financials": d.FINANCIALS,
    "get_filings": d.FILINGS,
    "get_news": d.NEWS,
}

RETURNS = [
    ("search_symbol", m.SearchResult),
    ("search_symbol", m.Candidate),
    ("get_quote", m.Quotes),
    ("get_quote", m.Quote),
    ("get_price_history", m.History),
    ("get_price_history", m.Summary),
    ("get_price_history", m.Bar),
    ("get_company_profile", m.Profile),
    ("get_company_profile", m.Metrics),
    ("get_company_profile", m.CryptoFacts),
    ("get_financials", m.Financials),
    ("get_financials", m.Period),
    ("get_filings", m.Filings),
    ("get_filings", m.Filing),
    ("get_news", m.News),
    ("get_news", m.NewsItem),
]


@pytest.mark.parametrize("name", sorted(ALL))
def test_a_description_survives_being_collapsed_to_one_line(name: str) -> None:
    assert " ".join(ALL[name].split()) == ALL[name]


@pytest.mark.parametrize("name", sorted(ALL))
def test_a_description_cannot_end_its_own_comment_block(name: str) -> None:
    assert "*/" not in ALL[name]


@pytest.mark.parametrize("name", sorted(ALL))
def test_a_description_names_its_arguments(name: str) -> None:
    assert "args: {" in ALL[name]


@pytest.mark.parametrize("name", sorted(ALL))
def test_a_description_never_hardcodes_its_own_namespace(name: str) -> None:
    assert "__" not in ALL[name]


@pytest.mark.parametrize(("name", "model"), RETURNS, ids=lambda x: getattr(x, "__name__", x))
def test_every_returned_field_is_named_in_the_prose(name: str, model: type) -> None:
    missing = [field for field in model.model_fields if field not in ALL[name]]

    assert missing == []


@pytest.mark.parametrize("value", ["1mo", "3mo", "6mo", "1y", "5y", "1d", "1wk"])
def test_history_names_every_allowed_period_and_interval(value: str) -> None:
    assert f"'{value}'" in d.HISTORY


def test_search_teaches_the_two_id_shapes_that_are_not_tickers() -> None:
    assert "1155.KL" in d.SEARCH and "MAYBANK is not an id" in d.SEARCH
    assert "crypto:bitcoin" in d.SEARCH and "BTC is not an id" in d.SEARCH


def test_quote_says_the_data_is_delayed_and_when_it_was_fetched() -> None:
    assert "DELAYED" in d.QUOTE and "as_of" in d.QUOTE


def test_history_tells_the_model_which_interval_fits_which_range() -> None:
    assert "1d for up to 3mo" in d.HISTORY
    assert "summary.change_pct" in d.HISTORY


def test_profile_forbids_estimating_a_missing_ratio_and_explains_pct() -> None:
    assert "never estimated" in d.PROFILE
    assert "36.7 means 36.7%" in d.PROFILE


def test_financials_warn_about_units_and_single_quarters() -> None:
    assert "NOT millions" in d.FINANCIALS
    assert "single quarters" in d.FINANCIALS


def test_filings_say_the_document_text_is_not_returned() -> None:
    assert "not returned" in d.FILINGS


def test_news_forbids_inferring_a_story_from_its_title() -> None:
    assert "do not infer" in d.NEWS
