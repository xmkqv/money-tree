from decimal import ROUND_DOWN, ROUND_UP, Decimal
from typing import Literal

from mt.rules.shared import settings


type Direction = Literal[-1, 1]


def entry_quantity(
    equity: float,
    price: float,
    stop_distance: float,
    direction: Direction,
) -> Decimal:
    risk = settings.risk
    per_trade = risk.per_day_max / risk.positions_max
    allocation = 1 / risk.positions_max
    capital, last, distance, allocation_d, per_trade_d, minimum, maximum = (
        Decimal(str(value))
        for value in (
            equity,
            price,
            stop_distance,
            allocation,
            per_trade,
            risk.notional_usd_min,
            risk.notional_usd_max,
        )
    )
    quantity = round_quantity(
        min(capital * allocation_d / last, capital * per_trade_d / distance, maximum / last),
        is_whole=direction == -1,
    )
    return quantity if quantity * last >= minimum else Decimal(0)


def round_quantity(quantity: float | Decimal, *, is_whole: bool = False) -> Decimal:
    precision = Decimal(1).scaleb(0 if is_whole else -settings.risk.quantity_decimal_places)
    return Decimal(str(quantity)).quantize(precision, rounding=ROUND_DOWN)


def next_stop(direction: Direction, active: float, candidate: float) -> float:
    return max(active, candidate) if direction == 1 else min(active, candidate)


def round_stop(direction: Direction, stop: float) -> float:
    rounding = ROUND_DOWN if direction == 1 else ROUND_UP
    return float(Decimal(str(stop)).quantize(Decimal("0.01"), rounding=rounding))
