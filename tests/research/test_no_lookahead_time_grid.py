"""The no-lookahead claim is a claim about time, not about row order.

`run_next_observation` pairs a decision at bar `t` with the outcome of the
*next* bar, and the guarantee that a report reader relies on is that the
settling outcome had not finished forming when the decision was taken.

That guarantee was enforced positionally: the inputs were outer-joined and
`shift(-1)` was taken on the union. When the outcome column sits on a finer
grid than the signal, the union's next row is a fraction of a second after the
decision. The trade was still labelled `execution > decision`, and every test
that existed passed, because the wrong answer was a *different* row of the
union rather than a wrong row of either input.

A comment saying the shift is one bar forward would not have caught it either.
The shift really is one row forward; what was wrong is which sequence of bars
that row belongs to. So these tests state the property in the units the claim
is made in, and include the input that separates the two readings of the
column contract.
"""

from __future__ import annotations

import pandas as pd
import pytest

from market_relationship_discovery.backtesting.engine import ResearchBacktester


def minute_grid(size: int) -> pd.DatetimeIndex:
    return pd.date_range("2026-09-25", periods=size, freq="min", tz="UTC")


def test_an_outcome_inside_the_decision_bar_is_refused() -> None:
    """The leak this module exists for: a finer outcome grid.

    The signal is decided on the close of the 12:00 minute bar. The outcome
    column is on a one-second grid, so before the fix the engine attached the
    12:00:01 outcome to that decision: a period overlapping the bar the
    decision was computed from, reported as a legitimate later trade.
    """
    signal_index = minute_grid(1)
    outcome_index = pd.date_range("2026-09-25 00:00:00", periods=60, freq="s", tz="UTC")
    signals = pd.Series([True], index=signal_index)
    gross_edges = pd.Series(1.0, index=outcome_index)
    costs = pd.Series(0.0, index=outcome_index)

    with pytest.raises(ValueError, match="must share one observation grid"):
        ResearchBacktester().run_next_observation(signals, gross_edges, costs)


def test_the_refusal_names_the_two_counts_that_disagree() -> None:
    """A reader must be able to see which column was on which grid."""
    signal_index = minute_grid(1)
    outcome_index = minute_grid(3)
    signals = pd.Series([True], index=signal_index)
    gross_edges = pd.Series(1.0, index=outcome_index)
    costs = pd.Series(0.0, index=outcome_index)

    with pytest.raises(ValueError, match="signal has 1 observations, gross edge has 3"):
        ResearchBacktester().run_next_observation(signals, gross_edges, costs)


def test_the_mirror_case_is_refused_too() -> None:
    """A coarser outcome grid is refused, not quietly accepted.

    This direction is the more flattering error. The engine would have skipped
    every intervening bar and settled the decision four hours later, which
    still looks like a forward trade in every printed field.
    """
    signal_index = pd.date_range("2026-09-25", periods=60, freq="s", tz="UTC")
    outcome_index = minute_grid(2)
    signals = pd.Series(True, index=signal_index)
    gross_edges = pd.Series(1.0, index=outcome_index)
    costs = pd.Series(0.0, index=outcome_index)

    with pytest.raises(ValueError, match="must share one observation grid"):
        ResearchBacktester().run_next_observation(signals, gross_edges, costs)


def test_a_cost_column_on_its_own_grid_is_refused() -> None:
    """The check covers all three columns.

    A cost column measured on a different clock than the edge it is netted
    against produces a net figure that is not a figure about any single bar.
    """
    index = minute_grid(3)
    signals = pd.Series([True, False, True], index=index)
    gross_edges = pd.Series(0.01, index=index)
    costs = pd.Series(0.0, index=minute_grid(2))

    with pytest.raises(ValueError, match="signal has 3 observations, cost has 2"):
        ResearchBacktester().run_next_observation(signals, gross_edges, costs)


def test_matching_grids_are_accepted() -> None:
    """The one-grid rule must not refuse the intended use."""
    index = minute_grid(3)
    signals = pd.Series([True, False, True], index=index)
    gross_edges = pd.Series([999.0, 0.01, 0.02], index=index)
    costs = pd.Series(0.0, index=index)

    result = ResearchBacktester().run_next_observation(signals, gross_edges, costs)

    # The last bar cannot be a decision: there is no bar after it to settle it.
    assert [trade.decision_timestamp for trade in result.trades] == [index[0]]
    assert [trade.execution_timestamp for trade in result.trades] == [index[1]]


def test_a_missing_outcome_bar_does_not_settle_a_decision() -> None:
    """A hole in the outcome column must not be filled from a later bar.

    Positional pairing reaches past a hole, so a decision whose own next bar
    has no outcome would be settled by whichever bar happened to follow it.
    """
    index = minute_grid(4)
    signals = pd.Series([True, True, True, True], index=index)
    gross_edges = pd.Series([1.0, 2.0, float("nan"), 4.0], index=index)
    costs = pd.Series(0.0, index=index)

    result = ResearchBacktester().run_next_observation(signals, gross_edges, costs)

    # The decision at index[1] has no outcome of its own and must not borrow
    # the one at index[3], so index[2] settles index[1] never appears.
    assert [trade.decision_timestamp for trade in result.trades] == [index[0], index[2]]
    assert result.trades[0].gross_edge == 2.0
    assert result.trades[1].gross_edge == 4.0


def test_a_missing_signal_bar_is_not_decided_from_a_later_signal() -> None:
    """A hole in the signal column must not shift a decision onto a neighbour."""
    index = minute_grid(4)
    signals = pd.Series([float("nan"), float("nan"), True, True], index=index)
    gross_edges = pd.Series([1.0, 2.0, 3.0, 4.0], index=index)
    costs = pd.Series(0.0, index=index)

    result = ResearchBacktester().run_next_observation(signals, gross_edges, costs)

    assert [trade.decision_timestamp for trade in result.trades] == [index[2]]


@pytest.mark.parametrize("column", ["signal", "gross edge", "cost"])
def test_a_non_timestamp_index_is_refused(column: str) -> None:
    """The pairing is a claim about time and needs a clock to make it."""
    index = minute_grid(3)
    series = {
        "signal": pd.Series([True, True, True], index=index),
        "gross edge": pd.Series(0.01, index=index),
        "cost": pd.Series(0.0, index=index),
    }
    series[column] = pd.Series(series[column].to_numpy())

    with pytest.raises(TypeError, match="must be indexed by timestamp"):
        ResearchBacktester().run_next_observation(
            series["signal"], series["gross edge"], series["cost"]
        )


def test_unsorted_and_missing_timestamps_are_refused() -> None:
    """An unsorted index makes 'the next bar' ambiguous, and NaT cannot be ordered."""
    index = minute_grid(3)
    signals = pd.Series([True, True, True], index=index[::-1])
    gross_edges = pd.Series(0.01, index=index[::-1])
    costs = pd.Series(0.0, index=index[::-1])

    with pytest.raises(ValueError, match="must be sorted"):
        ResearchBacktester().run_next_observation(signals, gross_edges, costs)

    with_nat = pd.DatetimeIndex(["2026-09-25 00:00:00+00:00", pd.NaT])
    nat_signals = pd.Series([True, True], index=with_nat)
    nat_edges = pd.Series(0.01, index=with_nat)

    with pytest.raises(ValueError, match="cannot be missing"):
        ResearchBacktester().run_next_observation(
            nat_signals, nat_edges, pd.Series(0.0, index=with_nat)
        )


def test_the_settling_outcome_is_strictly_after_the_decision_on_one_grid() -> None:
    """The property the whole function exists to provide, in its own units.

    A decision at `t` must be settled by the outcome of a bar that begins
    after `t` closes. On one grid this is a full bar, so a signal derived from
    bar `t` cannot already know the bar that settles it.
    """
    index = minute_grid(6)
    signals = pd.Series(True, index=index)
    gross_edges = pd.Series(1.0, index=index)
    costs = pd.Series(0.0, index=index)

    result = ResearchBacktester().run_next_observation(signals, gross_edges, costs)

    for trade in result.trades:
        assert trade.execution_timestamp > trade.decision_timestamp
        assert trade.execution_timestamp - trade.decision_timestamp == pd.Timedelta(minutes=1)


def test_changing_a_later_outcome_never_moves_an_earlier_trade() -> None:
    """Realized outcomes are the only thing the engine may read forward.

    Each trade is a function of its own decision bar and the bar after it.
    Perturbing everything beyond a decision must leave that trade alone, which
    is what makes the pairing safe to reason about rather than merely ordered.
    """
    index = minute_grid(8)
    signals = pd.Series([True, False, True, False, True, False, True, False], index=index)
    gross_edges = pd.Series(0.01, index=index)
    costs = pd.Series(0.0, index=index)

    original = ResearchBacktester().run_next_observation(signals, gross_edges, costs)
    changed_edges = gross_edges.copy()
    changed_edges.iloc[4:] = 1e6
    changed = ResearchBacktester().run_next_observation(signals, changed_edges, costs)

    early = [t for t in original.trades if t.execution_timestamp <= index[3]]
    early_changed = [t for t in changed.trades if t.execution_timestamp <= index[3]]

    assert [(t.decision_timestamp, t.gross_edge) for t in early] == [
        (t.decision_timestamp, t.gross_edge) for t in early_changed
    ]
    assert early
