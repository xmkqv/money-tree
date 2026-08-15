from __future__ import annotations

from decimal import ROUND_DOWN, Decimal

from money_tree.model import Direction, PositionState

USD_LOSS_PLANNED_MAX = Decimal("0.80")
USD_LOSS_SESSION_MAX = Decimal("1.00")
QUANTITY_STEP = Decimal("0.000000001")


def floor_price(value: float, usd_price_tick: float) -> float:
    if value <= 0 or usd_price_tick <= 0:
        raise ValueError("price and price tick must be positive")
    tick = Decimal(str(usd_price_tick))
    units = (Decimal(str(value)) / tick).to_integral_value(rounding=ROUND_DOWN)
    return float(units * tick)


def size_long_position(
    portfolio_value: Decimal,
    entry_price: Decimal,
    position_fraction: Decimal,
    quantity_step: Decimal = Decimal("1"),
) -> Decimal:
    if portfolio_value <= 0 or entry_price <= 0 or quantity_step <= 0:
        raise ValueError("portfolio value, entry price, and quantity step must be positive")
    if not Decimal("0") < position_fraction <= Decimal("1"):
        raise ValueError("position fraction must be greater than zero and at most one")
    return (portfolio_value * position_fraction / entry_price).quantize(
        quantity_step,
        rounding=ROUND_DOWN,
    )


def size_position(
    entry_price: Decimal,
    protective_stop_price: Decimal,
    direction: Direction,
    loss_limit: Decimal = USD_LOSS_PLANNED_MAX,
) -> Decimal:
    price_risk = abs(entry_price - protective_stop_price)
    if entry_price <= 0 or protective_stop_price <= 0:
        raise ValueError("entry and protective stop prices must be positive")
    if price_risk == 0:
        raise ValueError("entry and protective stop prices must differ")
    if loss_limit <= 0:
        raise ValueError("loss limit must be positive")
    if direction is Direction.FLAT:
        raise ValueError("a flat direction cannot open a position")
    quantity = loss_limit / price_risk
    if direction is Direction.SHORT:
        return quantity.quantize(Decimal("1"), rounding=ROUND_DOWN)
    return quantity.quantize(QUANTITY_STEP, rounding=ROUND_DOWN)


def has_reached_loss_limit(
    position: PositionState,
    mark_price: Decimal,
    loss_limit: Decimal = USD_LOSS_SESSION_MAX,
) -> bool:
    if mark_price <= 0:
        raise ValueError("mark price must be positive")
    if loss_limit <= 0:
        raise ValueError("loss limit must be positive")
    return position.calculate_profit_and_loss(mark_price) <= -loss_limit
