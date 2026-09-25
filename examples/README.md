# Examples

The CSV files in this directory are deterministic software fixtures, not market evidence. Their repetitive values may produce high win rates and must never be interpreted as profitable strategies.

- `no_lookahead_signals.csv` demonstrates that a signal at `t` is evaluated at `t+1`.
- `walk_forward_signals.csv` exercises walk-forward folds, a two-stage ensemble, and Monte Carlo robustness.
- `broker_a_ticks.csv` and `broker_b_ticks.csv` produce a synthetic synchronized cross-broker episode with a 20 ms source delay, not an arbitrage claim.
- `broker_a_contract.json` and `broker_b_contract.json` are synthetic compatible contract specifications for safety-gate testing.

Replace these files with carefully validated research data before drawing market conclusions.
