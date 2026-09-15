# markets

Investment **research** data for a model that is asked "how is Maybank doing",
"compare Apple and Microsoft on margins" or "what did bitcoin do this year":
quotes, price history, company profiles with valuation ratios, financial
statements, SEC filings and headlines. Research only — nothing here places an
order, and nothing here is advice; it is the numbers, each labelled with what it
is.

Seven tools over three free sources:

| Tool | Source |
|---|---|
| `search_symbol` | Yahoo search + CoinGecko search |
| `get_quote` (batched, per-item status) | Yahoo `fast_info` / CoinGecko `/coins/markets` |
| `get_price_history` (capped rows + full-range summary) | Yahoo `history()` / CoinGecko `/market_chart` |
| `get_company_profile` (+ valuation & margin ratios) | Yahoo `info` / CoinGecko `/coins/{id}` |
| `get_financials` (income / balance / cashflow) | Yahoo statements |
| `get_filings` (US only, URL per filing) | SEC EDGAR submissions |
| `get_news` (headlines only) | Yahoo (coins via their `BTC-USD` pair) |

## One id vocabulary

| id | is | why this shape |
|---|---|---|
| `AAPL`, `SPY` | US stock / ETF | Yahoo's ticker |
| `1155.KL` | Bursa Malaysia stock | Bursa's 4-digit code + Yahoo's suffix. **`MAYBANK` is not an id** — Malaysian stocks are numbered |
| `crypto:bitcoin` | coin | CoinGecko's id. **`BTC` is not an id** — crypto symbols collide |

`search_symbol` returns ids; the model passes them back unchanged. Routing is
`symbol.py`, and it is the only place the server knows a market.

## What is deliberately not here

- **Technicals.** A moving average is ten lines of TypeScript over `rows`; a
  tool would be a schema for something the sandbox does better.
- **Bursa announcements / quarterly reports.** Bursa Malaysia has no free feed:
  `bursamalaysia.com` is Cloudflare-fronted and its terms forbid redistribution;
  the free mirrors (KLSE Screener, i3investor) are scrapers of grey standing.
  Yahoo's `.KL` statements are the licensed path and are what `get_financials`
  returns. EODHD covers KLSE on paid plans if this ever needs more.
- **XBRL (`companyfacts`).** Multi-megabyte per company and needs a us-gaap
  tag mapping to mean anything; Yahoo's statements are the same numbers, shaped.
- **Filing text.** `get_filings` lists what exists with a URL each; reading a
  10-K section is a follow-up.
- **Binance / ccxt.** Deeper crypto history, keyless — but no market cap or
  supply, Binance-listed coins only, and `binance.com` is unlicensed in
  Malaysia. CoinGecko's one year of daily prices is enough for research.

## Requirements

| Variable | Default | Notes |
|---|---|---|
| `SEC_USER_AGENT` | — | required. EDGAR's fair-access policy wants `Name email`; a bare client gets 403. Not a secret; the committed value is generic, put yours in `config.local.json` |
| `COINGECKO_API_KEY` | — | required. A free **Demo** key (no billing) from coingecko.com/en/api/pricing. The keyless endpoint rate-limits after a handful of calls |
| `MARKETS_MAX_ROWS` | `70` | history rows per call. 70 pretty-print to ~12 KB (130 to ~23 KB), and a result is re-sent every turn |
| `MARKETS_MAX_IDS` | `10` | ids per `get_quote` |
| `MARKETS_CALL_BUDGET_SECONDS` | `45` | `get_quote` returns what finished and marks the rest `timeout` |
| `MARKETS_TIMEOUT_SECONDS` | `20` | per HTTP request |
| `MARKETS_EDGAR_DATA_URL`, `MARKETS_EDGAR_WWW_URL`, `MARKETS_COINGECKO_BASE_URL` | the real hosts | overrides for tests |

Yahoo needs nothing, which is also its warranty: `yfinance` reads unofficial
endpoints, breaks a few times a year, and Yahoo's terms are personal use.

## Every number says what it is

The recorded failures of LLM financial analysis are invented figures, millions
mistaken for billions, a stale price presented as live, and the wrong company
behind a ticker. The shapes are built against each:

- every result carries `as_of` and `source`; money carries `currency`
- statements carry `period_end` and `scale: 1` (units as reported, never millions),
  and quarters are single quarters
- ratios say their basis in their name (`pe_ttm`, `forward_pe`) and `_pct` fields
  are already percentages; a ratio the source lacks is `null`, and the description
  tells the model to report it as unavailable, never to estimate
- `search_symbol` never guesses: several candidates or none, with a `detail`
- an unknown id is `status: not_found` on a normal result; only an unreachable
  source fails a call, and in `get_quote` even that is a per-item `error`

## Licensing, in one paragraph

Free tiers are **personal use**: Yahoo's terms, CoinGecko Demo's, and Bursa's
data licence all say so; SEC data is public domain. That is fine for the person
running their own harness. Serving other people, or charging for the output,
needs licensed data — and in Malaysia the Securities Commission's guidance
(SC-GN/1-2020) treats issuing analyses of securities *as part of a business* as
licensable investment advice, disclaimer or not. Not this server's problem to
solve; worth knowing before it becomes one.

## Catalog cost

Measured 2026-09-15 through the harness's own `McpServerStore`: the committed
config (`instagram`, `places`, `sysmon`, this) offers 13 MCP tools; a local
config that also declares `jobs` and `yt` offers 25, and `list_functions` over
those renders to ~26 KB. `docs/mcp-tool-scaling.md` §5 puts the point to
re-measure the catalog near 28 tools — the next server is the one to measure at.

## Tests

```sh
cd mcp-servers/markets
uv run pytest                      # hermetic; Yahoo is a fake, HTTP is a MockTransport
MARKETS_LIVE=1 SEC_USER_AGENT="Name email" COINGECKO_API_KEY=CG-… \
  uv run pytest tests/integration/test_live.py --no-cov   # the real sources, once
```

The live suite re-verifies the shapes the fixtures were written from (Yahoo
1.7.0, 2026-09-14): `1155.KL` quotes in MYR and has quarterly statements,
`public bank` resolves to `1295.KL` first, Apple's 10-Qs have EDGAR URLs, and
CoinGecko finds bitcoin and charts six months of weekly bars.
