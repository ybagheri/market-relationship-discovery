import pytest

from market_relationship_discovery.config.settings import CostSettings
from market_relationship_discovery.costs.analyzer import CostAwareAnalyzer, CostModel
from market_relationship_discovery.synthetic.engine import Discrepancy, DiscrepancyKind


def test_gross_edge_is_reduced_by_costs() -> None:
    discrepancy = Discrepancy(
        kind=DiscrepancyKind.EXECUTABLE,
        absolute_difference=0.001,
        percentage_difference=0.1,
        buy_target_sell_synthetic=0.001,
        sell_target_buy_synthetic=-0.002,
    )
    analyzer = CostAwareAnalyzer(
        CostModel.from_settings(CostSettings(commission=0.0002, slippage=0.0001))
    )

    buy, sell = analyzer.analyze(discrepancy)

    assert buy.gross_edge == 0.001
    assert buy.net_edge == pytest.approx(0.0007)
    assert buy.survives_costs is True
    assert sell.survives_costs is False
