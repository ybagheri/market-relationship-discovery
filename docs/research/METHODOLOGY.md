# Research Methodology

## Scope

Research classifies observations into theoretical discrepancy, executable discrepancy under explicit bid/ask assumptions, statistical relationship, and cost-adjusted hypothetical edge. These classes are not interchangeable.

## Pipeline

1. Normalize source timestamps to UTC.
2. Validate duplicates, missing values, positive prices, and bid/ask invariants.
3. Align feeds within a configured tolerance and retain delay information.
4. Parse and evaluate synthetic formulas.
5. Compare actual quote with theoretical and executable synthetic intervals.
6. Apply spread-independent research cost assumptions separately.
7. Measure correlation, spread normalization, persistence, and lead/lag.
8. Compute causal rolling beta and stability diagnostics.
9. Report an OLS-residual cointegration check using an augmented Dickey-Fuller test on the residuals, corroborated by a KPSS level-stationarity test.
10. Label all output as a research candidate unless a later validation process proves more.

## Stationarity and cointegration

Cointegration is tested with a two-step Engle-Granger style procedure. The target is regressed on the benchmark, and an augmented Dickey-Fuller test with AIC lag selection is applied to the OLS residuals using `statsmodels`. A KPSS level-stationarity test is run on the same residuals as corroboration, because both tests can reject and a disagreement is a meaningful result.

Two safeguards exist because a naive implementation of this procedure reports confident false positives:

- At least 30 aligned observations are required. Below that the result is reported as `unavailable` with a reason.
- A constant, non-finite, or otherwise degenerate residual series is reported as `unavailable`. A perfect formula identity leaves no residual variation to test, and an earlier approximation returned a sentinel value that was reported as strong cointegration evidence.

Each result reports `cointegrated_at_significance`, the ADF and KPSS conclusions, whether the two tests agree, and `kpss_p_value_is_bounded`. The KPSS lookup table bounds its p-value from below, so a bounded result is flagged rather than presented as an exact probability.

A rejected null hypothesis is evidence about the historical sample only. It is not evidence of an executable edge, and it does not survive costs by itself.

## Statistical limitations

Pearson correlation measures linear co-movement; Spearman measures rank co-movement. Neither establishes causality, cointegration, or arbitrage. Rolling z-score depends on its window and regime. Half-life is descriptive and unstable in non-stationary or sparse data. Lead/lag results can change with resampling and timestamp tolerance.

The cointegration, ADF, and KPSS outputs are retrospective full-sample diagnostics. They do not establish causality, execution, future returns, or multiple-testing-adjusted significance. Advanced research also supports causal volatility regimes, dependency-graph expansion, and deterministic chronological ridge ranking over bar-price panels.

## Data requirements

Tick data is preferred for cross-broker executable research. Bar data supports slower relationship research but cannot establish a tick-level opportunity. Broker symbol specifications, sessions, timestamps, and feed aggregation must be recorded.
