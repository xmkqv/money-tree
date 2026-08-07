# Models

Research record, predating money_tree/node.py

Tensor transformations and stateful or device-backed model operations share the unified `models` concern

Transform and predict are not layers; they are instances of one interface selected by
config, and callers own their composition and execution

`model(model_config, grain): prediction`

Loading and batching are not part of this concern; they terminate the locked data pipe,
which is described in [Data](data.md)

## Model stacks and predictors

Research checked on 2026-07-28

### Shape-compliant options

#### Decision

Use a benchmark portfolio rather than naming one universal forecasting model

Adopt these initial roles

| Role | Default | Reason |
| --- | --- | --- |
| AutoML benchmark | AutoGluon TimeSeries | Strong preprocessing, selection, and ensembles |
| Trainable Torch model | NeuralForecast NHITS | Fast and strong long-horizon baseline |
| Trainable Transformer | NeuralForecast PatchTST | Efficient modern challenger |
| Zero-shot model | Chronos-2 | Multivariate and covariate-aware pretrained path |
| Interpretable model | PyTorch Forecasting TFT | Variable selection and attention diagnostics |
| Classical controls | Seasonal naive and linear | Detect expensive models that add no value |

No model operation should influence live decisions until it beats controls in purged walk-forward tests after costs

#### Foundation models

##### Chronos-2

[Chronos-2](https://github.com/amazon-science/chronos-forecasting) is the first
pretrained candidate

Its official pipeline supports univariate, multivariate, and covariate-informed forecasts

The package also includes smaller Chronos-Bolt checkpoints

Chronos-Bolt is useful when latency and memory dominate accuracy

Strengths

- Direct pretrained inference
- Quantile forecasts
- Pandas panel interface
- Multiple checkpoint sizes
- Active 2026 releases

Watch

- GPU and model-download requirements
- Model-card license and redistribution terms
- Sensitivity to financial scale changes and market closures
- Fine-tuning cost against simple trainable models

##### TimesFM 2.5

[TimesFM 2.5](https://github.com/google-research/timesfm) offers a 200M Torch model

The official repository reports a 16k context and a 1k horizon

It provides an optional quantile head and XReg covariate support

Strengths

- Long context
- Simple zero-shot interface
- Torch and Flax backends
- Input normalization in the model pipeline
- Apache-licensed code

Watch

- The open package is not a supported Google product
- Covariates use a separate regression path
- Checkpoint terms still need model-card review

##### Moirai 2.0

[Uni2TS](https://github.com/SalesforceAIResearch/uni2ts) is a Torch library for Moirai

Moirai is designed for varied frequencies, dimensions, and distributions

Strengths

- Any-variate modeling
- Probabilistic outputs
- Flexible patching
- Published evaluation tooling

Watch

- More research surface than production surface
- Smaller operations community than Chronos or AutoGluon
- Reproduce finance-specific results before adoption

#### Trainable Torch libraries

##### NeuralForecast

[NeuralForecast](https://github.com/Nixtla/neuralforecast) is the preferred lean
training stack

It includes NHITS, NBEATSx, PatchTST, iTransformer, TFT, DeepAR, TiDE, and others

Start with a deliberately small model set

| Model | Add when | Avoid when |
| --- | --- | --- |
| NHITS | Long horizon or smooth multi-scale structure | Very short irregular events |
| PatchTST | Long context and global panel scale | Covariate semantics are still unclear |
| TFT | Rich known inputs and interpretation matter | Latency or simplicity dominates |
| NBEATSx | Exogenous inputs with a strong basis model | Cross-series interactions dominate |
| DeepAR | Distributional autoregressive control | Long sampled inference is too slow |
| DLinear | Cheap strong linear control | Nonlinear lift is already proven |

##### PyTorch Forecasting

[PyTorch Forecasting models](https://pytorch-forecasting.readthedocs.io/en/stable/models.html)
include TFT, NHiTS, DeepAR, and NBEATS

Use it when its dataset and interpretation tooling justify a Lightning dependency

TFT is not a default merely because finance has many features

Its value must appear in ablations and stable feature importance

##### Darts

[Darts Torch models](https://unit8co.github.io/darts/userguide/torch_forecasting_models)
share fit, predict, backtest, covariate, and checkpoint interfaces

Use Darts for rapid model interchange and foundation-model experiments

Do not let Darts backtests stand in for order and fill simulation

##### AutoGluon TimeSeries

[AutoGluon TimeSeries](https://auto.gluon.ai/stable/tutorials/timeseries/forecasting-quick-start.html)
fits statistical, tree, deep, foundation, and weighted ensemble models

Use its time budget and leaderboard to establish a hard benchmark

Inspect skipped or failed models rather than accepting the final leaderboard blindly

Its current release requires Python below 3.14

#### Package status

Versions are current PyPI releases observed on 2026-07-28

| Package | Version | Python | Position |
| --- | --- | --- | --- |
| [torch](https://pypi.org/project/torch/) | 2.13.0 | `>=3.10` | Runtime |
| [NeuralForecast](https://pypi.org/project/neuralforecast/) | 3.2.0 | `>=3.10` | Preferred trainable stack |
| [PyTorch Forecasting](https://pypi.org/project/pytorch-forecasting/) | 1.8.0 | `>=3.10,<3.15` | Rich covariate stack |
| [Darts](https://pypi.org/project/u8darts/) | 0.41.0 | `>=3.10` | Unified experiment stack |
| [Chronos](https://pypi.org/project/chronos-forecasting/) | 2.3.1 | `>=3.10` | Preferred pretrained stack |
| [TimesFM](https://pypi.org/project/timesfm/) | 2.0.2 | `>=3.10` | Pretrained challenger |
| [Uni2TS](https://pypi.org/project/uni2ts/) | 2.0.0 | `>=3.10` | Moirai challenger |
| [AutoGluon TimeSeries](https://pypi.org/project/autogluon.timeseries/) | 1.5.0 | `>=3.10,<3.14` | AutoML benchmark |
| [GluonTS](https://pypi.org/project/gluonts/) | 0.16.3 | `>=3.7` | Probabilistic toolkit |

Resolve and smoke-test every full extra on Python 3.13

Metadata compatibility does not guarantee binary-wheel compatibility

#### Recommendation

Use AutoGluon to learn what is competitive

Use NeuralForecast to build the first narrow Torch production path

Keep Chronos-2 as the pretrained benchmark and fallback

Earn every more complex model through leakage-safe financial evaluation

### Other

#### What high performance means

Rank models on a Pareto frontier rather than one public benchmark score

| Axis | Required evidence |
| --- | --- |
| Forecast skill | Out-of-sample loss across regimes and instruments |
| Decision value | Net return, turnover, drawdown, and capacity |
| Calibration | Coverage and sharpness of forecast intervals |
| Stability | Dispersion across windows, universes, and seeds |
| Latency | Batch and single-snapshot inference |
| Throughput | Forecasts per second at the live universe size |
| Memory | Peak host and accelerator memory |
| Operability | Deterministic load, versioning, and failure behavior |

Published time-series benchmark wins are candidate evidence only

Financial data differs through low signal, drift, revisions, and transaction costs

#### Ready-made transform and model combinations

| Combination | Model family | Covariates | Probabilistic | Best use |
| --- | --- | --- | --- | --- |
| AutoGluon plus Chronos-2 ensemble | Foundation plus mixed ensemble | Known, past, static | Yes | Broad first benchmark |
| NeuralForecast plus NHITS | MLP interpolation | Static, historic, future | Yes | Long horizon and global panels |
| NeuralForecast plus PatchTST | Patch Transformer | Static, historic, future | Yes | Long context with many series |
| PyTorch Forecasting plus TFT | Recurrent attention | Rich typed covariates | Yes | Interpretability and regime features |
| PyTorch Forecasting plus NHiTS | Hierarchical interpolation | Covariates | Yes | Direct multi-horizon forecasts |
| Darts Pipeline plus NHiTS or TFT | Multiple | Past and future | Yes | Unified experiments |
| Chronos pipeline plus Chronos-2 | Foundation Transformer | Native in Chronos-2 | Yes | Zero-shot and low-data tasks |
| TimesFM normalization plus 2.5 | Decoder-only foundation model | XReg | Yes | Long zero-shot contexts |
| Uni2TS plus Moirai 2.0 | Universal masked Transformer | Any-variate | Yes | Research on mixed variates |
| GluonTS transforms plus DeepAR | Autoregressive recurrent | Dynamic and static | Yes | Mature probabilistic baseline |

Transforms and model execution appear together because both are operations in the models concern

#### Prediction targets

Predict tradable quantities rather than raw prices by default

| Target | Use |
| --- | --- |
| Forward log return | Direction and magnitude |
| Residual return | Cross-sectional selection |
| Realized volatility | Sizing and risk |
| Return quantiles | Tail-aware allocation |
| Probability of positive net return | Threshold policies |
| Spread or slippage | Execution-aware gating |
| Liquidity or volume | Capacity and scheduling |

Use separate heads or models when target scales and loss functions conflict

Never select the target only because one model forecasts it well

#### Validation design

1. Freeze point-in-time source snapshots
2. Split by time before fitting any transform
3. Purge overlapping label horizons
4. Add an embargo for selection and delayed inputs
5. Evaluate expanding and rolling windows
6. Test stable and stressed market regimes
7. Preserve delisted instruments in historical universes
8. Tune inside each training window or freeze tuning beforehand
9. Report all tried models to expose selection bias
10. Re-run finalists across multiple seeds

##### Metrics

Forecast metrics

- Mean absolute scaled error
- Root mean squared scaled error
- Quantile loss
- Interval coverage and width
- Brier score for directional probabilities
- Rank information coefficient

Decision metrics

- Net return after fees and spread
- Turnover and holding time
- Maximum drawdown
- Tail loss and downside deviation
- Exposure and concentration
- Capacity under volume limits

Operations metrics

- Cold-start time
- P50 and P99 inference latency
- Universe throughput
- Peak CPU and accelerator memory
- Artifact and checkpoint size
- Failure rate on missing or novel inputs

#### Ensemble rule

Prefer a small diverse ensemble over many correlated Transformers

Include at least one naive, one linear, one trainable Torch, and one pretrained model

Fit ensemble weights only on out-of-fold predictions

Constrain weights and record the exact constituent versions

Disable a constituent when its live input contract is not satisfied

#### Interface implications

The generic models interface permits any input-to-output operation

A scalar mapping per symbol is sufficient for a first point-return model

Probabilistic trading will eventually need these additional fields

- Horizon and target unit
- Point estimate
- Quantiles or distribution parameters
- Calibration state
- Prediction timestamp
- Model and transform hash
- Data snapshot id
- Validity and staleness

Add a richer implementation-specific output only after the first benchmark proves its use

#### Adoption sequence

1. Implement seasonal-naive and linear controls
2. Benchmark AutoGluon under a fixed time budget
3. Train NeuralForecast NHITS and PatchTST on the same folds
4. Run Chronos-2 zero-shot on unchanged test windows
5. Add TFT only for a rich-covariate ablation
6. Compare net decision value and operations cost
7. Promote the smallest model on the winning Pareto frontier
8. Shadow it before paper orders

## Tensor transforms and preprocessing

Research checked on 2026-07-28

### Shape-compliant options

#### Decision

Keep point-in-time market transforms in project code

Delegate scaling, windowing, and tensor collation to the selected Torch model stack

Benchmark three ready-made transform and model combinations first

1. AutoGluon TimeSeries plus Chronos-2 and its weighted ensemble
2. NeuralForecast scaling plus NHITS and PatchTST
3. Darts pipelines plus NHiTS, TFT, and foundation-model challengers

This avoids one universal transform layer that copies data into every library's private format

#### Package status

Versions are current PyPI releases observed on 2026-07-28

| Package | Version | Python range | Activity | Role |
| --- | --- | --- | --- | --- |
| [torch](https://pypi.org/project/torch/) | 2.13.0 | `>=3.10` | 2026-07 release | Tensor runtime |
| [AutoGluon TimeSeries](https://pypi.org/project/autogluon.timeseries/) | 1.5.0 | `>=3.10,<3.14` | 2025-12 release | AutoML pipeline |
| [NeuralForecast](https://pypi.org/project/neuralforecast/) | 3.2.0 | `>=3.10` | 2026-07 release | Fast global models |
| [Darts](https://pypi.org/project/u8darts/) | 0.41.0 | `>=3.10` | 2026-02 release | Unified transforms and models |
| [PyTorch Forecasting](https://pypi.org/project/pytorch-forecasting/) | 1.8.0 | `>=3.10,<3.15` | 2026-06 release | Dataset plus Lightning models |
| [Chronos](https://pypi.org/project/chronos-forecasting/) | 2.3.1 | `>=3.10` | 2026-07 release | Pretrained pipeline |
| [TimesFM](https://pypi.org/project/timesfm/) | 2.0.2 | `>=3.10` | 2026-07 release | Pretrained pipeline |
| [Uni2TS](https://pypi.org/project/uni2ts/) | 2.0.0 | `>=3.10` | 2025-11 release | Moirai pipeline |
| [GluonTS](https://pypi.org/project/gluonts/) | 0.16.3 | `>=3.7` | 2026-06 release | Transform framework |

Package metadata allows Python 3.13 unless the full dependency solver says otherwise

Lock each candidate in an isolated workspace extra before choosing it

#### Combination details

##### AutoGluon TimeSeries

The [quick start](https://auto.gluon.ai/stable/tutorials/timeseries/forecasting-quick-start.html)
uses a long panel with item id, timestamp, target, and optional covariates

One fit call can train statistical, tree, Torch, foundation, and ensemble models

Its current medium preset includes Chronos-2 and Temporal Fusion Transformer

Use it as the benchmark harness rather than the core production data contract

Best qualities

- Automatic frequency handling and validation
- Known, past, and static covariates
- Probabilistic forecasts and model selection
- Weighted ensembles over diverse model families
- A direct route to Chronos-2

Risks

- Heavy environment with constrained Python versions
- Some candidate failures are skipped rather than fatal
- Internal preprocessing is less transparent than a narrow custom path

##### NeuralForecast

[NeuralForecast](https://github.com/Nixtla/neuralforecast) exposes a consistent
long-data interface across NHITS, PatchTST, TFT, DeepAR, and many other Torch models

Its model configuration includes temporal scaling and exogenous variable lists

Use one scaler choice per experiment and persist the full model checkpoint

Best qualities

- Broad modern Torch model set
- Global training across many instruments
- Probabilistic losses and exogenous inputs
- Cross-validation and distributed training support
- Small distance from a pandas or Polars panel

Risks

- Model-specific preprocessing still needs careful inspection
- Financial calendars and point-in-time joins remain project concerns

##### Darts

Darts provides a composable
[Pipeline](https://unit8co.github.io/darts/generated_api/darts.dataprocessing.pipeline.html)

Its [transformers](https://unit8co.github.io/darts/generated_api/darts.dataprocessing.transformers.html)
include missing-value filling, scaling, differencing, Box-Cox, and window transforms

Pipelines can fit, transform, invert, and parallelize across multiple series

Best qualities

- Most complete ready-made preprocessing surface
- Uniform historical forecasts and backtests
- Native covariate encoders
- Classical, Torch, and foundation models under one API

Risks

- The `TimeSeries` container becomes another domain model
- Silent interpolation is dangerous for market closures and stale quotes
- General-purpose backtesting is not execution simulation

##### PyTorch Forecasting

[`TimeSeriesDataSet`](https://pytorch-forecasting.readthedocs.io/en/stable/api/pytorch_forecasting.data.timeseries.TimeSeriesDataSet.html)
handles variable groups, encoders, scalers, lags, and encoder-decoder windows

Use it when TFT interpretation or fine control over covariates wins the benchmark

Best qualities

- Strong categorical and continuous covariate handling
- Per-group normalization
- Randomized training windows
- Direct fit with TFT, NHiTS, and DeepAR

Risks

- Dataset construction can consume substantial memory
- Large out-of-core datasets need a custom dataset path
- Lightning choices propagate into training and deployment

##### Foundation pipelines

[Chronos-2](https://github.com/amazon-science/chronos-forecasting) accepts
univariate, multivariate, and covariate-informed inputs

[TimesFM 2.5](https://github.com/google-research/timesfm) provides a Torch
checkpoint, input normalization, 16k context, and optional quantile forecasts

[Moirai](https://github.com/SalesforceAIResearch/uni2ts) uses the Torch-based
Uni2TS transformation and evaluation stack

Treat each internal normalization path as part of the checkpoint

Do not apply a second scaler unless the model documentation explicitly requires it

##### Grain

Grain is locked as the batching stage of the data pipe and is described in
[Data](data.md); every option above receives its batches rather than loading data itself

#### Recommendation

Start with AutoGluon as the breadth-first benchmark

Promote NeuralForecast plus NHITS and PatchTST as the first lean production challenger

Use Darts when its preprocessing and evaluation surface saves more code than it adds

Keep point-in-time finance logic outside every model library

### Other

#### Required transform boundary

```text
committed observations
  -> point-in-time joins
  -> aligned panel
  -> train-only fitted transforms
  -> model-native windows
  -> tensors and masks
```

The transform artifact must contain both configuration and fitted state

The same artifact must be used for backtest, paper, and live inference

#### Ready-made combinations

| Rank | Preprocessor | Model | Best fit | Main tradeoff |
| --- | --- | --- | --- | --- |
| 1 | AutoGluon `TimeSeriesDataFrame` | Chronos-2 plus ensemble | Fast broad benchmark | Python `<3.14` and a large dependency set |
| 2 | NeuralForecast built-in scaling | NHITS plus PatchTST | Trainable global models | Less preprocessing breadth |
| 3 | Darts `Pipeline` | NHiTS, TFT, or Chronos-2 | Unified experiments | Its data abstraction overlaps money-tree |
| 4 | PyTorch Forecasting `TimeSeriesDataSet` | TFT, NHiTS, or DeepAR | Rich covariates | Lightning-centric training stack |
| 5 | TimesFM normalization | TimesFM 2.5 | Long zero-shot context | XReg handles covariates separately |
| 6 | Uni2TS transforms | Moirai 2.0 | Any-variate probabilistic work | Research-oriented integration |
| 7 | GluonTS transform chains | PyTorch estimators | Custom probabilistic models | Lower-level composition |

These combinations belong here because preprocessing and model execution share one concern

#### Financial transforms

A project-owned models operation should handle only domain facts shared across models

| Concern | Required behavior |
| --- | --- |
| Corporate actions | Use adjusted or raw series consistently |
| Symbol changes | Resolve through point-in-time instrument ids |
| Calendar | Keep venue sessions and explicit missingness |
| Returns | Declare arithmetic, log, horizon, and currency |
| Fundamentals | Join on first available time, not period end |
| Macro | Select the vintage known at prediction time |
| FX | Convert with a contemporaneously available rate |
| Staleness | Emit age and mask rather than forward-fill silently |
| Cross-section | Fit ranks and normalizers inside each timestamp |
| Targets | Shift before splitting and audit the final train timestamp |

Do not interpolate across exchange closures

Do not normalize with validation or test observations

Do not compute revised features before their publication time

Do not let a window cross an instrument's listing or delisting boundary

#### Transform artifact

Persist these values for every fitted pipeline

- Input schema and units
- Instrument universe rule
- Calendar and timezone
- Feature definitions
- Target definition and horizon
- Split boundaries
- Fitted scaler state
- Missing-value policy
- Window and stride
- Covariate availability class
- Library and checkpoint versions
- Source snapshot ids
- Code revision

Hash the artifact and attach the hash to every model output

#### Performance rules

1. Filter and join in DuckDB or Polars before materializing tensors
2. Keep Arrow-native numeric columns until model conversion
3. Batch many instruments into global models
4. Avoid repeated pandas index reshaping inside each epoch
5. Use pinned host memory only when transfer benchmarks improve
6. Set mixed precision only after accuracy and calibration checks
7. Benchmark `torch.compile` on stable shapes and real horizons
8. Cache deterministic windows by snapshot and transform hash
9. Profile data pipeline stalls before increasing GPU size

High performance means end-to-end throughput without leakage

It does not mean the fastest isolated tensor transform

#### Evaluation protocol

Use the same committed panel and split schedule for every combination

Measure these transform-specific outcomes

- Rows rejected by schema checks
- Missingness by feature and session
- Fit and transform wall time
- Peak host memory
- Host-to-device throughput
- Artifact size
- Inverse-transform round-trip error
- Reproducibility across processes
- Leakage audit failures
