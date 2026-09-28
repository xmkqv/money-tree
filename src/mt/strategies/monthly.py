from abc import abstractmethod
from datetime import datetime, timedelta
from typing import ClassVar

from mt.data.asset import Asset

from .base import Candidate, Holding, Portfolio, Session, Strategy


class Monthly(Strategy):
    entry_minutes: ClassVar[int]
    stop_fraction: ClassVar[float]

    def __init__(self, portfolio: Portfolio) -> None:
        super().__init__(portfolio)
        self._month: tuple[int, int] | None = None
        self._picks: tuple[Asset, ...] = ()

    @classmethod
    def entry_window(cls, opens: datetime, closes: datetime) -> tuple[datetime, datetime]:
        return min(closes, opens + timedelta(minutes=cls.entry_minutes)), closes

    @abstractmethod
    def select(self, now: datetime) -> tuple[Asset, ...] | None: ...

    def entries(self) -> tuple[Asset, ...]:
        return self._picks

    def rebalance(self, now: datetime) -> None:
        if self._month == (now.year, now.month):
            return
        picks = self.select(now)
        if picks is not None:
            self._month, self._picks = (now.year, now.month), picks

    def run(self, session: Session) -> None:
        now = session.now
        self.rebalance(now)
        if self._month != (now.year, now.month):
            return
        for asset in self.entries():
            if self.portfolio.is_taken(self, asset):
                continue
            if self.is_capped(now):
                return
            price = self.portfolio.quote(asset)
            if price is None:
                continue
            candidate = Candidate(asset, price, price * (1 - self.stop_fraction))
            self.portfolio.enter(self, candidate, session)

    def manage(self, holding: Holding, session: Session) -> None:
        now = session.now
        price = self.portfolio.quote(holding.asset)
        if price is None:
            return
        if price <= holding.stop:
            self.portfolio.exit(holding, holding.stop_reason)
            return
        start, until = self.entry_window(session.opens, session.closes)
        if (
            start <= now < until
            and self._month == (now.year, now.month)
            and holding.asset not in self._picks
        ):
            self.portfolio.exit(holding, "signal")
