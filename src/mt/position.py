from decimal import ROUND_DOWN, Decimal
from math import ceil, floor
from typing import Literal


type Direction = Literal[-1, 1]


def entry_quantity(
    equity: float,
    price: float,
    stop_distance: float,
    position_fraction_max: float,
    risk_fraction_max: float,
    notional_usd_min: float,
) -> Decimal:
    quantity = min(
        equity * position_fraction_max / price,
        equity * risk_fraction_max / stop_distance,
    )
    if quantity * price < notional_usd_min:
        return Decimal(0)
    return round_quantity(quantity)


def round_quantity(quantity: float) -> Decimal:
    return Decimal(str(quantity)).quantize(Decimal("1"), rounding=ROUND_DOWN)


def next_stop(direction: Direction, active: float, candidate: float) -> float:
    return max(active, candidate) if direction == 1 else min(active, candidate)


def round_stop(direction: Direction, stop: float) -> float:
    pennies = round(stop * 100.0, 6)
    return (floor(pennies) if direction == 1 else ceil(pennies)) / 100.0
