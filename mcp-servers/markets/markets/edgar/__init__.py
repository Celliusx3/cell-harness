"""SEC filings from EDGAR's JSON APIs — US listings only.

Two hosts, both free and public domain: `www.sec.gov/files/company_tickers.json`
maps a ticker to a CIK (10k rows, fetched once per process), and
`data.sec.gov/submissions/CIK##########.json` lists a company's recent filings
as parallel arrays. The fair-access rules are a declared `User-Agent` and at
most 10 requests a second; a bare client gets 403 (verified live), which is
why the agent string is a startup requirement.

Not XBRL. `companyfacts` is multi-megabyte per company and needs a us-gaap tag
mapping to mean anything; statements come from Yahoo instead. What EDGAR adds
is the authoritative list *with a URL per filing* — the thing a research
answer can cite.
"""

from __future__ import annotations

from typing import Any

import httpx

from markets.data import RateLimited, Unavailable
from markets.models import EDGAR, Filing, Filings, now_iso
from markets.symbol import Symbol


class EdgarClient:
    def __init__(
        self,
        *,
        user_agent: str,
        data_url: str,
        www_url: str,
        timeout_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._data_url = data_url.rstrip("/")
        self._www_url = www_url.rstrip("/")
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)
        self._headers = {"User-Agent": user_agent, "Accept": "application/json"}
        self._ciks: dict[str, tuple[int, str]] | None = None

    async def filings(self, symbol: Symbol, form: str | None, limit: int) -> Filings:
        base = dict(id=symbol.id, source=EDGAR)
        if not symbol.is_us:
            return Filings(
                status="unsupported",
                detail="EDGAR holds SEC filings for US listings only; for a Bursa Malaysia "
                "stock use get_financials and get_news, for a coin get_company_profile",
                as_of=now_iso(),
                **base,
            )
        found = (await self._cik_map()).get(symbol.key)
        if found is None:
            return Filings(
                status="not_found",
                detail="EDGAR knows no SEC registrant with this ticker",
                as_of=now_iso(),
                **base,
            )
        cik, company = found
        payload = await self._get(f"{self._data_url}/submissions/CIK{cik:010d}.json")
        return Filings(
            status="ok",
            cik=str(cik),
            company=str(payload.get("name") or company),
            filings=self._recent(payload, cik, form, limit),
            as_of=now_iso(),
            **base,
        )

    def _recent(self, payload: Any, cik: int, form: str | None, limit: int) -> list[Filing]:
        recent = (payload.get("filings") or {}).get("recent") or {}
        wanted = form.strip().upper() if form else None
        out: list[Filing] = []
        for i, kind in enumerate(recent.get("form") or []):
            if wanted and str(kind).upper() != wanted:
                continue
            accession = str(_at(recent, "accessionNumber", i))
            document = str(_at(recent, "primaryDocument", i))
            out.append(
                Filing(
                    form=str(kind),
                    filed=str(_at(recent, "filingDate", i)),
                    period_of_report=str(_at(recent, "reportDate", i)),
                    accession=accession,
                    url=f"{self._www_url}/Archives/edgar/data/{cik}/"
                    f"{accession.replace('-', '')}/{document}",
                    description=str(_at(recent, "primaryDocDescription", i)),
                )
            )
            if len(out) >= limit:
                break
        return out

    async def _cik_map(self) -> dict[str, tuple[int, str]]:
        if self._ciks is None:
            rows = await self._get(f"{self._www_url}/files/company_tickers.json")
            self._ciks = {
                str(row["ticker"]).upper(): (int(row["cik_str"]), str(row.get("title") or ""))
                for row in rows.values()
                if row.get("ticker")
            }
        return self._ciks

    async def _get(self, url: str) -> Any:
        try:
            response = await self._client.get(url, headers=self._headers)
        except httpx.HTTPError as err:
            raise Unavailable(f"EDGAR could not be reached: {err}") from err
        if response.status_code == 429:
            raise RateLimited("EDGAR rate-limited the request; wait before retrying")
        if response.status_code == 403:
            raise Unavailable(
                "EDGAR refused the request (403): the SEC_USER_AGENT must be a real "
                "'Name email' string"
            )
        if response.status_code != 200:
            raise Unavailable(f"EDGAR answered HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as err:
            raise Unavailable("EDGAR answered with something that is not JSON") from err


def _at(recent: Any, key: str, i: int) -> Any:
    values = recent.get(key) or []
    return values[i] if i < len(values) else ""
