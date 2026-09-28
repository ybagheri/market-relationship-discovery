from dataclasses import replace

import pytest

from market_relationship_discovery.market_data.contract import (
    ContractCompatibilityStatus,
    ContractEdgeNormalizer,
    ContractSpecification,
    ContractSpecificationAnalyzer,
)


def specification(**overrides: object) -> ContractSpecification:
    values: dict[str, object] = {
        "broker": "BrokerA",
        "server": "ServerA",
        "symbol": "EURUSD",
        "description": "EURUSD",
        "path": "Forex\\EURUSD",
        "currency_base": "EUR",
        "currency_profit": "USD",
        "digits": 5,
        "point": 0.00001,
        "spread": 10,
        "trade_mode": 4,
        "contract_size": 100000.0,
        "volume_min": 0.01,
        "volume_max": 100.0,
        "volume_step": 0.01,
        "tick_size": 0.00001,
        "tick_value": 1.0,
        "margin_initial": 0.0,
    }
    values.update(overrides)
    return ContractSpecification(**values)


def test_missing_specifications_are_unverified() -> None:
    report = ContractSpecificationAnalyzer().compare(None, None)

    assert report.status is ContractCompatibilityStatus.UNVERIFIED
    assert report.issues


def test_identical_specifications_are_compatible() -> None:
    report = ContractSpecificationAnalyzer().compare(
        specification(),
        replace(specification(), broker="BrokerB", server="ServerB", spread=12),
    )

    assert report.status is ContractCompatibilityStatus.COMPATIBLE
    assert report.issues == ()
    assert report.contract_size_ratio == 1.0


def test_contract_size_difference_requires_normalization() -> None:
    report = ContractSpecificationAnalyzer().compare(
        specification(),
        replace(specification(), broker="BrokerB", contract_size=50000.0),
    )

    assert report.status is ContractCompatibilityStatus.NORMALIZATION_REQUIRED
    assert report.contract_size_ratio == 0.5


def test_contract_edge_normalizer_scales_volume_and_values_the_edge_once() -> None:
    """The price difference is realized once, not once per leg.

    Broker A quotes 100k units per lot and Broker B 50k, so one lot on A and two
    lots on B cover the same notional. A one-pip edge on that notional is worth
    $10 either way. Adding the two valuations would report $30 for $10 of
    profit, so the legs are reported as the two independent estimates they are.
    """
    contract_a = specification()
    contract_b = replace(
        specification(),
        broker="BrokerB",
        contract_size=50000.0,
        tick_value=0.5,
    )

    normalized = ContractEdgeNormalizer().normalize(0.0001, contract_a, contract_b)

    assert normalized.broker_a_volume == 1.0
    assert normalized.broker_b_volume == 2.0
    assert normalized.broker_a_pnl == pytest.approx(10.0)
    assert normalized.broker_b_pnl == pytest.approx(10.0)
    assert normalized.net_pnl == pytest.approx(10.0)
    assert normalized.legs_agree is True


def test_a_symmetric_opportunity_is_not_double_counted() -> None:
    """Identical contracts on both sides must not inflate a symmetric edge."""
    contract_a = specification()
    contract_b = replace(specification(), broker="BrokerB")

    normalized = ContractEdgeNormalizer().normalize(0.0004, contract_a, contract_b)

    assert normalized.broker_a_pnl == normalized.broker_b_pnl == pytest.approx(40.0)
    assert normalized.net_pnl == pytest.approx(40.0)
    assert normalized.net_pnl != pytest.approx(normalized.broker_a_pnl * 2)


def test_mutually_inconsistent_contracts_are_flagged_rather_than_summed() -> None:
    """Halving contract size while leaving tick value alone is not a real contract.

    The two legs then value the same edge differently. That is a metadata
    inconsistency to report, not extra profit to add.
    """
    contract_a = specification()
    contract_b = replace(specification(), broker="BrokerB", contract_size=50000.0)

    normalized = ContractEdgeNormalizer().normalize(0.0001, contract_a, contract_b)

    assert normalized.legs_agree is False
    assert normalized.broker_a_pnl == pytest.approx(10.0)
    assert normalized.broker_b_pnl == pytest.approx(20.0)
    assert normalized.leg_disagreement_ratio == pytest.approx(0.5)
    assert normalized.net_pnl == pytest.approx(normalized.broker_a_pnl)


def test_currency_difference_is_incompatible() -> None:
    report = ContractSpecificationAnalyzer().compare(
        specification(),
        replace(specification(), broker="BrokerB", currency_profit="GBP"),
    )

    assert report.status is ContractCompatibilityStatus.INCOMPATIBLE
    assert "profit currencies differ" in report.issues
