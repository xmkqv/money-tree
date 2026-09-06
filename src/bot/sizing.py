from decimal import ROUND_DOWN, Decimal
from math import ceil, floor, isfinite

from .config import settings
from .types import Direction


def entry_quantity(
    equity: float,
    price: float,
    stop_distance: float,
    position_fraction_max: float,
    risk_per_trade_max: float | None,
    fractional_orders: bool,
) -> Decimal:
    if (
        not all(isfinite(value) for value in (equity, price, stop_distance))
        or equity <= 0
        or price <= 0
        or stop_distance <= 0
    ):
        return Decimal(0)
    quantity = equity * position_fraction_max / price
    if risk_per_trade_max is not None:
        quantity = min(quantity, equity * risk_per_trade_max / stop_distance)
    if quantity * price < settings.risk.notional_usd_min:
        return Decimal(0)
    return quantity_value(quantity, fractional_orders)


def quantity_value(quantity: float, fractional_orders: bool) -> Decimal:
    increment = Decimal("0.000000001" if fractional_orders else "1")
    return Decimal(str(quantity)).quantize(increment, rounding=ROUND_DOWN)


def is_fractional_allowed(direction: Direction, fractional_orders: bool) -> bool:
    return fractional_orders and direction == 1


def next_stop(direction: Direction, active: float, candidate: float) -> float:
    return max(active, candidate) if direction == 1 else min(active, candidate)


def round_stop(direction: Direction, stop: float) -> float:
    pennies = round(stop * 100.0, 6)
    return (floor(pennies) if direction == 1 else ceil(pennies)) / 100.0
