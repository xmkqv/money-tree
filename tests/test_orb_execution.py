from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from bot.portfolio import Holding, Strategy


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
