from __future__ import annotations

import argparse
import os
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from math import isfinite
from typing import cast
from zoneinfo import ZoneInfo

import numpy as np
from alpaca.common.enums import Sort
from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.models import BarSet
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetCalendarRequest
from numpy.typing import NDArray

INSTRUMENTS = ("AAPL", "MSFT", "JPM", "XOM", "WMT")
MARKET_TIMEZONE = ZoneInfo("America/New_York")
SESSION_STARTED_ON_DEFAULT = date(2016, 1, 1)
SESSION_ENDED_BEFORE_DEFAULT = date(2026, 8, 1)
DECISION_START = time(9, 45)
DECISION_END = time(15, 45)
DECISION_INTERVAL = timedelta(minutes=15)
EXECUTION_DELAY = timedelta(minutes=1)
USD_NOTIONAL = 10.0
N_SESSION_MIN = 60
USD_SPREAD = 0.03
RATE_COMMISSION = 0.0
RATE_SECTION_31 = 0.0000206
USD_FINRA_TAF_PER_SHARE = 0.000195
USD_CAT_PER_SHARE = 0.000003
USD_CENT = 0.01

type FloatArray = NDArray[np.float64]
type IntArray = NDArray[np.int64]


@dataclass(frozen=True, slots=True)
class SessionRange:
    started_on: date
    ended_before: date


@dataclass(frozen=True, slots=True)
class AlpacaCredentials:
    api_key: str
    api_secret: str


@dataclass(frozen=True, slots=True)
class BarClose:
    closed_at: datetime
    price: float


@dataclass(frozen=True, slots=True)
class MarketObservations:
    instrument: str
    session_range: SessionRange
    session_dates: tuple[date, ...]
    decision_prices: FloatArray
    execution_prices: FloatArray
    n_excluded_session: int


@dataclass(frozen=True, slots=True)
class OrderBatch:
    directions: FloatArray


@dataclass(frozen=True, slots=True)
class ExplicitCosts:
    commission_by_session: FloatArray
    section_31_by_session: FloatArray
    finra_taf_by_session: FloatArray
    cat_by_session: FloatArray

    @property
    def by_session(self) -> FloatArray:
        return (
            self.commission_by_session
            + self.section_31_by_session
            + self.finra_taf_by_session
            + self.cat_by_session
        )

    @property
    def total(self) -> float:
        return float(self.by_session.sum())


@dataclass(frozen=True, slots=True)
class RoundTripResult:
    n_round_trip_by_session: IntArray
    share_quantity_by_session: FloatArray
    absolute_price_moves: FloatArray
    execution_costs: FloatArray
    explicit_costs: ExplicitCosts

    @property
    def n_round_trip(self) -> int:
        return int(self.n_round_trip_by_session.sum())


@dataclass(frozen=True, slots=True)
class ResearchStudy:
    observations: MarketObservations
    momentum: Mapping[timedelta, RoundTripResult]


def parse_session_range(program: str) -> SessionRange:
    parser = argparse.ArgumentParser(prog=program)
    parser.add_argument(
        "--start",
        type=date.fromisoformat,
        default=SESSION_STARTED_ON_DEFAULT,
    )
    parser.add_argument(
        "--end",
        type=date.fromisoformat,
        default=SESSION_ENDED_BEFORE_DEFAULT,
    )
    arguments = parser.parse_args()
    started_on = cast(date, arguments.start)
    ended_before = cast(date, arguments.end)
    if ended_before <= started_on:
        raise ValueError("end must follow start")
    return SessionRange(started_on, ended_before)


def load_alpaca_credentials() -> AlpacaCredentials:
    api_key = os.environ.get("ALPACA_API_KEY")
    api_secret = os.environ.get("ALPACA_API_SECRET")
    if not api_key or not api_secret:
        raise RuntimeError("missing ALPACA_API_KEY or ALPACA_API_SECRET")
    return AlpacaCredentials(api_key, api_secret)


def observe_bar_closes(
    instrument: str,
    session_range: SessionRange,
    credentials: AlpacaCredentials,
) -> list[BarClose]:
    client = StockHistoricalDataClient(credentials.api_key, credentials.api_secret)
    request = StockBarsRequest(
        symbol_or_symbols=instrument,
        start=datetime.combine(session_range.started_on, time(), MARKET_TIMEZONE),
        end=datetime.combine(session_range.ended_before, time(), MARKET_TIMEZONE),
        timeframe=TimeFrame.Minute,
        adjustment=Adjustment.RAW,
        feed=DataFeed.SIP,
        asof=session_range.ended_before.isoformat(),
        sort=Sort.ASC,
    )
    response = cast(BarSet, client.get_stock_bars(request))
    bars = response.data.get(instrument)
    if not bars:
        raise RuntimeError(f"alpaca returned no {instrument} bars")
    closes: list[BarClose] = []
    for bar in bars:
        close = BarClose(
            bar.timestamp.astimezone(MARKET_TIMEZONE) + EXECUTION_DELAY,
            float(bar.close),
        )
        if not isfinite(close.price) or close.price <= 0:
            raise RuntimeError(f"alpaca returned an invalid {instrument} price")
        if closes and close.closed_at <= closes[-1].closed_at:
            raise RuntimeError(f"alpaca returned unordered {instrument} bars")
        closes.append(close)
    return closes


def observe_session_dates(
    session_range: SessionRange,
    credentials: AlpacaCredentials,
) -> tuple[date, ...]:
    client = TradingClient(credentials.api_key, credentials.api_secret)
    request = GetCalendarRequest(
        start=session_range.started_on,
        end=session_range.ended_before - timedelta(days=1),
    )
    return tuple(session.date for session in client.get_calendar(request))


def iter_decision_times(session_date: date) -> Iterator[datetime]:
    decided_at = datetime.combine(session_date, DECISION_START, MARKET_TIMEZONE)
    ended_at = datetime.combine(session_date, DECISION_END, MARKET_TIMEZONE)
    while decided_at <= ended_at:
        yield decided_at
        decided_at += DECISION_INTERVAL


def observe_market(
    instrument: str,
    session_range: SessionRange,
    closes: Iterable[BarClose],
    expected_session_dates: Iterable[date],
) -> MarketObservations:
    prices_by_date: dict[date, dict[datetime, float]] = {}
    for close in closes:
        prices_by_time = prices_by_date.setdefault(close.closed_at.date(), {})
        if close.closed_at in prices_by_time:
            raise RuntimeError(f"duplicate bar close at {close.closed_at.isoformat()}")
        prices_by_time[close.closed_at] = close.price
    session_dates: list[date] = []
    decision_prices: list[list[float]] = []
    execution_prices: list[list[float]] = []
    n_excluded_session = 0
    expected_dates = tuple(expected_session_dates)
    if expected_dates != tuple(sorted(set(expected_dates))):
        raise RuntimeError("expected session dates must be unique and ordered")
    for session_date in expected_dates:
        prices_by_time = prices_by_date.get(session_date, {})
        decision_times = tuple(iter_decision_times(session_date))
        if any(
            decided_at not in prices_by_time or decided_at + EXECUTION_DELAY not in prices_by_time
            for decided_at in decision_times
        ):
            n_excluded_session += 1
            continue
        session_dates.append(session_date)
        decision_prices.append([prices_by_time[decided_at] for decided_at in decision_times])
        execution_prices.append(
            [prices_by_time[decided_at + EXECUTION_DELAY] for decided_at in decision_times]
        )
    n_decision = len(tuple(iter_decision_times(session_range.started_on)))
    return MarketObservations(
        instrument,
        session_range,
        tuple(session_dates),
        np.asarray(decision_prices, dtype=np.float64).reshape(-1, n_decision),
        np.asarray(execution_prices, dtype=np.float64).reshape(-1, n_decision),
        n_excluded_session,
    )


def round_fee_by_session(values: FloatArray) -> FloatArray:
    cents = np.nextafter(values / USD_CENT, -np.inf)
    return np.ceil(cents) * USD_CENT


def calculate_explicit_costs(
    sell_value_by_session: FloatArray,
    sell_share_by_session: FloatArray,
    executed_share_by_session: FloatArray,
) -> ExplicitCosts:
    return ExplicitCosts(
        round_fee_by_session(RATE_COMMISSION * sell_value_by_session),
        round_fee_by_session(RATE_SECTION_31 * sell_value_by_session),
        round_fee_by_session(USD_FINRA_TAF_PER_SHARE * sell_share_by_session),
        round_fee_by_session(USD_CAT_PER_SHARE * executed_share_by_session),
    )


def execute_orders(
    observations: MarketObservations,
    orders: OrderBatch,
) -> RoundTripResult:
    entry_decision_prices = observations.decision_prices[:, 1:-1]
    flatten_decision_prices = observations.decision_prices[:, 2:]
    entry_execution_prices = observations.execution_prices[:, 1:-1]
    flatten_execution_prices = observations.execution_prices[:, 2:]
    active = orders.directions != 0
    share_quantities = np.where(active, USD_NOTIONAL / entry_decision_prices, 0.0)
    entry_fill_prices = entry_execution_prices + orders.directions * USD_SPREAD / 2
    flatten_fill_prices = flatten_execution_prices - orders.directions * USD_SPREAD / 2
    decision_outcomes = (
        share_quantities * orders.directions * (flatten_decision_prices - entry_decision_prices)
    )
    fill_outcomes = share_quantities * orders.directions * (flatten_fill_prices - entry_fill_prices)
    absolute_price_moves = share_quantities * np.abs(
        flatten_decision_prices - entry_decision_prices
    )
    execution_costs = decision_outcomes - fill_outcomes
    sell_values = share_quantities * np.where(
        orders.directions > 0,
        flatten_fill_prices,
        entry_fill_prices,
    )
    n_round_trip_by_session = active.sum(axis=1, dtype=np.int64)
    share_quantity_by_session = share_quantities.sum(axis=1)
    sell_value_by_session = np.where(active, sell_values, 0).sum(axis=1)
    return RoundTripResult(
        n_round_trip_by_session,
        share_quantity_by_session,
        absolute_price_moves[active],
        execution_costs[active],
        calculate_explicit_costs(
            sell_value_by_session,
            share_quantity_by_session,
            2 * share_quantity_by_session,
        ),
    )


def decide_momentum_orders(observations: MarketObservations) -> OrderBatch:
    return OrderBatch(
        np.sign(observations.decision_prices[:, 1:-1] - observations.decision_prices[:, :-2])
    )


def build_research_study(
    instrument: str,
    session_range: SessionRange,
    credentials: AlpacaCredentials,
    expected_session_dates: tuple[date, ...],
) -> ResearchStudy:
    observations = observe_market(
        instrument,
        session_range,
        observe_bar_closes(instrument, session_range, credentials),
        expected_session_dates,
    )
    if len(observations.session_dates) < N_SESSION_MIN:
        raise RuntimeError(f"research requires at least {N_SESSION_MIN} complete sessions")
    return ResearchStudy(
        observations,
        {DECISION_INTERVAL: execute_orders(observations, decide_momentum_orders(observations))},
    )


def build_research_studies(session_range: SessionRange) -> tuple[ResearchStudy, ...]:
    credentials = load_alpaca_credentials()
    expected_session_dates = observe_session_dates(session_range, credentials)
    return tuple(
        build_research_study(
            instrument,
            session_range,
            credentials,
            expected_session_dates,
        )
        for instrument in INSTRUMENTS
    )
