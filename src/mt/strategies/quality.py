from datetime import date, datetime, timedelta
from typing import ClassVar

import httpx
from pydantic import ValidationError

from mt.data.asset import Asset
from mt.data.company import industry

from .base import Candidate, Holding, Portfolio, Session, Strategy


class Quality(Strategy):
    universe_size: ClassVar[int]
    keep_rank: ClassVar[int]
    fundamentals_max_age_days: ClassVar[int]
    excluded_industries: ClassVar[tuple[str, ...]]
    entry_minutes: ClassVar[int]
    stop_fraction: ClassVar[float]
    retry_minutes: ClassVar[int]

    def __init__(self, portfolio: Portfolio) -> None:
        super().__init__(portfolio)
        self._month: tuple[int, int] | None = None
        self._ranked: tuple[Asset, ...] = ()
        self._tried_at: datetime | None = None

    @classmethod
    def entry_window(cls, opens: datetime, closes: datetime) -> tuple[datetime, datetime]:
        return min(closes, opens + timedelta(minutes=cls.entry_minutes)), closes

    def prepare(self, now: datetime) -> None:
        self._refresh(now)

    def run(self, session: Session) -> None:
        now = session.now
        start, until = self.entry_window(session.opens, session.closes)
        if not start <= now < until:
            return
        self._refresh(now)
        if self._month != (now.year, now.month):
            return
        for asset in self._ranked[: self.holdings_max]:
            if self.portfolio.is_taken(self, asset, now.date()):
                continue
            if self.is_capped(now):
                return
            price = self.price(asset)
            if price is None:
                continue
            candidate = Candidate(asset, price, price * (1 - self.stop_fraction))
            self.portfolio.enter(self, candidate, session)

    def manage(self, holding: Holding, session: Session) -> None:
        now = session.now
        price = self.price(holding.asset)
        if price is None:
            return
        holding.highest = max(holding.highest, price)
        if price <= holding.stop:
            self.portfolio.exit(holding, holding.stop_reason)
            return
        start, until = self.entry_window(session.opens, session.closes)
        if (
            start <= now < until
            and self._month == (now.year, now.month)
            and holding.asset not in self._ranked
        ):
            self.portfolio.exit(holding, "signal")

    def _refresh(self, now: datetime) -> None:
        if self._month == (now.year, now.month):
            return
        if self._tried_at is not None and now - self._tried_at < timedelta(
            minutes=self.retry_minutes
        ):
            return
        self._tried_at = now
        try:
            ranked = self._rank(now.date())
        except (httpx.HTTPError, ValidationError) as error:
            self.portfolio.record(
                self,
                f"rank.failed.{now:%Y-%m-%dT%H:%M}",
                "warning",
                f"{self.name()} cannot rank: {type(error).__name__}; retrying in "
                f"{self.retry_minutes} min",
            )
            return
        if not ranked:
            self.portfolio.record(
                self,
                f"rank.emptied.{now.date()}",
                "warning",
                f"{self.name()} found no stock with fundamentals in the universe",
            )
            return
        self._month, self._ranked = (now.year, now.month), ranked

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
        scored.sort(key=lambda row: (-row[0], str(row[1])))
        ranked: list[tuple[float, Asset]] = []
        for row in scored:
            if industry(row[1], day) in self.excluded_industries:
                continue
            ranked.append(row)
            if len(ranked) == self.keep_rank:
                break
        if ranked:
            picks = ", ".join(
                f"{asset} {score:.2f}" for score, asset in ranked[: self.holdings_max]
            )
            self.portfolio.record(
                self,
                f"rank.read.{day}",
                "info",
                f"{self.name()} ranked {len(scored)} of {len(universe)} stocks; picks: {picks}",
            )
        return tuple(asset for _, asset in ranked)


class QualityGp(Quality):
    key = "quality_gp"
    code = "q"
