import pandas as pd
import pytest

from market_relationship_discovery.backtesting.walk_forward import (
    WalkForwardConfig,
    WalkForwardSplitter,
    WalkForwardValidator,
)


def frame(size: int = 36) -> pd.DataFrame:
    index = pd.date_range("2026-09-25", periods=size, freq="min", tz="UTC")
    return pd.DataFrame(
        {
            "signal": [float(index_value % 3 == 0) for index_value in range(size)],
            "gross_edge": [0.001 + (index_value % 4) / 10000 for index_value in range(size)],
            "cost": 0.0001,
        },
        index=index,
    )


def test_walk_forward_windows_are_strictly_chronological() -> None:
    index = frame(40).index
    config = WalkForwardConfig(10, 8, 8, 8)

    windows = WalkForwardSplitter(config).split(index)

    assert len(windows) == 2
    for window in windows:
        assert window.train_end < window.validation_start
        assert window.validation_end < window.test_start
    assert windows[1].test_start > windows[0].test_end


def test_test_outcomes_do_not_change_selected_threshold() -> None:
    data = frame()
    config = WalkForwardConfig(
        10,
        8,
        8,
        8,
        thresholds=(0.0, 0.5, 0.9),
        minimum_train_observations=1,
    )

    original = WalkForwardValidator().run(data, config, "signal", "gross_edge", "cost")
    changed = data.copy()
    changed.loc[changed.index[18] :, "gross_edge"] = 999.0
    modified = WalkForwardValidator().run(changed, config, "signal", "gross_edge", "cost")

    assert [fold.selected_threshold for fold in original.folds] == [
        fold.selected_threshold for fold in modified.folds
    ]
    assert original.aggregate_test_metrics.gross_edge != modified.aggregate_test_metrics.gross_edge


def test_fold_backtest_does_not_execute_into_next_split() -> None:
    data = frame()
    config = WalkForwardConfig(10, 8, 8, 8, thresholds=(0.0,), minimum_train_observations=1)

    result = WalkForwardValidator().run(data, config, "signal", "gross_edge", "cost")

    for fold in result.folds:
        assert all(
            trade.decision_timestamp <= fold.window.test_end
            and trade.execution_timestamp <= fold.window.test_end
            for trade in fold.test_trades
        )


def test_overlapping_test_windows_are_not_double_counted_in_the_aggregate() -> None:
    """Stepping by less than the test size re-scores the same bars.

    Concatenating the folds would report a larger out-of-sample sample than
    exists, along with an edge and a drawdown computed over a doubled,
    out-of-order equity path.
    """
    data = frame(40)
    overlapping = WalkForwardConfig(4, 3, 4, 2, thresholds=(0.0,))
    disjoint = WalkForwardConfig(4, 3, 4, 4, thresholds=(0.0,))

    result = WalkForwardValidator().run(data, overlapping, "signal", "gross_edge", "cost")
    baseline = WalkForwardValidator().run(data, disjoint, "signal", "gross_edge", "cost")

    assert result.test_windows_overlap is True
    assert result.duplicate_test_trades_removed > 0
    distinct = {trade.execution_timestamp for fold in result.folds for trade in fold.test_trades}
    assert result.aggregate_test_metrics.observations <= len(distinct)
    # The disjoint run is the honest measure of the same strategy.
    assert baseline.test_windows_overlap is False
    assert baseline.duplicate_test_trades_removed == 0
    assert result.aggregate_test_metrics.gross_edge == pytest.approx(
        baseline.aggregate_test_metrics.gross_edge, rel=0.35
    )


def test_a_zero_step_is_rejected_rather_than_silently_replaced() -> None:
    with pytest.raises(ValueError, match="step_observations must be positive"):
        WalkForwardSplitter(WalkForwardConfig(4, 3, 4, 0))


def test_insufficient_training_is_reported_without_test_selection() -> None:
    data = frame()
    config = WalkForwardConfig(10, 8, 8, 8, thresholds=(0.0,), minimum_train_observations=100)

    result = WalkForwardValidator().run(data, config, "signal", "gross_edge", "cost")

    assert result.completed_folds == 0
    assert all(fold.status == "insufficient_train_observations" for fold in result.folds)
    assert result.aggregate_test_metrics.observations == 0
