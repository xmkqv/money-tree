from __future__ import annotations

import json
import os
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from money_tree.risk import RiskState


class StateStore:
    def __init__(self, path: Path | None) -> None:
        self.path = path

    def load(self) -> RiskState:
        if self.path is None or not self.path.exists():
            return RiskState()
        payload = json.loads(self.path.read_text())
        return RiskState(
            trading_date=(
                date.fromisoformat(payload["trading_date"])
                if payload["trading_date"] is not None
                else None
            ),
            traded=payload["traded"],
            disabled=payload["disabled"],
            realized_pnl=Decimal(payload["realized_pnl"]),
            position_quantity=Decimal(payload["position_quantity"]),
            average_entry_price=Decimal(payload["average_entry_price"]),
            stop_price=Decimal(payload["stop_price"]) if payload["stop_price"] else None,
            entry_order_id=payload["entry_order_id"],
            stop_order_id=payload["stop_order_id"],
            exit_order_id=payload["exit_order_id"],
        )

    def save(self, state: RiskState) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "trading_date": state.trading_date.isoformat() if state.trading_date else None,
            "traded": state.traded,
            "disabled": state.disabled,
            "realized_pnl": str(state.realized_pnl),
            "position_quantity": str(state.position_quantity),
            "average_entry_price": str(state.average_entry_price),
            "stop_price": str(state.stop_price) if state.stop_price is not None else None,
            "entry_order_id": state.entry_order_id,
            "stop_order_id": state.stop_order_id,
            "exit_order_id": state.exit_order_id,
        }
        handle, temporary_name = tempfile.mkstemp(dir=self.path.parent, prefix=self.path.name)
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(handle, "w") as stream:
                json.dump(payload, stream, indent=2, sort_keys=True)
                stream.write("\n")
            temporary_path.replace(self.path)
        finally:
            temporary_path.unlink(missing_ok=True)
