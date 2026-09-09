from decimal import ROUND_DOWN, Decimal
from math import ceil, floor
from typing import Literal

from mt.config.settings import settings


type Direction = Literal[-1, 1]


def entry_quantity(
    equity: float,
    price: float,
    stop_distance: float,
    position_fraction_max: float,
    risk_fraction_max: float,
    notional_usd_min: float,
    direction: Direction = 1,
) -> Decimal:
    capital, last, distance, allocation, risk, minimum = map(
        lambda value: Decimal(str(value)),
        (equity, price, stop_distance, position_fraction_max, risk_fraction_max, notional_usd_min),
    )
    quantity = round_quantity(
        min(capital * allocation / last, capital * risk / distance), whole=direction == -1
    )
    return quantity if quantity * last >= minimum else Decimal(0)


def round_quantity(quantity: float | Decimal, *, whole: bool = False) -> Decimal:
    precision = Decimal(1).scaleb(0 if whole else -settings.risk.quantity_decimal_places)
    return Decimal(str(quantity)).quantize(precision, rounding=ROUND_DOWN)


def next_stop(direction: Direction, active: float, candidate: float) -> float:
    return max(active, candidate) if direction == 1 else min(active, candidate)


def round_stop(direction: Direction, stop: float) -> float:
    pennies = round(stop * 100.0, 6)
    return (floor(pennies) if direction == 1 else ceil(pennies)) / 100.0
