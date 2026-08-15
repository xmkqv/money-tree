from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import assert_never, cast

from money_tree.model import (
    MomentumLongState,
    OpeningRangeState,
    OrderRole,
    OwnedOrderState,
    PositionState,
    StrategyName,
    StrategyState,
    Tfb50State,
    TradingState,
)


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


def _parse_strategy_state(
    strategy: StrategyName,
    values: Mapping[str, object],
) -> StrategyState:
    match strategy:
        case StrategyName.OPENING_RANGE:
            keys = {"protective_stop_price"}
            _require_keys(values, keys, "strategy_state")
            return OpeningRangeState(
                protective_stop_price=_require_optional_decimal(
                    values["protective_stop_price"],
                    "strategy_state.protective_stop_price",
                )
            )
        case StrategyName.MOMENTUM_LONG:
            keys = {
                "entry_price",
                "initial_protective_stop_price",
                "active_protective_stop_price",
                "trail_activation_price",
                "highest_price",
            }
            _require_keys(values, keys, "strategy_state")
            return MomentumLongState(
                entry_price=_require_optional_decimal(
                    values["entry_price"], "strategy_state.entry_price"
                ),
                initial_protective_stop_price=_require_optional_decimal(
                    values["initial_protective_stop_price"],
                    "strategy_state.initial_protective_stop_price",
                ),
                active_protective_stop_price=_require_optional_decimal(
                    values["active_protective_stop_price"],
                    "strategy_state.active_protective_stop_price",
                ),
                trail_activation_price=_require_optional_decimal(
                    values["trail_activation_price"],
                    "strategy_state.trail_activation_price",
                ),
                highest_price=_require_optional_decimal(
                    values["highest_price"], "strategy_state.highest_price"
                ),
            )
        case StrategyName.TFB_50:
            keys = {
                "entered_on",
                "initial_protective_stop_price",
                "active_protective_stop_price",
            }
            _require_keys(values, keys, "strategy_state")
            return Tfb50State(
                entered_on=_require_optional_date(
                    values["entered_on"], "strategy_state.entered_on"
                ),
                initial_protective_stop_price=_require_optional_decimal(
                    values["initial_protective_stop_price"],
                    "strategy_state.initial_protective_stop_price",
                ),
                active_protective_stop_price=_require_optional_decimal(
                    values["active_protective_stop_price"],
                    "strategy_state.active_protective_stop_price",
                ),
            )
    assert_never(strategy)


def _dump_decimal(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _dump_strategy_state(state: StrategyState) -> dict[str, object]:
    if isinstance(state, OpeningRangeState):
        return {"protective_stop_price": _dump_decimal(state.protective_stop_price)}
    if isinstance(state, MomentumLongState):
        return {
            "entry_price": _dump_decimal(state.entry_price),
            "initial_protective_stop_price": _dump_decimal(
                state.initial_protective_stop_price
            ),
            "active_protective_stop_price": _dump_decimal(state.active_protective_stop_price),
            "trail_activation_price": _dump_decimal(state.trail_activation_price),
            "highest_price": _dump_decimal(state.highest_price),
        }
    if isinstance(state, Tfb50State):
        return {
            "entered_on": state.entered_on.isoformat() if state.entered_on else None,
            "initial_protective_stop_price": _dump_decimal(
                state.initial_protective_stop_price
            ),
            "active_protective_stop_price": _dump_decimal(state.active_protective_stop_price),
        }
    raise TypeError(f"unsupported strategy state {type(state).__name__}")


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
        handle, temporary_name = tempfile.mkstemp(dir=self.path.parent, prefix=self.path.name)
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(handle, "w") as stream:
                json.dump(self._dump(state), stream, indent=2, sort_keys=True)
                stream.write("\n")
            temporary_path.replace(self.path)
        finally:
            temporary_path.unlink(missing_ok=True)

    def _parse(self, payload: Mapping[str, object]) -> TradingState:
        _require_keys(
            payload,
            {
                "strategy",
                "instrument",
                "session_date",
                "entered",
                "disabled",
                "position",
                "orders",
                "strategy_state",
            },
            "trading state",
        )
        strategy_text = _require_text(payload["strategy"], "strategy")
        try:
            strategy = StrategyName(strategy_text)
        except ValueError as error:
            raise LoadTradingStateError(f"unsupported strategy {strategy_text!r}") from error
        position_values = _require_mapping(payload["position"], "position")
        _require_keys(
            position_values,
            {"quantity", "average_entry_price", "realized_profit_and_loss"},
            "position",
        )
        order_values = _require_mapping(payload["orders"], "orders")
        _require_keys(order_values, {role.value for role in OrderRole}, "orders")
        orders = OwnedOrderState()
        for role in OrderRole:
            orders.set_identifier(
                role,
                _require_optional_text(order_values[role.value], f"orders.{role.value}"),
            )
        strategy_values = _require_mapping(payload["strategy_state"], "strategy_state")
        return TradingState(
            strategy=strategy,
            instrument=_require_text(payload["instrument"], "instrument"),
            session_date=_require_optional_date(payload["session_date"], "session_date"),
            entered=_require_boolean(payload["entered"], "entered"),
            disabled=_require_boolean(payload["disabled"], "disabled"),
            position=PositionState(
                quantity=_require_decimal(position_values["quantity"], "position.quantity"),
                average_entry_price=_require_decimal(
                    position_values["average_entry_price"], "position.average_entry_price"
                ),
                realized_profit_and_loss=_require_decimal(
                    position_values["realized_profit_and_loss"],
                    "position.realized_profit_and_loss",
                ),
            ),
            orders=orders,
            strategy_state=_parse_strategy_state(strategy, strategy_values),
        )

    def _dump(self, state: TradingState) -> dict[str, object]:
        if state.strategy_state is None:
            raise RuntimeError("strategy state is not initialized")
        return {
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
            "orders": {
                role.value: state.orders.get_identifier(role)
                for role in OrderRole
            },
            "strategy_state": _dump_strategy_state(state.strategy_state),
        }
