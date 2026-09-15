"""The id vocabulary: one shape per market, and no guessing."""

from __future__ import annotations

import pytest

from markets.symbol import SymbolError, parse


def test_a_us_ticker_is_upper_cased_and_us() -> None:
    symbol = parse(" aapl ")

    assert (symbol.id, symbol.key, symbol.is_crypto, symbol.is_us) == ("AAPL", "AAPL", False, True)


def test_a_bursa_code_keeps_its_suffix_and_is_not_us() -> None:
    symbol = parse("1155.kl")

    assert symbol.id == "1155.KL"
    assert not symbol.is_us


def test_a_coin_is_prefixed_and_lower_cased() -> None:
    symbol = parse("Crypto:Bitcoin")

    assert (symbol.id, symbol.key, symbol.is_crypto, symbol.is_us) == (
        "crypto:bitcoin",
        "bitcoin",
        True,
        False,
    )


@pytest.mark.parametrize("raw", ["crypto:", "crypto: ", "crypto:Bit Coin", "crypto:BTC/USD"])
def test_a_malformed_coin_id_is_refused_with_the_shape_to_use(raw: str) -> None:
    with pytest.raises(SymbolError, match="crypto:bitcoin"):
        parse(raw)


@pytest.mark.parametrize("raw", ["", "  ", "AAPL AAPL", "$AAPL", "a" * 25])
def test_a_malformed_ticker_is_refused_and_points_at_search(raw: str) -> None:
    with pytest.raises(SymbolError, match="search_symbol"):
        parse(raw)
