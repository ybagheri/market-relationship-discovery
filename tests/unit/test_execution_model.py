"""Tests for margin, funding, and fill feasibility modelling.

The central safety property is that a broker-reported margin of ``0.0`` means
*not reported*. MetaTrader returns zero margin for many CFD symbols, and reading
that as free capital would make an unaffordable position look tradeable.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from market_relationship_discovery.config.settings import CostSettings
from market_relationship_discovery.costs.execution import (
    ExecutionAssessor,
    FillSimulator,
    FundingModel,
    MarginModel,
    MarginSource,
    VolumeStatus,
)
from market_relationship_discovery.market_data.contract import ContractSpecification


def specification(**overrides: float) -> ContractSpecification:
    base: dict[str, object] = {
        "broker": "Demo",
        "server": "Demo",
        "symbol": "XAUUSD",
        "description": "Gold",
        "path": "Metals\\XAUUSD",
        "currency_base": "USD",
        "currency_profit": "USD",
        "digits": 2,
        "point": 0.01,
        "spread": 19,
        "trade_mode": 4,
        "contract_size": 100.0,
        "volume_min": 0.01,
        "volume_max": 100.0,
        "volume_step": 0.01,
        "tick_size": 0.01,
        "tick_value": 1.0,
        "margin_initial": 0.0,
    }
    base.update(overrides)
    return ContractSpecification(**base)  # type: ignore[arg-type]


def test_broker_reported_margin_is_preferred() -> None:
    contract = specification(margin_initial=500.0)

    requirement = MarginModel(leverage=500).requirement(contract, volume=2.0, price=3000.0)

    assert requirement.source is MarginSource.BROKER_REPORTED
    assert requirement.margin == 1000.0
    assert requirement.is_known is True


def test_zero_broker_margin_is_treated_as_not_reported() -> None:
    """A zero margin field must never be read as free capital."""
    contract = specification(margin_initial=0.0)

    derived = MarginModel(leverage=500).requirement(contract, volume=1.0, price=3000.0)
    unknown = MarginModel().requirement(contract, volume=1.0, price=3000.0)

    assert derived.source is MarginSource.LEVERAGE_DERIVED
    assert derived.margin == pytest.approx(3000.0 * 100.0 / 500)
    assert unknown.source is MarginSource.UNAVAILABLE
    assert unknown.margin is None
    assert unknown.is_known is False


def test_missing_contract_leaves_margin_unavailable() -> None:
    requirement = MarginModel(leverage=500).requirement(None, volume=1.0, price=3000.0)

    assert requirement.source is MarginSource.UNAVAILABLE
    assert requirement.is_known is False


def test_notional_uses_contract_size_and_price() -> None:
    contract = specification(contract_size=100000.0)

    requirement = MarginModel(leverage=100).requirement(contract, volume=1.0, price=1.2)

    assert requirement.notional == pytest.approx(120000.0)
    assert requirement.margin == pytest.approx(1200.0)


def test_combined_margin_sums_both_legs() -> None:
    model = MarginModel(leverage=100)

    first, second = model.combined(
        specification(contract_size=100.0),
        specification(contract_size=100.0),
        1.0,
        1.0,
        3000.0,
        3000.0,
    )

    assert MarginModel.total((first, second)) == pytest.approx(6000.0)


def test_total_margin_is_unknown_when_any_leg_is_unknown() -> None:
    known = MarginModel(leverage=100).requirement(specification(), 1.0, 3000.0)
    unknown = MarginModel().requirement(specification(), 1.0, 3000.0)

    assert MarginModel.total((known, unknown)) is None
    assert MarginModel.total(()) is None


def test_fill_rounds_down_to_the_broker_volume_step() -> None:
    contract = specification(volume_step=0.1)

    estimate = FillSimulator().estimate(contract, 0.37)

    assert estimate.status is VolumeStatus.FILLABLE
    assert estimate.filled_volume == pytest.approx(0.3)
    assert estimate.limited_by == "volume_step"
    assert estimate.partial_fill is True


def test_fill_is_clamped_by_the_broker_volume_maximum() -> None:
    contract = specification(volume_max=10.0, volume_step=0.01)

    estimate = FillSimulator().estimate(contract, 25.0)

    assert estimate.status is VolumeStatus.ABOVE_MAXIMUM
    assert estimate.filled_volume == pytest.approx(10.0)
    assert estimate.limited_by == "volume_max"
    assert estimate.fill_ratio == pytest.approx(0.4)


def test_fill_below_minimum_volume_is_refused() -> None:
    contract = specification(volume_min=0.1, volume_step=0.01)

    estimate = FillSimulator().estimate(contract, 0.05)

    assert estimate.status is VolumeStatus.BELOW_MINIMUM
    assert estimate.filled_volume == 0.0


def test_fill_without_contract_is_unknown_not_refused() -> None:
    estimate = FillSimulator().estimate(None, 1.0)

    assert estimate.status is VolumeStatus.UNKNOWN_CONTRACT
    assert estimate.fill_ratio == 0.0


def test_observer_reported_bitcoin_volume_caps_differ_across_brokers() -> None:
    """The two configured brokers cap bitcoin size very differently.

    Broker A allows up to 300 lots while broker B allows 10, so a pair sized for
    broker A is only partially fillable on broker B.
    """
    broker_a = specification(volume_max=300.0, volume_step=0.01)
    broker_b = specification(volume_max=10.0, volume_step=0.01)

    first, second = FillSimulator().pair(broker_a, broker_b, 50.0, 50.0)

    assert first.filled_volume == pytest.approx(50.0)
    assert second.filled_volume == pytest.approx(10.0)
    assert second.status is VolumeStatus.ABOVE_MAXIMUM


def test_funding_is_zero_within_a_single_session() -> None:
    model = FundingModel(daily_rate_fraction=0.0005)
    contract = specification()

    cost = model.cost(contract, 100000.0, date(2026, 9, 25), date(2026, 9, 25))

    assert cost.cost == 0.0
    assert cost.nights == 0


def test_funding_accrues_per_night_held() -> None:
    model = FundingModel(daily_rate_fraction=0.0005)

    cost = model.cost(specification(), 100000.0, date(2026, 9, 25), date(2026, 9, 28))

    assert cost.nights == 3
    assert cost.cost == pytest.approx(100000.0 * 0.0005 * 3)


def test_triple_swap_applies_on_the_configured_rollover_weekday() -> None:
    model = FundingModel(daily_rate_fraction=0.0005, triple_swap_weekday=2)
    wednesday = date(2026, 9, 23)
    assert wednesday.weekday() == 2

    cost = model.cost(specification(), 100000.0, wednesday, date(2026, 9, 24))

    assert cost.applied_triple_swap is True
    assert cost.cost == pytest.approx(100000.0 * 0.0005 * 3)


def test_funding_can_be_disabled() -> None:
    model = FundingModel(daily_rate_fraction=0.0005, enabled=False)

    cost = model.cost(specification(), 100000.0, date(2026, 9, 25), date(2026, 9, 30))

    assert cost.cost == 0.0
    assert model.enabled is False


def test_execution_is_executable_when_margin_is_derived_and_size_fits() -> None:
    assessor = ExecutionAssessor(
        MarginModel(leverage=500),
        FillSimulator(),
        leverage=500,
    )

    assessment = assessor.assess(
        specification(),
        specification(),
        1.0,
        1.0,
        3000.0,
        3000.0,
    )

    assert assessment.executable is True
    assert assessment.capital_verified is True
    assert assessment.blocking_reasons == ()
    assert assessment.binding_fill_ratio == pytest.approx(1.0)


def test_partial_fill_is_still_executable_but_reports_the_reduced_size() -> None:
    """A broker-side cap reduces size without destroying the opportunity.

    PnL scales with filled volume, so a capped fill remains executable. The
    reduced size is reported through ``binding_fill_ratio`` and the fill objects
    rather than being hidden, and ``minimum_fill_ratio`` is the control for
    callers that require a minimum size.
    """
    assessor = ExecutionAssessor(
        MarginModel(leverage=500),
        FillSimulator(),
        leverage=500,
    )

    assessment = assessor.assess(
        specification(volume_min=0.01),
        specification(volume_max=10.0),
        1.0,
        50.0,
        3000.0,
        3000.0,
    )

    assert assessment.executable is True
    assert assessment.blocking_reasons == ()
    assert assessment.fill_b.status is VolumeStatus.ABOVE_MAXIMUM
    assert assessment.fill_b.filled_volume == pytest.approx(10.0)
    assert assessment.binding_fill_ratio == pytest.approx(0.2)


def test_execution_is_blocked_when_the_fill_ratio_is_below_the_minimum() -> None:
    assessor = ExecutionAssessor(
        MarginModel(leverage=500),
        FillSimulator(),
        leverage=500,
        minimum_fill_ratio=0.5,
    )

    assessment = assessor.assess(
        specification(volume_max=10.0),
        specification(volume_max=10.0),
        50.0,
        50.0,
        3000.0,
        3000.0,
    )

    assert assessment.executable is False
    assert any("fill ratio" in reason for reason in assessment.blocking_reasons)


def test_unknown_capital_is_reported_without_deleting_the_opportunity() -> None:
    """Missing margin lowers confidence but is not proof of infeasibility."""
    assessor = ExecutionAssessor(MarginModel(), FillSimulator())

    assessment = assessor.assess(
        specification(),
        specification(),
        1.0,
        1.0,
        3000.0,
        3000.0,
    )

    assert assessment.executable is True
    assert assessment.capital_verified is False
    assert assessment.blocking_reasons == ()
    assert any("must not be read as free margin" in reason for reason in assessment.reasons)


def test_execution_parameters_are_validated() -> None:
    with pytest.raises(ValueError, match="leverage"):
        MarginModel(leverage=0)
    with pytest.raises(ValueError, match="volume"):
        MarginModel().requirement(specification(), 0.0, 3000.0)
    with pytest.raises(ValueError, match="price"):
        MarginModel().requirement(specification(), 1.0, 0.0)
    with pytest.raises(ValueError, match="requested_volume"):
        FillSimulator().estimate(specification(), 0.0)
    with pytest.raises(ValueError, match="triple_swap_weekday"):
        FundingModel(triple_swap_weekday=9)
    with pytest.raises(ValueError, match="minimum_fill_ratio"):
        ExecutionAssessor(MarginModel(), FillSimulator(), minimum_fill_ratio=1.5)


def test_cost_settings_expose_execution_assumptions() -> None:
    settings = CostSettings(
        volume=2.5,
        leverage=500,
        funding_daily_rate=0.0004,
        minimum_fill_ratio=0.25,
    )

    assert settings.volume == 2.5
    assert settings.leverage == 500
    assert settings.funding_daily_rate == 0.0004
    assert settings.minimum_fill_ratio == 0.25


def test_contract_rejects_a_replaced_margin_that_is_negative() -> None:
    with pytest.raises(ValueError):
        replace(specification(), margin_initial=-1.0)
