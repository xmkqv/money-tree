from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from bot.portfolio import Holding, Pending, Strategy


# BBD, 2026-08-26 09:47 ET: one 3031.01 share entry that Alpaca filled in nine pieces.
# The live bot attached its protective stop to the 25 share slice and left 3006 unguarded.
BBD_FILLS = [1440.0, 1364.0, 3.0, 125.0, 37.0, 33.0, 4.0, 25.0, 0.01]
BBD_TOTAL = sum(BBD_FILLS)
BBD_PRICE = 3.32
BBD_STOP = 3.28


@dataclass
class FakeAsset:
    symbol: str


@dataclass
class FakeOrder:
    asset: FakeAsset
    side: str
    quantity: Decimal | float
    avg_fill_price: float | None = None
    stop_price: float | None = None
    active: bool = True

    def is_active(self) -> bool:
        return self.active


@dataclass
class FakePosition:
    symbol: str
    qty: float

    @property
    def quantity(self) -> float:
        return self.qty


class FakeStrategy(Strategy):
    """A Strategy with every broker touchpoint stubbed, so the fill path can be replayed."""

    def __init__(self) -> None:  # noqa: D107 - deliberately bypasses StrategyBase.__init__
        self.parameters = {"fractional_orders": True}
        self._holdings = {}
        self._pending = {}
        self._claims = {}
        self._stops = {}
        self._closing = set()
        self._events = set()
        self.exporter = None
        self.filled = 0.0
        self.submitted: list[FakeOrder] = []
        self.slept = 0

    # --- broker stubs -------------------------------------------------
    def get_position(self, asset: str) -> FakePosition | None:
        return FakePosition(asset, self.filled) if self.filled > 0 else None

    def get_last_price(self, asset: str) -> float:
        return BBD_PRICE

    def get_orders(self) -> list[FakeOrder]:
        return [order for order in self.submitted if order.active]

    def cancel_open_orders(self, orders: list[FakeOrder]) -> None:
        for order in orders:
            order.active = False

    def sleep(self, seconds: float) -> None:
        self.slept += 1

    def create_order(self, asset: str, quantity: Any, side: str, **kwargs: Any) -> FakeOrder:
        return FakeOrder(FakeAsset(asset), side, quantity, stop_price=kwargs.get("stop_price"))

    def submit_order(self, order: FakeOrder) -> None:
        self.submitted.append(order)

    def _order_id(self, engine: str, kind: str, signal: str, risk: float) -> str:
        return f"mt-o-{signal}-{kind}-0-0"

    # --- helpers ------------------------------------------------------
    def resting_stop(self, asset: str) -> FakeOrder | None:
        stops = [
            order
            for order in self.submitted
            if order.active and order.asset.symbol == asset and order.stop_price is not None
        ]
        return stops[-1] if stops else None


def arrange_entry(strategy: FakeStrategy) -> Holding:
    holding = Holding(
        "orb",
        "BBD",
        "BBD",
        BBD_PRICE,
        BBD_STOP,
        BBD_PRICE - BBD_STOP,
        BBD_PRICE,
        datetime(2026, 8, 26, 13, 47, tzinfo=UTC),
        direction=1,
        lowest=BBD_PRICE,
    )
    strategy._pending["BBD"] = Pending(holding, holding.entered_at, BBD_TOTAL * BBD_PRICE)
    return holding


def replay_fills(strategy: FakeStrategy, fills: list[float]) -> None:
    """Deliver each partial fill the way lumibot does: one callback per slice."""
    for slice_quantity in fills:
        strategy.filled += slice_quantity
        order = FakeOrder(FakeAsset("BBD"), "buy", slice_quantity, avg_fill_price=BBD_PRICE)
        strategy.on_filled_order(
            FakePosition("BBD", strategy.filled), order, BBD_PRICE, slice_quantity, 1.0
        )


@pytest.fixture
def strategy() -> FakeStrategy:
    return FakeStrategy()


def test_stop_covers_whole_position_when_entry_fills_in_pieces(
    strategy: FakeStrategy,
) -> None:
    arrange_entry(strategy)

    replay_fills(strategy, BBD_FILLS)

    stop = strategy.resting_stop("BBD")
    assert stop is not None
    assert float(stop.quantity) == pytest.approx(BBD_TOTAL)


def test_original_quantity_is_the_whole_position_not_one_slice(
    strategy: FakeStrategy,
) -> None:
    arrange_entry(strategy)

    replay_fills(strategy, BBD_FILLS)

    assert strategy._holdings["BBD"].original_quantity == pytest.approx(BBD_TOTAL)


def test_scale_out_tranches_are_measured_against_the_whole_position(
    strategy: FakeStrategy,
) -> None:
    arrange_entry(strategy)

    replay_fills(strategy, BBD_FILLS)

    original = strategy._holdings["BBD"].original_quantity
    assert original * 0.5 == pytest.approx(BBD_TOTAL * 0.5)
    assert original * 0.25 == pytest.approx(BBD_TOTAL * 0.25)


def test_reconcile_resizes_a_stop_that_undercovers_the_position(
    strategy: FakeStrategy,
) -> None:
    holding = arrange_entry(strategy)
    strategy.filled = BBD_FILLS[0]
    replay_fills(strategy, [0.0])
    strategy.filled = BBD_TOTAL

    strategy._resync_stops({"BBD": FakePosition("BBD", BBD_TOTAL)})

    stop = strategy.resting_stop("BBD")
    assert stop is not None
    assert float(stop.quantity) == pytest.approx(BBD_TOTAL)
    assert holding.original_quantity == pytest.approx(BBD_TOTAL)


def test_reconcile_leaves_a_fully_covered_stop_alone(strategy: FakeStrategy) -> None:
    arrange_entry(strategy)
    replay_fills(strategy, BBD_FILLS)
    before = len(strategy.submitted)

    strategy._resync_stops({"BBD": FakePosition("BBD", BBD_TOTAL)})

    assert len(strategy.submitted) == before


def test_reconcile_does_not_inflate_original_quantity_after_a_scale_out(
    strategy: FakeStrategy,
) -> None:
    holding = arrange_entry(strategy)
    replay_fills(strategy, BBD_FILLS)
    holding.stage = 1
    remaining = BBD_TOTAL * 0.5

    strategy._resync_stops({"BBD": FakePosition("BBD", remaining)})

    assert holding.original_quantity == pytest.approx(BBD_TOTAL)


def test_entry_price_uses_the_order_average_not_a_single_slice(
    strategy: FakeStrategy,
) -> None:
    arrange_entry(strategy)
    order = FakeOrder(FakeAsset("BBD"), "buy", 1440.0, avg_fill_price=3.30)
    strategy.filled = BBD_TOTAL

    strategy.on_filled_order(FakePosition("BBD", BBD_TOTAL), order, 3.35, 1440.0, 1.0)

    assert strategy._holdings["BBD"].entry == pytest.approx(3.30)


def test_entry_price_falls_back_to_the_fill_price_without_an_average(
    strategy: FakeStrategy,
) -> None:
    arrange_entry(strategy)
    order = FakeOrder(FakeAsset("BBD"), "buy", 1440.0, avg_fill_price=None)
    strategy.filled = BBD_TOTAL

    strategy.on_filled_order(FakePosition("BBD", BBD_TOTAL), order, 3.35, 1440.0, 1.0)

    assert strategy._holdings["BBD"].entry == pytest.approx(3.35)
