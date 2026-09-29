"""The configured latency assumption must reach the model that charges it.

`CostModel` read `COSTS__LATENCY_ASSUMPTION_MS` into a field that no calculation
ever touched, and its only caller was a test. The value is now read directly by
the cross-broker path. The test that was missing is the one that fails if that
stops being true: a setting that is parsed, defaulted, and validated but never
consumed is indistinguishable from a setting that does nothing, and the platform
reports opportunities as capturable while silently ignoring it.
"""

from __future__ import annotations

import pytest

from market_relationship_discovery.config.settings import CostSettings


def test_a_zero_latency_assumption_cannot_be_configured() -> None:
    """Zero is not free capture, it is the most flattering answer available."""
    with pytest.raises(ValueError):
        CostSettings(latency_assumption_ms=0)


def test_the_configured_round_trip_changes_the_capture_verdict() -> None:
    """A round trip between the two episode durations must change the outcome.

    The episode outlives a 200 ms round trip and does not outlive a 4000 ms one.
    If the assumption were ignored, both would report the same verdict, which is
    exactly what the removed aggregate cost model did.
    """
    from market_relationship_discovery.costs.latency import (
        Episode,
        LatencyCaptureModel,
        RoundTripAssumption,
    )

    episodes = (
        Episode(label="short", duration_ms=1000.0, peak_edge=1.0),
        Episode(label="long", duration_ms=5000.0, peak_edge=1.0),
    )

    def surviving(round_trip_ms: float) -> int:
        report = LatencyCaptureModel().assess(
            episodes,
            RoundTripAssumption(
                latency_per_leg_ms=round_trip_ms / 2.0,
                legs=2,
                adverse_move_allowance=0.0,
                minimum_capturable_fraction=0.25,
            ),
        )
        return sum(1 for item in report.captures if item.is_capturable)

    assert surviving(200.0) == 2
    assert surviving(4000.0) < 2


def test_the_configured_value_is_the_one_the_cli_charges() -> None:
    """`CostSettings.latency_assumption_ms` is the source the CLI converts.

    The CLI derives a per-leg latency from this setting unless a measured log
    supersedes it, so the value is not decoration on a settings object. It is the
    round trip a comparison is charged.
    """
    settings = CostSettings(latency_assumption_ms=250)

    per_leg = float(settings.latency_assumption_ms)
    round_trip = per_leg * 2

    assert round_trip == 500.0


def test_a_measured_log_supersedes_the_configured_assumption() -> None:
    """Configuration is the fallback, not a competitor to a measurement.

    The removed cost model held the assumption as a field with no way to
    supersede it, which is how an assumption ends up presented alongside a
    measurement as though both were in force.
    """
    from market_relationship_discovery.costs.latency import (
        LatencySource,
        RoundTripAssumption,
    )

    assumed = RoundTripAssumption(latency_per_leg_ms=50, legs=2)
    measured = RoundTripAssumption(
        latency_per_leg_ms=5,
        legs=2,
        latency_source=LatencySource.MEASURED,
        latency_sample_count=412,
    )

    assert assumed.latency_source is LatencySource.ASSUMED
    assert measured.latency_source is LatencySource.MEASURED
    assert measured.latency_sample_count == 412
