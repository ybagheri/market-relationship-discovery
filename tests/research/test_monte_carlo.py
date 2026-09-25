from dataclasses import replace

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


def test_monte_carlo_requires_trades_and_known_scenarios() -> None:
    simulator = MonteCarloRobustnessSimulator()
    config = MonteCarloConfig(simulations=10)

    with pytest.raises(InsufficientDataError):
        simulator.run((), build_stress_scenarios(["baseline"]), config)
    with pytest.raises(ValueError, match="unknown"):
        build_stress_scenarios(["unknown"])
