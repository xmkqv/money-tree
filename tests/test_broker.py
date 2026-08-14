from decimal import Decimal
from unittest import TestCase

from money_tree.broker import AccountSnapshot, reconcile_account
from money_tree.model import Direction, OrderRole, StrategyName, TradingState


class ReconcileAccountTest(TestCase):
    def _open_state(self, strategy: StrategyName = StrategyName.MOMENTUM_LONG) -> TradingState:
        state = TradingState(strategy, "SPY")
        state.position.quantity = Decimal("2")
        state.position.average_entry_price = Decimal("100")
        return state

    def test_rejects_unknown_order(self) -> None:
        state = TradingState(StrategyName.OPENING_RANGE, "SPY")
        snapshot = AccountSnapshot(None, None, frozenset({"unknown"}))

        with self.assertRaisesRegex(RuntimeError, "broker order that is not an owned order"):
            reconcile_account(snapshot, state)

    def test_rejects_unknown_position(self) -> None:
        state = TradingState(StrategyName.OPENING_RANGE, "SPY")
        snapshot = AccountSnapshot(Decimal("1"), Decimal("100"), frozenset())

        with self.assertRaisesRegex(RuntimeError, "broker position that is not an owned position"):
            reconcile_account(snapshot, state)

    def test_clears_missing_owned_order(self) -> None:
        state = TradingState(StrategyName.OPENING_RANGE, "SPY")
        state.orders.set_id(OrderRole.ENTRY, "missing")

        reconcile_account(AccountSnapshot(None, None, frozenset()), state)

        self.assertIsNone(state.orders.get_id(OrderRole.ENTRY))

    def test_accepts_matching_position(self) -> None:
        state = self._open_state()

        reconcile_account(
            AccountSnapshot(Decimal("2"), Decimal("100"), frozenset()),
            state,
        )

        self.assertEqual(state.position.direction, Direction.LONG)

    def test_rejects_a_missing_broker_position(self) -> None:
        state = self._open_state()

        with self.assertRaisesRegex(RuntimeError, "broker position is missing"):
            reconcile_account(AccountSnapshot(None, None, frozenset()), state)

    def test_clears_a_missing_protective_stop_for_restoration(self) -> None:
        state = self._open_state(StrategyName.OPENING_RANGE)
        state.orders.set_id(OrderRole.PROTECTIVE_STOP, "missing")

        reconcile_account(
            AccountSnapshot(Decimal("2"), Decimal("100"), frozenset()),
            state,
        )

        self.assertIsNone(state.orders.get_id(OrderRole.PROTECTIVE_STOP))

    def test_rejects_a_position_average_entry_price_mismatch(self) -> None:
        state = self._open_state()

        with self.assertRaisesRegex(RuntimeError, "broker position that is not an owned position"):
            reconcile_account(
                AccountSnapshot(Decimal("2"), Decimal("101"), frozenset()),
                state,
            )
