"""Margin, funding, and fill-feasibility modelling for research estimates.

This module completes the cost side of the platform. It exists because a gross
cross-broker discrepancy is not a tradeable amount until three further questions
are answered:

* how much capital must be committed to hold the position,
* what does holding it overnight cost in funding,
* can the requested size actually be filled at either broker.

Every model reports where its numbers came from and refuses to invent a value.
In particular a broker-reported margin of ``0.0`` means *not reported*, not
*free*: MetaTrader returns zero margin for many CFD symbols even though the
account is subject to leverage limits, and treating that as free margin would
make an unaffordable position look affordable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from market_relationship_discovery.market_data.contract import ContractSpecification


class MarginSource(StrEnum):
    """Where a margin figure came from.

    ``UNAVAILABLE`` is a first-class outcome. A research report must be able to
    say that capital requirements are unknown instead of implying they are zero.
    """

    BROKER_REPORTED = "broker_reported"
    LEVERAGE_DERIVED = "leverage_derived"
    UNAVAILABLE = "unavailable"


class VolumeStatus(StrEnum):
    FILLABLE = "fillable"
    BELOW_MINIMUM = "below_minimum"
    ABOVE_MAXIMUM = "above_maximum"
    UNKNOWN_CONTRACT = "unknown_contract"


@dataclass(frozen=True, slots=True)
class MarginRequirement:
    """Capital committed to hold one position."""

    margin: float | None
    source: MarginSource
    notional: float | None
    leverage: int | None

    @property
    def is_known(self) -> bool:
        return self.margin is not None and self.source is not MarginSource.UNAVAILABLE

    def to_dict(self) -> dict[str, object]:
        return {
            "margin": self.margin,
            "source": self.source.value,
            "notional": self.notional,
            "leverage": self.leverage,
        }


@dataclass(frozen=True, slots=True)
class FillEstimate:
    """Whether a requested size can actually be filled at one broker."""

    status: VolumeStatus
    requested_volume: float
    filled_volume: float
    limited_by: str | None
    partial_fill: bool

    @property
    def fill_ratio(self) -> float:
        if self.requested_volume <= 0:
            return 0.0
        return min(1.0, self.filled_volume / self.requested_volume)

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "requested_volume": self.requested_volume,
            "filled_volume": self.filled_volume,
            "limited_by": self.limited_by,
            "partial_fill": self.partial_fill,
            "fill_ratio": self.fill_ratio,
        }


@dataclass(frozen=True, slots=True)
class FundingCost:
    """Holding cost accrued over a period."""

    cost: float
    nights: int
    applied_triple_swap: bool
    annualized_rate: float | None

    def to_dict(self) -> dict[str, object]:
        return {
            "cost": self.cost,
            "nights": self.nights,
            "applied_triple_swap": self.applied_triple_swap,
            "annualized_rate": self.annualized_rate,
        }


class MarginModel:
    """Estimate the margin a position commits.

    Broker-reported margin is preferred. When the broker does not report it, a
    leverage-derived figure is used and clearly labelled, and when no leverage is
    configured the result is explicitly unavailable.
    """

    def __init__(self, leverage: int | None = None) -> None:
        if leverage is not None and leverage <= 0:
            raise ValueError("leverage must be positive when provided")
        self._leverage = leverage

    def requirement(
        self,
        specification: ContractSpecification | None,
        volume: float,
        price: float,
    ) -> MarginRequirement:
        if volume <= 0:
            raise ValueError("volume must be positive")
        if price <= 0:
            raise ValueError("price must be positive")
        if specification is None:
            return MarginRequirement(None, MarginSource.UNAVAILABLE, None, self._leverage)
        notional = volume * specification.contract_size * price
        if specification.margin_initial > 0.0:
            return MarginRequirement(
                margin=specification.margin_initial * volume,
                source=MarginSource.BROKER_REPORTED,
                notional=notional,
                leverage=self._leverage,
            )
        if self._leverage is None:
            return MarginRequirement(
                margin=None,
                source=MarginSource.UNAVAILABLE,
                notional=notional,
                leverage=None,
            )
        return MarginRequirement(
            margin=notional / self._leverage,
            source=MarginSource.LEVERAGE_DERIVED,
            notional=notional,
            leverage=self._leverage,
        )

    def combined(
        self,
        specification_a: ContractSpecification | None,
        specification_b: ContractSpecification | None,
        volume_a: float,
        volume_b: float,
        price_a: float,
        price_b: float,
    ) -> tuple[MarginRequirement, MarginRequirement]:
        """Margin for both legs of a cross-broker pair.

        A cross-broker position commits capital on both sides at the same time,
        so the pair is only as feasible as the larger of the two requirements.
        """
        return (
            self.requirement(specification_a, volume_a, price_a),
            self.requirement(specification_b, volume_b, price_b),
        )

    @staticmethod
    def total(requirements: tuple[MarginRequirement, ...]) -> float | None:
        values = [item.margin for item in requirements if item.margin is not None]
        if len(values) != len(requirements) or not values:
            return None
        return sum(values)


class FillSimulator:
    """Reduce a requested volume to what a broker would actually accept.

    Brokers reject volumes that are not multiples of ``volume_step`` and cap
    exposure at ``volume_max``. A size above that cap is a partial fill, not an
    opportunity, so it is reported rather than silently truncated.
    """

    def estimate(
        self,
        specification: ContractSpecification | None,
        requested_volume: float,
    ) -> FillEstimate:
        if requested_volume <= 0:
            raise ValueError("requested_volume must be positive")
        if specification is None:
            return FillEstimate(
                status=VolumeStatus.UNKNOWN_CONTRACT,
                requested_volume=requested_volume,
                filled_volume=0.0,
                limited_by="missing_contract_specification",
                partial_fill=True,
            )
        step = specification.volume_step
        stepped = self._round_down(requested_volume, step)
        if stepped < specification.volume_min:
            return FillEstimate(
                status=VolumeStatus.BELOW_MINIMUM,
                requested_volume=requested_volume,
                filled_volume=0.0,
                limited_by="volume_min",
                partial_fill=True,
            )
        if requested_volume > specification.volume_max:
            capped = self._round_down(specification.volume_max, step)
            return FillEstimate(
                status=VolumeStatus.ABOVE_MAXIMUM,
                requested_volume=requested_volume,
                filled_volume=capped,
                limited_by="volume_max",
                partial_fill=True,
            )
        if stepped < requested_volume:
            return FillEstimate(
                status=VolumeStatus.FILLABLE,
                requested_volume=requested_volume,
                filled_volume=stepped,
                limited_by="volume_step",
                partial_fill=True,
            )
        return FillEstimate(
            status=VolumeStatus.FILLABLE,
            requested_volume=requested_volume,
            filled_volume=stepped,
            limited_by=None,
            partial_fill=False,
        )

    def pair(
        self,
        specification_a: ContractSpecification | None,
        specification_b: ContractSpecification | None,
        requested_volume_a: float,
        requested_volume_b: float,
    ) -> tuple[FillEstimate, FillEstimate]:
        """Fill estimates for both legs, scaled to the worse of the two.

        A cross-broker pair is only as executable as its weaker side, so the
        binding constraint is reported rather than averaged away.
        """
        first = self.estimate(specification_a, requested_volume_a)
        second = self.estimate(specification_b, requested_volume_b)
        return first, second

    @staticmethod
    def _round_down(volume: float, step: float) -> float:
        if step <= 0:
            return volume
        steps = int(volume / step + 1e-9)
        return round(steps * step, 10)


class FundingModel:
    """Accrue overnight funding, including the triple-swap rollover.

    Funding is a function of how long a position is held, so it cannot be folded
    into a flat per-trade constant without hiding the holding-time risk.
    """

    def __init__(
        self,
        daily_rate_fraction: float = 0.0,
        triple_swap_weekday: int = 2,
        enabled: bool = True,
    ) -> None:
        if triple_swap_weekday < 0 or triple_swap_weekday > 6:
            raise ValueError("triple_swap_weekday must be a weekday index from 0 to 6")
        self._daily_rate = daily_rate_fraction
        self._triple_swap_weekday = triple_swap_weekday
        self._enabled = enabled

    @property
    def daily_rate_fraction(self) -> float:
        return self._daily_rate

    @property
    def enabled(self) -> bool:
        return self._enabled

    def cost(
        self,
        specification: ContractSpecification | None,
        notional: float | None,
        start: date,
        end: date,
    ) -> FundingCost:
        """Accrue funding for whole days held between ``start`` and ``end``.

        A position opened and closed inside the same day accrues nothing, which
        is why the cross-broker research layer applies funding per opportunity
        episode rather than per tick observation.
        """
        nights = max(0, (end - start).days)
        if nights == 0 or not self._enabled or self._daily_rate == 0.0:
            return FundingCost(0.0, 0, False, self._daily_rate or None)
        if notional is None or specification is None:
            return FundingCost(0.0, nights, False, self._daily_rate)
        multiplier = 1.0
        if nights == 1 and start.weekday() == self._triple_swap_weekday:
            multiplier = 3.0
        accrued = abs(notional) * self._daily_rate * nights * multiplier
        return FundingCost(accrued, nights, multiplier > 1.0, self._daily_rate)

    def horizon_days(self, start: date, days: int) -> date:
        if days < 0:
            raise ValueError("days cannot be negative")
        return start + timedelta(days=days)


@dataclass(frozen=True, slots=True)
class ExecutionAssessment:
    """Combined feasibility verdict for a candidate cross-broker position.

    ``executable`` reflects only constraints that are *known* to fail, such as a
    size the broker cannot accept. Incomplete information is reported through
    ``capital_verified`` and ``reasons`` instead, so a missing configuration
    value downgrades confidence without silently deleting observations.
    """

    executable: bool
    capital_verified: bool
    reasons: tuple[str, ...]
    blocking_reasons: tuple[str, ...]
    margin_a: MarginRequirement
    margin_b: MarginRequirement
    total_margin: float | None
    fill_a: FillEstimate
    fill_b: FillEstimate
    binding_fill_ratio: float

    def to_dict(self) -> dict[str, object]:
        return {
            "executable": self.executable,
            "capital_verified": self.capital_verified,
            "reasons": list(self.reasons),
            "blocking_reasons": list(self.blocking_reasons),
            "margin_a": self.margin_a.to_dict(),
            "margin_b": self.margin_b.to_dict(),
            "total_margin": self.total_margin,
            "fill_a": self.fill_a.to_dict(),
            "fill_b": self.fill_b.to_dict(),
            "binding_fill_ratio": self.binding_fill_ratio,
        }


class ExecutionAssessor:
    """Judge whether a sized cross-broker position could actually be held.

    A candidate is refused when either broker demonstrably cannot fill the
    requested size, or when the achievable size falls below the configured
    minimum. When capital requirements cannot be determined the verdict is
    reported as unverified rather than assumed affordable, but the observation is
    not deleted: an unknown margin is a confidence problem, not proof of
    infeasibility.
    """

    def __init__(
        self,
        margin_model: MarginModel,
        fill_simulator: FillSimulator,
        leverage: int | None = None,
        minimum_fill_ratio: float = 0.0,
    ) -> None:
        if not 0.0 <= minimum_fill_ratio <= 1.0:
            raise ValueError("minimum_fill_ratio must be between zero and one")
        self._margin = margin_model
        self._fills = fill_simulator
        self._leverage = leverage
        self._minimum_fill_ratio = minimum_fill_ratio

    def assess(
        self,
        specification_a: ContractSpecification | None,
        specification_b: ContractSpecification | None,
        volume_a: float,
        volume_b: float,
        price_a: float,
        price_b: float,
    ) -> ExecutionAssessment:
        margin_a, margin_b = self._margin.combined(
            specification_a,
            specification_b,
            volume_a,
            volume_b,
            price_a,
            price_b,
        )
        fill_a, fill_b = self._fills.pair(
            specification_a,
            specification_b,
            volume_a,
            volume_b,
        )
        total_margin = MarginModel.total((margin_a, margin_b))
        blocking: list[str] = []
        notes: list[str] = []
        if fill_a.status is VolumeStatus.UNKNOWN_CONTRACT:
            # An absent specification is missing information, not a demonstrated
            # refusal. The cross-broker layer already reports this as an
            # unverified contract, so it must not delete the observation.
            notes.append("broker A contract specification is absent, so no fill estimate exists")
        if fill_b.status is VolumeStatus.UNKNOWN_CONTRACT:
            notes.append("broker B contract specification is absent, so no fill estimate exists")
        if fill_a.status is VolumeStatus.BELOW_MINIMUM:
            blocking.append("requested size is below the broker A minimum volume")
        if fill_b.status is VolumeStatus.BELOW_MINIMUM:
            blocking.append("requested size is below the broker B minimum volume")
        binding = min(fill_a.fill_ratio, fill_b.fill_ratio)
        if fill_a.status is not VolumeStatus.UNKNOWN_CONTRACT and (
            fill_b.status is not VolumeStatus.UNKNOWN_CONTRACT
        ):
            if binding < self._minimum_fill_ratio:
                blocking.append(
                    f"binding fill ratio {binding:.4f} is below the required "
                    f"{self._minimum_fill_ratio:.4f}"
                )
        else:
            notes.append("fill ratio could not be verified without both contract specifications")
        capital_verified = margin_a.is_known and margin_b.is_known
        if not capital_verified:
            notes.append(
                "margin requirement is unknown; capital adequacy is unverified and must not "
                "be read as free margin"
            )
        if self._leverage is None and not (
            margin_a.source is MarginSource.BROKER_REPORTED
            and margin_b.source is MarginSource.BROKER_REPORTED
        ):
            notes.append("account leverage is not configured and the broker does not report margin")
        return ExecutionAssessment(
            executable=not blocking,
            capital_verified=capital_verified,
            reasons=tuple(blocking + notes),
            blocking_reasons=tuple(blocking),
            margin_a=margin_a,
            margin_b=margin_b,
            total_margin=total_margin,
            fill_a=fill_a,
            fill_b=fill_b,
            binding_fill_ratio=binding,
        )
