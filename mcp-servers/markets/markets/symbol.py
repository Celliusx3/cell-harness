"""The one routing decision: what kind of thing an id names.

One vocabulary across three markets so the same tool serves all of them:
`AAPL` and `SPY` are Yahoo tickers, `1155.KL` is a Bursa Malaysia stock by its
4-digit code with Yahoo's suffix, `crypto:bitcoin` is a CoinGecko id. The
prefix is deliberate — crypto symbols have no governance (`BTG`, `WBTC` and
plain names collide), so a bare `bitcoin` is refused rather than guessed. The
model gets ids from `search_symbol` and passes them back unchanged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_TICKER = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,19}$")
_COIN = re.compile(r"^[a-z0-9][a-z0-9\-]{0,63}$")
CRYPTO_PREFIX = "crypto:"


class SymbolError(ValueError):
    """The id is not in the vocabulary. The message says what is."""


@dataclass(frozen=True)
class Symbol:
    id: str
    key: str
    is_crypto: bool

    @property
    def is_us(self) -> bool:
        # A Yahoo ticker with no exchange suffix is a US listing. Only US
        # listings have EDGAR filings.
        return not self.is_crypto and "." not in self.key


def parse(raw: str) -> Symbol:
    text = raw.strip()
    if text.lower().startswith(CRYPTO_PREFIX):
        coin = text[len(CRYPTO_PREFIX) :].strip().lower()
        if not _COIN.match(coin):
            raise SymbolError(
                f"{raw!r} is not a crypto id: expected crypto:<coingecko-id> such as "
                "crypto:bitcoin — get the id from search_symbol"
            )
        return Symbol(id=f"{CRYPTO_PREFIX}{coin}", key=coin, is_crypto=True)

    ticker = text.upper()
    if not _TICKER.match(ticker):
        raise SymbolError(
            f"{raw!r} is not a ticker: expected a Yahoo symbol such as AAPL or 1155.KL, or "
            "crypto:<id> for a coin — use search_symbol to find it"
        )
    return Symbol(id=ticker, key=ticker, is_crypto=False)
