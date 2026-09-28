import pandas as pd
import pytest

from market_relationship_discovery.backtesting.engine import ResearchBacktester


def test_backtest_keeps_gross_and_net_metrics_separate() -> None:
    gross = pd.Series([0.002, -0.001, 0.003])
    costs = pd.Series([0.0005, 0.0005, 0.0005])

    result = ResearchBacktester().run(gross, costs)

    assert result.observations == 3
    assert result.opportunities == 2
    assert result.gross_edge == 0.004
    assert result.net_edge == 0.0025
    # Two of the three trades were profitable; the negative bar was not a trade.
    assert result.win_rate == 1.0
    assert result.observation_win_rate == 2 / 3


def test_win_rate_ignores_bars_that_were_never_opportunities() -> None:
    """A long stretch of idle bars must not dilute the rate of taken trades."""
    gross = pd.Series([0.004, 0.002, -0.001, -0.001, -0.001, -0.001])
    costs = pd.Series([0.0] * 6)

    result = ResearchBacktester().run(gross, costs)

    assert result.opportunities == 2
    assert result.win_rate == 1.0
    assert result.average_return == pytest.approx(0.003)
    assert result.observation_win_rate == pytest.approx(1 / 3)


def test_drawdown_is_measured_from_the_starting_equity() -> None:
    """A curve that opens below its own high must report the decline.

    Without a zero seed the running peak is the first observation, so any loss
    before the first gain is invisible and the reported drawdown is zero.
    """
    result = ResearchBacktester().run(
        pd.Series([-1.0, 0.5, 0.2]),
        pd.Series([0.0, 0.0, 0.0]),
    )

    assert result.drawdown == pytest.approx(-1.0)


def test_a_curve_that_only_rises_reports_no_drawdown() -> None:
    result = ResearchBacktester().run(
        pd.Series([0.1, 0.2, 0.3]),
        pd.Series([0.0, 0.0, 0.0]),
    )

    assert result.drawdown == 0.0


def test_excursions_are_reported_on_the_net_curve() -> None:
    """Both risk figures must share the basis the drawdown uses."""
    result = ResearchBacktester().run(
        pd.Series([0.004, -0.001, 0.002]),
        pd.Series([0.001, 0.001, 0.001]),
    )

    assert result.maximum_adverse_excursion == pytest.approx(-0.002)
    assert result.maximum_favorable_excursion == pytest.approx(0.003 + 0.001)
