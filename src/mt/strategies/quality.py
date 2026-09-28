from datetime import date, datetime, timedelta
from typing import ClassVar

import httpx2
from pydantic import ValidationError

from mt.data.asset import Asset
from mt.data.company import industry

from .base import Portfolio, ranked
from .monthly import Monthly


class Quality(Monthly):
    universe_size: ClassVar[int]
    keep_rank: ClassVar[int]
    fundamentals_max_age_days: ClassVar[int]
    excluded_industries: ClassVar[tuple[str, ...]]
    retry_minutes: ClassVar[int]

    def __init__(self, portfolio: Portfolio) -> None:
        super().__init__(portfolio)
        self._tried_at: datetime | None = None

    def prepare(self, now: datetime) -> None:
        self.rebalance(now)

    def entries(self) -> tuple[Asset, ...]:
        return self._picks[: self.holdings_max]

    def select(self, now: datetime) -> tuple[Asset, ...] | None:
        if self._tried_at is not None and now - self._tried_at < timedelta(
            minutes=self.retry_minutes
        ):
            return None
        self._tried_at = now
        try:
            ranked = self._rank(now.date())
        except (httpx2.HTTPError, ValidationError) as error:
            self.portfolio.record(
                self,
                f"rank.failed.{now:%Y-%m-%dT%H:%M}",
                "warning",
                f"{self.name()} cannot rank: {type(error).__name__}; retrying in "
                f"{self.retry_minutes} min",
            )
            return None
        if not ranked:
            self.portfolio.record(
                self,
                f"rank.emptied.{now.date()}",
                "warning",
                f"{self.name()} found no stock with fundamentals in the universe",
            )
            return None
        return ranked

    def _rank(self, day: date) -> tuple[Asset, ...]:
        from mt.data.edgar import ciks, fundamentals

        universe = self.portfolio.assets()[: self.universe_size]
        if not universe:
            return ()
        tickers = ciks()
        facts = fundamentals(day)
        oldest = day - timedelta(days=self.fundamentals_max_age_days)
        scored: list[tuple[float, Asset]] = []
        for asset in universe:
            cik = tickers.get(asset.symbol)
            found = None if cik is None else facts.get(cik)
            if found is None or found.period_end < oldest:
                continue
            scored.append((found.gross_profitability, asset))
        scored = ranked(scored, symbol=lambda row: str(row[1]), turnover=lambda row: row[0])
        kept: list[tuple[float, Asset]] = []
        for row in scored:
            if industry(row[1], day) in self.excluded_industries:
                continue
            kept.append(row)
            if len(kept) == self.keep_rank:
                break
        if kept:
            picks = ", ".join(f"{asset} {score:.2f}" for score, asset in kept[: self.holdings_max])
            self.portfolio.record(
                self,
                f"rank.read.{day}",
                "info",
                f"{self.name()} ranked {len(scored)} of {len(universe)} stocks; picks: {picks}",
            )
        return tuple(asset for _, asset in kept)


class QualityGp(Quality):
    key = "quality_gp"
    code = "q"
