"""What the seven tools return.

Pydantic models so the server emits an `outputSchema` and populates
`structuredContent` — without which a code-mode script reads `undefined`
(`docs/mcp-tool-scaling.md` §6).

**Per-item `status`, never a per-item failure.** A tool `Failure` becomes a
thrown `Error` in the sandbox and takes every sibling with it. An unknown
ticker is an answer (`not_found`); only a dead network is a failure.

**Every number travels with what it is.** The research literature's recorded
failures are the model inventing a figure, mixing millions with billions, or
presenting last year's quarter as current. So every result carries `as_of` and
`source`, money carries `currency`, statements carry `period_end` and `scale`,
and a metric's basis is in its name (`pe_ttm`, `forward_pe`). Nothing is a
bare float the model has to guess about.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

Status = Literal["ok", "not_found", "unsupported", "timeout", "error"]
Kind = Literal["stock", "etf", "crypto"]
Statement = Literal["income", "balance", "cashflow"]
FiscalPeriod = Literal["annual", "quarterly"]
Range = Literal["1mo", "3mo", "6mo", "1y", "5y"]
Interval = Literal["1d", "1wk", "1mo"]

YAHOO = "yahoo_finance"
COINGECKO = "coingecko"
EDGAR = "sec_edgar"


def now_iso() -> str:
    """When the server fetched it. Quotes from free sources are delayed, and the
    model is told so; this is the honest upper bound on freshness."""
    return datetime.now(UTC).isoformat(timespec="seconds")


class Candidate(BaseModel):
    id: str = Field(description="The canonical id every other tool accepts.")
    name: str
    exchange: str = ""
    kind: Kind


class SearchResult(BaseModel):
    query_sent: str
    candidates: list[Candidate] = Field(default_factory=list)
    detail: str = ""
    as_of: str
    source: str


class Quote(BaseModel):
    id: str
    status: Status
    detail: str = ""
    kind: Kind | None = None
    price: float | None = None
    previous_close: float | None = None
    change_pct: float | None = None
    day_low: float | None = None
    day_high: float | None = None
    week52_low: float | None = None
    week52_high: float | None = None
    market_cap: float | None = None
    volume: float | None = None
    currency: str = ""
    exchange: str = ""
    as_of: str
    source: str


class Quotes(BaseModel):
    items: list[Quote] = Field(default_factory=list)
    as_of: str


class Bar(BaseModel):
    date: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float
    volume: float | None = None


class Summary(BaseModel):
    first_close: float
    last_close: float
    high: float
    low: float
    change_pct: float


class History(BaseModel):
    id: str
    status: Status
    detail: str = ""
    period: Range
    interval: Interval
    currency: str = ""
    adjusted: bool = True
    truncated: bool = False
    summary: Summary | None = None
    rows: list[Bar] = Field(default_factory=list)
    as_of: str
    source: str


class Metrics(BaseModel):
    """Yahoo's pre-computed ratios, TTM unless the name says forward. Null when
    Yahoo has none — a bank has no gross margin, an ETF no P/E. Percentages are
    percentages (`36.7`, not `0.367`) and say so in their name."""

    pe_ttm: float | None = None
    forward_pe: float | None = None
    price_to_book: float | None = None
    price_to_sales_ttm: float | None = None
    ev_to_ebitda: float | None = None
    gross_margin_pct: float | None = None
    operating_margin_pct: float | None = None
    net_margin_pct: float | None = None
    return_on_equity_pct: float | None = None
    debt_to_equity_pct: float | None = None
    dividend_yield_pct: float | None = None


class CryptoFacts(BaseModel):
    symbol: str = ""
    market_cap_rank: int | None = None
    circulating_supply: float | None = None
    max_supply: float | None = None
    ath: float | None = None
    ath_date: str = ""
    genesis_date: str = ""
    categories: list[str] = Field(default_factory=list)


class Profile(BaseModel):
    id: str
    status: Status
    detail: str = ""
    kind: Kind | None = None
    name: str = ""
    exchange: str = ""
    sector: str = ""
    industry: str = ""
    currency: str = ""
    description: str = ""
    market_cap: float | None = None
    shares_outstanding: float | None = None
    website: str = ""
    metrics: Metrics = Field(default_factory=Metrics)
    crypto: CryptoFacts | None = None
    as_of: str
    source: str


class Period(BaseModel):
    period_end: str
    items: dict[str, float] = Field(default_factory=dict)


class Financials(BaseModel):
    id: str
    status: Status
    detail: str = ""
    statement: Statement
    period: FiscalPeriod
    currency: str = ""
    scale: int = Field(default=1, description="As reported: units of currency, not millions.")
    periods: list[Period] = Field(default_factory=list)
    as_of: str
    source: str


class Filing(BaseModel):
    form: str
    filed: str
    period_of_report: str = ""
    accession: str
    url: str
    description: str = ""


class Filings(BaseModel):
    id: str
    status: Status
    detail: str = ""
    cik: str = ""
    company: str = ""
    filings: list[Filing] = Field(default_factory=list)
    as_of: str
    source: str


class NewsItem(BaseModel):
    title: str
    publisher: str = ""
    published: str = ""
    url: str = ""


class News(BaseModel):
    id: str
    status: Status
    detail: str = ""
    items: list[NewsItem] = Field(default_factory=list)
    as_of: str
    source: str
