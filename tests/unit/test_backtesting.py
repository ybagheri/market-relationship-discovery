import pandas as pd

from market_relationship_discovery.backtesting.engine import ResearchBacktester


def test_backtest_keeps_gross_and_net_metrics_separate() -> None:
    gross = pd.Series([0.002, -0.001, 0.003])
    costs = pd.Series([0.0005, 0.0005, 0.0005])

    result = ResearchBacktester().run(gross, costs)

    assert result.observations == 3
    assert result.opportunities == 2
    assert result.gross_edge == 0.004
    assert result.net_edge == 0.0025
    assert result.win_rate == 2 / 3
