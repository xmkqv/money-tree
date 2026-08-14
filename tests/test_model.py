from decimal import Decimal
from unittest import TestCase

from money_tree.model import (
    Direction,
    OrderRole,
    OrderSide,
    OwnedOrderState,
    PositionState,
    StrategyName,
    TradingState,
)


class PositionStateTest(TestCase):
    def test_returns_flat_after_complete_long_round_trip(self) -> None:
        position = PositionState()
        position.record_fill(OrderSide.BUY, Decimal("100"), Decimal("2"))
        position.record_fill(OrderSide.SELL, Decimal("103"), Decimal("2"))

        self.assertEqual(position.direction, Direction.FLAT)
        self.assertEqual(position.quantity, Decimal("0"))
        self.assertEqual(position.average_entry_price, Decimal("0"))
        self.assertEqual(position.realized_profit_and_loss, Decimal("6"))

    def test_returns_profit_after_partial_short_flatten(self) -> None:
        position = PositionState()
        position.record_fill(OrderSide.SELL, Decimal("100"), Decimal("3"))
        position.record_fill(OrderSide.BUY, Decimal("98"), Decimal("2"))

        self.assertEqual(position.direction, Direction.SHORT)
        self.assertEqual(position.quantity, Decimal("-1"))
        self.assertEqual(position.realized_profit_and_loss, Decimal("4"))
        self.assertEqual(position.calculate_profit_and_loss(Decimal("97")), Decimal("7"))

    def test_rejects_an_open_position_without_an_average_entry_price(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive average entry price"):
            PositionState(quantity=Decimal("1"))


class OwnedOrderStateTest(TestCase):
    def test_updates_identifier_by_order_role(self) -> None:
        orders = OwnedOrderState()

        orders.set_id(OrderRole.PROTECTIVE_STOP, "stop-id")

        self.assertEqual(orders.get_id(OrderRole.PROTECTIVE_STOP), "stop-id")
        self.assertEqual(orders.ids, {"stop-id"})

    def test_rejects_duplicate_identifiers(self) -> None:
        state = TradingState(StrategyName.OPENING_RANGE, "SPY")
        state.orders.set_id(OrderRole.ENTRY, "duplicate")
        state.orders.set_id(OrderRole.PROTECTIVE_STOP, "duplicate")

        with self.assertRaisesRegex(ValueError, "identifiers must be distinct"):
            state.validate()
