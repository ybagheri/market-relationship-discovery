from dataclasses import replace

import numpy as np
import pytest

from market_relationship_discovery.backtesting.engine import NoLookAheadTrade
from market_relationship_discovery.backtesting.monte_carlo import (
    MonteCarloConfig,
    MonteCarloRobustnessSimulator,
    StressScenario,
    build_stress_scenarios,
)
from market_relationship_discovery.domain.errors import InsufficientDataError


def trades(count: int = 20) -> tuple[NoLookAheadTrade, ...]:
    return tuple(
        NoLookAheadTrade(
            decision_timestamp=index,
            execution_timestamp=index + 1,
            signal=1.0,
            gross_edge=0.01 + (index % 3) / 1000,
            cost=0.001,
        )
        for index in range(count)
    )


def losing_trades(count: int = 40) -> tuple[NoLookAheadTrade, ...]:
    """An alternating win/loss sequence, so drawdowns vary between simulations."""
    return tuple(
        NoLookAheadTrade(
            decision_timestamp=index,
            execution_timestamp=index + 1,
            signal=1.0,
            gross_edge=0.05 if index % 2 == 0 else -0.10,
            cost=0.02,
        )
        for index in range(count)
    )


def test_monte_carlo_is_deterministic_for_same_seed() -> None:
    simulator = MonteCarloRobustnessSimulator()
    config = MonteCarloConfig(simulations=100, random_seed=7, block_size=3)

    first = simulator.run(trades(), build_stress_scenarios(["baseline"]), config)
    second = simulator.run(trades(), build_stress_scenarios(["baseline"]), config)

    assert first == second


def test_combined_stress_reduces_return_and_observed_trades() -> None:
    results = MonteCarloRobustnessSimulator().run(
        trades(),
        build_stress_scenarios(["baseline", "combined_stress"]),
        MonteCarloConfig(simulations=200, random_seed=11, block_size=2),
    )

    baseline = results[0].metrics
    stressed = results[1].metrics
    assert stressed.mean_total_net_edge < baseline.mean_total_net_edge
    assert stressed.mean_observed_trades < baseline.mean_observed_trades
    assert stressed.probability_positive <= baseline.probability_positive


def test_return_shock_reduces_deterministic_mean() -> None:
    baseline = StressScenario("baseline")
    shocked = replace(baseline, name="shocked", return_shock_std=0.05)

    results = MonteCarloRobustnessSimulator().run(
        trades(),
        (baseline, shocked),
        MonteCarloConfig(simulations=500, random_seed=3),
    )

    assert results[1].metrics.expected_shortfall < results[0].metrics.expected_shortfall
    assert results[1].metrics.probability_positive < results[0].metrics.probability_positive


def profitable_trades(count: int = 50) -> tuple[NoLookAheadTrade, ...]:
    return tuple(
        NoLookAheadTrade(
            decision_timestamp=index,
            execution_timestamp=index + 1,
            signal=1.0,
            gross_edge=0.10,
            cost=0.02,
        )
        for index in range(count)
    )


def test_every_stress_scenario_is_worse_than_the_baseline_on_a_profitable_sample() -> None:
    """A stress test must not improve on the run it is stressing.

    Dropping a trade used to zero its cost as well as its profit, which
    discounted the scenario's own cost multiplier by the missed fraction. On a
    sample that was already unprofitable, that was enough to make the stress
    scenario look better than the baseline.
    """
    results = MonteCarloRobustnessSimulator().run(
        profitable_trades(),
        build_stress_scenarios(["baseline", "wider_spread", "latency", "combined_stress"]),
        MonteCarloConfig(simulations=300, random_seed=42, block_size=3),
    )
    baseline = results[0].metrics

    for result in results[1:]:
        assert (
            result.metrics.mean_total_net_edge < baseline.mean_total_net_edge
        ), f"{result.scenario.name} is not worse than the baseline"


def test_a_missed_trade_still_costs_its_attempt() -> None:
    """Missing an opportunity is paid for, not refunded."""
    results = MonteCarloRobustnessSimulator().run(
        profitable_trades(),
        build_stress_scenarios(["baseline", "latency"]),
        MonteCarloConfig(simulations=200, random_seed=7, block_size=2),
    )
    baseline, latency = (result.metrics for result in results)

    assert latency.mean_observed_trades < baseline.mean_observed_trades
    # Had the missed trades been free, dropping them would have removed the same
    # gross edge and no cost at all.
    gross_lost = 0.10 * (baseline.mean_observed_trades - latency.mean_observed_trades)
    assert baseline.mean_total_net_edge - latency.mean_total_net_edge < gross_lost


def test_confidence_drawdown_is_deeper_than_the_median() -> None:
    """The confidence bound must not be milder than a typical drawdown.

    Drawdowns are negative, so the deep tail is the lower quantile. Reading the
    upper one reported the shallowest of the worst cases as the bound, which is
    the number a reader would size capital against.
    """
    metrics = (
        MonteCarloRobustnessSimulator()
        .run(
            losing_trades(),
            build_stress_scenarios(["baseline"]),
            MonteCarloConfig(simulations=400, random_seed=5, block_size=3),
        )[0]
        .metrics
    )

    assert metrics.confidence_max_drawdown < 0.0
    assert metrics.confidence_max_drawdown <= metrics.median_max_drawdown


def test_confidence_drawdown_reads_the_deep_tail_of_the_distribution() -> None:
    """Pin the quantile direction against a distribution with a known tail.

    Totals and drawdowns are stored with opposite signs, so the same quantile
    that bounds returns correctly inverts the drawdown bound. The two metrics are
    checked against the same simulated sample to make that asymmetry explicit.
    """
    totals = np.asarray([-10.0, -8.0, -6.0, -5.0, -4.0, -3.0, -2.0, 0.0, 1.0, 2.0])
    drawdowns = np.asarray([-40.0, -35.0, -30.0, -25.0, -20.0, -15.0, -10.0, -5.0, -2.0, -1.0])
    tail_probability = 0.025

    metrics = MonteCarloRobustnessSimulator._distribution_metrics(
        totals,
        drawdowns,
        np.zeros(10),
        np.full(10, 10.0),
        0.95,
    )

    # For a signed series the lower tail is the pessimistic one.
    assert metrics.lower_confidence_quantile == pytest.approx(float(np.quantile(totals, 0.025)))
    assert metrics.confidence_max_drawdown == pytest.approx(
        float(np.quantile(drawdowns, tail_probability))
    )
    assert metrics.confidence_max_drawdown == pytest.approx(-38.875)
    assert metrics.confidence_max_drawdown < metrics.median_max_drawdown


def test_monte_carlo_requires_trades_and_known_scenarios() -> None:
    simulator = MonteCarloRobustnessSimulator()
    config = MonteCarloConfig(simulations=10)

    with pytest.raises(InsufficientDataError):
        simulator.run((), build_stress_scenarios(["baseline"]), config)
    with pytest.raises(ValueError, match="unknown"):
        build_stress_scenarios(["unknown"])
