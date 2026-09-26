"""Tests for capture-verdict sensitivity.

A verdict that flips across a plausible parameter range describes the assumption
rather than the market, so the sweep exists to measure that distance. The
classifier must also refuse to call an immaterial verdict robust, which is the
mistake a binary survives-check makes on its own.
"""

from __future__ import annotations

import pytest

from market_relationship_discovery.costs.latency import Episode, RoundTripAssumption
from market_relationship_discovery.costs.sensitivity import (
    Fragility,
    LatencySensitivityAnalyzer,
    SensitivityAxis,
    SweepPoint,
)
from market_relationship_discovery.domain.errors import InsufficientDataError

GRID = (1.0, 10.0, 50.0, 100.0, 500.0, 1000.0, 5000.0, 10000.0)


def episodes(durations: list[float], peak: float = 1.0) -> tuple[Episode, ...]:
    return tuple(
        Episode(label=f"EP{index:03d}", duration_ms=value, peak_edge=peak)
        for index, value in enumerate(durations)
    )


def test_a_long_lived_opportunity_survives_the_whole_grid() -> None:
    """Bitcoin-like episodes last over a minute, so latency barely matters."""
    report = LatencySensitivityAnalyzer().sweep(
        episodes([65_500.0, 67_000.0, 120_000.0, 356_000.0, 90_000.0] * 4, peak=8.95),
        RoundTripAssumption(latency_per_leg_ms=50.0, legs=2),
        GRID,
    )

    assert report.fragility is Fragility.ALWAYS_HOLDS
    assert report.is_fragile is False
    assert report.baseline_survives is True
    assert report.lowest_failing_value is None
    assert len(report.points) == len(GRID)


def test_a_verdict_that_only_survives_one_setting_is_a_knife_edge() -> None:
    """Episodes that barely outlast the round trip are the fragile case."""
    report = LatencySensitivityAnalyzer().sweep(
        episodes([200.0] * 8 + [150.0] * 2),
        RoundTripAssumption(latency_per_leg_ms=50.0, legs=2),
        GRID,
    )

    assert report.fragility in {Fragility.KNIFE_EDGE, Fragility.SENSITIVE}
    assert report.is_fragile is True


def test_a_surviving_but_immaterial_verdict_is_not_called_stable() -> None:
    """Two capturable episodes out of sixteen is not a finding.

    The binary survives check answers yes across the grid while the captured
    share of the edge is tiny. Reporting that as stable would be more misleading
    than reporting nothing.
    """
    report = LatencySensitivityAnalyzer().sweep(
        episodes([0.0] * 14 + [6000.0] * 2, peak=0.05),
        RoundTripAssumption(latency_per_leg_ms=50.0, legs=2),
        GRID,
    )

    assert report.baseline_survives is True
    assert report.fragility is Fragility.NOMINAL
    assert report.is_fragile is True
    assert report.is_material is False
    assert report.baseline_capturable_fraction == pytest.approx(0.125)
    assert report.baseline_captured_share < 0.20


def test_a_material_and_robust_verdict_is_reported_as_stable() -> None:
    report = LatencySensitivityAnalyzer().sweep(
        episodes([4000.0] * 8 + [0.0] * 2, peak=0.2),
        RoundTripAssumption(latency_per_leg_ms=50.0, legs=2),
        GRID,
    )

    assert report.fragility is Fragility.STABLE
    assert report.is_fragile is False
    assert report.is_material is True
    assert report.baseline_capturable_fraction == pytest.approx(0.8)


def test_a_verdict_that_never_survives_is_reported_as_always_failing() -> None:
    report = LatencySensitivityAnalyzer().sweep(
        episodes([0.0] * 10, peak=0.2),
        RoundTripAssumption(latency_per_leg_ms=50.0, legs=2),
        GRID,
    )

    assert report.fragility is Fragility.ALWAYS_FAILS
    assert report.is_fragile is True
    assert report.baseline_survives is False
    assert report.highest_surviving_value is None


def test_the_baseline_point_is_marked_and_locatable() -> None:
    report = LatencySensitivityAnalyzer().sweep(
        episodes([4000.0] * 8, peak=0.2),
        RoundTripAssumption(latency_per_leg_ms=100.0, legs=2),
        GRID,
    )

    baselines = [point for point in report.points if point.is_baseline]

    assert len(baselines) == 1
    assert baselines[0].value == 100.0
    assert baselines[0].round_trip_ms == 200.0
    assert report.baseline_value == 100.0


def test_latency_degrades_monotonically() -> None:
    """A slower round trip can only remove capturable episodes, never add them."""
    report = LatencySensitivityAnalyzer().sweep(
        episodes([500.0, 900.0, 2500.0, 8000.0] * 3, peak=0.2),
        RoundTripAssumption(latency_per_leg_ms=50.0, legs=2),
        GRID,
    )

    capturable = [point.capturable for point in report.points]
    captured = [point.mean_captured_edge for point in report.points]

    assert capturable == sorted(capturable, reverse=True)
    assert captured == sorted(captured, reverse=True)


def test_episodes_can_be_rebuilt_from_a_persisted_report() -> None:
    payload = {
        "captures": [
            {"label": "A", "duration_ms": 1000.0, "peak_edge": 0.2},
            {"label": "B", "duration_ms": 0.0, "peak_edge": 0.1},
            {"label": "C", "duration_ms": None, "peak_edge": 0.1},
            {"label": "D", "duration_ms": 500.0, "peak_edge": 0.0},
            "not a mapping",
        ]
    }

    rebuilt = LatencySensitivityAnalyzer().episodes_from_report(payload)

    assert [item.label for item in rebuilt] == ["A", "B"]
    assert rebuilt[0].duration_ms == 1000.0


def test_a_report_with_no_captures_yields_no_episodes() -> None:
    assert LatencySensitivityAnalyzer().episodes_from_report({}) == ()
    assert LatencySensitivityAnalyzer().episodes_from_report({"captures": []}) == ()


def test_the_adverse_move_sweep_reuses_the_same_model() -> None:
    report = LatencySensitivityAnalyzer().sweep_adverse_move(
        episodes([4000.0] * 8, peak=0.2),
        RoundTripAssumption(latency_per_leg_ms=50.0, legs=2, adverse_move_allowance=0.01),
        (0.0, 0.05, 0.1, 0.5),
    )

    assert report.axis is SensitivityAxis.ADVERSE_MOVE_ALLOWANCE
    assert report.baseline_value == 0.01
    net = [point.mean_captured_edge for point in report.points]
    assert net == sorted(net, reverse=True)


def test_report_is_serializable() -> None:
    report = LatencySensitivityAnalyzer().sweep(
        episodes([4000.0] * 8, peak=0.2),
        RoundTripAssumption(latency_per_leg_ms=50.0, legs=2),
        GRID,
    )

    payload = report.to_dict()

    assert payload["axis"] == "latency_per_leg_ms"
    assert payload["is_fragile"] is False
    assert payload["is_material"] is True
    assert len(payload["points"]) == len(GRID)
    assert "baseline_captured_share" in payload


def test_the_grid_is_validated() -> None:
    analyzer = LatencySensitivityAnalyzer()
    assumption = RoundTripAssumption(latency_per_leg_ms=50.0, legs=2)

    with pytest.raises(ValueError, match="at least one grid value"):
        analyzer.sweep(episodes([1000.0]), assumption, ())
    with pytest.raises(ValueError, match="must be positive"):
        analyzer.sweep(episodes([1000.0]), assumption, (10.0, 0.0))
    with pytest.raises(ValueError, match="must be numeric"):
        analyzer.sweep(episodes([1000.0]), assumption, (10.0, "fast"))


def test_sweeping_requires_episodes() -> None:
    analyzer = LatencySensitivityAnalyzer()
    assumption = RoundTripAssumption(latency_per_leg_ms=50.0, legs=2)

    with pytest.raises(InsufficientDataError, match="at least one measured"):
        analyzer.sweep((), assumption, GRID)
    with pytest.raises(InsufficientDataError, match="at least one measured"):
        analyzer.sweep_adverse_move((), assumption, (0.0,))


def test_a_single_point_grid_is_accepted() -> None:
    report = LatencySensitivityAnalyzer().sweep(
        episodes([4000.0] * 4, peak=0.2),
        RoundTripAssumption(latency_per_leg_ms=50.0, legs=2),
        (50.0,),
    )

    assert len(report.points) == 1
    assert report.fragility is Fragility.ALWAYS_HOLDS


def test_sweep_point_is_serializable() -> None:
    point = SweepPoint(
        value=50.0,
        round_trip_ms=100.0,
        capturable=2,
        marginal=1,
        not_capturable=13,
        mean_captured_edge=0.006,
        captured_share_of_peak=0.12,
        survives=True,
        is_baseline=True,
    )

    payload = point.to_dict()

    assert payload["value"] == 50.0
    assert payload["capturable"] == 2
    assert payload["is_baseline"] is True
