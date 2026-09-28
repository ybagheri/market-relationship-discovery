"""Tests for latency-aware opportunity capture.

The motivating gap was that opportunity duration was measured and reported but
never compared to the time an order actually takes. On real cross-broker data
most episodes lasted zero milliseconds, which an episode count alone presents as
a healthy number of opportunities.
"""

from __future__ import annotations

import pytest

from market_relationship_discovery.costs.latency import (
    CaptureStatus,
    Episode,
    LatencyCaptureModel,
    RoundTripAssumption,
)
from market_relationship_discovery.domain.errors import InsufficientDataError


def episode(label: str, duration_ms: float, peak_edge: float = 1.0) -> Episode:
    return Episode(label=label, duration_ms=duration_ms, peak_edge=peak_edge)


def test_captured_edge_is_the_mean_over_the_remaining_window() -> None:
    """The expected edge is the average over the window, not its first instant.

    Once both legs are open at the round trip, the position is held until the
    edge closes, so the expected capture is the mean of the decaying edge across
    that window. Returning the value at the moment the round trip completes
    reports the best case available in the window and, under linear decay, is
    exactly double the mean.
    """
    report = LatencyCaptureModel().assess(
        [episode("EP000", 1000.0, peak_edge=1.0)],
        RoundTripAssumption(latency_per_leg_ms=50, legs=2),
    )

    capture = report.captures[0]
    # Linear decay from 1.0 at the start to zero at 1000 ms, averaged over the
    # 900 ms the position is actually held.
    assert capture.captured_edge == pytest.approx(0.45)
    assert capture.captured_edge < capture.peak_edge * capture.capturable_fraction


def test_a_peak_late_in_the_episode_is_not_treated_as_occurring_at_the_start() -> None:
    """The peak's position in the episode must enter the model.

    The producer takes the maximum over the whole episode, which can occur at any
    point. The previous formula multiplied the peak by the surviving share of the
    episode's life, which credits the position with an edge as large as the peak
    for the entire window regardless of when the peak arrived. Here that
    optimistic figure is 0.9, and the profile that has to reach the peak and can
    only decay afterwards averages 0.549.
    """
    report = LatencyCaptureModel().assess(
        [Episode(label="EP000", duration_ms=1000.0, peak_edge=1.0, peak_offset_ms=900.0)],
        RoundTripAssumption(latency_per_leg_ms=50, legs=2),
    )

    capture = report.captures[0]
    # Rising from zero at the start to the peak at 900 ms, then decaying to zero
    # by 1000 ms, averaged over the 900 ms the position is held.
    assert capture.captured_edge == pytest.approx(0.549382, abs=1e-6)
    assert capture.captured_edge < capture.peak_edge * capture.capturable_fraction


def test_peak_offset_is_reported_with_the_capture() -> None:
    report = LatencyCaptureModel().assess(
        [Episode(label="EP000", duration_ms=1000.0, peak_edge=0.4, peak_offset_ms=250.0)],
        RoundTripAssumption(latency_per_leg_ms=50, legs=2),
    )

    payload = report.captures[0].to_dict()

    assert payload["peak_offset_ms"] == pytest.approx(250.0)


def test_peak_offset_outside_the_episode_is_refused() -> None:
    with pytest.raises(ValueError, match="peak_offset_ms"):
        Episode(label="EP", duration_ms=100.0, peak_edge=1.0, peak_offset_ms=-1.0)
    with pytest.raises(ValueError, match="peak_offset_ms"):
        Episode(label="EP", duration_ms=100.0, peak_edge=1.0, peak_offset_ms=101.0)


def test_the_window_verdict_is_unchanged_by_the_edge_profile() -> None:
    """``capturable_fraction`` describes the window, not the edge.

    The verdict has always been a share of the episode's life during which the
    position can be open. Correcting the edge figure must not quietly turn a
    duration question into a magnitude question.
    """
    report = LatencyCaptureModel().assess(
        [Episode(label="EP000", duration_ms=6000.0, peak_edge=0.21, peak_offset_ms=4000.0)],
        RoundTripAssumption(latency_per_leg_ms=50, legs=2, minimum_capturable_fraction=0.25),
    )

    capture = report.captures[0]
    assert capture.capturable_fraction == pytest.approx((6000.0 - 100.0) / 6000.0)
    assert capture.status is CaptureStatus.CAPTURABLE


def test_round_trip_multiplies_latency_by_legs() -> None:
    assert RoundTripAssumption(latency_per_leg_ms=50, legs=2).round_trip_ms == 100.0
    assert RoundTripAssumption(latency_per_leg_ms=20, legs=3).round_trip_ms == 60.0


def test_a_tiny_round_trip_still_captures_almost_everything() -> None:
    report = LatencyCaptureModel().assess(
        [episode("EP000", 10_000.0, peak_edge=0.5)],
        RoundTripAssumption(latency_per_leg_ms=1.0, legs=2),
    )

    assert report.captures[0].capturable_fraction == pytest.approx(0.9998)


def test_an_episode_shorter_than_the_round_trip_captures_nothing() -> None:
    """A crossable tick that lasted one instant cannot be traded."""
    report = LatencyCaptureModel().assess(
        [episode("EP000", 0.0, peak_edge=0.21)],
        RoundTripAssumption(latency_per_leg_ms=50, legs=2),
    )

    capture = report.captures[0]
    assert capture.capturable_fraction == 0.0
    assert capture.captured_edge == 0.0
    assert capture.status is CaptureStatus.NOT_CAPTURABLE
    assert report.survives is False


def test_a_long_episode_retains_most_of_its_edge() -> None:
    report = LatencyCaptureModel().assess(
        [episode("EP000", 6000.0, peak_edge=0.21)],
        RoundTripAssumption(latency_per_leg_ms=50, legs=2),
    )

    capture = report.captures[0]
    assert capture.capturable_fraction == pytest.approx((6000.0 - 100.0) / 6000.0)
    assert capture.status is CaptureStatus.CAPTURABLE
    assert report.survives is True


def test_a_zero_latency_assumption_is_refused() -> None:
    """A zero round trip would report every episode as fully capturable.

    An absent latency assumption is unknown, not free, the same way a
    broker-reported margin of zero is unknown rather than free margin.
    """
    with pytest.raises(ValueError, match="must be positive"):
        RoundTripAssumption(latency_per_leg_ms=0.0)

    with pytest.raises(ValueError, match="must be positive"):
        RoundTripAssumption(latency_per_leg_ms=-5.0)


def test_a_partially_surviving_episode_is_marked_marginal() -> None:
    """A window that only just outlasts the round trip leaves little behind."""
    report = LatencyCaptureModel().assess(
        [episode("EP000", 130.0, peak_edge=1.0)],
        RoundTripAssumption(latency_per_leg_ms=50, legs=2, minimum_capturable_fraction=0.25),
    )

    capture = report.captures[0]
    assert capture.capturable_fraction == pytest.approx(30.0 / 130.0)
    assert capture.status is CaptureStatus.MARGINAL
    assert capture.is_capturable is False
    assert report.capturable == 0
    assert report.marginal == 1


def test_an_adverse_move_allowance_can_erase_a_captured_edge() -> None:
    report = LatencyCaptureModel().assess(
        [episode("EP000", 1000.0, peak_edge=0.2)],
        RoundTripAssumption(
            latency_per_leg_ms=50,
            legs=2,
            adverse_move_allowance=0.5,
        ),
    )

    capture = report.captures[0]
    assert capture.captured_edge > 0
    assert capture.net_captured_edge < 0
    assert capture.status is CaptureStatus.NOT_CAPTURABLE


def test_latency_can_reduce_a_healthy_opportunity_count_to_nothing() -> None:
    """The real finding: many episodes are shorter than one round trip."""
    model = LatencyCaptureModel()
    episodes = [episode(f"EP{index:03d}", 0.0, peak_edge=0.05) for index in range(14)]
    episodes.append(episode("EP014", 6000.0, peak_edge=0.05))
    episodes.append(episode("EP015", 6000.0, peak_edge=0.05))

    realistic = model.assess(episodes, RoundTripAssumption(latency_per_leg_ms=50, legs=2))
    impossible = model.assess(episodes, RoundTripAssumption(latency_per_leg_ms=3000, legs=2))

    assert realistic.episodes == 16
    assert realistic.capturable == 2
    assert realistic.not_capturable == 14
    assert realistic.survives is True

    assert impossible.capturable == 0
    assert impossible.not_capturable == 16
    assert impossible.survives is False
    assert impossible.mean_captured_edge == 0.0


def test_report_summarises_durations_and_edges() -> None:
    """The median of an even-sized sample is the upper of the two middles."""
    report = LatencyCaptureModel().assess(
        [
            episode("SHORT", 0.0, peak_edge=0.1),
            episode("LONG", 4000.0, peak_edge=0.3),
        ],
        RoundTripAssumption(latency_per_leg_ms=50, legs=2),
    )

    assert report.episodes == 2
    assert report.round_trip_ms == 100.0
    assert report.median_duration_ms == 4000.0
    assert report.maximum_duration_ms == 4000.0
    assert report.mean_peak_edge == pytest.approx(0.2)
    assert report.capturable_fraction == pytest.approx(0.5)


def test_report_is_serializable() -> None:
    report = LatencyCaptureModel().assess(
        [episode("EP000", 1000.0, peak_edge=0.2)],
        RoundTripAssumption(latency_per_leg_ms=50, legs=2, adverse_move_allowance=0.01),
    )

    payload = report.to_dict()

    assert payload["episodes"] == 1
    assert payload["survives"] is True
    assert payload["assumptions"]["round_trip_ms"] == 100.0
    assert payload["assumptions"]["adverse_move_allowance"] == 0.01
    assert len(payload["captures"]) == 1


def test_episodes_can_be_built_from_parallel_sequences() -> None:
    model = LatencyCaptureModel()

    episodes = model.episodes_from_durations([0.0, 6000.0], [0.05, 0.2])

    assert [item.label for item in episodes] == ["EP000", "EP001"]
    assert episodes[0].duration_ms == 0.0


def test_mismatched_sequences_are_rejected() -> None:
    with pytest.raises(ValueError, match="same length"):
        LatencyCaptureModel().episodes_from_durations([1.0], [0.1, 0.2])


def test_no_episodes_is_reported_clearly() -> None:
    with pytest.raises(InsufficientDataError, match="at least one measured"):
        LatencyCaptureModel().assess([], RoundTripAssumption())


def test_episodes_are_validated() -> None:
    with pytest.raises(ValueError, match="duration_ms"):
        Episode(label="EP", duration_ms=-1.0, peak_edge=1.0)
    with pytest.raises(ValueError, match="peak_edge"):
        Episode(label="EP", duration_ms=1.0, peak_edge=0.0)


def test_assumptions_are_validated() -> None:
    with pytest.raises(ValueError, match="at least one leg"):
        RoundTripAssumption(legs=0)
    with pytest.raises(ValueError, match="adverse_move_allowance"):
        RoundTripAssumption(adverse_move_allowance=-0.1)
    with pytest.raises(ValueError, match="minimum_capturable_fraction"):
        RoundTripAssumption(minimum_capturable_fraction=1.5)
