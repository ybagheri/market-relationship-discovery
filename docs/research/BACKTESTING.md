# Backtesting

## Implemented research controls

`ResearchBacktester.run_next_observation` pairs a signal at timestamp `t` only with an outcome that had not finished forming at `t`. `WalkForwardValidator` selects an activation threshold on train data only, reports validation, and evaluates the fixed threshold on each test window. Signals and outcomes cannot cross the end of an evaluation window.

## Which bar a `gross_edge` value is labelled with

A return series can be labelled at the bar it **starts** or the bar it
**ends**, and the two readings differ by exactly one bar. `OutcomeConvention`
names the reading and the caller must supply it:

| Convention | `edge[t]` covers | A decision at `t` is settled by |
| --- | --- | --- |
| `earned_over_following_bar` (default) | `[t, t+1)` | the value at `t+1` |
| `realised_at_bar` | `[t-1, t)` | the value at `t` |

The engine previously hard-coded the first reading and said so nowhere. A
caller whose column was labelled the second way got a backtest that settled
every decision one bar late: internally consistent, plausibly causal, and
measuring a different rule than the one intended. A comment would not have
prevented it, because the reading is a property of the *caller's data*, not of
the function. It is now an argument, and the report records which one produced
the figures in `outcome_convention`.

Note that `realised_at_bar` uses a zero offset, which is correct and not a
degenerate case: the decision and its outcome describe the same bar, and both
are computed from data up to that bar's close. The invariant is that no value
is read from a bar that closed *before* the decision, not that every trade
spans two bars. Under `realised_at_bar` the last bar can therefore be decided,
and under `earned_over_following_bar` it cannot.

`WalkForwardConfig` and `MultiStageBacktester.run` carry the convention too, so
every fold of a run settles on the same bar. A run whose folds disagreed would
produce an aggregate that is not a measurement of anything.

`MultiStageBacktester` combines causal score columns with explicit weights and thresholds. It reports the ensemble and every individual stage. `CausalFeatureBuilder` provides rolling z-score, momentum, and realized-volatility features that use only current and past values.

## "The next bar" has to mean the same bar to everyone

The no-lookahead guarantee is a claim about time, and it is only true when the
signal, gross-edge, and cost columns are all indexed by the same observation
grid. All three are required to share one `DatetimeIndex`, and a mismatch is
refused with the two observation counts that disagree.

This was not enforced before. The three columns were outer-joined and shifted
one row, which is a claim about *row order*, not about time. On two inputs
that agree the two readings are identical, so nothing distinguished them. They
part company as soon as the columns sit on different clocks:

- A **finer** outcome grid meant the "next row" was a fraction of a second
  after the decision. The trade was still labelled `execution > decision` and
  still satisfied every test that existed, while the settling outcome was a
  period overlapping the very bar the decision was computed from. That is
  lookahead.
- A **coarser** outcome grid was the flattering direction: the engine skipped
  every intervening bar and settled the decision hours later, which still
  looks like a forward trade in every printed field.

A comment saying the shift is one bar forward would not have caught either
case. The shift was one row forward; what was wrong is which sequence of bars
that row belonged to. The tests therefore state the property in the units the
claim is made in, and include the inputs that separate the two readings.

A missing observation is a second way to get this wrong, and it is refused the
same way rather than filled: a decision whose own next bar has no outcome is
dropped, never settled by a later bar.

## Reproducibility

CLI experiments generate an `EXP-*` identifier and JSON report containing software version, source filename and SHA-256, UTC data period, parameters, fold windows, metrics, trades, and limitations. The `robustness` command adds reproducible block-bootstrap simulations and named stress scenarios.

## Required future controls

- Arbitrary model fitting must receive training data only.
- Combinatorial optimization requires multiple-testing controls.
- Slippage, spread widening, latency, and session gaps require scenario tests.
- Monte Carlo block bootstrap does not capture every regime change or cross-trade dependency.
- Externally supplied stage columns must be audited for causality.

## Interpretation

A positive result is a hypothesis under assumptions, not guaranteed profit. The example CSV files are deterministic software fixtures and are not market evidence. No order execution or fill simulation is implemented.
