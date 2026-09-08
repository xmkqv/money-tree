from decimal import ROUND_DOWN, Decimal
from math import ceil, floor, isfinite
from typing import Literal


type Direction = Literal[-1, 1]


def entry_quantity(
    equity: float,
    price: float,
    stop_distance: float,
    position_fraction_max: float,
    risk_per_trade_max: float | None,
    notional_usd_min: float,
    is_fractional: bool,
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
    if quantity * price < notional_usd_min:
        return Decimal(0)
    return round_quantity(quantity, is_fractional)


def round_quantity(quantity: float, is_fractional: bool) -> Decimal:
    increment = Decimal("0.000000001" if is_fractional else "1")
    return Decimal(str(quantity)).quantize(increment, rounding=ROUND_DOWN)


def is_fractional_allowed(direction: Direction, does_allow_fractions: bool) -> bool:
    return does_allow_fractions and direction == 1


def next_stop(direction: Direction, active: float, candidate: float) -> float:
    return max(active, candidate) if direction == 1 else min(active, candidate)


def round_stop(direction: Direction, stop: float) -> float:
    pennies = round(stop * 100.0, 6)
    return (floor(pennies) if direction == 1 else ceil(pennies)) / 100.0
