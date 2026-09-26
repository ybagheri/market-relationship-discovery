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
    SynchronizationMode,
    TickAggregation,
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


def test_contract_size_difference_is_volume_and_pnl_normalized() -> None:
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
    assert (
        analysis.summary.classification
        == "crossable_after_cost_pnl_normalized_research_capital_unverified"
    )
    assert analysis.summary.contract_normalization_applied is True
    assert analysis.summary.broker_b_volume_per_broker_a_volume == 2.0
    assert analysis.summary.maximum_normalized_net_pnl is not None
    assert analysis.opportunities


def test_configured_leverage_verifies_capital_and_drops_the_caveat() -> None:
    """A leverage-derived margin is a real figure, so capital becomes verified.

    The example contracts report ``margin_initial`` as zero, which MetaTrader uses
    to mean "not reported" rather than "free". Supplying account leverage turns
    that unknown into a derived margin and removes the caveat.
    """
    contract_a = ContractSpecification.from_dict(
        json.loads(Path("examples/broker_a_contract.json").read_text(encoding="utf-8"))
    )
    contract_b = ContractSpecification.from_dict(
        json.loads(Path("examples/broker_b_contract.json").read_text(encoding="utf-8"))
    )
    broker_a = tick_frame([(1.1000, 1.1002), (1.1001, 1.1003)])
    broker_b = tick_frame([(1.1006, 1.1008), (1.1007, 1.1009)])

    analysis = CrossBrokerComparisonEngine().compare(
        broker_a,
        broker_b,
        replace(
            request(),
            contract_a=contract_a,
            contract_b=contract_b,
            leverage=500,
        ),
    )

    execution = analysis.summary.execution
    assert execution is not None
    assert execution.capital_verified is True
    assert execution.executable is True
    assert execution.total_margin is not None
    assert analysis.summary.classification == "crossable_after_cost_contract_validated_research"


def test_symmetric_synchronization_keeps_only_mutual_nearest_matches() -> None:
    broker_a = tick_frame([(1.1, 1.2), (1.2, 1.3)], [0, 10])
    broker_b = tick_frame([(1.3, 1.4), (1.4, 1.5)], [10, 20])

    analysis = CrossBrokerComparisonEngine().compare(
        broker_a,
        broker_b,
        replace(request(), synchronization_mode=SynchronizationMode.SYMMETRIC),
    )

    assert analysis.summary.synchronization_mode is SynchronizationMode.SYMMETRIC
    assert analysis.summary.aligned_observations == 1
    assert analysis.summary.unmatched_broker_a_rows == 1
    assert analysis.summary.unmatched_broker_b_rows == 1
    assert analysis.aligned_observations["timestamp"].iloc[0] == pd.Timestamp(
        "2026-09-25T00:00:00.010Z"
    )


def test_incompatible_contracts_block_crossable_episodes() -> None:
    contract_a = ContractSpecification.from_dict(
        json.loads(Path("examples/broker_a_contract.json").read_text(encoding="utf-8"))
    )
    contract_b = replace(
        ContractSpecification.from_dict(
            json.loads(Path("examples/broker_b_contract.json").read_text(encoding="utf-8"))
        ),
        currency_profit="GBP",
    )
    broker_a = tick_frame([(1.1000, 1.1002), (1.1001, 1.1003)])
    broker_b = tick_frame([(1.1006, 1.1008), (1.1007, 1.1009)])

    analysis = CrossBrokerComparisonEngine().compare(
        broker_a,
        broker_b,
        replace(request(), contract_a=contract_a, contract_b=contract_b),
    )

    assert analysis.summary.contract_status is ContractCompatibilityStatus.INCOMPATIBLE
    assert analysis.summary.classification == "blocked_by_contract_specification"
    assert analysis.summary.contract_blocked_observations == 2
    assert analysis.opportunities == ()


def test_tick_duplicate_updates_are_explicitly_aggregated() -> None:
    broker_a = tick_frame([(1.1000, 1.1002), (1.1001, 1.1003)], [0, 0])
    broker_b = tick_frame([(1.1005, 1.1007), (1.1006, 1.1008)])

    analysis = CrossBrokerComparisonEngine().compare(broker_a, broker_b, request())

    assert analysis.summary.broker_a_duplicate_timestamps == 1
    assert analysis.summary.tick_aggregation is TickAggregation.LAST
    assert analysis.aligned_observations["a_bid"].iloc[0] == 1.1001


def test_alignment_rejects_duplicate_and_unmatched_data() -> None:
    duplicate = tick_frame([(1.1, 1.2), (1.1, 1.2)], [0, 0])
    valid = tick_frame([(1.1, 1.2)])
    engine = CrossBrokerComparisonEngine()

    with pytest.raises(DataQualityError):
        engine.compare(
            duplicate,
            valid,
            replace(request(), tick_aggregation=TickAggregation.NONE),
        )
    far = tick_frame([(1.1, 1.2)], [1000])
    with pytest.raises(InsufficientDataError):
        engine.compare(valid, far, request())
