from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_DOWN, Decimal

from money_tree.orb import BreakoutSide

PLANNED_LOSS = Decimal("0.80")
DAILY_LOSS = Decimal("1.00")
QUANTITY_STEP = Decimal("0.000000001")


def size_position(
    entry_price: Decimal,
    stop_price: Decimal,
    side: BreakoutSide,
    loss: Decimal = PLANNED_LOSS,
) -> Decimal:
    price_risk = abs(entry_price - stop_price)
    if entry_price <= 0 or stop_price <= 0:
        raise ValueError("entry and stop prices must be positive")
    if price_risk == 0:
        raise ValueError("entry and stop prices must differ")
    quantity = loss / price_risk
    if side is BreakoutSide.SHORT:
        return quantity.quantize(Decimal("1"), rounding=ROUND_DOWN)
    return quantity.quantize(QUANTITY_STEP, rounding=ROUND_DOWN)


@dataclass(slots=True)
class RiskState:
    trading_date: date | None = None
    traded: bool = False
    disabled: bool = False
    realized_pnl: Decimal = Decimal("0")
    position_quantity: Decimal = Decimal("0")
    average_entry_price: Decimal = Decimal("0")
    stop_price: Decimal | None = None
    entry_order_id: str | None = None
    stop_order_id: str | None = None
    exit_order_id: str | None = None

    def reset(self, trading_date: date) -> None:
        if self.position_quantity != 0:
            raise RuntimeError("cannot reset risk while a position is open")
        self.trading_date = trading_date
        self.traded = False
        self.disabled = False
        self.realized_pnl = Decimal("0")
        self.average_entry_price = Decimal("0")
        self.stop_price = None
        self.entry_order_id = None
        self.stop_order_id = None
        self.exit_order_id = None

    def record_fill(self, side: str, price: Decimal, quantity: Decimal) -> None:
        if price <= 0 or quantity <= 0:
            raise ValueError("fill price and quantity must be positive")
        signed_fill = quantity if side == "buy" else -quantity
        if side not in {"buy", "sell"}:
            raise ValueError(f"unsupported fill side {side!r}")
        position = self.position_quantity
        if position == 0 or position * signed_fill > 0:
            total = abs(position) + quantity
            self.average_entry_price = (
                self.average_entry_price * abs(position) + price * quantity
            ) / total
            self.position_quantity += signed_fill
            return
        closed_quantity = min(abs(position), quantity)
        direction = Decimal("1") if position > 0 else Decimal("-1")
        self.realized_pnl += (price - self.average_entry_price) * closed_quantity * direction
        self.position_quantity += signed_fill
        if self.position_quantity == 0:
            self.average_entry_price = Decimal("0")
            self.stop_price = None
        elif position * self.position_quantity < 0:
            self.average_entry_price = price

    def pnl(self, mark_price: Decimal) -> Decimal:
        unrealized = (mark_price - self.average_entry_price) * self.position_quantity
        return self.realized_pnl + unrealized

    def has_daily_loss(self, mark_price: Decimal) -> bool:
        return self.pnl(mark_price) <= -DAILY_LOSS

    def order_ids(self) -> set[str]:
        return {
            identifier
            for identifier in (self.entry_order_id, self.stop_order_id, self.exit_order_id)
            if identifier is not None
        }
