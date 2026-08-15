from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from functools import partial
from math import ceil, isfinite, sqrt
from multiprocessing import get_context
from os import process_cpu_count

import numpy as np
import polars as pl
from arch.bootstrap import StationaryBootstrap, optimal_block_length

from exps.world import (
    DECISION_INTERVAL,
    N_SESSION_MIN,
    USD_SPREAD,
    FloatArray,
    IntArray,
    ResearchStudy,
    build_research_studies,
    parse_session_range,
)

N_BOOTSTRAP_REPLICATION = 10_000
SEED_BOOTSTRAP = 20_260_815
PROBABILITY_CONFIDENCE = 0.95
N_SESSION_RECENT = 1_260
N_SESSION_CURRENT = 504
N_SESSION_ROLLING = 252
N_SESSION_ROLLING_STEP = 63
USD_SPREAD_SCENARIOS = (0.01, 0.03, 0.05)
BOOTSTRAP_METHOD_STUDENTIZED = "stationary_studentized"

METRIC_BREAK_EVEN = "break_even_accuracy"
METRIC_ROLLING = "rolling_break_even_accuracy"
METRIC_SPREAD = "spread_break_even_accuracy"
METRIC_PLANNING = "planning_accuracy"

SCOPE = pl.Enum(["stock", "panel"])
METRIC = pl.Enum([METRIC_BREAK_EVEN, METRIC_ROLLING, METRIC_SPREAD, METRIC_PLANNING])
WINDOW = pl.Enum(["full", "recent", "current", "maximum_rolling", "rolling"])
BOOTSTRAP_METHOD = pl.Enum([BOOTSTRAP_METHOD_STUDENTIZED])

SESSION_SCHEMA = pl.Schema(
    {
        "session_date": pl.Date,
        "absolute_price_move": pl.Float64,
        "transaction_cost": pl.Float64,
        "round_trip_count": pl.UInt64,
        "directional_observation_count": pl.UInt64,
        "share_quantity": pl.Float64,
    }
)

RESULT_SCHEMA = pl.Schema(
    {
        "scope": SCOPE,
        "metric": METRIC,
        "instrument": pl.String,
        "window": WINDOW,
        "started_on": pl.Date,
        "ended_on": pl.Date,
        "spread_usd": pl.Float64,
        "estimate": pl.Float64,
        "estimate_minimum": pl.Float64,
        "estimate_maximum": pl.Float64,
        "confidence_bound_upper": pl.Float64,
        "session_count": pl.UInt32,
        "window_count": pl.UInt32,
        "directional_observation_count": pl.UInt64,
        "transaction_cost_usd": pl.Float64,
        "absolute_price_move_usd": pl.Float64,
        "confidence_probability": pl.Float64,
        "bootstrap_method": BOOTSTRAP_METHOD,
        "bootstrap_replication_count": pl.UInt32,
        "bootstrap_block_size": pl.UInt32,
        "bootstrap_seed": pl.UInt64,
    }
)


@dataclass(frozen=True, slots=True)
class AccuracyEvidence:
    estimate: float
    confidence_bound_upper: float
    bootstrap_block_size: int


def sum_by_session(values: pl.Series, session_counts: pl.Series, name: str) -> pl.Series:
    if session_counts.dtype != pl.UInt64:
        raise TypeError("session counts must use UInt64")
    if values.len() != session_counts.sum():
        raise ValueError("session counts must match the value count")
    ends = session_counts.cum_sum()
    zero = pl.Series([0], dtype=values.dtype)
    prefix_sums = pl.concat([zero, values.cum_sum()])
    return (prefix_sums.gather(ends) - prefix_sums.gather(ends - session_counts)).rename(name)


def build_session_frame(study: ResearchStudy) -> pl.DataFrame:
    result = study.momentum[DECISION_INTERVAL]
    round_trip_counts = pl.Series(result.n_round_trip_by_session, dtype=pl.UInt64, strict=True)
    price_moves = pl.Series(result.absolute_price_moves, dtype=pl.Float64, strict=True)
    sessions = pl.DataFrame(
        {
            "session_date": study.observations.session_dates,
            "absolute_price_move": sum_by_session(
                price_moves, round_trip_counts, "absolute_price_move"
            ),
            "transaction_cost": sum_by_session(
                pl.Series(result.execution_costs, dtype=pl.Float64, strict=True),
                round_trip_counts,
                "transaction_cost",
            )
            + pl.Series(result.explicit_costs.by_session, dtype=pl.Float64, strict=True),
            "round_trip_count": round_trip_counts,
            "directional_observation_count": sum_by_session(
                price_moves.ne(0).cast(pl.UInt64),
                round_trip_counts,
                "directional_observation_count",
            ),
            "share_quantity": result.share_quantity_by_session,
        },
        schema=SESSION_SCHEMA,
        strict=True,
    )
    validate_session_frame(sessions)
    return sessions


def validate_session_frame(sessions: pl.DataFrame) -> None:
    if sessions.schema != SESSION_SCHEMA:
        raise TypeError("session frame has an invalid schema")
    if sessions.is_empty():
        raise ValueError("session frame must not be empty")
    valid = sessions.select(
        pl.all_horizontal(pl.all().is_not_null()).all()
        & (pl.col("session_date").n_unique() == pl.len())
        & pl.col("session_date").is_sorted()
        & pl.all_horizontal(
            pl.col("absolute_price_move", "transaction_cost", "share_quantity").is_finite(),
            pl.col("absolute_price_move", "transaction_cost", "share_quantity") >= 0,
        ).all()
        & (pl.col("directional_observation_count") <= pl.col("round_trip_count")).all()
    ).item()
    if not valid:
        raise ValueError("session frame has invalid values")


def build_balanced_panel(sessions: pl.DataFrame) -> pl.DataFrame:
    if sessions.is_empty():
        raise ValueError("panel sessions must not be empty")
    if sessions.select("instrument", "session_date").is_duplicated().any():
        raise ValueError("panel instrument sessions must be unique")
    instrument_count = sessions.get_column("instrument").n_unique()
    panel = (
        sessions.lazy()
        .group_by("session_date")
        .agg(
            pl.exclude("instrument", "session_date").sum(),
            instrument_count=pl.col("instrument").n_unique(),
        )
        .filter(pl.col("instrument_count") == instrument_count)
        .drop("instrument_count")
        .sort("session_date")
        .cast(SESSION_SCHEMA, strict=True)
        .collect()
    )
    validate_session_frame(panel)
    if panel.height < N_SESSION_MIN:
        raise RuntimeError(f"balanced panel requires at least {N_SESSION_MIN} sessions")
    return panel


def calculate_accuracy(absolute_price_move: float, transaction_cost: float) -> float:
    if (
        not isfinite(absolute_price_move)
        or absolute_price_move <= 0
        or not 0 <= transaction_cost <= absolute_price_move
    ):
        raise RuntimeError("break-even accuracy is infeasible")
    return 0.5 + transaction_cost / (2 * absolute_price_move)


def calculate_break_even_accuracy(
    absolute_price_moves: FloatArray,
    transaction_costs: FloatArray,
) -> float:
    return calculate_accuracy(
        float(absolute_price_moves.sum()),
        float(transaction_costs.sum()),
    )


def calculate_bootstrap_accuracy(
    absolute_price_moves: FloatArray,
    transaction_costs: FloatArray,
) -> FloatArray:
    accuracy = calculate_accuracy(
        float(absolute_price_moves.sum()),
        float(transaction_costs.sum()),
    )
    return np.array([accuracy], dtype=np.float64)


def calculate_block_jackknife_standard_error(
    parameters: FloatArray,
    absolute_price_moves: FloatArray,
    transaction_costs: FloatArray,
    *,
    group_starts: IntArray,
) -> FloatArray:
    if (
        parameters.size != 1
        or not np.isfinite(parameters).all()
        or absolute_price_moves.size != transaction_costs.size
        or group_starts.ndim != 1
        or group_starts.size < 2
        or group_starts[0] != 0
        or group_starts[-1] >= absolute_price_moves.size
        or np.any(np.diff(group_starts) <= 0)
    ):
        raise ValueError("block jackknife inputs are invalid")
    group_count = group_starts.size
    price_moves_by_group = np.add.reduceat(absolute_price_moves, group_starts)
    transaction_costs_by_group = np.add.reduceat(transaction_costs, group_starts)
    price_moves_without_group = absolute_price_moves.sum() - price_moves_by_group
    transaction_costs_without_group = transaction_costs.sum() - transaction_costs_by_group
    if np.any(
        (price_moves_without_group <= 0)
        | (transaction_costs_without_group < 0)
        | (transaction_costs_without_group > price_moves_without_group)
    ):
        raise RuntimeError("block jackknife produced an infeasible deleted sample")
    deleted_accuracies = 0.5 + transaction_costs_without_group / (2 * price_moves_without_group)
    deleted_mean = float(deleted_accuracies.mean())
    standard_error = sqrt(
        (group_count - 1) / group_count * float(np.square(deleted_accuracies - deleted_mean).sum())
    )
    if not isfinite(standard_error) or standard_error <= 0:
        raise RuntimeError("block jackknife returned a nonpositive standard error")
    return np.array([standard_error], dtype=np.float64)


def calculate_block_size(
    absolute_price_moves: FloatArray,
    transaction_costs: FloatArray,
    estimate: float,
) -> int:
    transaction_cost_ratio = 2 * estimate - 1
    influence = transaction_costs - transaction_cost_ratio * absolute_price_moves
    block_lengths = optimal_block_length(influence)
    stationary_block_length = float(block_lengths["stationary"].iloc[0])
    if not isfinite(stationary_block_length) or stationary_block_length <= 0:
        raise RuntimeError("arch did not estimate a stationary block length")
    return ceil(stationary_block_length)


def calculate_upper_confidence_bound(
    absolute_price_moves: FloatArray,
    transaction_costs: FloatArray,
    block_size: int,
    *,
    replication_count: int,
    seed: int,
) -> float:
    if replication_count <= 0:
        raise ValueError("bootstrap replication count must be positive")
    group_count = absolute_price_moves.size // block_size
    if group_count < 2:
        raise RuntimeError("block jackknife requires at least two groups")
    group_starts = np.linspace(
        0,
        absolute_price_moves.size,
        group_count + 1,
        dtype=np.int64,
    )[:-1]
    bootstrap = StationaryBootstrap(
        block_size,
        absolute_price_moves,
        transaction_costs,
        seed=seed,
    )
    confidence_interval = bootstrap.conf_int(
        calculate_bootstrap_accuracy,
        reps=replication_count,
        method="studentized",
        size=PROBABILITY_CONFIDENCE,
        tail="upper",
        std_err_func=partial(
            calculate_block_jackknife_standard_error,
            group_starts=group_starts,
        ),
    )
    return float(confidence_interval[1, 0])


def calculate_accuracy_evidence(
    absolute_price_moves: FloatArray,
    transaction_costs: FloatArray,
    *,
    replication_count: int = N_BOOTSTRAP_REPLICATION,
    seed: int = SEED_BOOTSTRAP,
) -> AccuracyEvidence:
    if (
        absolute_price_moves.ndim != 1
        or transaction_costs.ndim != 1
        or absolute_price_moves.size != transaction_costs.size
        or not np.isfinite(absolute_price_moves).all()
        or not np.isfinite(transaction_costs).all()
        or np.any(absolute_price_moves < 0)
        or np.any(transaction_costs < 0)
    ):
        raise ValueError("accuracy evidence inputs are invalid")
    if absolute_price_moves.size < N_SESSION_MIN:
        raise RuntimeError(f"inference requires at least {N_SESSION_MIN} complete sessions")
    estimate = calculate_break_even_accuracy(absolute_price_moves, transaction_costs)
    block_size = calculate_block_size(absolute_price_moves, transaction_costs, estimate)
    confidence_bound_upper = calculate_upper_confidence_bound(
        absolute_price_moves,
        transaction_costs,
        block_size,
        replication_count=replication_count,
        seed=seed,
    )
    if not isfinite(confidence_bound_upper) or confidence_bound_upper < estimate:
        raise RuntimeError("bootstrap returned invalid accuracy evidence")
    return AccuracyEvidence(estimate, confidence_bound_upper, block_size)


type AccuracyEvidenceTask = tuple[str, FloatArray, FloatArray, int, int]


def calculate_accuracy_evidence_task(task: AccuracyEvidenceTask) -> tuple[str, AccuracyEvidence]:
    window, absolute_price_moves, transaction_costs, replication_count, seed = task
    return window, calculate_accuracy_evidence(
        absolute_price_moves,
        transaction_costs,
        replication_count=replication_count,
        seed=seed,
    )


def calculate_accuracy_evidence_by_window(
    windows: dict[str, tuple[FloatArray, FloatArray]],
    *,
    replication_count: int,
    seed: int,
    worker_count: int | None,
) -> dict[str, AccuracyEvidence]:
    tasks: list[AccuracyEvidenceTask] = [
        (window, absolute_price_moves, transaction_costs, replication_count, seed)
        for window, (absolute_price_moves, transaction_costs) in windows.items()
    ]
    if not tasks:
        raise ValueError("accuracy evidence windows must not be empty")
    resolved_worker_count = min(len(tasks), process_cpu_count() or 1)
    if worker_count is not None:
        if worker_count <= 0:
            raise ValueError("worker count must be positive")
        resolved_worker_count = min(len(tasks), worker_count)
    if resolved_worker_count == 1:
        return dict(map(calculate_accuracy_evidence_task, tasks))
    with ProcessPoolExecutor(
        max_workers=resolved_worker_count,
        mp_context=get_context("spawn"),
    ) as executor:
        return dict(executor.map(calculate_accuracy_evidence_task, tasks))


def calculate_accuracy_expression(
    transaction_cost: str,
    absolute_price_move: str,
    name: str = "estimate",
) -> pl.Expr:
    return (0.5 + pl.col(transaction_cost) / (2 * pl.col(absolute_price_move))).alias(name)


def calculate_accuracies(summaries: pl.LazyFrame) -> pl.LazyFrame:
    return summaries.with_columns(
        calculate_accuracy_expression("transaction_cost_usd", "absolute_price_move_usd")
    )


def summarize_sessions(sessions: pl.LazyFrame, *groups: str) -> pl.LazyFrame:
    return sessions.group_by(*groups).agg(
        started_on=pl.first("session_date"),
        ended_on=pl.last("session_date"),
        session_count=pl.len(),
        directional_observation_count=pl.sum("directional_observation_count"),
        transaction_cost_usd=pl.sum("transaction_cost"),
        absolute_price_move_usd=pl.sum("absolute_price_move"),
        share_quantity=pl.sum("share_quantity"),
    )


def summarize_rolling_accuracy(sessions: pl.LazyFrame) -> pl.LazyFrame:
    rolling = (
        sessions.with_columns(
            position=pl.int_range(pl.len(), dtype=pl.Int64).over("instrument"),
            final_start=pl.len().over("instrument").cast(pl.Int64) - N_SESSION_ROLLING,
            absolute_price_move=pl.col("absolute_price_move")
            .rolling_sum(N_SESSION_ROLLING)
            .over("instrument"),
            transaction_cost=pl.col("transaction_cost")
            .rolling_sum(N_SESSION_ROLLING)
            .over("instrument"),
        )
        .with_columns(start=pl.col("position") - N_SESSION_ROLLING + 1)
        .filter(
            (pl.col("start") >= 0)
            & (
                (pl.col("start") % N_SESSION_ROLLING_STEP == 0)
                | (pl.col("start") == pl.col("final_start"))
            )
        )
        .with_columns(
            calculate_accuracy_expression(
                "transaction_cost",
                "absolute_price_move",
                "_accuracy",
            )
        )
    )
    maximum_accuracy = pl.col("_accuracy").max()
    return rolling.group_by("instrument").agg(
        window_count=pl.len(),
        maximum_start=pl.col("start").filter(pl.col("_accuracy") == maximum_accuracy).min(),
        estimate_minimum=pl.col("_accuracy").min(),
        estimate_maximum=maximum_accuracy,
        estimate=pl.col("_accuracy").last(),
    )


def add_result_labels(
    result: pl.LazyFrame,
    scope: str,
    metric: str,
    window: str | None,
) -> pl.LazyFrame:
    return result.with_columns(
        scope=pl.lit(scope),
        metric=pl.lit(metric),
        window=pl.lit(window, dtype=pl.String),
    )


def align_result_schema(result: pl.LazyFrame) -> pl.LazyFrame:
    names = result.collect_schema().names()
    missing = [
        pl.lit(None, dtype=dtype).alias(name)
        for name, dtype in RESULT_SCHEMA.items()
        if name not in names
    ]
    return (
        result.with_columns(*missing).cast(RESULT_SCHEMA, strict=True).select(RESULT_SCHEMA.names())
    )


def concat_result_plans(results: list[pl.LazyFrame]) -> pl.LazyFrame:
    if not results:
        raise ValueError("results must not be empty")
    return pl.concat([align_result_schema(result) for result in results], how="vertical")


def build_stock_results(sessions: pl.DataFrame) -> pl.DataFrame:
    session_plan = sessions.lazy()
    summary = summarize_sessions(session_plan, "instrument")
    current = summarize_sessions(
        session_plan.group_by("instrument").tail(N_SESSION_CURRENT),
        "instrument",
    )
    rolling = summary.join(
        summarize_rolling_accuracy(session_plan),
        on="instrument",
        validate="1:1",
    ).drop("maximum_start")
    result = concat_result_plans(
        [
            add_result_labels(
                calculate_accuracies(summary),
                "stock",
                METRIC_BREAK_EVEN,
                "full",
            ),
            add_result_labels(
                calculate_accuracies(current),
                "stock",
                METRIC_BREAK_EVEN,
                "current",
            ),
            add_result_labels(rolling, "stock", METRIC_ROLLING, "rolling"),
        ]
    ).collect()
    minimum_session_count = (
        result.filter((pl.col("metric") == METRIC_BREAK_EVEN) & (pl.col("window") == "full"))
        .get_column("session_count")
        .min()
    )
    if not isinstance(minimum_session_count, int) or minimum_session_count < N_SESSION_CURRENT:
        raise RuntimeError(f"sample requires at least {N_SESSION_CURRENT} sessions")
    return result


def build_panel_results(
    panel: pl.DataFrame,
    *,
    bootstrap_replication_count: int = N_BOOTSTRAP_REPLICATION,
    bootstrap_seed: int = SEED_BOOTSTRAP,
    worker_count: int | None = None,
) -> pl.DataFrame:
    if panel.height < N_SESSION_RECENT:
        raise RuntimeError(f"sample requires at least {N_SESSION_RECENT} sessions")
    panel_sessions = panel.lazy().with_columns(instrument=pl.lit(None, dtype=pl.String))
    summary = summarize_sessions(panel_sessions, "instrument")
    rolling = summarize_rolling_accuracy(panel_sessions).collect()
    if (
        rolling.height != 1
        or rolling.select(
            pl.col("estimate").is_null()
            | ~pl.col("estimate").is_finite()
            | ~pl.col("estimate").is_between(0.5, 1)
        ).item()
    ):
        raise RuntimeError("rolling accuracy produced an infeasible window")
    maximum_start = int(rolling.get_column("maximum_start").item())
    window_bounds = {
        "full": (0, panel.height),
        "recent": (panel.height - N_SESSION_RECENT, panel.height),
        "current": (panel.height - N_SESSION_CURRENT, panel.height),
        "maximum_rolling": (maximum_start, maximum_start + N_SESSION_ROLLING),
    }
    evidence_values = panel.select(
        "absolute_price_move",
        "transaction_cost",
    ).to_numpy(order="fortran")
    absolute_price_moves = evidence_values[:, 0]
    transaction_costs = evidence_values[:, 1]
    evidence_windows = {
        window: (
            absolute_price_moves[start:stop],
            transaction_costs[start:stop],
        )
        for window, (start, stop) in window_bounds.items()
    }
    evidence_by_window = calculate_accuracy_evidence_by_window(
        evidence_windows,
        replication_count=bootstrap_replication_count,
        seed=bootstrap_seed,
        worker_count=worker_count,
    )
    evidence = pl.DataFrame(
        [
            {
                "window": window,
                "estimate": item.estimate,
                "confidence_bound_upper": item.confidence_bound_upper,
                "confidence_probability": PROBABILITY_CONFIDENCE,
                "bootstrap_method": BOOTSTRAP_METHOD_STUDENTIZED,
                "bootstrap_replication_count": bootstrap_replication_count,
                "bootstrap_block_size": item.bootstrap_block_size,
                "bootstrap_seed": bootstrap_seed,
            }
            for window, item in evidence_by_window.items()
        ],
        schema={
            "window": pl.String,
            "estimate": pl.Float64,
            "confidence_bound_upper": pl.Float64,
            "confidence_probability": pl.Float64,
            "bootstrap_method": pl.String,
            "bootstrap_replication_count": pl.UInt32,
            "bootstrap_block_size": pl.UInt32,
            "bootstrap_seed": pl.UInt64,
        },
        strict=True,
    )
    window_sessions = pl.concat(
        [
            panel.slice(start, stop - start)
            .lazy()
            .with_columns(
                instrument=pl.lit(None, dtype=pl.String),
                window=pl.lit(window, dtype=pl.String),
            )
            for window, (start, stop) in window_bounds.items()
        ],
        how="vertical",
    )
    evidence_results = (
        summarize_sessions(window_sessions, "instrument", "window")
        .join(evidence.lazy(), on="window", validate="m:1")
        .with_columns(
            scope=pl.lit("panel"),
            metric=pl.lit(METRIC_BREAK_EVEN),
        )
    )
    rolling_result = summary.join(
        rolling.lazy(),
        on="instrument",
        nulls_equal=True,
        validate="1:1",
    ).drop("maximum_start")
    spreads = pl.DataFrame(
        {"spread_usd": USD_SPREAD_SCENARIOS},
        schema={"spread_usd": pl.Float64},
    ).lazy()
    spread_sessions = (
        panel.slice(window_bounds["current"][0], N_SESSION_CURRENT)
        .lazy()
        .with_columns(instrument=pl.lit(None, dtype=pl.String))
        .join(spreads, how="cross")
        .with_columns(
            transaction_cost=pl.col("transaction_cost")
            + (pl.col("spread_usd") - USD_SPREAD) * pl.col("share_quantity")
        )
    )
    if (
        spread_sessions.select(
            (~pl.col("transaction_cost").is_finite() | (pl.col("transaction_cost") < 0)).any()
        )
        .collect()
        .item()
    ):
        raise ValueError("spread produced invalid transaction costs")
    spread_result = calculate_accuracies(
        summarize_sessions(spread_sessions, "instrument", "spread_usd")
    )
    planning_result = pl.DataFrame(
        {"estimate": [max(item.confidence_bound_upper for item in evidence_by_window.values())]}
    ).lazy()
    return concat_result_plans(
        [
            evidence_results,
            add_result_labels(rolling_result, "panel", METRIC_ROLLING, "rolling"),
            add_result_labels(spread_result, "panel", METRIC_SPREAD, "current"),
            add_result_labels(planning_result, "panel", METRIC_PLANNING, None),
        ]
    ).collect()


def concat_results(results: list[pl.DataFrame]) -> pl.DataFrame:
    if not results:
        raise ValueError("results must not be empty")
    result = (
        concat_result_plans([item.lazy() for item in results])
        .sort(
            "scope",
            "instrument",
            "metric",
            "window",
            "spread_usd",
            nulls_last=True,
        )
        .collect()
    )
    invalid = result.select(
        pl.col("estimate").is_null().any()
        | (~pl.col("estimate").is_finite()).any()
        | (pl.col("estimate") < 0.5).any()
        | ((pl.col("metric") != METRIC_PLANNING) & (pl.col("estimate") > 1)).any()
    ).item()
    if invalid:
        raise RuntimeError("break-even accuracy is infeasible")
    return result


def main() -> pl.DataFrame:
    studies = build_research_studies(parse_session_range("break-even-accuracy"))
    sessions = pl.concat(
        (
            build_session_frame(study).with_columns(
                instrument=pl.lit(study.observations.instrument, dtype=pl.String)
            )
            for study in studies
        ),
        how="vertical",
        rechunk=True,
    )
    panel = build_balanced_panel(sessions)
    return concat_results([build_stock_results(sessions), build_panel_results(panel)])


if __name__ == "__main__":
    _ = main()
