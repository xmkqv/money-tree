# Transformers

Research checked on 2026-07-28

## Shape-compliant options

### Decision

Keep point-in-time market transforms in project code

Delegate scaling, windowing, and tensor collation to the selected Torch model stack

Benchmark three ready-made preprocessor and predictor combinations first

1. AutoGluon TimeSeries plus Chronos-2 and its weighted ensemble
2. NeuralForecast scaling plus NHITS and PatchTST
3. Darts pipelines plus NHiTS, TFT, and foundation-model challengers

This avoids one universal transformer that copies data into every library's private format

### Package status

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

### Combination details

#### AutoGluon TimeSeries

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

#### NeuralForecast

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

#### Darts

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

#### PyTorch Forecasting

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

#### Foundation pipelines

[Chronos-2](https://github.com/amazon-science/chronos-forecasting) accepts
univariate, multivariate, and covariate-informed inputs

[TimesFM 2.5](https://github.com/google-research/timesfm) provides a Torch
checkpoint, input normalization, 16k context, and optional quantile forecasts

[Moirai](https://github.com/SalesforceAIResearch/uni2ts) uses the Torch-based
Uni2TS transformation and evaluation stack

Treat each internal normalization path as part of the checkpoint

Do not apply a second scaler unless the model documentation explicitly requires it

### Recommendation

Start with AutoGluon as the breadth-first benchmark

Promote NeuralForecast plus NHITS and PatchTST as the first lean production challenger

Use Darts when its preprocessing and evaluation surface saves more code than it adds

Keep point-in-time finance logic outside every model library

## Other

### Required transform boundary

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

### Ready-made combinations

| Rank | Preprocessor | Predictor | Best fit | Main tradeoff |
| --- | --- | --- | --- | --- |
| 1 | AutoGluon `TimeSeriesDataFrame` | Chronos-2 plus ensemble | Fast broad benchmark | Python `<3.14` and a large dependency set |
| 2 | NeuralForecast built-in scaling | NHITS plus PatchTST | Trainable global models | Less preprocessing breadth |
| 3 | Darts `Pipeline` | NHiTS, TFT, or Chronos-2 | Unified experiments | Its data abstraction overlaps money-tree |
| 4 | PyTorch Forecasting `TimeSeriesDataSet` | TFT, NHiTS, or DeepAR | Rich covariates | Lightning-centric training stack |
| 5 | TimesFM normalization | TimesFM 2.5 | Long zero-shot context | XReg handles covariates separately |
| 6 | Uni2TS transforms | Moirai 2.0 | Any-variate probabilistic work | Research-oriented integration |
| 7 | GluonTS transform chains | PyTorch estimators | Custom probabilistic models | Lower-level composition |

Duplication with the model catalog is intentional

### Financial transforms

The project-owned transformer should handle only domain facts shared across models

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

### Transform artifact

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

Hash the artifact and attach the hash to every forecast

### Performance rules

1. Filter and join in DuckDB or Polars before materializing tensors
2. Keep Arrow-native numeric columns until model conversion
3. Batch many instruments into global models
4. Avoid repeated pandas index reshaping inside each epoch
5. Use pinned host memory only when transfer benchmarks improve
6. Set mixed precision only after accuracy and calibration checks
7. Benchmark `torch.compile` on stable shapes and real horizons
8. Cache deterministic windows by snapshot and transform hash
9. Profile data-loader stalls before increasing GPU size

High performance means end-to-end throughput without leakage

It does not mean the fastest isolated tensor transform

### Evaluation protocol

Use the same committed panel and split schedule for every combination

Measure these transformer-specific outcomes

- Rows rejected by schema checks
- Missingness by feature and session
- Fit and transform wall time
- Peak host memory
- Host-to-device throughput
- Artifact size
- Inverse-transform round-trip error
- Reproducibility across processes
- Leakage audit failures
