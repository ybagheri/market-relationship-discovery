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
9. Report retrospective OLS-residual cointegration, fixed-lag ADF, and level KPSS approximations.
10. Label all output as a research candidate unless a later validation process proves more.

## Statistical limitations

Pearson correlation measures linear co-movement; Spearman measures rank co-movement. Neither establishes causality, cointegration, or arbitrage. Rolling z-score depends on its window and regime. Half-life is descriptive and unstable in non-stationary or sparse data. Lead/lag results can change with resampling and timestamp tolerance.

The cointegration, ADF, and KPSS outputs are retrospective full-sample approximations. They do not establish causality, execution, future returns, or multiple-testing-adjusted significance. Advanced research also supports causal volatility regimes, dependency-graph expansion, and deterministic chronological ridge ranking over bar-price panels.

## Data requirements

Tick data is preferred for cross-broker executable research. Bar data supports slower relationship research but cannot establish a tick-level opportunity. Broker symbol specifications, sessions, timestamps, and feed aggregation must be recorded.
