"""Sensitivity of a capture verdict to the assumptions behind it.

The latency capture verdict is a function of assumed inputs: a round-trip time
and an adverse-move allowance. Reporting a single verdict invites the reader to
treat it as a measurement, when it is the output of a model at one point in a
parameter space.

Real runs show how much that matters. On one cross-broker gold comparison, 2 of
16 measured episodes were capturable at a 100 ms round trip and 0 of 16 at
6000 ms, from identical data. A verdict that flips across a plausible parameter
range is not a finding about the market; it is a statement about the assumption.

This module sweeps the assumed inputs over a grid and reports how far the
conclusion travels from the configured baseline.

## What this is not

It is not an optimiser. The sweep never selects a favourable parameter and never
reports a best case as a headline. The baseline is the configured assumption, and
the interesting output is the distance from that baseline to the point where the
verdict fails. A result that only holds at one setting is reported as fragile,
not as successful.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from itertools import pairwise

from market_relationship_discovery.costs.latency import (
    Episode,
    LatencyCaptureModel,
    LatencyCaptureReport,
    RoundTripAssumption,
)
from market_relationship_discovery.domain.errors import InsufficientDataError

DEFAULT_LATENCY_GRID_MS: tuple[float, ...] = (
    1.0,
    5.0,
    10.0,
    25.0,
    50.0,
    100.0,
    250.0,
    500.0,
    1000.0,
    2500.0,
    5000.0,
    10000.0,
)

# A verdict is treated as immaterial when the baseline captures less than a
# quarter of the measured episodes, or less than a fifth of the peak edge. Below
# those levels the binary question "is anything capturable" stops carrying
# information, and answering it yes would overstate the result.
MATERIAL_CAPTURABLE_FRACTION = 0.25
MATERIAL_CAPTURED_SHARE = 0.20


class SensitivityAxis(StrEnum):
    """Which assumed input is being varied."""

    LATENCY_PER_LEG_MS = "latency_per_leg_ms"
    ADVERSE_MOVE_ALLOWANCE = "adverse_move_allowance"


class Fragility(StrEnum):
    """How dependent the verdict is on the exact assumption chosen.

    ``NOMINAL`` is separated from ``STABLE`` deliberately. A verdict can survive
    every point on the grid while capturing almost nothing: on one observed gold
    run two of sixteen episodes were capturable and 14.6 percent of the peak
    edge survived, falling to 0.6 percent at a slower round trip. That is
    arithmetic stability, not a finding, and reporting it as stable would be
    more misleading than reporting nothing.
    """

    STABLE = "stable"
    SENSITIVE = "sensitive"
    KNIFE_EDGE = "knife_edge"
    ALWAYS_FAILS = "always_fails"
    ALWAYS_HOLDS = "always_holds"
    NOMINAL = "nominal"


@dataclass(frozen=True, slots=True)
class SweepPoint:
    """The verdict at one point in the swept parameter space."""

    value: float
    round_trip_ms: float
    capturable: int
    marginal: int
    not_capturable: int
    mean_captured_edge: float
    captured_share_of_peak: float
    survives: bool
    is_baseline: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "value": self.value,
            "round_trip_ms": self.round_trip_ms,
            "capturable": self.capturable,
            "marginal": self.marginal,
            "not_capturable": self.not_capturable,
            "mean_captured_edge": self.mean_captured_edge,
            "captured_share_of_peak": self.captured_share_of_peak,
            "survives": self.survives,
            "is_baseline": self.is_baseline,
        }


@dataclass(frozen=True, slots=True)
class SensitivityReport:
    """How far a capture verdict travels across a swept assumption."""

    axis: SensitivityAxis
    baseline_value: float
    points: tuple[SweepPoint, ...]
    fragility: Fragility
    highest_surviving_value: float | None
    lowest_failing_value: float | None
    baseline_survives: bool
    episodes: int
    baseline_capturable_fraction: float = 0.0
    baseline_captured_share: float = 0.0

    @property
    def is_fragile(self) -> bool:
        return self.fragility in {
            Fragility.SENSITIVE,
            Fragility.KNIFE_EDGE,
            Fragility.NOMINAL,
            Fragility.ALWAYS_FAILS,
        }

    @property
    def is_material(self) -> bool:
        """Whether the baseline captures enough of the opportunity to matter.

        Separate from :attr:`is_fragile` because a verdict can be perfectly stable
        and still capture a negligible share of the edge.
        """
        return (
            self.baseline_survives
            and self.fragility is not Fragility.NOMINAL
            and self.baseline_capturable_fraction > 0.0
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "axis": self.axis.value,
            "baseline_value": self.baseline_value,
            "baseline_survives": self.baseline_survives,
            "baseline_capturable_fraction": self.baseline_capturable_fraction,
            "baseline_captured_share": self.baseline_captured_share,
            "fragility": self.fragility.value,
            "is_fragile": self.is_fragile,
            "is_material": self.is_material,
            "highest_surviving_value": self.highest_surviving_value,
            "lowest_failing_value": self.lowest_failing_value,
            "episodes": self.episodes,
            "points": [point.to_dict() for point in self.points],
        }


class LatencySensitivityAnalyzer:
    """Re-run the capture model across a grid of assumed inputs.

    The capture calculation is never reimplemented here. Each grid point is one
    call into the existing :class:`LatencyCaptureModel`, so a sweep and a single
    assessment cannot disagree.
    """

    def __init__(self, model: LatencyCaptureModel | None = None) -> None:
        self._model = model or LatencyCaptureModel()

    def sweep(
        self,
        episodes: Sequence[Episode],
        baseline: RoundTripAssumption,
        grid: Sequence[float] = DEFAULT_LATENCY_GRID_MS,
    ) -> SensitivityReport:
        """Vary the round-trip latency and report how far the verdict travels.

        The grid is expressed as latency **per leg**, matching the configured
        assumption, so a reader can compare it directly with
        ``COSTS__LATENCY_ASSUMPTION_MS``.
        """
        if not episodes:
            raise InsufficientDataError(
                "sensitivity sweep requires at least one measured opportunity episode"
            )
        values = self._validated_grid(grid)
        points: list[SweepPoint] = []
        for value in values:
            assumption = RoundTripAssumption(
                latency_per_leg_ms=value,
                legs=baseline.legs,
                adverse_move_allowance=baseline.adverse_move_allowance,
                minimum_capturable_fraction=baseline.minimum_capturable_fraction,
            )
            report = self._model.assess(episodes, assumption)
            points.append(self._point(report, value, baseline))
        return self._report(SensitivityAxis.LATENCY_PER_LEG_MS, baseline.latency_per_leg_ms, points)

    def sweep_adverse_move(
        self,
        episodes: Sequence[Episode],
        baseline: RoundTripAssumption,
        allowances: Sequence[float],
    ) -> SensitivityReport:
        """Vary the adverse-move allowance against a fixed round trip."""
        if not episodes:
            raise InsufficientDataError(
                "sensitivity sweep requires at least one measured opportunity episode"
            )
        values = self._validated_grid(allowances, positive=False)
        points: list[SweepPoint] = []
        for value in values:
            assumption = RoundTripAssumption(
                latency_per_leg_ms=baseline.latency_per_leg_ms,
                legs=baseline.legs,
                adverse_move_allowance=value,
                minimum_capturable_fraction=baseline.minimum_capturable_fraction,
            )
            report = self._model.assess(episodes, assumption)
            points.append(self._point(report, value, baseline))
        return self._report(
            SensitivityAxis.ADVERSE_MOVE_ALLOWANCE,
            baseline.adverse_move_allowance,
            points,
        )

    def episodes_from_report(self, report: Mapping[str, object]) -> tuple[Episode, ...]:
        """Rebuild episodes from a persisted capture report.

        A saved comparison already records each episode's duration and peak edge,
        so a sweep needs no recollection and no re-alignment of the source data.
        """
        captures = report.get("captures")
        episodes: list[Episode] = []
        if isinstance(captures, list):
            for index, item in enumerate(captures):
                if not isinstance(item, dict):
                    continue
                duration = item.get("duration_ms")
                peak = item.get("peak_edge")
                if not isinstance(duration, (int, float)) or isinstance(duration, bool):
                    continue
                if not isinstance(peak, (int, float)) or isinstance(peak, bool):
                    continue
                if float(peak) <= 0:
                    continue
                episodes.append(
                    Episode(
                        label=str(item.get("label") or f"EP{index:03d}"),
                        duration_ms=float(duration),
                        peak_edge=float(peak),
                    )
                )
        return tuple(episodes)

    @staticmethod
    def _point(
        report: LatencyCaptureReport,
        value: float,
        baseline: RoundTripAssumption,
    ) -> SweepPoint:
        share = report.mean_captured_edge / report.mean_peak_edge if report.mean_peak_edge else 0.0
        return SweepPoint(
            value=value,
            round_trip_ms=report.round_trip_ms,
            capturable=report.capturable,
            marginal=report.marginal,
            not_capturable=report.not_capturable,
            mean_captured_edge=report.mean_captured_edge,
            captured_share_of_peak=share,
            survives=report.survives,
            is_baseline=value == baseline.latency_per_leg_ms,
        )

    @staticmethod
    def _report(
        axis: SensitivityAxis,
        baseline_value: float,
        points: list[SweepPoint],
    ) -> SensitivityReport:
        surviving = [point.value for point in points if point.survives]
        failing = [point.value for point in points if not point.survives]
        baseline_survives = any(point.is_baseline and point.survives for point in points)
        baseline = next((point for point in points if point.is_baseline), None)
        episodes = (
            points[0].capturable + points[0].marginal + points[0].not_capturable if points else 0
        )
        capturable_fraction = (
            baseline.capturable / episodes if baseline is not None and episodes else 0.0
        )
        captured_share = baseline.captured_share_of_peak if baseline is not None else 0.0
        fragility = _fragility(
            points,
            surviving,
            failing,
            axis,
            baseline_value,
            capturable_fraction,
            captured_share,
        )
        return SensitivityReport(
            axis=axis,
            baseline_value=baseline_value,
            points=tuple(points),
            fragility=fragility,
            highest_surviving_value=max(surviving) if surviving else None,
            lowest_failing_value=min(failing) if failing else None,
            baseline_survives=baseline_survives,
            episodes=episodes,
            baseline_capturable_fraction=capturable_fraction,
            baseline_captured_share=captured_share,
        )

    @staticmethod
    def _validated_grid(grid: Sequence[float], positive: bool = True) -> tuple[float, ...]:
        if not grid:
            raise ValueError("a sensitivity sweep needs at least one grid value")
        values: list[float] = []
        for value in grid:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("grid values must be numeric")
            number = float(value)
            if positive and number <= 0:
                raise ValueError("latency grid values must be positive")
            if number < 0:
                raise ValueError("grid values cannot be negative")
            values.append(number)
        return tuple(sorted(set(values)))


def _fragility(
    points: list[SweepPoint],
    surviving: list[float],
    failing: list[float],
    axis: SensitivityAxis,
    baseline_value: float,
    capturable_fraction: float,
    captured_share: float,
) -> Fragility:
    """Classify how much the verdict depends on the exact assumed value.

    Materiality is judged first. If the baseline captures a negligible share of
    the opportunities or of the edge, the verdict describes noise however
    consistently it repeats, and the label says so instead of reporting
    arithmetic stability as a result.
    """
    if not surviving:
        return Fragility.ALWAYS_FAILS
    if capturable_fraction < MATERIAL_CAPTURABLE_FRACTION:
        return Fragility.NOMINAL
    if captured_share < MATERIAL_CAPTURED_SHARE:
        return Fragility.NOMINAL
    if not failing:
        return Fragility.ALWAYS_HOLDS
    boundary = max(surviving)
    if axis is SensitivityAxis.LATENCY_PER_LEG_MS:
        # Latency degrades monotonically: a slower round trip can only remove
        # capturable episodes, never add them. A single surviving point on the
        # grid means the verdict only holds under a narrow optimistic setting.
        if boundary == min(surviving):
            return Fragility.KNIFE_EDGE
        step = _step(points)
        span = boundary - min(surviving)
        if step > 0 and span <= step:
            return Fragility.KNIFE_EDGE
        if boundary <= baseline_value:
            return Fragility.SENSITIVE
        return Fragility.STABLE
    if boundary == min(surviving) and min(failing) - boundary <= abs(boundary) * 0.25:
        return Fragility.KNIFE_EDGE
    return Fragility.SENSITIVE


def _step(points: list[SweepPoint]) -> float:
    values = sorted(point.value for point in points)
    if len(values) < 2:
        return 0.0
    return min(second - first for first, second in pairwise(values))
