from argparse import ArgumentParser, Namespace
from pathlib import Path
from sys import stdout
from typing import Any, cast

import polars as pl
from arch.bootstrap import StationaryBootstrap


SCHEMA = {
    "usd_absolute_price_move": pl.Float64,
    "usd_transaction_cost": pl.Float64,
}


def _estimate(
    usd_absolute_price_moves: Any,
    usd_transaction_costs: Any,
) -> list[float]:
    usd_absolute_price_move = float(usd_absolute_price_moves.sum())
    usd_transaction_cost = float(usd_transaction_costs.sum())
    if usd_absolute_price_move <= 0 or usd_transaction_cost > usd_absolute_price_move:
        raise ValueError("break-even accuracy is infeasible")
    return [0.5 + usd_transaction_cost / (2 * usd_absolute_price_move)]


def _read(path: Path) -> tuple[pl.Series, pl.Series]:
    sessions = (
        pl.scan_csv(path, schema_overrides=SCHEMA)
        .select(*SCHEMA)
        .collect(engine="streaming")
    )
    if sessions.is_empty():
        raise ValueError("the input must contain sessions")
    usd_absolute_price_moves = sessions["usd_absolute_price_move"]
    usd_transaction_costs = sessions["usd_transaction_cost"]
    unusable = any(
        column.null_count() or not column.is_finite().all() or (column < 0).any()
        for column in (usd_absolute_price_moves, usd_transaction_costs)
    )
    if unusable or (usd_transaction_costs > usd_absolute_price_moves).any():
        raise ValueError("the input contains invalid session values")
    return usd_absolute_price_moves, usd_transaction_costs


def _arguments() -> Namespace:
    parser = ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--block-size", type=int, default=5)
    parser.add_argument("--confidence", type=float, default=0.95)
    parser.add_argument("--replications", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20_260_816)
    return parser.parse_args()


def _main() -> None:
    arguments = _arguments()
    if arguments.block_size <= 0 or arguments.replications <= 0:
        raise ValueError("bootstrap counts must be positive")
    if not 0 < arguments.confidence < 1:
        raise ValueError("confidence must be between zero and one")
    confidence = float(arguments.confidence)
    usd_absolute_price_moves, usd_transaction_costs = _read(arguments.input)
    estimate = _estimate(usd_absolute_price_moves, usd_transaction_costs)[0]
    bootstrap = StationaryBootstrap(
        arguments.block_size,
        usd_absolute_price_moves.to_numpy(),
        usd_transaction_costs.to_numpy(),
        seed=arguments.seed,
    )
    samples = bootstrap.apply(cast(Any, _estimate), reps=arguments.replications)
    bound = pl.Series(samples[:, 0]).quantile(confidence, interpolation="linear")
    result = pl.DataFrame(
        {
            "estimate": [estimate],
            "confidence_bound_upper": [bound],
            "confidence_probability": [confidence],
            "n_session": [len(usd_absolute_price_moves)],
            "n_bootstrap_block": [arguments.block_size],
            "n_bootstrap_replication": [arguments.replications],
            "bootstrap_seed": [arguments.seed],
        }
    )
    result.write_csv(stdout)


if __name__ == "__main__":
    _main()
