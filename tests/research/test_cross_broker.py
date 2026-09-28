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


def continuous_opportunity(span_ms: int, tick_ms: int = 20) -> tuple[pd.DataFrame, pd.DataFrame]:
    """A densely quoted crossable edge lasting ``span_ms`` of wall-clock time.

    The two feeds are 0.6 pips apart through the whole window, so the edge is
    continuously observable rather than two isolated instants.
    """
    offsets = list(range(0, span_ms + tick_ms, tick_ms))
    broker_a = tick_frame([(1.1000, 1.1002)] * len(offsets), offsets)
    broker_b = tick_frame([(1.1006, 1.1008)] * len(offsets), offsets)
    return broker_a, broker_b


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
    # Halving the contract size halves the tick value too, which is what a real
    # broker quoting the same instrument at half the lot size reports.
    contract_b = replace(
        ContractSpecification.from_dict(
            json.loads(Path("examples/broker_b_contract.json").read_text(encoding="utf-8"))
        ),
        contract_size=50000.0,
        tick_value=0.5,
    )
    broker_a, broker_b = continuous_opportunity(2000)
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
    assert analysis.summary.normalized_pnl_legs_agree is True
    assert analysis.opportunities


def test_inconsistent_contract_legs_are_reported_with_the_pnl_they_qualify() -> None:
    """Two legs that disagree are a metadata problem, not extra profit.

    A broker that halved its contract size without halving its tick value is not
    describing the same instrument, so the two valuations of one position differ.
    The report must say so rather than presenting the edge as reliably money.
    """
    contract_a = ContractSpecification.from_dict(
        json.loads(Path("examples/broker_a_contract.json").read_text(encoding="utf-8"))
    )
    contract_b = replace(
        ContractSpecification.from_dict(
            json.loads(Path("examples/broker_b_contract.json").read_text(encoding="utf-8"))
        ),
        contract_size=50000.0,
    )
    broker_a, broker_b = continuous_opportunity(2000)

    analysis = CrossBrokerComparisonEngine().compare(
        broker_a,
        broker_b,
        replace(request(), contract_a=contract_a, contract_b=contract_b),
    )

    assert analysis.summary.normalized_pnl_legs_agree is False
    assert analysis.summary.normalized_pnl_leg_disagreement_ratio == pytest.approx(0.5)
    assert analysis.summary.classification.endswith("_contract_legs_disagree")
    # The edge is still valued once, not summed across the two legs.
    assert analysis.summary.maximum_normalized_net_pnl == pytest.approx(
        analysis.aligned_observations["normalized_net_pnl"].max()
    )


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
    broker_a, broker_b = continuous_opportunity(2000)
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


def test_symmetric_synchronization_is_unaffected_by_broker_row_order() -> None:
    """A feed whose rows arrive out of order must align exactly as a sorted one.

    Event-time matching searches a sorted array. Feeding it an unsorted one pairs
    each tick with the wrong neighbour instead of failing, which silently
    discarded observations and mislabelled the delay as zero.
    """
    broker_a = tick_frame([(1.1, 1.2), (1.1, 1.2), (1.1, 1.2)], [0, 10, 20])
    broker_b_sorted = tick_frame([(1.1, 1.2), (1.1, 1.2), (1.1, 1.2)], [0, 10, 20])
    broker_b_shuffled = broker_b_sorted.iloc[[2, 0, 1]].reset_index(drop=True)

    engine = CrossBrokerComparisonEngine()
    ordered = engine.compare(
        broker_a,
        broker_b_sorted,
        replace(request(), synchronization_mode=SynchronizationMode.SYMMETRIC),
    )
    shuffled = engine.compare(
        broker_a,
        broker_b_shuffled,
        replace(request(), synchronization_mode=SynchronizationMode.SYMMETRIC),
    )

    assert shuffled.summary.aligned_observations == ordered.summary.aligned_observations == 3
    assert (
        shuffled.summary.mean_alignment_delay_ms == ordered.summary.mean_alignment_delay_ms == 0.0
    )
    assert shuffled.aligned_observations["timestamp"].tolist() == (
        ordered.aligned_observations["timestamp"].tolist()
    )


def test_a_time_gap_separates_opportunity_episodes() -> None:
    """Two crossable instants are not one long opportunity.

    The edge was visible at two disjoint moments, so nothing could be held across
    the gap between them. Index adjacency would report a single multi-second
    episode and hand its inflated duration to the latency model.
    """
    broker_a = tick_frame([(1.1000, 1.1002), (1.1000, 1.1002)], [0, 10_000])
    broker_b = tick_frame([(1.1006, 1.1008), (1.1006, 1.1008)], [0, 10_000])

    analysis = CrossBrokerComparisonEngine().compare(broker_a, broker_b, request())

    assert analysis.summary.crossable_observations == 2
    assert analysis.summary.opportunity_count == 2
    assert all(opportunity.duration_ms == 0.0 for opportunity in analysis.opportunities)
    assert analysis.summary.maximum_opportunity_duration_ms == 0.0


def test_the_episode_records_where_its_peak_was_observed() -> None:
    """The latency model needs the peak's position, not only its size.

    The maximum over an episode is taken from whichever tick happened to be
    widest, which can be anywhere in the window. A consumer that treats the peak
    as the episode's starting value credits the position with an edge as large
    as the peak for the whole episode, so the offset has to travel with the
    measurement rather than being assumed.
    """
    broker_a = tick_frame([(1.1000, 1.1002)] * 4, [0, 1000, 2000, 3000])
    broker_b = tick_frame(
        [(1.1004, 1.1006), (1.1006, 1.1008), (1.1012, 1.1014), (1.1005, 1.1007)],
        [0, 1000, 2000, 3000],
    )

    analysis = CrossBrokerComparisonEngine().compare(broker_a, broker_b, request())

    opportunity = analysis.opportunities[0]
    assert opportunity.duration_ms == 3000.0
    # The widest gap is the third tick, two seconds into a three-second episode.
    assert opportunity.peak_offset_ms == pytest.approx(2000.0)
    assert 0.0 < opportunity.peak_offset_ms < opportunity.duration_ms


def test_a_continuous_run_stays_one_episode() -> None:
    """Ticking through an opportunity without a gap is still a single episode."""
    broker_a = tick_frame([(1.1000, 1.1002), (1.1001, 1.1003), (1.1002, 1.1004)], [0, 20, 40])
    broker_b = tick_frame([(1.1006, 1.1008), (1.1006, 1.1008), (1.1006, 1.1008)], [0, 20, 40])

    analysis = CrossBrokerComparisonEngine().compare(broker_a, broker_b, request())

    assert analysis.summary.opportunity_count == 1
    assert analysis.opportunities[0].observations == 3
    assert analysis.opportunities[0].duration_ms == 40.0


def test_explicit_episode_gap_can_bridge_a_sparse_feed() -> None:
    """A known tick-sparse feed can widen the gap the caller considers continuous."""
    broker_a = tick_frame([(1.1000, 1.1002), (1.1000, 1.1002)], [0, 10_000])
    broker_b = tick_frame([(1.1006, 1.1008), (1.1006, 1.1008)], [0, 10_000])

    analysis = CrossBrokerComparisonEngine().compare(
        broker_a,
        broker_b,
        replace(request(), maximum_episode_gap_ms=30_000),
    )

    assert analysis.summary.opportunity_count == 1
    assert analysis.opportunities[0].duration_ms == 10_000.0


def test_non_finite_and_empty_broker_data_are_rejected_explicitly() -> None:
    """A missing or unpriced feed is a data problem, not a zero or a symbol mismatch."""
    engine = CrossBrokerComparisonEngine()
    valid = tick_frame([(1.1, 1.2)])

    with pytest.raises(DataQualityError, match="no rows"):
        engine.compare(
            pd.DataFrame(columns=["timestamp", "symbol", "bid", "ask"]), valid, request()
        )

    nan_price = valid.assign(bid=float("nan"))
    with pytest.raises(DataQualityError, match="finite"):
        engine.compare(nan_price, valid, request())

    with pytest.raises(DataQualityError, match="missing columns"):
        engine.compare(valid.drop(columns=["timestamp"]), valid, request())


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
