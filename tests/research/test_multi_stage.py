import pandas as pd
import pytest

from market_relationship_discovery.backtesting.multi_stage import (
    CausalFeatureBuilder,
    MultiStageBacktester,
    SignalStage,
)


def test_multi_stage_ensemble_uses_next_observation_outcomes() -> None:
    index = pd.date_range("2026-09-25", periods=5, freq="min", tz="UTC")
    frame = pd.DataFrame(
        {
            "momentum": [100.0, -1.0, 1.0, -1.0, 1.0],
            "reversion": [100.0, 1.0, -1.0, 1.0, -1.0],
            "gross_edge": [999.0, 0.01, 0.02, 0.03, 0.04],
            "cost": 0.001,
        },
        index=index,
    )
    stages = (
        SignalStage("momentum", "momentum", 1.0),
        SignalStage("reversion", "reversion", 1.0),
    )

    result = MultiStageBacktester().run(frame, stages, "gross_edge", "cost")

    assert result.ensemble.trades[0].execution_timestamp == index[1]
    assert result.ensemble.metrics.gross_edge == pytest.approx(0.01)
    assert 999.0 not in {trade.gross_edge for trade in result.ensemble.trades}
    assert set(result.stages) == {"momentum", "reversion"}


def test_causal_features_do_not_change_when_future_changes() -> None:
    index = pd.date_range("2026-09-25", periods=20, freq="min", tz="UTC")
    original = pd.Series(range(1, 21), index=index, dtype=float)
    modified = original.copy()
    modified.iloc[10:] = 1000.0

    original_zscore = CausalFeatureBuilder.rolling_zscore(original, 5)
    modified_zscore = CausalFeatureBuilder.rolling_zscore(modified, 5)
    original_momentum = CausalFeatureBuilder.momentum(original, 3)
    modified_momentum = CausalFeatureBuilder.momentum(modified, 3)

    pd.testing.assert_series_equal(original_zscore.iloc[:10], modified_zscore.iloc[:10])
    pd.testing.assert_series_equal(original_momentum.iloc[:10], modified_momentum.iloc[:10])
