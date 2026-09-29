from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from math import isclose, isfinite
from typing import Any

# Relative tolerance within which the two legs' valuations of the same position
# are considered consistent. Broker specifications are reported at finite
# precision, so exact equality is not a reasonable expectation.
LEG_AGREEMENT_TOLERANCE = 0.05

# Relative tolerance within which two specifications are taken to value one
# unit of the underlying identically. This compares two numbers that describe
# the *same instrument*, not two valuations of a market outcome, so it is
# deliberately tighter than the leg-agreement tolerance: a broker rounding a
# published field is tolerated, a broker describing a different scale is not.
VALUE_PER_UNIT_TOLERANCE = 0.01

_TRADE_MODE_ISSUE = "trade modes are not fully available"


class ContractCompatibilityStatus(StrEnum):
    UNVERIFIED = "unverified"
    COMPATIBLE = "compatible"
    NORMALIZATION_REQUIRED = "normalization_required"
    INCOMPATIBLE = "incompatible"
    REVIEW_REQUIRED = "review_required"


@dataclass(frozen=True, slots=True)
class ContractSpecification:
    broker: str
    server: str
    symbol: str
    description: str
    path: str
    currency_base: str
    currency_profit: str
    digits: int
    point: float
    spread: int | None
    trade_mode: int | None
    contract_size: float
    volume_min: float
    volume_max: float
    volume_step: float
    tick_size: float
    tick_value: float
    margin_initial: float

    def __post_init__(self) -> None:
        numeric = (
            self.point,
            self.contract_size,
            self.volume_min,
            self.volume_max,
            self.volume_step,
            self.tick_size,
            self.tick_value,
            self.margin_initial,
        )
        if not all(isfinite(value) and value >= 0 for value in numeric):
            raise ValueError("contract specification values must be finite and non-negative")
        if (
            self.digits < 0
            or self.point <= 0
            or self.contract_size <= 0
            or self.volume_step <= 0
            or self.volume_min <= 0
            or self.tick_size <= 0
            or self.tick_value <= 0
        ):
            raise ValueError(
                "digits, point, contract size, volume bounds, tick size, and tick value "
                "must be positive"
            )
        if self.volume_max < self.volume_min:
            raise ValueError("volume maximum cannot be below volume minimum")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ContractSpecification:
        return cls(**value)


@dataclass(frozen=True, slots=True)
class ContractCompatibilityReport:
    status: ContractCompatibilityStatus
    issues: tuple[str, ...]
    contract_size_ratio: float | None
    tick_value_ratio: float | None


@dataclass(frozen=True, slots=True)
class NormalizedContractEdge:
    broker_a_volume: float
    broker_b_volume: float
    net_edge: float
    net_pnl: float
    broker_a_pnl: float
    broker_b_pnl: float
    legs_agree: bool

    @property
    def leg_disagreement_ratio(self) -> float:
        """Relative gap between the two independent valuations of one position.

        Both legs describe the *same* realized profit, so a large gap means the
        two contract specifications are mutually inconsistent rather than that
        the profit is uncertain.
        """
        scale = max(abs(self.broker_a_pnl), abs(self.broker_b_pnl))
        if scale == 0.0:
            return 0.0
        return abs(self.broker_a_pnl - self.broker_b_pnl) / scale


class ContractEdgeNormalizer:
    def normalize(
        self,
        net_edge: float,
        specification_a: ContractSpecification,
        specification_b: ContractSpecification,
        broker_a_volume: float = 1.0,
    ) -> NormalizedContractEdge:
        if broker_a_volume <= 0:
            raise ValueError("broker_a_volume must be positive")
        if specification_a.currency_profit.upper() != specification_b.currency_profit.upper():
            raise ValueError("PnL normalization requires matching profit currencies")
        broker_b_volume = (
            broker_a_volume * specification_a.contract_size / specification_b.contract_size
        )
        # A cross-broker position realizes the price difference *once*: buy one
        # leg, sell the other, and the whole spread is the profit. The two legs
        # are therefore two independent valuations of the same money, not two
        # amounts to add. Summing them would roughly double a symmetric
        # opportunity and mis-weight an asymmetric one.
        broker_a_pnl = (
            net_edge * broker_a_volume * specification_a.tick_value / specification_a.tick_size
        )
        broker_b_pnl = (
            net_edge * broker_b_volume * specification_b.tick_value / specification_b.tick_size
        )
        edge = NormalizedContractEdge(
            broker_a_volume=broker_a_volume,
            broker_b_volume=broker_b_volume,
            net_edge=net_edge,
            net_pnl=broker_a_pnl,
            broker_a_pnl=broker_a_pnl,
            broker_b_pnl=broker_b_pnl,
            legs_agree=False,
        )
        return replace(edge, legs_agree=edge.leg_disagreement_ratio <= LEG_AGREEMENT_TOLERANCE)


class ContractSpecificationAnalyzer:
    def compare(
        self,
        specification_a: ContractSpecification | None,
        specification_b: ContractSpecification | None,
    ) -> ContractCompatibilityReport:
        if specification_a is None and specification_b is None:
            return ContractCompatibilityReport(
                ContractCompatibilityStatus.UNVERIFIED,
                ("contract specifications were not provided",),
                None,
                None,
            )
        if specification_a is None or specification_b is None:
            return ContractCompatibilityReport(
                ContractCompatibilityStatus.REVIEW_REQUIRED,
                ("both broker contract specifications are required",),
                None,
                None,
            )
        issues: list[str] = []
        if specification_a.currency_base.upper() != specification_b.currency_base.upper():
            issues.append("base currencies differ")
        if specification_a.currency_profit.upper() != specification_b.currency_profit.upper():
            issues.append("profit currencies differ")
        if not self._same(specification_a.point, specification_b.point):
            issues.append("point sizes differ")
        if not self._same(specification_a.tick_size, specification_b.tick_size):
            issues.append("tick sizes differ")
        if not self._digits_match_point(specification_a) or not self._digits_match_point(
            specification_b
        ):
            issues.append("digits and point size are inconsistent")
        if not self._same(specification_a.volume_min, specification_b.volume_min):
            issues.append("minimum volumes differ")
        if not self._same(specification_a.volume_max, specification_b.volume_max):
            issues.append("maximum volumes differ")
        if not self._same(specification_a.volume_step, specification_b.volume_step):
            issues.append("volume steps differ")
        if specification_a.trade_mode is None or specification_b.trade_mode is None:
            issues.append(_TRADE_MODE_ISSUE)
        elif specification_a.trade_mode != specification_b.trade_mode:
            issues.append("trade modes differ")
        size_ratio = self._ratio(specification_b.contract_size, specification_a.contract_size)
        tick_ratio = self._ratio(specification_b.tick_value, specification_a.tick_value)
        hard_issues = [issue for issue in issues if issue != _TRADE_MODE_ISSUE]
        if hard_issues:
            return ContractCompatibilityReport(
                ContractCompatibilityStatus.INCOMPATIBLE,
                tuple(hard_issues),
                size_ratio,
                tick_ratio,
            )
        if issues:
            return ContractCompatibilityReport(
                ContractCompatibilityStatus.REVIEW_REQUIRED,
                tuple(issues),
                size_ratio,
                tick_ratio,
            )
        # A broker that halves its contract size must also halve its tick value,
        # because both scale the same quantity: the money value of one unit of
        # the underlying. When only one of them moves, the two specifications
        # do not describe the same instrument at any volume, and no normalization
        # can reconcile them — a volume that balances the notional leaves the two
        # legs valuing it differently, which is the inconsistency the legs-agree
        # check reports further downstream as a disagreeing pair.
        if not self._values_the_same_instrument(specification_a, specification_b):
            return ContractCompatibilityReport(
                ContractCompatibilityStatus.INCOMPATIBLE,
                (
                    "contract size and tick value do not scale together; the two "
                    "specifications do not value the same instrument",
                ),
                size_ratio,
                tick_ratio,
            )
        if not self._same(specification_a.contract_size, specification_b.contract_size):
            return ContractCompatibilityReport(
                ContractCompatibilityStatus.NORMALIZATION_REQUIRED,
                ("contract sizes differ; volume or PnL normalization is required",),
                size_ratio,
                tick_ratio,
            )
        if not self._same(specification_a.tick_value, specification_b.tick_value):
            return ContractCompatibilityReport(
                ContractCompatibilityStatus.NORMALIZATION_REQUIRED,
                ("tick values differ; PnL normalization is required",),
                size_ratio,
                tick_ratio,
            )
        return ContractCompatibilityReport(
            ContractCompatibilityStatus.COMPATIBLE,
            (),
            size_ratio,
            tick_ratio,
        )

    @staticmethod
    def _value_per_unit(specification: ContractSpecification) -> float:
        """Money value of one unit of the underlying per unit of price.

        One lot covers ``contract_size`` units of the base currency and a price
        move of ``tick_size`` is worth ``tick_value``, so the two describe the
        same economic quantity and a broker quoting the same instrument at a
        different lot size must scale both together.
        """
        return specification.tick_value / (specification.tick_size * specification.contract_size)

    @classmethod
    def _values_the_same_instrument(
        cls, specification_a: ContractSpecification, specification_b: ContractSpecification
    ) -> bool:
        return isclose(
            cls._value_per_unit(specification_a),
            cls._value_per_unit(specification_b),
            rel_tol=VALUE_PER_UNIT_TOLERANCE,
            abs_tol=0.0,
        )

    @staticmethod
    def _same(left: float, right: float) -> bool:
        return isclose(left, right, rel_tol=1e-9, abs_tol=1e-12)

    @staticmethod
    def _digits_match_point(specification: ContractSpecification) -> bool:
        expected = 10.0 ** (-specification.digits)
        return isclose(expected, specification.point, rel_tol=1e-6, abs_tol=1e-12)

    @staticmethod
    def _ratio(numerator: float, denominator: float) -> float | None:
        return numerator / denominator if denominator else None
