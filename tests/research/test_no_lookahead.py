from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from market_relationship_discovery.backtesting.engine import ResearchBacktester


def test_next_observation_backtest_excludes_current_and_future_rows() -> None:
    timestamps = [datetime(2026, 9, 25, tzinfo=UTC) + timedelta(minutes=i) for i in range(4)]
    signals = pd.Series([1, 0, 1, 0], index=timestamps)
    gross_edges = pd.Series([999.0, 0.01, 0.02, 0.03], index=timestamps)
    costs = pd.Series([0.0, 0.001, 0.002, 0.003], index=timestamps)

    result = ResearchBacktester().run_next_observation(signals, gross_edges, costs)

    assert result.metrics.observations == 2
    assert result.metrics.gross_edge == 0.04
    assert result.metrics.net_edge == pytest.approx(0.036)
    assert result.trades[0].decision_timestamp == timestamps[0]
    assert result.trades[0].execution_timestamp == timestamps[1]
    assert result.trades[1].execution_timestamp == timestamps[3]


def test_last_signal_has_no_future_observation() -> None:
    timestamps = pd.date_range("2026-09-25", periods=2, freq="min", tz="UTC")
    signals = pd.Series([0, 1], index=timestamps)
    gross_edges = pd.Series([0.01, 0.02], index=timestamps)
    costs = pd.Series([0.0, 0.001], index=timestamps)

    result = ResearchBacktester().run_next_observation(signals, gross_edges, costs)

    assert result.metrics.observations == 0
    assert result.trades == ()
