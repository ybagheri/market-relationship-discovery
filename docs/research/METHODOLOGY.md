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
8. Label all output as a research candidate unless a later validation process proves more.

## Statistical limitations

Pearson correlation measures linear co-movement; Spearman measures rank co-movement. Neither establishes causality, cointegration, or arbitrage. Rolling z-score depends on its window and regime. Half-life is descriptive and unstable in non-stationary or sparse data. Lead/lag results can change with resampling and timestamp tolerance.

A complete cointegration workflow, stationarity tests, multiple-testing correction, and out-of-sample ranking are planned but are not claimed as implemented in this foundation.

## Data requirements

Tick data is preferred for cross-broker executable research. Bar data supports slower relationship research but cannot establish a tick-level opportunity. Broker symbol specifications, sessions, timestamps, and feed aggregation must be recorded.
