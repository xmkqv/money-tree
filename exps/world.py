from __future__ import annotations

import argparse
import os
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import cast
from zoneinfo import ZoneInfo

import numpy as np
from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.models import BarSet
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from numpy.typing import NDArray

INSTRUMENT = "AAPL"
MARKET_TIMEZONE = ZoneInfo("America/New_York")
SESSION_STARTED_ON_DEFAULT = date(2025, 8, 1)
SESSION_ENDED_BEFORE_DEFAULT = date(2026, 8, 1)
DECISION_START = time(9, 45)
DECISION_END = time(15, 45)
DECISION_INTERVAL = timedelta(minutes=15)
EXECUTION_DELAY = timedelta(minutes=1)
N_SHARE = 1.0
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


def observe_bar_closes(session_range: SessionRange) -> list[BarClose]:
    credentials = load_alpaca_credentials()
    client = StockHistoricalDataClient(credentials.api_key, credentials.api_secret)
    request = StockBarsRequest(
        symbol_or_symbols=INSTRUMENT,
        start=datetime.combine(session_range.started_on, time(), MARKET_TIMEZONE),
        end=datetime.combine(session_range.ended_before, time(), MARKET_TIMEZONE),
        timeframe=TimeFrame.Minute,
        adjustment=Adjustment.ALL,
        feed=DataFeed.SIP,
    )
    response = cast(BarSet, client.get_stock_bars(request))
    bars = response.data.get(INSTRUMENT)
    if not bars:
        raise RuntimeError(f"alpaca returned no {INSTRUMENT} bars")
    return [
        BarClose(
            bar.timestamp.astimezone(MARKET_TIMEZONE) + EXECUTION_DELAY,
            float(bar.close),
        )
        for bar in bars
    ]


def iter_decision_times(session_date: date) -> Iterator[datetime]:
    decided_at = datetime.combine(session_date, DECISION_START, MARKET_TIMEZONE)
    ended_at = datetime.combine(session_date, DECISION_END, MARKET_TIMEZONE)
    while decided_at <= ended_at:
        yield decided_at
        decided_at += DECISION_INTERVAL


def observe_market(
    session_range: SessionRange,
    closes: Iterable[BarClose],
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
    for session_date in sorted(prices_by_date):
        prices_by_time = prices_by_date[session_date]
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
    n_round_trip_by_session: IntArray,
) -> ExplicitCosts:
    n_sell_share = n_round_trip_by_session.astype(np.float64) * N_SHARE
    n_executed_share = 2 * n_sell_share
    return ExplicitCosts(
        round_fee_by_session(RATE_COMMISSION * sell_value_by_session),
        round_fee_by_session(RATE_SECTION_31 * sell_value_by_session),
        round_fee_by_session(USD_FINRA_TAF_PER_SHARE * n_sell_share),
        round_fee_by_session(USD_CAT_PER_SHARE * n_executed_share),
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
    entry_fill_prices = entry_execution_prices + orders.directions * USD_SPREAD / 2
    flatten_fill_prices = flatten_execution_prices - orders.directions * USD_SPREAD / 2
    decision_outcomes = (
        N_SHARE * orders.directions * (flatten_decision_prices - entry_decision_prices)
    )
    fill_outcomes = N_SHARE * orders.directions * (flatten_fill_prices - entry_fill_prices)
    absolute_price_moves = N_SHARE * np.abs(flatten_decision_prices - entry_decision_prices)
    execution_costs = decision_outcomes - fill_outcomes
    sell_values = N_SHARE * np.where(
        orders.directions > 0,
        flatten_fill_prices,
        entry_fill_prices,
    )
    n_round_trip_by_session = active.sum(axis=1, dtype=np.int64)
    sell_value_by_session = np.where(active, sell_values, 0).sum(axis=1)
    return RoundTripResult(
        n_round_trip_by_session,
        absolute_price_moves[active],
        execution_costs[active],
        calculate_explicit_costs(sell_value_by_session, n_round_trip_by_session),
    )


def decide_momentum_orders(observations: MarketObservations) -> OrderBatch:
    return OrderBatch(
        np.sign(observations.decision_prices[:, 1:-1] - observations.decision_prices[:, :-2])
    )


def build_research_study(session_range: SessionRange) -> ResearchStudy:
    observations = observe_market(session_range, observe_bar_closes(session_range))
    if len(observations.session_dates) < N_SESSION_MIN:
        raise RuntimeError(f"research requires at least {N_SESSION_MIN} complete sessions")
    return ResearchStudy(
        observations,
        {DECISION_INTERVAL: execute_orders(observations, decide_momentum_orders(observations))},
    )
