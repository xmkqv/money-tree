import inspect
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_DOWN, Decimal
from typing import Any

import pytest

from bot.portfolio import Holding, Strategy
from bot.strategies.shared import entry_quantity, fractional_allowed


@dataclass
class FakeAsset:
    symbol: str


@dataclass
class FakeOrder:
    asset: FakeAsset
    side: str
    quantity: Decimal | float
    client_order_id: str = ""
    stop_price: float | None = None
    active: bool = True

    def is_active(self) -> bool:
        return self.active


class CancelStrategy(Strategy):
    """Exercises _cancel and _protect without a broker."""

    def __init__(self, resting: list[FakeOrder]) -> None:
        self.parameters = {"fractional_orders": True}
        self._holdings = {}
        self._stops = {}
        self._closing = set()
        self._events = set()
        self.exporter = None
        self.resting = resting
        self.submitted: list[FakeOrder] = []
        self.position = 0.0

    def get_orders(self) -> list[FakeOrder]:
        return [order for order in self.resting if order.active]

    def cancel_open_orders(self, orders: list[FakeOrder]) -> None:
        for order in orders:
            order.active = False

    def sleep(self, seconds: float) -> None:
        return None

    def get_last_price(self, asset: str) -> float:
        return 10.0

    def get_position(self, asset: str) -> Any:
        return None

    def _quantity(self, asset: str) -> float:
        return self.position

    def create_order(self, asset: str, quantity: Any, side: str, **kwargs: Any) -> FakeOrder:
        return FakeOrder(
            FakeAsset(asset),
            side,
            quantity,
            client_order_id=kwargs.get("custom_params", {}).get("client_order_id", ""),
            stop_price=kwargs.get("stop_price"),
        )

    def submit_order(self, order: FakeOrder) -> None:
        self.submitted.append(order)
        self.resting.append(order)


def holding_for(asset: str = "BBD") -> Holding:
    return Holding(
        "orb",
        asset,
        asset,
        10.0,
        9.5,
        0.5,
        10.0,
        datetime(2026, 8, 26, 13, 47, tzinfo=UTC),
        direction=1,
        original_quantity=1000.0,
        lowest=10.0,
    )


# --- shorts settle in whole shares ----------------------------------------


def short_holding(asset: str = "BBD", original: float = 23.0) -> Holding:
    return Holding(
        "orb",
        asset,
        asset,
        10.0,
        10.5,
        0.5,
        10.0,
        datetime(2026, 8, 26, 13, 47, tzinfo=UTC),
        direction=-1,
        original_quantity=original,
        lowest=10.0,
    )


def test_fractional_allowed_only_ever_applies_to_a_long() -> None:
    assert fractional_allowed(1, True) is True
    assert fractional_allowed(1, False) is False
    assert fractional_allowed(-1, True) is False, "a broker lends shares, not fractions"
    assert fractional_allowed(-1, False) is False


def test_a_short_entry_is_sized_in_whole_shares() -> None:
    """Same equity and stop, opposite directions: only the long keeps a fraction."""
    arguments = (100_000.0, 425.80, 5.0, 0.10, 0.01)

    long_size = entry_quantity(*arguments, fractional_allowed(1, True))
    short_size = entry_quantity(*arguments, fractional_allowed(-1, True))

    assert long_size != long_size.to_integral_value(), "the long may hold a fraction"
    assert short_size == short_size.to_integral_value(), "the short may not"
    assert short_size == long_size.to_integral_value(rounding=ROUND_DOWN)


def test_a_short_stop_order_covers_whole_shares() -> None:
    strategy = CancelStrategy([])
    strategy.position = 23.4802
    strategy.parameters = {"fractional_orders": True}

    strategy._protect(short_holding(), 23.4802)

    quantity = Decimal(str(strategy.submitted[-1].quantity))
    assert strategy.submitted[-1].side == "buy", "a short is protected by a buy stop"
    assert quantity == Decimal(23)


def test_a_short_scale_out_rounds_down_and_never_strips_the_stop() -> None:
    """A scale-out worth under a whole share is skipped, stop left in place."""
    stop = FakeOrder(
        FakeAsset("BBD"), "buy", 3.0, client_order_id="mt-o-s-BBD-11672-bbbbbbbb", stop_price=10.5
    )
    strategy = CancelStrategy([stop])
    strategy.position = 3.0
    strategy.parameters = {"fractional_orders": True}

    # A quarter of a three-share short is 0.75 — less than one whole share.
    strategy._exit(short_holding(original=3.0), 0.75)

    assert not strategy.submitted, "no zero-quantity order may be sent"
    assert stop.active, "the resting stop must survive a skipped scale-out"


def test_a_long_scale_out_keeps_its_fraction() -> None:
    strategy = CancelStrategy([])
    strategy.position = 1000.0
    strategy.parameters = {"fractional_orders": True}

    strategy._exit(holding_for(), 500.5)

    assert Decimal(str(strategy.submitted[-1].quantity)) == Decimal("500.5")


# --- C4: _protect must not cancel a still-working entry order -------------


def test_protect_leaves_a_working_entry_order_alone() -> None:
    entry = FakeOrder(FakeAsset("BBD"), "buy", 3031.0, client_order_id="mt-o-e-BBD-11672-aaaaaaaa")
    strategy = CancelStrategy([entry])
    strategy.position = 1440.0

    strategy._protect(holding_for(), 1440.0)

    assert entry.active, "the unfilled remainder of the entry order was cancelled"


def test_protect_still_replaces_an_existing_stop() -> None:
    entry = FakeOrder(FakeAsset("BBD"), "buy", 3031.0, client_order_id="mt-o-e-BBD-11672-aaaaaaaa")
    stop = FakeOrder(
        FakeAsset("BBD"), "sell", 25.0, client_order_id="mt-o-s-BBD-11672-bbbbbbbb", stop_price=9.5
    )
    strategy = CancelStrategy([entry, stop])
    strategy.position = 3031.0

    strategy._protect(holding_for(), 3031.0)

    assert not stop.active, "the undersized stop should have been replaced"
    assert entry.active
    assert float(strategy.submitted[-1].quantity) == pytest.approx(3031.0)


def test_cancel_without_a_kind_still_clears_everything() -> None:
    entry = FakeOrder(FakeAsset("BBD"), "buy", 3031.0, client_order_id="mt-o-e-BBD-11672-aaaaaaaa")
    stop = FakeOrder(
        FakeAsset("BBD"), "sell", 25.0, client_order_id="mt-o-s-BBD-11672-bbbbbbbb", stop_price=9.5
    )
    strategy = CancelStrategy([entry, stop])

    strategy._cancel("BBD")

    assert not entry.active
    assert not stop.active


def test_cancel_ignores_other_symbols() -> None:
    mine = FakeOrder(
        FakeAsset("BBD"), "sell", 25.0, client_order_id="mt-o-s-BBD-11672-bbbbbbbb", stop_price=9.5
    )
    other = FakeOrder(
        FakeAsset("NKE"), "sell", 10.0, client_order_id="mt-o-s-NKE-11672-cccccccc", stop_price=9.5
    )
    strategy = CancelStrategy([mine, other])

    strategy._cancel("BBD", "s")

    assert not mine.active
    assert other.active


def test_order_kind_reads_the_kind_segment() -> None:
    strategy = CancelStrategy([])

    assert strategy._order_kind("mt-o-s-BBD-11672-bbbbbbbb") == "s"
    assert strategy._order_kind("mt-o-e-BBD-11672-aaaaaaaa") == "e"
    assert strategy._order_kind("mt-o-x-BBD-11672-dddddddd") == "x"
    assert strategy._order_kind("not-a-money-tree-id") is None
    assert strategy._order_kind("") is None


# --- C7: ORB's own risk cap governs its sizing ----------------------------


# A $50 stock with the stop $6 away (12%), so the risk cap binds and the
# notional cap does not:
#   notional cap        100_000 * 0.10 / 50 = 200.00 shares
#   risk cap at 0.005   100_000 * 0.005 / 6 =  83.33 shares  <- the old behaviour
#   risk cap at 0.010   100_000 * 0.010 / 6 = 166.67 shares  <- what the register asks for
WIDE_PRICE = 50.0
WIDE_STOP = 44.0
EQUITY = 100_000.0


class FakeAccount:
    portfolio_value = EQUITY


class FakeApi:
    def get_account(self) -> FakeAccount:
        return FakeAccount()

    def get_all_positions(self) -> list[Any]:
        return []


class FakeBroker:
    api = FakeApi()


class SizingStrategy(Strategy):
    """Drives the real _enter so the risk cap is exercised, not reimplemented."""

    def __init__(self, risk_per_trade_max: float) -> None:
        self.parameters = {
            "fractional_orders": True,
            "position_fraction_max": 0.10,
            "risk_per_trade_max": risk_per_trade_max,
        }
        self._enabled = {"orb", "sma"}
        self._holdings = {}
        self._pending = {}
        self._claims = {}
        self._stops = {}
        self._closing = set()
        self._events = set()
        self._orb_traded = set()
        self._orb_scanned = set()
        self.exporter = None
        self.broker = FakeBroker()
        self.submitted: list[FakeOrder] = []

    def create_order(self, asset: str, quantity: Any, side: str, **kwargs: Any) -> FakeOrder:
        return FakeOrder(
            FakeAsset(asset),
            side,
            quantity,
            client_order_id=kwargs.get("custom_params", {}).get("client_order_id", ""),
        )

    def submit_order(self, order: FakeOrder) -> None:
        self.submitted.append(order)


def enter_wide_stop(strategy: SizingStrategy, engine: str, own_cap: float | None) -> float:
    accepted = strategy._enter(
        engine,
        "WIDE",
        "WIDE",
        WIDE_PRICE,
        WIDE_STOP,
        datetime(2026, 8, 26, 13, 50, tzinfo=UTC),
        risk_fraction_max=own_cap,
    )
    assert accepted
    return float(strategy.submitted[-1].quantity)


def test_orb_uses_its_own_risk_cap_not_the_tighter_global() -> None:
    strategy = SizingStrategy(risk_per_trade_max=0.005)

    quantity = enter_wide_stop(strategy, "orb", 0.01)

    assert quantity == pytest.approx(EQUITY * 0.01 / (WIDE_PRICE - WIDE_STOP), rel=1e-6)


def test_strategies_without_their_own_cap_keep_the_global() -> None:
    strategy = SizingStrategy(risk_per_trade_max=0.005)

    quantity = enter_wide_stop(strategy, "sma", None)

    assert quantity == pytest.approx(EQUITY * 0.005 / (WIDE_PRICE - WIDE_STOP), rel=1e-6)


def test_the_notional_cap_still_wins_when_the_stop_is_close() -> None:
    strategy = SizingStrategy(risk_per_trade_max=0.005)

    accepted = strategy._enter(
        "orb",
        "TIGHT",
        "TIGHT",
        WIDE_PRICE,
        WIDE_PRICE - 0.10,
        datetime(2026, 8, 26, 13, 50, tzinfo=UTC),
        risk_fraction_max=0.01,
    )

    assert accepted
    assert float(strategy.submitted[-1].quantity) == pytest.approx(EQUITY * 0.10 / WIDE_PRICE)


# --- C6: one ORB entry per symbol per day, across both breakout engines ---


class TradedStrategy(SizingStrategy):
    """SizingStrategy with both breakout engines enabled."""

    def __init__(self, risk_per_trade_max: float = 0.005) -> None:
        super().__init__(risk_per_trade_max)
        self._enabled = {"orb", "orb_momentum", "sma"}


def enter(strategy: TradedStrategy, engine: str, symbol: str) -> bool:
    return strategy._enter(
        engine,
        symbol,
        symbol,
        WIDE_PRICE,
        WIDE_PRICE - 0.10,
        datetime(2026, 8, 25, 13, 50, tzinfo=UTC),
        risk_fraction_max=0.01 if engine == "orb" else None,
    )


def test_a_filled_entry_is_recorded_against_the_symbol_and_day() -> None:
    strategy = TradedStrategy()

    assert enter(strategy, "orb", "AUR")

    assert (datetime(2026, 8, 25, 13, 50, tzinfo=UTC).date(), "AUR") in strategy._orb_traded


def test_the_scan_skips_a_symbol_already_traded_today() -> None:
    """ORB-10m re-entered AUR 51s after ORB-5m stopped out of it on 2026-08-25.

    The ledger is keyed by (day, symbol) with no engine, so one breakout engine
    entering a name closes it to the other for the rest of the session.
    """
    source = inspect.getsource(Strategy._run_orb_variant)

    assert "(now.date(), symbol) in self._orb_traded" in source
    assert "self._orb_traded: set[tuple[date, str]]" in inspect.getsource(Strategy.initialize)


def test_a_position_restored_mid_session_still_blocks_re_entry() -> None:
    assert "self._orb_traded.add(" in inspect.getsource(Strategy._restore)


def test_the_daily_engines_do_not_write_to_the_traded_ledger() -> None:
    strategy = TradedStrategy()
    strategy._enabled = {"sma"}

    assert strategy._enter(
        "sma",
        "CCK",
        "CCK",
        WIDE_PRICE,
        WIDE_PRICE - 0.10,
        datetime(2026, 8, 25, 13, 50, tzinfo=UTC),
    )

    assert strategy._orb_traded == set()
