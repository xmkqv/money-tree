# Deciders

The `deciders` concern owns decision formation

`decider(decider_config, prediction): decision`

Research checked on 2026-07-28

## Shape-compliant options

### Decision

Keep the live decider interface small and deterministic

Use analysis engines offline to fit and validate policy parameters

Adopt [skfolio](https://skfolio.org/) as the first portfolio research engine

Add [CVXPortfolio](https://www.cvxportfolio.com/) when explicit costs and
multi-period optimization become necessary

Use NautilusTrader only if money-tree later needs a full event-driven simulation engine

### Portfolio and risk engines

| Engine | License | Main capability | Activity | Fit |
| --- | --- | --- | --- | --- |
| [skfolio](https://github.com/skfolio/skfolio) | BSD-3 | Portfolio optimization and model selection | Active | Primary research default |
| [CVXPortfolio](https://github.com/cvxgrp/cvxportfolio) | Apache-2 | Cost-aware single and multi-period optimization | Active | Advanced policy |
| [Riskfolio-Lib](https://github.com/dcajasn/Riskfolio-Lib) | BSD-3 | Broad risk measures and portfolio models | Active | Research challenger |
| [PyPortfolioOpt](https://github.com/robertmartin8/PyPortfolioOpt) | MIT | Mean variance, Black-Litterman, HRP | Active | Simple optimizer |
| [cvxpy](https://www.cvxpy.org/) | Apache-2 | General convex optimization | Active | Custom constrained policy |
| [PyPortfolioAnalysis](https://pyportfolioanalysis.readthedocs.io/) | Open source | PortfolioAnalytics-style workflows | Quiet | Legacy reference |

#### skfolio

skfolio uses scikit-learn estimator, pipeline, tuning, and cross-validation patterns

It includes classical, robust, clustering, and risk-budgeting approaches

It also exposes portfolio measures, costs, constraints, and stress testing

Why it leads

- Natural fit for a typed Python decider implementation
- Time-series-aware model selection
- Broad optimizer and estimator catalog
- Active Python 3.13-compatible releases
- Easier ablation than a monolithic trading engine

Watch

- Solver availability and license
- Optimizer instability under noisy expected returns
- Hidden turnover from small forecast changes

#### CVXPortfolio

CVXPortfolio is strongest when holdings, transaction costs, constraints, and time interact

It can express single-period and multi-period policies with market simulators

Add it only when a simple constrained optimizer misses measured requirements

#### Riskfolio-Lib

Riskfolio-Lib provides a very broad set of risk measures and portfolio formulations

Use it to challenge the chosen optimizer on tail and hierarchical allocations

Its breadth increases the multiple-testing burden

#### PyPortfolioOpt

PyPortfolioOpt is a clear baseline for efficient frontiers, Black-Litterman, and HRP

Use it for transparent prototypes and comparison tests

Prefer skfolio when estimator selection and cross-validation matter

### Default policy

Start with a transparent constrained policy before optimizer search

1. Reject stale or invalid forecasts
2. Convert the forecast to expected net return
3. Shrink expected return toward zero
4. Scale by a conservative volatility estimate
5. Clip per-instrument risk
6. Neutralize required factors and currency
7. Apply gross, net, sector, and concentration limits
8. Suppress trades below a cost-aware no-trade threshold
9. Round only at the trader boundary
10. Emit target positions with a full decision trace

This policy becomes the control for skfolio and CVXPortfolio candidates

### Recommendation

Use a project-owned deterministic policy as the live baseline

Use skfolio for optimizer research and model selection

Add CVXPortfolio for measured cost-aware or multi-period needs

Evaluate NautilusTrader only as a deliberate full-stack replacement

## Other

### Decider interface

```text
model output
  -> confidence and freshness gate
  -> expected return and risk estimates
  -> constrained target optimization
  -> turnover and capacity limits
  -> decision
```

The decider must not place, retry, or reconcile orders

The trader interprets the decision without changing its portfolio intent

### Backtest and trading engines

| Engine | Architecture | Analysis strength | Live parity | Position |
| --- | --- | --- | --- | --- |
| [NautilusTrader](https://nautilustrader.io/) | Rust event core with Python | Microstructure and fills | Strong | Best full-engine option |
| [LEAN](https://www.lean.io/) | C# event engine with Python | Multi-asset institutional scope | Strong | Broad alternative platform |
| [vectorbt](https://vectorbt.dev/) | Vectorized pandas, NumPy, Numba, Rust | Massive parameter sweeps | Limited in OSS | Signal research |
| [Zipline Reloaded](https://github.com/stefan-jansen/zipline-reloaded) | Event driven | Equity factor research | Limited | Historical workflow |
| [backtesting.py](https://kernc.github.io/backtesting.py/) | Compact vector and event hybrid | Fast strategy prototypes | No | Educational control |
| [Backtrader](https://www.backtrader.com/) | Event driven | Mature feature breadth | Adapters vary | Legacy option |
| [bt](https://pmorissette.github.io/bt/) | Tree of allocation algos | Portfolio rebalancing | No | Allocation research |
| [QSTrader](https://www.quantstart.com/qstrader/) | Event driven | Portfolio backtests | No | Educational reference |

#### NautilusTrader

NautilusTrader provides nanosecond event simulation, order books, fills, risk, and live adapters

Its Rust core and Python strategy surface make it the performance leader in this catalog

Adopting it would replace several money-tree responsibilities rather than fill one layer

Evaluate it as an architecture choice, not a small decider dependency

#### LEAN

LEAN supports research, backtest, portfolio construction, risk, and live venues

It offers many built-in portfolio models and corporate-action handling

Its C# engine and complete framework can compose and execute the money-tree interfaces

#### vectorbt

vectorbt is ideal for broad vectorized signal and parameter exploration

The open edition does not provide the full feature set advertised for its paid edition

Use it to reject weak ideas quickly, then verify finalists in an event engine

#### Older Python engines

Backtrader's latest PyPI upload observed here is from 2023

Zipline Reloaded, backtesting.py, bt, and QSTrader have more recent releases

Prefer maintained engines for new production dependencies

### Pricing and valuation engines

| Engine | Focus | Runtime | Best use |
| --- | --- | --- | --- |
| [QuantLib](https://www.quantlib.org/) | Derivatives, curves, credit, risk | C++ with Python bindings | Standard pricing reference |
| [FinancePy](https://github.com/domokane/FinancePy) | Rates, credit, equity, FX | Python plus Numba | Readable pricing research |
| [rateslib](https://rateslib.com/) | Fixed-income curves and derivatives | Python | Rates portfolios |
| [OpenGamma Strata](https://strata.opengamma.io/) | Market risk and derivatives | Java | Institutional JVM stack |

Use these engines to derive fair value, Greeks, and risk inputs

Do not use them as a general target-position policy

### Analytics and reporting engines

| Engine | Focus | Use |
| --- | --- | --- |
| [QuantStats](https://github.com/ranaroussi/quantstats) | Performance reports | Human review |
| [empyrical-reloaded](https://github.com/stefan-jansen/empyrical-reloaded) | Return and risk metrics | Programmatic metrics |
| [OpenBB](https://openbb.co/) | Research data and analysis platform | Analyst workspace |
| [Microsoft Qlib](https://github.com/microsoft/qlib) | AI research workflow | End-to-end experiment reference |
| [TA-Lib](https://ta-lib.org/) | Technical indicators | Feature baselines |

Reports never validate a strategy by themselves

Use one canonical metric implementation in automated promotion gates

### Package status

Versions are current PyPI releases observed on 2026-07-28

| Package | Version | Python | Last release |
| --- | --- | --- | --- |
| [skfolio](https://pypi.org/project/skfolio/) | 0.20.1 | `>=3.10` | 2026-04 |
| [Riskfolio-Lib](https://pypi.org/project/riskfolio-lib/) | 7.3.0 | `>=3.10` | 2026-05 |
| [PyPortfolioOpt](https://pypi.org/project/pyportfolioopt/) | 1.6.0 | Unspecified | 2026-02 |
| [vectorbt](https://pypi.org/project/vectorbt/) | 1.1.0 | `>=3.11,<3.15` | 2026-07 |
| [backtesting](https://pypi.org/project/backtesting/) | 0.6.6 | `>=3.9` | 2026-07 |
| [backtrader](https://pypi.org/project/backtrader/) | 1.9.78.123 | Unspecified | 2023-04 |
| [zipline-reloaded](https://pypi.org/project/zipline-reloaded/) | 3.1.1 | `>=3.10` | 2025-07 |
| [nautilus-trader](https://pypi.org/project/nautilus-trader/) | 1.230.0 | `>=3.12,<3.15` | 2026-06 |
| [bt](https://pypi.org/project/bt/) | 1.2.0 | `>=3.9` | 2026-04 |
| [QuantStats](https://pypi.org/project/quantstats/) | 0.0.81 | `>=3.10` | 2026-01 |
| [QuantLib](https://pypi.org/project/QuantLib/) | 1.43 | Unspecified | 2026-07 |
| [FinancePy](https://pypi.org/project/financepy/) | 1.0.1 | `>=3.8` | 2025-08 |
| [rateslib](https://pypi.org/project/rateslib/) | 2.7.1 | `>=3.10` | 2026-04 |

Install candidates in isolated extras because solver dependencies vary

### Solver and failure rules

- Set an explicit solver and version
- Bound solve time
- Reject infeasible results
- Verify every constraint after solving
- Compare predicted and realized turnover
- Use deterministic fallback targets
- Never reuse stale targets without an expiry
- Attach optimizer inputs and status to the decision trace
- Treat NaN, infinite, and missing risk values as fatal

### Evaluation

Compare deciders with identical forecasts and execution assumptions

Measure these outcomes

- Net return after modeled costs
- Turnover and trade count
- Gross, net, factor, and currency exposure
- Concentration and liquidity usage
- Drawdown and expected shortfall
- Constraint violation count
- Solver time and failure rate
- Sensitivity to small forecast perturbations
- Performance under forecast sign inversion

The sign-inversion test exposes accidental beta and backtest leakage
