# Monte Carlo Robustness

## Purpose

Monte Carlo analysis measures how a historical trade sequence behaves under resampling and explicit stress assumptions. It is a sensitivity test, not a forecast, probability of live profitability, or guarantee.

## Sampling method

`MonteCarloRobustnessSimulator` uses circular block bootstrap with a configurable block size. Sampling contiguous blocks preserves short-run ordering and dependence better than independent trade shuffling. The same sampled indices and random shocks are reused across scenarios in each simulation, providing common random numbers for comparison.

The simulator reports mean and median total net edge, lower and upper confidence quantiles, probability of a positive simulated result, expected shortfall, worst result, median and confidence-level drawdown, mean win rate, and mean observed trades.

## Sign conventions in the distribution metrics

Total net edge and drawdown are stored with opposite signs, and the two confidence bounds must follow suit:

- `lower_confidence_quantile` is the lower tail of total net edge, the pessimistic end for a return.
- `confidence_max_drawdown` is the lower tail of the drawdown distribution, because drawdowns are negative or zero. The pessimistic end is therefore the *more negative* quantile, not the higher one.

Both are negative or zero, and a reader comparing the two should note that a drawdown bound is not comparable to a return bound: the first measures the depth of a peak-to-trough decline, the second the total result over the whole path. A `confidence_max_drawdown` milder than `median_max_drawdown` would mean the bound was read from the wrong tail, so the reported pair is expected to satisfy `confidence_max_drawdown <= median_max_drawdown <= 0`.

## Stress scenarios

Named scenarios are dimensionless transformations of recorded research trades:

- `baseline`: original gross edge and cost
- `wider_spread`: aggregate cost multiplied by 1.5
- `slippage`: aggregate cost multiplied by 1.25
- `latency`: 5% probability that a trade is missed
- `combined_stress`: aggregate cost multiplied by 2.0 and 10% missed trades

A non-negative return shock can be added to non-baseline scenarios. Multipliers are assumptions and must be calibrated to the instrument, timeframe, and execution path.

## Reproducibility

The `robustness` CLI records simulation count, confidence level, random seed, block size, scenario parameters, source hash, software version, and UTC data period in an `EXP-*` JSON report.

## Limitations

Block bootstrap cannot model every regime change, cross-trade dependency, liquidity collapse, feed outage, or structural market break. Costs are aggregated and cannot be separated into commission, spread, funding, and slippage unless the input experiment records them separately. A high simulated win rate on synthetic example data is not market evidence.
