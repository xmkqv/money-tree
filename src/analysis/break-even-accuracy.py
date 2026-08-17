from argparse import ArgumentParser
from pathlib import Path
from sys import stdout
from typing import Any, cast

import polars as pl
from arch.bootstrap import StationaryBootstrap


SCHEMA = {"usd_absolute_price_move": pl.Float64, "usd_transaction_cost": pl.Float64}
BLOCK_SIZE = 5
CONFIDENCE = 0.95
REPLICATIONS = 10_000
SEED = 20_260_816


def _estimate(usd_absolute_price_moves: Any, usd_transaction_costs: Any) -> list[float]:
    usd_absolute_price_move = float(usd_absolute_price_moves.sum())
    usd_transaction_cost = float(usd_transaction_costs.sum())
    if usd_absolute_price_move <= 0 or usd_transaction_cost > usd_absolute_price_move:
        raise ValueError("break-even accuracy is infeasible")
    return [0.5 + usd_transaction_cost / (2 * usd_absolute_price_move)]


def _read(path: Path) -> tuple[pl.Series, pl.Series]:
    sessions = (
        pl.scan_csv(path, schema_overrides=SCHEMA).select(*SCHEMA).collect(engine="streaming")
    )
    usd_absolute_price_moves = sessions["usd_absolute_price_move"]
    usd_transaction_costs = sessions["usd_transaction_cost"]
    unusable = any(
        column.null_count() or not column.is_finite().all() or (column < 0).any()
        for column in (usd_absolute_price_moves, usd_transaction_costs)
    )
    if unusable or (usd_transaction_costs > usd_absolute_price_moves).any():
        raise ValueError("the input contains invalid session values")
    return usd_absolute_price_moves, usd_transaction_costs


def _main() -> None:
    parser = ArgumentParser()
    parser.add_argument("input", type=Path)
    usd_absolute_price_moves, usd_transaction_costs = _read(parser.parse_args().input)
    estimate = _estimate(usd_absolute_price_moves, usd_transaction_costs)[0]
    bootstrap = StationaryBootstrap(
        BLOCK_SIZE, usd_absolute_price_moves.to_numpy(), usd_transaction_costs.to_numpy(), seed=SEED
    )
    samples = bootstrap.apply(cast(Any, _estimate), reps=REPLICATIONS)
    bound = pl.Series(samples[:, 0]).quantile(CONFIDENCE, interpolation="linear")
    result = pl.DataFrame(
        {
            "estimate": [estimate],
            "confidence_bound_upper": [bound],
            "confidence_probability": [CONFIDENCE],
            "n_session": [len(usd_absolute_price_moves)],
            "n_bootstrap_block": [BLOCK_SIZE],
            "n_bootstrap_replication": [REPLICATIONS],
            "bootstrap_seed": [SEED],
        }
    )
    result.write_csv(stdout)


if __name__ == "__main__":
    _main()
