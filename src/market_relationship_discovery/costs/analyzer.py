from __future__ import annotations

from dataclasses import dataclass

from market_relationship_discovery.config.settings import CostSettings
from market_relationship_discovery.synthetic.engine import Discrepancy


@dataclass(frozen=True, slots=True)
class CostModel:
    commission: float
    slippage: float
    latency_assumption_ms: int
    other_costs: float

    @classmethod
    def from_settings(cls, settings: CostSettings) -> CostModel:
        return cls(
            commission=settings.commission,
            slippage=settings.slippage,
            latency_assumption_ms=settings.latency_assumption_ms,
            other_costs=settings.other_costs,
        )

    @property
    def total(self) -> float:
        return self.commission + self.slippage + self.other_costs


@dataclass(frozen=True, slots=True)
class NetEdge:
    direction: str
    gross_edge: float
    net_edge: float
    survives_costs: bool


class CostAwareAnalyzer:
    def __init__(self, cost_model: CostModel) -> None:
        self._cost_model = cost_model

    def analyze(self, discrepancy: Discrepancy) -> tuple[NetEdge, NetEdge]:
        total_costs = self._cost_model.total
        buy = NetEdge(
            direction="buy_target_sell_synthetic",
            gross_edge=discrepancy.buy_target_sell_synthetic,
            net_edge=discrepancy.buy_target_sell_synthetic - total_costs,
            survives_costs=discrepancy.buy_target_sell_synthetic > total_costs,
        )
        sell = NetEdge(
            direction="sell_target_buy_synthetic",
            gross_edge=discrepancy.sell_target_buy_synthetic,
            net_edge=discrepancy.sell_target_buy_synthetic - total_costs,
            survives_costs=discrepancy.sell_target_buy_synthetic > total_costs,
        )
        return buy, sell
