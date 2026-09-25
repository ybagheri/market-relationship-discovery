# Walk-Forward Validation

## Objective

Walk-forward validation separates parameter selection from evaluation. Each fold has chronological train, validation, and test windows. A signal at time `t` is paired only with the next observation inside the same evaluation window.

## Current implementation

`WalkForwardSplitter` creates rolling folds from a unique, sorted UTC `DatetimeIndex`. Train, validation, and test windows do not overlap inside a fold. With a step smaller than the train size, later training windows may contain earlier test observations, as expected in a rolling design; test windows must remain sequential and are not used to choose the current threshold.

`WalkForwardValidator` evaluates candidate activation thresholds on train data only, selects the threshold with the highest mean next-observation net edge, reports validation performance, and then evaluates that fixed threshold on test data. A fold with insufficient train trades is marked as such and contributes no test trades.

The final timestamp in each window is not executed because its next observation is outside that window. This conservative boundary prevents a signal from using an outcome across a train/validation/test split.

## Multi-stage research

`MultiStageBacktester` combines causal score columns with explicit weights and thresholds. `CausalFeatureBuilder` supplies rolling z-score, momentum, and realized-volatility features that use only current and past values. The ensemble is evaluated at the next observation, and each individual stage is also reported.

Stage columns must themselves be causal. The engine cannot infer whether an externally supplied column contains future leakage.

## Reproducibility

Every CLI experiment records an `EXP-*` identifier, UTC creation time, software version, source filename, SHA-256 hash, data period, parameters, limitations, and the generated JSON report path. The report does not include the absolute source path.

## Limitations

The current selector handles scalar activation thresholds only. It does not fit arbitrary machine-learning models, perform combinatorial parameter optimization, or correct for multiple testing. Walk-forward results remain historical hypotheses and do not guarantee future performance.
