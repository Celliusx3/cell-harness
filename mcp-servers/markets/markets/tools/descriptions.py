"""The model's only documentation."""

from __future__ import annotations

SEARCH = (
    "Find the canonical id for a company, ETF or coin by name or ticker; every other tool takes "
    "the id this returns. args: { query: string, kind?: 'stock' | 'etf' | 'crypto' }. Returns "
    "{ query_sent, candidates: [{ id, name, exchange, kind }], detail, as_of, source }. Ids look "
    "like AAPL or SPY (US), 1155.KL (Bursa Malaysia: the 4-digit stock code plus .KL) and "
    "crypto:bitcoin (a CoinGecko id, with the coin's symbol shown in name). Search by NAME "
    "('Maybank', 'Public Bank', 'Ethereum'), not by a ticker you have guessed: Malaysian stocks "
    "are numbered, not lettered, so MAYBANK is not an id and 1155.KL is, and crypto symbols "
    "collide, so BTC is not an id and crypto:bitcoin is. Several candidates is the normal "
    "answer for a common name (the same company can be listed on two exchanges); pick the one "
    "on the exchange the person means, or show them the list. An empty candidates list is not "
    "an error: read detail and try a shorter or different name."
)


QUOTE = (
    "Latest price for up to a handful of ids in one call, with per-item status. args: { ids: "
    "string[] }. Returns { items: [{ id, status, detail, kind, price, previous_close, "
    "change_pct, day_low, day_high, week52_low, week52_high, market_cap, volume, currency, "
    "exchange, as_of, source }], as_of }. status is one of ok, not_found, unsupported, timeout, "
    "error; read detail when it is not ok, and an item's problem never affects its siblings. "
    "Prices are DELAYED free data (Yahoo up to 20 minutes, CoinGecko about a minute) and as_of "
    "is when the server fetched them, so say 'as of' when you quote one and never present it as "
    "live. currency labels price and market_cap: MYR for .KL ids, USD for crypto. change_pct is "
    "versus previous_close (the prior session, or 24 hours for a coin). week52 fields are null "
    "for coins; day_low and day_high are the 24-hour range for them. Ask for the ids you need in "
    "one call rather than one call each: the server fetches them concurrently under a time "
    "budget and reports any that did not finish as timeout, which a second call for just those "
    "ids will fill."
)


HISTORY = (
    "Daily, weekly or monthly price bars over a range, plus a summary of the whole range. args: "
    "{ id: string, period?: '1mo' | '3mo' | '6mo' | '1y' | '5y', interval?: '1d' | '1wk' | "
    "'1mo' }. period defaults to 3mo and interval to 1d. Returns { id, status, detail, period, "
    "interval, currency, adjusted, truncated, summary: { first_close, last_close, high, low, "
    "change_pct }, rows: [{ date, open, high, low, close, volume }], as_of, source }. Bars are "
    "split- and dividend-adjusted (adjusted is true), dates are YYYY-MM-DD, and for a coin "
    "open, high and low are null because the free plan gives one price per day. Rows are "
    "CAPPED at a fixed count and a longer range is cut to its most recent bars with truncated "
    "true and a detail naming the coarser interval that fits — so choose the interval for the "
    "range: 1d for up to 3mo, 1wk for 6mo or 1y, 1mo for 5y. summary always covers the full range "
    "even when rows are cut, so for 'how has it done over the year' use summary.change_pct and "
    "skip the rows entirely. For a coin, 5y is served as 1y (the free plan's limit) and detail "
    "says so. Technical indicators are not a tool: compute a moving average or RSI from rows "
    "in a script."
)


PROFILE = (
    "What a company, ETF or coin is, with its valuation and profitability ratios, in one call. "
    "args: { id: string }. Returns { id, status, detail, kind, name, exchange, sector, industry, "
    "currency, description, market_cap, shares_outstanding, website, metrics: { pe_ttm, "
    "forward_pe, price_to_book, price_to_sales_ttm, ev_to_ebitda, gross_margin_pct, "
    "operating_margin_pct, net_margin_pct, return_on_equity_pct, debt_to_equity_pct, "
    "dividend_yield_pct }, crypto: { symbol, market_cap_rank, circulating_supply, max_supply, "
    "ath, ath_date, genesis_date, categories } | null, as_of, source }. Ratios are Yahoo's, "
    "trailing twelve months unless the name says forward; a null ratio means the source has "
    "none (a bank has no gross margin, an ETF no P/E) and must be reported as unavailable, "
    "never estimated. Fields ending in _pct are already percentages: 36.7 means 36.7%. For a "
    "coin, metrics are all null and crypto carries supply and all-time high instead; "
    "shares_outstanding is the circulating supply. This is the cheapest single call for "
    "comparing two names on valuation — call it once per id rather than reaching for "
    "get_financials."
)


FINANCIALS = (
    "One financial statement for a listed company, several periods at once, as reported. args: "
    "{ id: string, statement: 'income' | 'balance' | 'cashflow', period?: 'annual' | "
    "'quarterly', limit?: number }. period defaults to annual and limit (how many periods, "
    "newest first) to 4. Returns { id, status, detail, statement, period, currency, scale, "
    "periods: [{ period_end, items: { [line]: number } }], as_of, source }. items maps a line "
    "name such as 'Total Revenue', 'Net Income', 'Free Cash Flow' or 'Total Debt' to its value "
    "in currency units at scale 1 — full units, NOT millions, so 4.16e11 is 416 billion. "
    "period_end is the fiscal period's last day, and quarterly figures are single quarters, "
    "not cumulative and not trailing-twelve-month, so never add a quarter to an annual figure "
    "or call a quarter 'this year'. A line absent from a period was not reported for it. For a "
    "coin status is unsupported. Ask for the one statement you need; three calls fetch three "
    "statements, and for a valuation ratio get_company_profile already has it."
)


FILINGS = (
    "SEC filings for a US-listed company, newest first, each with a link to the document on "
    "EDGAR. args: { id: string, form?: string, limit?: number }. form filters to one exact "
    "form type such as '10-K', '10-Q', '8-K' or '4' (a 10-K/A is a different form and needs "
    "its own call); limit defaults to 10. Returns { id, status, detail, cik, company, "
    "filings: [{ form, filed, period_of_report, accession, url, description }], as_of, "
    "source }. filed is the date it reached the SEC and period_of_report the period it "
    "covers. status is unsupported for a .KL id or a coin — EDGAR holds US registrants only "
    "— and not_found for a US ticker that is not an SEC registrant. Give the person the url "
    "when you cite a filing: it opens the primary document directly. The document text is "
    "not returned; this lists what exists and when."
)


NEWS = (
    "Recent headlines about one company, ETF or coin. args: { id: string, limit?: number }. "
    "limit defaults to 8. Returns { id, status, detail, items: [{ title, publisher, "
    "published, url }], as_of, source }. published is ISO 8601 UTC. Headlines only — the "
    "article body is not fetched, so summarize what the titles say and give the url for the "
    "rest; do not infer a story's content from its title. An empty items list with status ok "
    "means the source has nothing recent, which for a small Bursa Malaysia stock is common "
    "and worth saying rather than treating as an error."
)
