# Backtesting

## Implemented research controls

`ResearchBacktester.run_next_observation` pairs a signal at timestamp `t` only with edge and cost at `t+1`. `WalkForwardValidator` selects an activation threshold on train data only, reports validation, and evaluates the fixed threshold on each test window. Signals and outcomes cannot cross the end of an evaluation window.

`MultiStageBacktester` combines causal score columns with explicit weights and thresholds. It reports the ensemble and every individual stage. `CausalFeatureBuilder` provides rolling z-score, momentum, and realized-volatility features that use only current and past values.

## Reproducibility

CLI experiments generate an `EXP-*` identifier and JSON report containing software version, source filename and SHA-256, UTC data period, parameters, fold windows, metrics, trades, and limitations.

## Required future controls

- Arbitrary model fitting must receive training data only.
- Combinatorial optimization requires multiple-testing controls.
- Slippage, spread widening, latency, and session gaps require scenario tests.
- Walk-forward does not replace Monte Carlo robustness testing.
- Externally supplied stage columns must be audited for causality.

## Interpretation

A positive result is a hypothesis under assumptions, not guaranteed profit. The example CSV files are deterministic software fixtures and are not market evidence. No order execution or fill simulation is implemented.
