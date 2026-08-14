from world import (
    INSTRUMENT,
    N_SHARE,
    RATE_SECTION_31,
    USD_CAT_PER_SHARE,
    USD_FINRA_TAF_PER_SHARE,
    USD_SPREAD,
    ResearchStudy,
    build_research_study,
    format_money,
    parse_session_range,
)


def print_claim(study: ResearchStudy) -> None:
    result = study.fifteen_minute_momentum
    directional = result.decision_profit_and_loss != 0
    if not directional.any():
        raise RuntimeError("claim requires nonzero target price changes")
    n_directional_observation = int(directional.sum())
    n_directional_hit = int((result.decision_profit_and_loss > 0).sum())
    directional_hit_rate = n_directional_hit / n_directional_observation
    transaction_cost = result.transaction_cost
    mean_transaction_cost = transaction_cost / result.n_round_trip
    mean_gain = float(result.decision_profit_and_loss[result.decision_profit_and_loss > 0].mean())
    mean_loss = float(-result.decision_profit_and_loss[result.decision_profit_and_loss < 0].mean())
    cost_per_observation = transaction_cost / n_directional_observation
    break_even_hit_rate = (mean_loss + cost_per_observation) / (mean_gain + mean_loss)
    costs = result.explicit_costs
    observations = study.observations
    peak_entry_value = N_SHARE * float(result.entry_fill_prices.max())
    oracle_peak_entry_value = N_SHARE * float(study.oracle.entry_fill_prices.max())

    print(
        f"{INSTRUMENT} sip feed | {observations.session_range.started_on} "
        f"<= session < {observations.session_range.ended_before}"
    )
    print("strategy | isolated 15-minute momentum | 1 share | flat after each horizon")
    print("execution | 1-minute delay | assumed spread=$0.03 | no market impact")
    print(
        "alpaca 2026-07-20 | "
        f"commission=0 section_31={RATE_SECTION_31:.7f} "
        f"finra_taf={USD_FINRA_TAF_PER_SHARE:.6f}/sell_share "
        f"cat={USD_CAT_PER_SHARE:.6f}/executed_share"
    )
    print(
        f"sample | complete_sessions={len(observations.session_dates)} "
        f"excluded_sessions={observations.n_excluded_session} "
        f"round_trips={result.n_round_trip}"
    )
    print(
        f"decision | directional_observations={n_directional_observation} "
        f"directional_hits={n_directional_hit} "
        f"directional_hit_rate={directional_hit_rate:.2%} "
        f"break_even_hit_rate={break_even_hit_rate:.2%}"
    )
    print(
        f"cost | assumed_spread={format_money(USD_SPREAD)} "
        f"mean_execution_cost={format_money(float(result.execution_costs.mean()))} "
        f"mean_explicit_cost={format_money(costs.total / result.n_round_trip)}"
    )
    print(
        f"hurdle | mean_transaction_cost={format_money(mean_transaction_cost)} "
        f"break_even_price_move={format_money(mean_transaction_cost / N_SHARE)}"
    )
    print(
        f"fees | commission={format_money(float(costs.commission_by_session.sum()))} "
        f"section_31={format_money(float(costs.section_31_by_session.sum()))} "
        f"finra_taf={format_money(float(costs.finra_taf_by_session.sum()))} "
        f"cat={format_money(float(costs.cat_by_session.sum()))}"
    )
    print(
        f"profit_and_loss | decision={format_money(float(result.decision_profit_and_loss.sum()))} "
        f"fill={format_money(float(result.fill_profit_and_loss.sum()))} "
        f"net={format_money(result.net_profit_and_loss)} "
        f"net_to_peak_entry_value={result.net_profit_and_loss / peak_entry_value:.4%}"
    )
    print(
        f"transaction_cost | execution={format_money(float(result.execution_costs.sum()))} "
        f"explicit={format_money(costs.total)} total={format_money(transaction_cost)}"
    )
    print(
        f"oracle | net_profit_and_loss={format_money(study.oracle.net_profit_and_loss)} "
        "net_to_peak_entry_value="
        f"{study.oracle.net_profit_and_loss / oracle_peak_entry_value:.4%}"
    )


def main() -> None:
    print_claim(build_research_study(parse_session_range("transaction-cost")))


if __name__ == "__main__":
    main()
