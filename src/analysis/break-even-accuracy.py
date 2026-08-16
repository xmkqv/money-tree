from argparse import ArgumentParser, Namespace
from pathlib import Path
from sys import stdout

import numpy as np
import polars as pl
from arch.bootstrap import StationaryBootstrap
from numpy.typing import NDArray


type FloatArray = NDArray[np.float64]

SCHEMA = {
    "usd_absolute_price_move": pl.Float64,
    "usd_transaction_cost": pl.Float64,
}


def _estimate(
    usd_absolute_price_moves: FloatArray,
    usd_transaction_costs: FloatArray,
) -> FloatArray:
    usd_absolute_price_move = float(usd_absolute_price_moves.sum())
    usd_transaction_cost = float(usd_transaction_costs.sum())
    if usd_absolute_price_move <= 0 or usd_transaction_cost > usd_absolute_price_move:
        raise ValueError("break-even accuracy is infeasible")
    estimate = 0.5 + usd_transaction_cost / (2 * usd_absolute_price_move)
    return np.array([estimate], dtype=np.float64)


def _read(path: Path) -> tuple[FloatArray, FloatArray]:
    sessions = (
        pl.scan_csv(path, schema_overrides=SCHEMA)
        .select(*SCHEMA)
        .collect(engine="streaming")
    )
    if sessions.is_empty():
        raise ValueError("the input must contain sessions")
    values = sessions.to_numpy()
    if (
        not np.isfinite(values).all()
        or np.any(values < 0)
        or np.any(values[:, 1] > values[:, 0])
    ):
        raise ValueError("the input contains invalid session values")
    return values[:, 0], values[:, 1]


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
    usd_absolute_price_moves, usd_transaction_costs = _read(arguments.input)
    estimate = _estimate(usd_absolute_price_moves, usd_transaction_costs).item()
    samples = StationaryBootstrap(
        arguments.block_size,
        usd_absolute_price_moves,
        usd_transaction_costs,
        seed=arguments.seed,
    ).apply(_estimate, reps=arguments.replications)
    result = pl.DataFrame(
        {
            "estimate": [estimate],
            "confidence_bound_upper": [
                float(np.quantile(samples[:, 0], arguments.confidence))
            ],
            "confidence_probability": [arguments.confidence],
            "n_session": [usd_absolute_price_moves.size],
            "n_bootstrap_block": [arguments.block_size],
            "n_bootstrap_replication": [arguments.replications],
            "bootstrap_seed": [arguments.seed],
        }
    )
    result.write_csv(stdout)


if __name__ == "__main__":
    _main()
