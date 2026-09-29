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


def test_a_consistently_scaled_contract_size_requires_normalization() -> None:
    """Halving the lot size and the tick value together is the same instrument.

    Both fields scale the money value of one unit of the underlying, so a broker
    quoting the same instrument at half the lot size reports half of each. The
    difference is real but reconcilable by volume normalization.
    """
    report = ContractSpecificationAnalyzer().compare(
        specification(),
        replace(
            specification(),
            broker="BrokerB",
            contract_size=50000.0,
            tick_value=0.5,
        ),
    )

    assert report.status is ContractCompatibilityStatus.NORMALIZATION_REQUIRED
    assert report.contract_size_ratio == 0.5


def test_a_differing_volume_cap_is_not_a_different_instrument() -> None:
    """A size limit is a fill-time constraint, not a statement about the contract.

    Observed on the live demo pair on 2026-09-29: WTI reports an identical
    `contract_size` (1000), `tick_size`, and `tick_value` (10) on both brokers
    and differs only in `volume_max` — 5 lots against 100. That is one
    instrument with a different size limit, and a study at a size both
    accept is valid. The earlier code refused the whole comparison, which was
    stricter than the evidence required, and the fill assessor already refuses
    a size a broker cannot take.
    """
    report = ContractSpecificationAnalyzer().compare(
        specification(),
        replace(specification(), broker="BrokerB", volume_max=5.0),
    )

    assert report.status is ContractCompatibilityStatus.COMPATIBLE
    assert report.blocks_comparison is False
    assert report.issues == ()


def test_the_size_asymmetry_is_still_reported() -> None:
    """A real limit must be visible, not silently dropped to make a gate pass."""
    report = ContractSpecificationAnalyzer().compare(
        specification(),
        replace(specification(), broker="BrokerB", volume_max=5.0),
    )

    assert any("maximum volumes differ" in advisory for advisory in report.advisories)


def test_an_advisory_never_blocks_by_being_noticed() -> None:
    """Advisories are kept apart from issues, which drive the blocking decision.

    An advisory placed in `issues` would block a comparison merely by being
    read, which is the behaviour being corrected.
    """
    report = ContractSpecificationAnalyzer().compare(
        specification(),
        replace(specification(), broker="BrokerB", volume_max=5.0),
    )

    assert "maximum volumes differ" not in " ".join(report.issues)
    assert ContractCompatibilityStatus.COMPATIBLE not in {
        ContractCompatibilityStatus.INCOMPATIBLE,
        ContractCompatibilityStatus.REVIEW_REQUIRED,
    }


def test_a_real_incompatibility_still_blocks_alongside_an_advisory() -> None:
    """An advisory must not soften a genuine mismatch."""
    report = ContractSpecificationAnalyzer().compare(
        specification(),
        replace(
            specification(),
            broker="BrokerB",
            volume_max=5.0,
            currency_profit="GBP",
        ),
    )

    assert report.status is ContractCompatibilityStatus.INCOMPATIBLE
    assert report.blocks_comparison is True
    assert "profit currencies differ" in report.issues
    assert report.advisories  # the cap is still reported


def test_the_fill_gate_still_refuses_a_size_the_broker_cannot_take() -> None:
    """The cap is enforced, just at fill time rather than by refusing the study."""
    from market_relationship_discovery.costs.execution import FillSimulator, VolumeStatus

    estimate = FillSimulator().estimate(
        specification=specification(volume_max=5.0), requested_volume=50.0
    )

    assert estimate.status is VolumeStatus.ABOVE_MAXIMUM
    assert estimate.limited_by == "volume_max"


def test_a_halving_the_contract_size_alone_is_refused() -> None:
    """Halving the lot size without halving the tick value is a different instrument.

    The two legs then value the same position differently at every volume, so no
    normalization can reconcile them. The earlier code returned
    ``normalization_required`` here and reported the disagreement only as an
    advisory suffix on an otherwise crossable opportunity.
    """
    report = ContractSpecificationAnalyzer().compare(
        specification(),
        replace(specification(), broker="BrokerB", contract_size=50000.0),
    )

    assert report.status is ContractCompatibilityStatus.INCOMPATIBLE
    assert "do not value the same instrument" in report.issues[0]


def test_halving_the_tick_value_alone_is_refused() -> None:
    report = ContractSpecificationAnalyzer().compare(
        specification(),
        replace(specification(), broker="BrokerB", tick_value=0.5),
    )

    assert report.status is ContractCompatibilityStatus.INCOMPATIBLE


def test_a_ten_times_difference_in_both_fields_is_the_same_instrument() -> None:
    report = ContractSpecificationAnalyzer().compare(
        specification(),
        replace(
            specification(),
            broker="BrokerB",
            contract_size=10000.0,
            tick_value=0.1,
        ),
    )

    assert report.status is ContractCompatibilityStatus.NORMALIZATION_REQUIRED
    assert report.contract_size_ratio == 0.1


def test_a_difference_larger_than_rounding_is_refused() -> None:
    """The tolerance absorbs a rounded field, not a changed scale.

    A 0.5% gap is a broker publishing at limited precision; a 2% gap means the
    two specifications value one unit of the underlying differently.
    """
    rounded = ContractSpecificationAnalyzer().compare(
        specification(),
        replace(
            specification(),
            broker="BrokerB",
            contract_size=50000.0,
            tick_value=0.5 * 1.005,
        ),
    )
    changed = ContractSpecificationAnalyzer().compare(
        specification(),
        replace(
            specification(),
            broker="BrokerB",
            contract_size=50000.0,
            tick_value=0.5 * 0.98,
        ),
    )

    assert rounded.status is ContractCompatibilityStatus.NORMALIZATION_REQUIRED
    assert changed.status is ContractCompatibilityStatus.INCOMPATIBLE


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
