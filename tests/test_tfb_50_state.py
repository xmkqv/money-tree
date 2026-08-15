from __future__ import annotations

import json
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from money_tree.model import MomentumLongState, StrategyName, Tfb50State, TradingState
from money_tree.state import StateStore


class Tfb50StateStoreTest(unittest.TestCase):
    def test_restores_entry_date_and_stop_prices(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            store = StateStore(path, strategy=StrategyName.TFB_50, instrument="SPY")
            state = TradingState(StrategyName.TFB_50, "SPY")
            state.position.quantity = Decimal("10")
            state.position.average_entry_price = Decimal("100")
            detail = state.strategy_state
            self.assertIsInstance(detail, Tfb50State)
            assert isinstance(detail, Tfb50State)
            detail.entered_on = date(2026, 8, 15)
            detail.initial_protective_stop_price = Decimal("95")
            detail.active_protective_stop_price = Decimal("97")

            store.save(state)
            restored = store.load()
            payload = json.loads(path.read_text())

        self.assertEqual(restored, state)
        self.assertEqual(payload["tfb_50"]["entered_on"], "2026-08-15")

    def test_keeps_existing_momentum_state_format(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            store = StateStore(path, strategy=StrategyName.MOMENTUM_LONG, instrument="SPY")
            state = TradingState(StrategyName.MOMENTUM_LONG, "SPY")
            detail = state.strategy_state
            self.assertIsInstance(detail, MomentumLongState)
            assert isinstance(detail, MomentumLongState)
            detail.entry_price = Decimal("100")
            detail.initial_protective_stop_price = Decimal("95")
            detail.active_protective_stop_price = Decimal("97")
            detail.trail_activation_price = Decimal("110")
            detail.highest_price = Decimal("108")

            store.save(state)
            restored = store.load()
            payload = json.loads(path.read_text())

        self.assertEqual(restored, state)
        self.assertEqual(payload["momentum_long"]["entry_price"], "100")


if __name__ == "__main__":
    unittest.main()
