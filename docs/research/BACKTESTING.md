# Backtesting

## Current foundation

`ResearchBacktester` accepts an already-constructed historical edge series and an aligned cost series. It reports observations, opportunities, gross and net edge, win rate, average return, excursions, drawdown, and cost percentage. It does not create a trading strategy or fill orders.

## Required future controls

- Signals may only use observations available at the decision timestamp.
- Execution must occur at the next valid timestamp or a configurable delay.
- Rolling windows must not include future rows.
- Training, validation, and test periods must remain separate.
- Slippage, spread widening, latency, and session gaps require scenario tests.
- Walk-forward and Monte Carlo modules are planned, not implemented.

## Interpretation

A positive backtest result is a hypothesis under assumptions. It is not evidence of guaranteed profit. Results must include data period, symbols, broker, parameters, costs, code version, and experiment ID.
