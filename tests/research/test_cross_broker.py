import json
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from market_relationship_discovery.domain.errors import DataQualityError, InsufficientDataError
from market_relationship_discovery.market_data.contract import (
    ContractCompatibilityStatus,
    ContractSpecification,
)
from market_relationship_discovery.market_data.cross_broker import (
    ComparisonKind,
    CrossBrokerComparisonEngine,
    CrossBrokerRequest,
    OpportunityDirection,
)


def tick_frame(
    prices: list[tuple[float, float]], offsets_ms: list[int] | None = None
) -> pd.DataFrame:
    offsets = offsets_ms or [index * 60_000 for index in range(len(prices))]
    return pd.DataFrame(
        {
            "timestamp": [
                pd.Timestamp("2026-09-25T00:00:00Z") + pd.Timedelta(milliseconds=offset)
                for offset in offsets
            ],
            "symbol": "EURUSD",
            "bid": [price[0] for price in prices],
            "ask": [price[1] for price in prices],
        }
    )


def request(cost: float = 0.0001) -> CrossBrokerRequest:
    return CrossBrokerRequest(
        "BrokerA",
        "BrokerB",
        "EURUSD",
        ComparisonKind.TICK,
        100,
        cost,
    )


def test_tick_comparison_aligns_and_builds_crossable_episode() -> None:
    broker_a = tick_frame(
        [(1.1000, 1.1002), (1.1001, 1.1003), (1.1002, 1.1004), (1.1003, 1.1005), (1.1004, 1.1006)]
    )
    broker_b = tick_frame(
        [
            (1.1006, 1.1008),
            (1.1006, 1.1008),
            (1.1006, 1.1008),
            (1.0998, 1.1006),
            (1.0998, 1.1006),
        ],
        [20, 60_020, 120_020, 180_020, 240_020],
    )

    analysis = CrossBrokerComparisonEngine().compare(broker_a, broker_b, request())

    assert analysis.summary.aligned_observations == 5
    assert analysis.summary.mean_alignment_delay_ms == 20.0
    assert analysis.summary.crossable_observations == 3
    assert analysis.summary.opportunity_count == 1
    assert analysis.opportunities[0].direction is OpportunityDirection.BUY_A_SELL_B
    assert analysis.opportunities[0].duration_ms == 120_000.0
    assert analysis.opportunities[0].maximum_net_edge == pytest.approx(0.0003)


def test_additional_cost_can_remove_crossable_episode() -> None:
    broker_a = tick_frame([(1.1000, 1.1002), (1.1001, 1.1003)])
    broker_b = tick_frame([(1.1004, 1.1006), (1.1005, 1.1007)])

    analysis = CrossBrokerComparisonEngine().compare(
        broker_a,
        broker_b,
        request(cost=0.0003),
    )

    assert analysis.summary.crossable_observations == 0
    assert analysis.opportunities == ()


def test_bar_difference_is_never_classified_as_crossable() -> None:
    broker_a = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-09-25", periods=3, freq="min", tz="UTC"),
            "symbol": "EURUSD",
            "close": [100.0, 101.0, 102.0],
        }
    )
    broker_b = broker_a.assign(close=[90.0, 91.0, 92.0])
    bar_request = CrossBrokerRequest(
        "BrokerA",
        "BrokerB",
        "EURUSD",
        ComparisonKind.BAR,
        100,
    )

    analysis = CrossBrokerComparisonEngine().compare(broker_a, broker_b, bar_request)

    assert analysis.summary.classification == "theoretical_bar_price_comparison"
    assert analysis.summary.maximum_absolute_price_difference == 10.0
    assert analysis.summary.opportunity_count == 0
    assert analysis.summary.maximum_net_crossable_edge is None


def test_incompatible_contracts_block_crossable_episodes() -> None:
    contract_a = ContractSpecification.from_dict(
        json.loads(Path("examples/broker_a_contract.json").read_text(encoding="utf-8"))
    )
    contract_b = replace(
        ContractSpecification.from_dict(
            json.loads(Path("examples/broker_b_contract.json").read_text(encoding="utf-8"))
        ),
        contract_size=50000.0,
    )
    broker_a = tick_frame([(1.1000, 1.1002), (1.1001, 1.1003)])
    broker_b = tick_frame([(1.1006, 1.1008), (1.1007, 1.1009)])

    analysis = CrossBrokerComparisonEngine().compare(
        broker_a,
        broker_b,
        replace(request(), contract_a=contract_a, contract_b=contract_b),
    )

    assert analysis.summary.contract_status is ContractCompatibilityStatus.NORMALIZATION_REQUIRED
    assert analysis.summary.classification == "blocked_by_contract_specification"
    assert analysis.summary.contract_blocked_observations == 2
    assert analysis.opportunities == ()


def test_alignment_rejects_duplicate_and_unmatched_data() -> None:
    duplicate = tick_frame([(1.1, 1.2), (1.1, 1.2)], [0, 0])
    valid = tick_frame([(1.1, 1.2)])
    engine = CrossBrokerComparisonEngine()

    with pytest.raises(DataQualityError):
        engine.compare(duplicate, valid, request())
    far = tick_frame([(1.1, 1.2)], [1000])
    with pytest.raises(InsufficientDataError):
        engine.compare(valid, far, request())
