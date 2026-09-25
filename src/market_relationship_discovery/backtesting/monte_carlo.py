from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from market_relationship_discovery.backtesting.engine import NoLookAheadTrade
from market_relationship_discovery.domain.errors import InsufficientDataError


@dataclass(frozen=True, slots=True)
class MonteCarloConfig:
    simulations: int = 1000
    confidence_level: float = 0.95
    random_seed: int = 42
    block_size: int = 1

    def __post_init__(self) -> None:
        if self.simulations < 1:
            raise ValueError("simulations must be positive")
        if not 0.0 < self.confidence_level < 1.0:
            raise ValueError("confidence_level must be between zero and one")
        if self.block_size < 1:
            raise ValueError("block_size must be positive")


@dataclass(frozen=True, slots=True)
class StressScenario:
    name: str
    cost_multiplier: float = 1.0
    gross_edge_multiplier: float = 1.0
    additional_cost: float = 0.0
    missed_trade_probability: float = 0.0
    return_shock_std: float = 0.0

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("scenario name is required")
        if self.cost_multiplier < 0 or self.gross_edge_multiplier < 0:
            raise ValueError("scenario multipliers cannot be negative")
        if self.additional_cost < 0 or self.return_shock_std < 0:
            raise ValueError("scenario costs and shocks cannot be negative")
        if not 0.0 <= self.missed_trade_probability <= 1.0:
            raise ValueError("missed_trade_probability must be between zero and one")


@dataclass(frozen=True, slots=True)
class DistributionMetrics:
    simulations: int
    mean_total_net_edge: float
    median_total_net_edge: float
    lower_confidence_quantile: float
    upper_confidence_quantile: float
    probability_positive: float
    expected_shortfall: float
    worst_total_net_edge: float
    median_max_drawdown: float
    confidence_max_drawdown: float
    mean_win_rate: float
    mean_observed_trades: float


@dataclass(frozen=True, slots=True)
class ScenarioSimulationResult:
    scenario: StressScenario
    metrics: DistributionMetrics


STRESS_SCENARIOS: dict[str, StressScenario] = {
    "baseline": StressScenario("baseline"),
    "wider_spread": StressScenario("wider_spread", cost_multiplier=1.5),
    "slippage": StressScenario("slippage", cost_multiplier=1.25),
    "latency": StressScenario("latency", missed_trade_probability=0.05),
    "combined_stress": StressScenario(
        "combined_stress",
        cost_multiplier=2.0,
        missed_trade_probability=0.10,
    ),
}


class MonteCarloRobustnessSimulator:
    def run(
        self,
        trades: tuple[NoLookAheadTrade, ...],
        scenarios: tuple[StressScenario, ...],
        config: MonteCarloConfig,
    ) -> tuple[ScenarioSimulationResult, ...]:
        if not trades:
            raise InsufficientDataError("Monte Carlo robustness requires at least one trade")
        if not scenarios:
            raise ValueError("at least one stress scenario is required")
        if any(trade.cost < 0 for trade in trades):
            raise ValueError("trade costs cannot be negative")
        gross = np.asarray([trade.gross_edge for trade in trades], dtype=float)
        costs = np.asarray([trade.cost for trade in trades], dtype=float)
        totals = {scenario.name: np.zeros(config.simulations) for scenario in scenarios}
        drawdowns = {scenario.name: np.zeros(config.simulations) for scenario in scenarios}
        win_rates = {scenario.name: np.zeros(config.simulations) for scenario in scenarios}
        observations = {scenario.name: np.zeros(config.simulations) for scenario in scenarios}
        trade_count = len(trades)
        for simulation in range(config.simulations):
            generator = np.random.default_rng(config.random_seed + simulation)
            sampled_indices = self._sample_indices(generator, trade_count, config.block_size)
            missed = generator.random(trade_count)
            shocks = generator.normal(0.0, 1.0, trade_count)
            for scenario in scenarios:
                keep = missed >= scenario.missed_trade_probability
                simulated_gross = (
                    gross[sampled_indices] * scenario.gross_edge_multiplier
                    + shocks * scenario.return_shock_std
                )
                simulated_cost = (
                    costs[sampled_indices] * scenario.cost_multiplier + scenario.additional_cost
                )
                net = np.where(keep, simulated_gross - simulated_cost, 0.0)
                equity = np.cumsum(net)
                drawdown = equity - np.maximum.accumulate(np.r_[0.0, equity])[1:]
                totals[scenario.name][simulation] = float(net.sum())
                drawdowns[scenario.name][simulation] = float(drawdown.min())
                observed = int(keep.sum())
                observations[scenario.name][simulation] = observed
                win_rates[scenario.name][simulation] = (
                    float((net[keep] > 0).mean()) if observed else 0.0
                )
        return tuple(
            ScenarioSimulationResult(
                scenario=scenario,
                metrics=self._distribution_metrics(
                    totals[scenario.name],
                    drawdowns[scenario.name],
                    win_rates[scenario.name],
                    observations[scenario.name],
                    config.confidence_level,
                ),
            )
            for scenario in scenarios
        )

    @staticmethod
    def _sample_indices(
        generator: np.random.Generator,
        trade_count: int,
        block_size: int,
    ) -> np.ndarray:
        sampled: list[int] = []
        while len(sampled) < trade_count:
            start = int(generator.integers(0, trade_count))
            sampled.extend((start + offset) % trade_count for offset in range(block_size))
        return np.asarray(sampled[:trade_count], dtype=int)

    @staticmethod
    def _distribution_metrics(
        totals: np.ndarray,
        drawdowns: np.ndarray,
        win_rates: np.ndarray,
        observations: np.ndarray,
        confidence_level: float,
    ) -> DistributionMetrics:
        tail_probability = (1.0 - confidence_level) / 2.0
        lower = float(np.quantile(totals, tail_probability))
        upper = float(np.quantile(totals, 1.0 - tail_probability))
        tail = totals[totals <= lower]
        return DistributionMetrics(
            simulations=len(totals),
            mean_total_net_edge=float(totals.mean()),
            median_total_net_edge=float(np.median(totals)),
            lower_confidence_quantile=lower,
            upper_confidence_quantile=upper,
            probability_positive=float((totals > 0.0).mean()),
            expected_shortfall=float(tail.mean()),
            worst_total_net_edge=float(totals.min()),
            median_max_drawdown=float(np.median(drawdowns)),
            confidence_max_drawdown=float(np.quantile(drawdowns, 1.0 - tail_probability)),
            mean_win_rate=float(win_rates.mean()),
            mean_observed_trades=float(observations.mean()),
        )


def build_stress_scenarios(names: list[str]) -> tuple[StressScenario, ...]:
    if not names:
        names = list(STRESS_SCENARIOS)
    if len(names) != len(set(names)):
        raise ValueError("stress scenario names must be unique")
    scenarios: list[StressScenario] = []
    for name in names:
        scenario = STRESS_SCENARIOS.get(name)
        if scenario is None:
            raise ValueError(f"unknown stress scenario: {name}")
        scenarios.append(scenario)
    return tuple(scenarios)
