# Advanced Discovery

## Scope

Advanced discovery operates on a bar-price panel and produces research candidates. It does not claim that a historical formula relationship is executable or profitable, and it does not use future observations to fit its ranking model.

## Price panel input

`discover --input` accepts CSV or Parquet files in either format:

- Wide: `timestamp,EURUSD,GBPUSD,EURGBP`
- Long: `timestamp,symbol,close`

Long input is pivoted into a wide panel. Timestamps are parsed as UTC, panels are sorted, duplicate wide timestamps and duplicate `(timestamp, symbol)` rows are rejected, prices must be numeric and positive, and missing values are not forward-filled.

## Pipeline

1. Load and validate the panel.
2. Build a directed hypergraph from the declarative relationship catalog. Each formula is one edge with all of its source symbols.
3. Expand relationships from observed symbols up to `--max-depth`.
4. Evaluate target-versus-synthetic discrepancy, Pearson, Spearman, half-life, rolling z-score, causal regime labels, and rolling beta stability.
5. Report retrospective OLS-residual cointegration, fixed-lag ADF, and level KPSS approximation diagnostics.
6. Fit a standardized NumPy ridge model on the chronological training portion only.
7. Predict and rank candidates on later observations by mean predicted next absolute z-score.
8. Write an `EXP-*.json` report with source hash, parameters, regimes, graph edges, candidate summaries, ranking metadata, and limitations.

## Regimes

Volatility is the rolling standard deviation of log returns. Low and high thresholds are expanding quantiles of volatility observed by that timestamp, so future data cannot change earlier labels. A constant-price segment is labeled normal volatility.

## Statistical diagnostics

`--rolling-beta-window` controls the causal beta window. Beta stability reports valid windows, sign fractions, sign consistency, and dispersion. Cointegration uses an OLS residual ADF approximation; ADF uses a fixed-lag OLS normal approximation; KPSS uses a level CUSUM chi-square approximation. These tests are retrospective full-sample diagnostics and are not ranking features.

## Ranking safety

The ridge model is deterministic, uses no random seed, and does not import or require scikit-learn. `next_abs_zscore` is an outcome label used only for training/evaluation of the ranker, never as an input feature. Insufficient observations produce explicit candidate status and are excluded from the ranked list.

The output is a research ordering, not a profitability claim. Bar data does not establish tick execution, and the report does not model funding, commission, margin, slippage, latency, partial fills, or broker-specific rules.
