from dataclasses import dataclass
from datetime import date

import httpx
from pydantic import Field, TypeAdapter

from mt.rules.bot import settings as bot_settings

from .http import Payload, http_timeout


FRAMES_URL = "https://data.sec.gov/api/xbrl/frames/us-gaap/{concept}/USD/{period}.json"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
GROSS_PROFIT = "GrossProfit"
REVENUES = (
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet",
)
COSTS = ("CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold")
ASSETS = "Assets"
YEARS = 3
NOT_FOUND = 404
CLIENT = httpx.Client(
    timeout=http_timeout(bot_settings.edgar.timeout),
    follow_redirects=True,
    headers={"User-Agent": bot_settings.edgar.user_agent},
)


class Fact(Payload):
    cik: int
    end: date
    val: float


class _Frame(Payload):
    data: list[Fact]


class Ticker(Payload):
    cik: int = Field(alias="cik_str")
    ticker: str


@dataclass(frozen=True, slots=True)
class Fundamentals:
    gross_profit: float
    assets: float
    period_end: date

    @property
    def gross_profitability(self) -> float:
        return self.gross_profit / self.assets


tickers_adapter = TypeAdapter(dict[str, Ticker])


def ciks() -> dict[str, int]:
    payload = tickers_adapter.validate_python(_get(TICKERS_URL))
    found: dict[str, int] = {}
    for row in payload.values():
        found.setdefault(row.ticker.upper().replace("-", "."), row.cik)
    return found


def fundamentals(day: date) -> dict[int, Fundamentals]:
    flows: dict[int, tuple[date, float]] = {}
    for year in range(day.year, day.year - YEARS, -1):
        for cik, (end, value) in _gross_profits(f"CY{year}").items():
            if end <= day and (cik not in flows or end > flows[cik][0]):
                flows[cik] = end, value
    balances: dict[tuple[int, date], float] = {}
    for year in range(day.year, day.year - YEARS, -1):
        for quarter in range(4, 0, -1):
            if date(year, 3 * quarter - 2, 1) > day:
                continue
            for fact in _facts(ASSETS, f"CY{year}Q{quarter}I").values():
                balances[fact.cik, fact.end] = fact.val
    found: dict[int, Fundamentals] = {}
    for cik, (end, value) in flows.items():
        assets = balances.get((cik, end))
        if assets is not None and assets > 0:
            found[cik] = Fundamentals(value, assets, end)
    return found


def _gross_profits(period: str) -> dict[int, tuple[date, float]]:
    reported = _facts(GROSS_PROFIT, period)
    revenues = _first(REVENUES, period)
    costs = _first(COSTS, period)
    found = {cik: (fact.end, fact.val) for cik, fact in reported.items()}
    for cik, revenue in revenues.items():
        cost = costs.get(cik)
        if cik in found or cost is None or cost.end != revenue.end:
            continue
        found[cik] = revenue.end, revenue.val - cost.val
    return found


def _first(concepts: tuple[str, ...], period: str) -> dict[int, Fact]:
    found: dict[int, Fact] = {}
    for concept in concepts:
        for cik, fact in _facts(concept, period).items():
            found.setdefault(cik, fact)
    return found


def _facts(concept: str, period: str) -> dict[int, Fact]:
    response = CLIENT.get(FRAMES_URL.format(concept=concept, period=period))
    if response.status_code == NOT_FOUND:
        return {}
    response.raise_for_status()
    return {fact.cik: fact for fact in _Frame.model_validate(response.json()).data}


def _get(url: str) -> object:
    response = CLIENT.get(url)
    response.raise_for_status()
    return response.json()
