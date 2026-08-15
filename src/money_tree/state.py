from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import fields
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import cast

from money_tree.model import (
    OrderRole,
    OwnedOrderState,
    PositionState,
    StrategyName,
    TradingState,
    create_strategy_state,
)

STATE_VERSION = 1


class LoadTradingStateError(ValueError):
    pass


def _require_mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise LoadTradingStateError(f"{name} must be an object")
    return cast(dict[str, object], value)


def _require_keys(values: Mapping[str, object], keys: set[str], name: str) -> None:
    actual = set(values)
    if actual != keys:
        raise LoadTradingStateError(
            f"{name} fields differ: missing={sorted(keys - actual)} extra={sorted(actual - keys)}"
        )


def _require_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise LoadTradingStateError(f"{name} must be nonempty text")
    return value


def _require_optional_text(value: object, name: str) -> str | None:
    if value is None:
        return None
    return _require_text(value, name)


def _require_boolean(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise LoadTradingStateError(f"{name} must be a boolean")
    return value


def _require_decimal(value: object, name: str) -> Decimal:
    if not isinstance(value, str):
        raise LoadTradingStateError(f"{name} must be decimal text")
    try:
        return Decimal(value)
    except InvalidOperation as error:
        raise LoadTradingStateError(f"{name} must be decimal text") from error


def _require_optional_decimal(value: object, name: str) -> Decimal | None:
    if value is None:
        return None
    return _require_decimal(value, name)


def _require_optional_date(value: object, name: str) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise LoadTradingStateError(f"{name} must be ISO date text or null")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise LoadTradingStateError(f"{name} must be ISO date text or null") from error


def _dump_decimal(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _dump_strategy_value(value: Decimal | date | None) -> str | None:
    if isinstance(value, date):
        return value.isoformat()
    return _dump_decimal(value)


class StateStore:
    def __init__(
        self,
        path: Path | None,
        *,
        strategy: StrategyName,
        instrument: str,
    ) -> None:
        self.path = path
        self.strategy = strategy
        self.instrument = instrument

    def load(self) -> TradingState:
        if self.path is None or not self.path.exists():
            return TradingState(self.strategy, self.instrument)
        try:
            payload = json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError) as error:
            raise LoadTradingStateError(f"trading state {self.path} could not be read") from error
        try:
            state = self._parse(_require_mapping(payload, "trading state"))
            state.validate()
        except LoadTradingStateError:
            raise
        except (ArithmeticError, ValueError) as error:
            raise LoadTradingStateError("trading state values are invalid") from error
        if state.strategy is not self.strategy:
            raise LoadTradingStateError(
                f"trading state strategy is {state.strategy.value}, expected {self.strategy.value}"
            )
        if state.instrument != self.instrument:
            raise LoadTradingStateError(
                f"trading state instrument is {state.instrument}, expected {self.instrument}"
            )
        return state

    def save(self, state: TradingState) -> None:
        if state.strategy is not self.strategy or state.instrument != self.instrument:
            raise ValueError("trading state identity differs from its store")
        state.validate()
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._dump(state)
        handle, temporary_name = tempfile.mkstemp(dir=self.path.parent, prefix=self.path.name)
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(handle, "w") as stream:
                json.dump(payload, stream, indent=2, sort_keys=True)
                stream.write("\n")
            temporary_path.replace(self.path)
        finally:
            temporary_path.unlink(missing_ok=True)

    def _parse(self, payload: Mapping[str, object]) -> TradingState:
        common_keys = {
            "version",
            "strategy",
            "instrument",
            "session_date",
            "entered",
            "disabled",
            "position",
            "orders",
        }
        strategy_text = _require_text(payload.get("strategy"), "strategy")
        try:
            strategy = StrategyName(strategy_text)
        except ValueError as error:
            raise LoadTradingStateError(f"unsupported strategy {strategy_text!r}") from error
        detail_key = strategy.value.replace("-", "_")
        _require_keys(payload, common_keys | {detail_key}, "trading state")
        if payload["version"] != STATE_VERSION:
            raise LoadTradingStateError(f"unsupported trading state version {payload['version']!r}")
        session_value = payload["session_date"]
        if session_value is not None and not isinstance(session_value, str):
            raise LoadTradingStateError("session_date must be ISO date text or null")
        try:
            session_date = date.fromisoformat(session_value) if session_value is not None else None
        except ValueError as error:
            raise LoadTradingStateError("session_date must be ISO date text or null") from error
        position_values = _require_mapping(payload["position"], "position")
        _require_keys(
            position_values,
            {"quantity", "average_entry_price", "realized_profit_and_loss"},
            "position",
        )
        orders = _require_mapping(payload["orders"], "orders")
        _require_keys(orders, {role.value for role in OrderRole}, "orders")
        detail = _require_mapping(payload[detail_key], detail_key)
        strategy_state = create_strategy_state(strategy)
        detail_fields = {item.name for item in fields(strategy_state)}
        _require_keys(detail, detail_fields, detail_key)
        for item in fields(strategy_state):
            item_name = f"{detail_key}.{item.name}"
            value = (
                _require_optional_date(detail[item.name], item_name)
                if item.name.endswith("_on")
                else _require_optional_decimal(detail[item.name], item_name)
            )
            setattr(
                strategy_state,
                item.name,
                value,
            )
        owned_orders = OwnedOrderState()
        for role in OrderRole:
            owned_orders.set_id(
                role,
                _require_optional_text(orders[role.value], f"orders.{role.value}"),
            )
        return TradingState(
            strategy=strategy,
            instrument=_require_text(payload["instrument"], "instrument"),
            session_date=session_date,
            entered=_require_boolean(payload["entered"], "entered"),
            disabled=_require_boolean(payload["disabled"], "disabled"),
            position=PositionState(
                quantity=_require_decimal(position_values["quantity"], "position.quantity"),
                average_entry_price=_require_decimal(
                    position_values["average_entry_price"],
                    "position.average_entry_price",
                ),
                realized_profit_and_loss=_require_decimal(
                    position_values["realized_profit_and_loss"],
                    "position.realized_profit_and_loss",
                ),
            ),
            orders=owned_orders,
            strategy_state=strategy_state,
        )

    def _dump(self, state: TradingState) -> dict[str, object]:
        detail_key = state.strategy.value.replace("-", "_")
        strategy_state = state.strategy_state
        if strategy_state is None:
            raise RuntimeError("strategy state is not initialized")
        detail = {
            item.name: _dump_strategy_value(getattr(strategy_state, item.name))
            for item in fields(strategy_state)
        }
        return {
            "version": STATE_VERSION,
            "strategy": state.strategy.value,
            "instrument": state.instrument,
            "session_date": state.session_date.isoformat() if state.session_date else None,
            "entered": state.entered,
            "disabled": state.disabled,
            "position": {
                "quantity": str(state.position.quantity),
                "average_entry_price": str(state.position.average_entry_price),
                "realized_profit_and_loss": str(state.position.realized_profit_and_loss),
            },
            "orders": {role.value: state.orders.get_id(role) for role in OrderRole},
            detail_key: detail,
        }
