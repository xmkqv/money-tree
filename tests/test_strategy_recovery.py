from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from unittest import TestCase
from unittest.mock import patch

from lumibot.entities import Asset, Order, Position

from money_tree.model import OrderRole, StrategyName, TradingState
from money_tree.strategies.momentum_long import MomentumLongStrategy
from money_tree.strategies.opening_range import OpeningRangeStrategy


class StrategyRecoveryTest(TestCase):
    def _strategy(
        self,
        strategy_class: type[OpeningRangeStrategy] | type[MomentumLongStrategy],
        strategy_name: StrategyName,
        quantity: Decimal = Decimal("1"),
    ) -> OpeningRangeStrategy | MomentumLongStrategy:
        strategy = object.__new__(strategy_class)
        strategy.state = TradingState(strategy_name, "SPY")
        strategy.state.session_date = date(2026, 8, 14)
        strategy.state.position.quantity = quantity
        strategy.state.position.average_entry_price = Decimal("100")
        strategy.owned_orders = {}
        strategy.instrument = cast(Asset, SimpleNamespace(symbol="SPY"))
        strategy.broker = SimpleNamespace(IS_BACKTESTING_BROKER=True)
        return strategy

    def _open_strategy(
        self,
        strategy_class: type[OpeningRangeStrategy] | type[MomentumLongStrategy],
        strategy_name: StrategyName,
    ) -> tuple[OpeningRangeStrategy | MomentumLongStrategy, Order]:
        strategy = self._strategy(strategy_class, strategy_name)
        order = cast(Order, SimpleNamespace(identifier="protective-stop-id"))
        strategy.owned_orders = {OrderRole.PROTECTIVE_STOP: order}
        strategy.state.orders.set_id(OrderRole.PROTECTIVE_STOP, "protective-stop-id")
        return strategy, order

    def test_canceled_protective_stop_flattens_and_disables_entry(self) -> None:
        for strategy_class, strategy_name in (
            (OpeningRangeStrategy, StrategyName.OPENING_RANGE),
            (MomentumLongStrategy, StrategyName.MOMENTUM_LONG),
        ):
            with self.subTest(strategy=strategy_name):
                strategy, order = self._open_strategy(strategy_class, strategy_name)
                with patch.object(strategy, "_flatten") as flatten:
                    strategy.on_canceled_order(order)

                flatten.assert_called_once_with("protective stop canceled", disable=True)
                self.assertIsNone(strategy.state.orders.get_id(OrderRole.PROTECTIVE_STOP))

    def test_rejected_protective_stop_flattens_and_disables_entry(self) -> None:
        for strategy_class, strategy_name in (
            (OpeningRangeStrategy, StrategyName.OPENING_RANGE),
            (MomentumLongStrategy, StrategyName.MOMENTUM_LONG),
        ):
            with self.subTest(strategy=strategy_name):
                strategy, order = self._open_strategy(strategy_class, strategy_name)
                with patch.object(strategy, "_flatten") as flatten:
                    strategy.on_error_order(order, RuntimeError("rejected"))

                flatten.assert_called_once_with(
                    "protective stop rejected: rejected",
                    disable=True,
                )
                self.assertIsNone(strategy.state.orders.get_id(OrderRole.PROTECTIVE_STOP))

    def test_rejected_flatten_order_saves_state_and_stops(self) -> None:
        strategy, order = self._open_strategy(
            OpeningRangeStrategy,
            StrategyName.OPENING_RANGE,
        )
        strategy.owned_orders = {OrderRole.FLATTEN: order}
        strategy.state.orders.set_id(OrderRole.PROTECTIVE_STOP, None)
        strategy.state.orders.set_id(OrderRole.FLATTEN, "protective-stop-id")

        with (
            patch.object(strategy, "_save_state") as save_state,
            self.assertRaisesRegex(RuntimeError, "flatten order rejected"),
        ):
            strategy.on_error_order(order, RuntimeError("rejected"))

        save_state.assert_called_once_with()
        self.assertIsNone(strategy.state.orders.get_id(OrderRole.FLATTEN))

    def test_fill_callbacks_record_partial_and_complete_entry_fills(self) -> None:
        for strategy_class, strategy_name in (
            (OpeningRangeStrategy, StrategyName.OPENING_RANGE),
            (MomentumLongStrategy, StrategyName.MOMENTUM_LONG),
        ):
            for complete in (False, True):
                with self.subTest(strategy=strategy_name, complete=complete):
                    strategy = self._strategy(strategy_class, strategy_name, Decimal("0"))
                    order = cast(
                        Order,
                        SimpleNamespace(identifier="entry-id", side=Order.OrderSide.BUY),
                    )
                    position = cast(Position, SimpleNamespace(avg_fill_price=100.0))
                    strategy.owned_orders[OrderRole.ENTRY] = order
                    strategy.state.orders.set_id(OrderRole.ENTRY, "entry-id")
                    callback = (
                        strategy.on_filled_order if complete else strategy.on_partially_filled_order
                    )

                    with (
                        patch.object(strategy, "_record_entry_fill") as record_entry_fill,
                        patch.object(strategy, "_save_state"),
                    ):
                        callback(position, order, 100.0, 0.5, 1.0)

                    record_entry_fill.assert_called_once_with(position, 100.0)
                    self.assertTrue(strategy.state.entered)
                    self.assertEqual(strategy.state.position.quantity, Decimal("0.5"))
                    expected_id = None if complete else "entry-id"
                    self.assertEqual(strategy.state.orders.get_id(OrderRole.ENTRY), expected_id)

    def test_protective_stops_use_strategy_time_in_force_and_closing_side(self) -> None:
        cases = (
            (OpeningRangeStrategy, StrategyName.OPENING_RANGE, Decimal("1"), "day"),
            (OpeningRangeStrategy, StrategyName.OPENING_RANGE, Decimal("-1"), "day"),
            (MomentumLongStrategy, StrategyName.MOMENTUM_LONG, Decimal("1"), "gtc"),
        )
        for strategy_class, strategy_name, quantity, time_in_force in cases:
            with self.subTest(strategy=strategy_name, quantity=quantity):
                strategy = self._strategy(strategy_class, strategy_name, quantity)
                created_order = cast(Order, SimpleNamespace())
                submitted_order = cast(
                    Order,
                    SimpleNamespace(identifier="stop-id", status="submitted"),
                )
                expected_side = Order.OrderSide.SELL if quantity > 0 else Order.OrderSide.BUY

                with (
                    patch.object(
                        strategy, "create_order", return_value=created_order
                    ) as create_order,
                    patch.object(strategy, "submit_order", return_value=submitted_order),
                    patch.object(strategy, "_save_state"),
                ):
                    strategy._replace_protective_stop(Decimal("99"))

                self.assertEqual(create_order.call_args.args[2], expected_side)
                self.assertEqual(create_order.call_args.kwargs["time_in_force"], time_in_force)
                self.assertEqual(strategy.state.orders.get_id(OrderRole.PROTECTIVE_STOP), "stop-id")

    def test_flatten_uses_the_position_closing_side(self) -> None:
        for quantity, expected_side in (
            (Decimal("1"), Order.OrderSide.SELL),
            (Decimal("-1"), Order.OrderSide.BUY),
        ):
            with self.subTest(quantity=quantity):
                strategy = self._strategy(
                    OpeningRangeStrategy,
                    StrategyName.OPENING_RANGE,
                    quantity,
                )
                created_order = cast(Order, SimpleNamespace())
                submitted_order = cast(
                    Order,
                    SimpleNamespace(identifier="flatten-id", status="submitted"),
                )

                with (
                    patch.object(
                        strategy, "create_order", return_value=created_order
                    ) as create_order,
                    patch.object(strategy, "submit_order", return_value=submitted_order),
                    patch.object(strategy, "log_message"),
                    patch.object(strategy, "_save_state"),
                ):
                    strategy._flatten("test", disable=False)

                self.assertEqual(create_order.call_args.args[2], expected_side)
                self.assertEqual(create_order.call_args.kwargs["time_in_force"], "day")
                self.assertEqual(strategy.state.orders.get_id(OrderRole.FLATTEN), "flatten-id")
