from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from math import isclose, isfinite
from typing import Any


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
        broker_a_pnl = (
            net_edge * broker_a_volume * specification_a.tick_value / specification_a.tick_size
        )
        broker_b_pnl = (
            net_edge * broker_b_volume * specification_b.tick_value / specification_b.tick_size
        )
        return NormalizedContractEdge(
            broker_a_volume=broker_a_volume,
            broker_b_volume=broker_b_volume,
            net_edge=net_edge,
            net_pnl=broker_a_pnl + broker_b_pnl,
            broker_a_pnl=broker_a_pnl,
            broker_b_pnl=broker_b_pnl,
        )


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
            issues.append("trade modes are not fully available")
        elif specification_a.trade_mode != specification_b.trade_mode:
            issues.append("trade modes differ")
        size_ratio = self._ratio(specification_b.contract_size, specification_a.contract_size)
        tick_ratio = self._ratio(specification_b.tick_value, specification_a.tick_value)
        hard_issues = [issue for issue in issues if issue != "trade modes are not fully available"]
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
    def _same(left: float, right: float) -> bool:
        return isclose(left, right, rel_tol=1e-9, abs_tol=1e-12)

    @staticmethod
    def _digits_match_point(specification: ContractSpecification) -> bool:
        expected = 10.0 ** (-specification.digits)
        return isclose(expected, specification.point, rel_tol=1e-6, abs_tol=1e-12)

    @staticmethod
    def _ratio(numerator: float, denominator: float) -> float | None:
        return numerator / denominator if denominator else None
