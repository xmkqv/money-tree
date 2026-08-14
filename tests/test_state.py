import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from money_tree.model import (
    MomentumLongState,
    OpeningRangeState,
    OrderRole,
    StrategyName,
    TradingState,
)
from money_tree.state import LoadTradingStateError, StateStore


class StateStoreTest(TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "state.json"

    def test_restores_opening_range_state(self) -> None:
        store = StateStore(self.path, strategy=StrategyName.OPENING_RANGE, instrument="SPY")
        state = TradingState(StrategyName.OPENING_RANGE, "SPY")
        state.session_date = date(2026, 8, 14)
        state.entered = True
        state.position.quantity = Decimal("2.5")
        state.position.average_entry_price = Decimal("100")
        state.position.realized_profit_and_loss = Decimal("1.25")
        state.orders.set_id(OrderRole.ENTRY, "entry-id")
        opening_range = state.strategy_state
        assert isinstance(opening_range, OpeningRangeState)
        opening_range.protective_stop_price = Decimal("99")

        store.save(state)
        restored = store.load()
        payload = json.loads(self.path.read_text())

        self.assertEqual(restored, state)
        self.assertEqual(payload["version"], 1)
        self.assertEqual(
            payload["orders"],
            {"entry": "entry-id", "protective-stop": None, "flatten": None},
        )
        self.assertEqual(payload["opening_range"], {"protective_stop_price": "99"})

    def test_restores_momentum_state(self) -> None:
        store = StateStore(self.path, strategy=StrategyName.MOMENTUM_LONG, instrument="SPY")
        state = TradingState(StrategyName.MOMENTUM_LONG, "SPY")
        momentum = state.strategy_state
        assert isinstance(momentum, MomentumLongState)
        momentum.entry_price = Decimal("100")
        momentum.initial_protective_stop_price = Decimal("95")
        momentum.active_protective_stop_price = Decimal("97")
        momentum.trail_activation_price = Decimal("110")
        momentum.highest_price = Decimal("108")

        store.save(state)
        restored = store.load()

        self.assertEqual(restored, state)

    def test_rejects_strategy_identity_mismatch(self) -> None:
        StateStore(
            self.path,
            strategy=StrategyName.OPENING_RANGE,
            instrument="SPY",
        ).save(TradingState(StrategyName.OPENING_RANGE, "SPY"))
        store = StateStore(self.path, strategy=StrategyName.MOMENTUM_LONG, instrument="SPY")

        with self.assertRaisesRegex(LoadTradingStateError, "strategy is opening-range"):
            store.load()

    def test_rejects_instrument_identity_mismatch(self) -> None:
        StateStore(
            self.path,
            strategy=StrategyName.OPENING_RANGE,
            instrument="SPY",
        ).save(TradingState(StrategyName.OPENING_RANGE, "SPY"))
        store = StateStore(self.path, strategy=StrategyName.OPENING_RANGE, instrument="QQQ")

        with self.assertRaisesRegex(LoadTradingStateError, "instrument is SPY"):
            store.load()

    def test_rejects_nonfinite_position_values(self) -> None:
        store = StateStore(self.path, strategy=StrategyName.OPENING_RANGE, instrument="SPY")
        store.save(TradingState(StrategyName.OPENING_RANGE, "SPY"))
        payload = json.loads(self.path.read_text())
        payload["position"]["realized_profit_and_loss"] = "NaN"
        self.path.write_text(json.dumps(payload))

        with self.assertRaisesRegex(LoadTradingStateError, "values are invalid"):
            store.load()

    def test_rejects_legacy_state_schema(self) -> None:
        self.path.write_text(json.dumps({"trading_date": "2026-08-14"}))
        store = StateStore(self.path, strategy=StrategyName.OPENING_RANGE, instrument="SPY")

        with self.assertRaises(LoadTradingStateError):
            store.load()
