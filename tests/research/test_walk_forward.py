import pandas as pd

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


def test_insufficient_training_is_reported_without_test_selection() -> None:
    data = frame()
    config = WalkForwardConfig(10, 8, 8, 8, thresholds=(0.0,), minimum_train_observations=100)

    result = WalkForwardValidator().run(data, config, "signal", "gross_edge", "cost")

    assert result.completed_folds == 0
    assert all(fold.status == "insufficient_train_observations" for fold in result.folds)
    assert result.aggregate_test_metrics.observations == 0
