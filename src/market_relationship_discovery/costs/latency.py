"""Latency-aware opportunity capture modelling.

The cross-broker layer measures how long each opportunity episode lasted and
already reports the median and maximum duration. Nothing compared those durations
to the time an order actually takes, so an episode that closed after thirty
milliseconds was counted exactly like one that stayed open for a minute.

That comparison is the difference between a discrepancy and an opportunity. This
module asks a narrow question: given a round-trip assumption, how much of each
measured episode is still available when the position could be closed?

## What it models

- the time a round trip takes, across however many legs are involved,
- linear decay of the edge over the life of the episode,
- an explicit adverse-move allowance for the round trip.

## What it does not model

Queue position, order-book depth, partial-fill probability, exchange rejection,
and market impact. Those cannot be observed from research data, so a verdict of
``capturable`` means no *known* constraint rules the episode out. It is not a
prediction that a fill will occur.

Decay is modelled as linear because the alternative would be to assume a decay
shape and present the result as measured. Linear decay is the least
conspicuous assumption available and is stated rather than hidden.

The adverse-move allowance defaults to zero. It is a configured assumption, not
an estimate, and reporting it as a visible input keeps it from being mistaken for
a measured quantity.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from market_relationship_discovery.costs.measurement import LatencySource
from market_relationship_discovery.domain.errors import InsufficientDataError


class CaptureStatus(StrEnum):
    """Verdict for one measured opportunity episode."""

    CAPTURABLE = "capturable"
    MARGINAL = "marginal"
    NOT_CAPTURABLE = "not_capturable"


@dataclass(frozen=True, slots=True)
class Episode:
    """The measured properties of one opportunity episode.

    ``duration_ms`` and ``peak_edge`` come from the cross-broker analysis, so the
    model consumes measurement rather than inventing it.

    ``peak_offset_ms`` is where inside the episode the peak was observed. The
    maximum over an episode is not necessarily at its start: crediting the
    whole episode with an edge as large as the peak assumes the peak occurred
    first, and the model cannot use the peak as a starting value without knowing
    when it arrives.
    """

    label: str
    duration_ms: float
    peak_edge: float
    peak_offset_ms: float = 0.0

    def __post_init__(self) -> None:
        if self.duration_ms < 0:
            raise ValueError("duration_ms cannot be negative")
        if not self.peak_edge > 0:
            raise ValueError("peak_edge must be positive for a capturable episode")
        if not 0.0 <= self.peak_offset_ms <= self.duration_ms:
            raise ValueError("peak_offset_ms must fall inside the episode")


@dataclass(frozen=True, slots=True)
class RoundTripAssumption:
    """Time and adverse-move assumptions for completing both legs.

    Latency is deliberately required to be positive. A zero round trip reports
    every episode as fully capturable, which is the most flattering answer the
    model can produce, and it is the answer a forgotten configuration value
    silently yields. The same reasoning that treats a broker-reported margin of
    zero as *not reported* applies here: an absent latency assumption is unknown,
    not free.
    """

    latency_per_leg_ms: float = 50.0
    legs: int = 2
    adverse_move_allowance: float = 0.0
    minimum_capturable_fraction: float = 0.25
    latency_source: LatencySource = LatencySource.ASSUMED
    latency_sample_count: int = 0

    def __post_init__(self) -> None:
        if self.latency_per_leg_ms <= 0:
            raise ValueError(
                "latency_per_leg_ms must be positive; a zero round trip would report "
                "every episode as fully capturable"
            )
        if self.legs < 1:
            raise ValueError("a round trip needs at least one leg")
        if self.adverse_move_allowance < 0:
            raise ValueError("adverse_move_allowance cannot be negative")
        if not 0.0 <= self.minimum_capturable_fraction <= 1.0:
            raise ValueError("minimum_capturable_fraction must be between zero and one")

    @property
    def round_trip_ms(self) -> float:
        """Time to observe, act on both legs, and complete."""
        return self.latency_per_leg_ms * self.legs

    def to_dict(self) -> dict[str, object]:
        return {
            "latency_per_leg_ms": self.latency_per_leg_ms,
            "legs": self.legs,
            "round_trip_ms": self.round_trip_ms,
            "adverse_move_allowance": self.adverse_move_allowance,
            "minimum_capturable_fraction": self.minimum_capturable_fraction,
            "latency_source": self.latency_source.value,
            "latency_sample_count": self.latency_sample_count,
        }


@dataclass(frozen=True, slots=True)
class EpisodeCapture:
    """Capture estimate for a single episode."""

    label: str
    duration_ms: float
    peak_edge: float
    peak_offset_ms: float
    round_trip_ms: float
    capturable_fraction: float
    captured_edge: float
    net_captured_edge: float
    status: CaptureStatus

    @property
    def is_capturable(self) -> bool:
        """Whether this episode retained enough of its edge to be worth taking.

        Marginal episodes are not capturable: they survived the round trip but
        left too little behind to clear the configured fraction.
        """
        return self.status is CaptureStatus.CAPTURABLE

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "duration_ms": self.duration_ms,
            "peak_edge": self.peak_edge,
            "peak_offset_ms": self.peak_offset_ms,
            "round_trip_ms": self.round_trip_ms,
            "capturable_fraction": self.capturable_fraction,
            "captured_edge": self.captured_edge,
            "net_captured_edge": self.net_captured_edge,
            "status": self.status.value,
        }


@dataclass(frozen=True, slots=True)
class LatencyCaptureReport:
    """Aggregate capture estimate across every measured episode."""

    episodes: int
    capturable: int
    marginal: int
    not_capturable: int
    round_trip_ms: float
    median_duration_ms: float
    maximum_duration_ms: float
    mean_peak_edge: float
    mean_captured_edge: float
    mean_net_captured_edge: float
    assumptions: RoundTripAssumption
    captures: tuple[EpisodeCapture, ...]

    @property
    def capturable_fraction(self) -> float:
        return self.capturable / self.episodes if self.episodes else 0.0

    @property
    def survives(self) -> bool:
        """Whether any episode is capturable under the stated assumptions."""
        return self.capturable > 0

    def to_dict(self) -> dict[str, object]:
        return {
            "episodes": self.episodes,
            "capturable": self.capturable,
            "marginal": self.marginal,
            "not_capturable": self.not_capturable,
            "capturable_fraction": self.capturable_fraction,
            "round_trip_ms": self.round_trip_ms,
            "median_duration_ms": self.median_duration_ms,
            "maximum_duration_ms": self.maximum_duration_ms,
            "mean_peak_edge": self.mean_peak_edge,
            "mean_captured_edge": self.mean_captured_edge,
            "mean_net_captured_edge": self.mean_net_captured_edge,
            "survives": self.survives,
            "assumptions": self.assumptions.to_dict(),
            "captures": [item.to_dict() for item in self.captures],
        }


def _mean_edge_over_window(
    peak_edge: float,
    peak_offset_ms: float,
    duration_ms: float,
    round_trip_ms: float,
) -> float:
    """Mean edge across the window in which the position is held.

    The profile is a tent: zero at the start, ``peak_edge`` at
    ``peak_offset_ms``, zero at ``duration_ms``. The position is held from
    ``round_trip_ms`` to ``duration_ms``, so the mean is the integral over that
    window divided by its width.

    The two segments are integrated separately, because the peak offset can fall
    on either side of the round trip:

    * rising segment, ``peak * t / offset``, whose integral is
      ``peak * (b**2 - a**2) / (2 * offset)``,
    * decaying segment, ``peak * (duration - t) / (duration - offset)``, whose
      integral is ``peak * (duration * (b - a) - (b**2 - a**2) / 2) /
      (duration - offset)``.

    A peak at the very start reduces this to ``peak * (duration - round_trip) /
    (2 * duration)``, exactly half the value the edge holds when the round trip
    completes, which is the correction being made.
    """
    if duration_ms <= 0.0 or duration_ms <= round_trip_ms:
        return 0.0
    window = duration_ms - round_trip_ms
    offset = min(max(peak_offset_ms, 0.0), duration_ms)
    total = 0.0
    if offset > 0.0:
        upper = min(offset, duration_ms)
        if upper > round_trip_ms:
            total += peak_edge * (upper**2 - round_trip_ms**2) / (2.0 * offset)
    decay_width = duration_ms - offset
    if decay_width > 0.0:
        lower = max(round_trip_ms, offset)
        if duration_ms > lower:
            total += (
                peak_edge
                * (duration_ms * (duration_ms - lower) - (duration_ms**2 - lower**2) / 2.0)
                / decay_width
            )
    return total / window


class LatencyCaptureModel:
    """Estimate how much of a measured episode survives a round trip.

    Two separate questions are answered, and conflating them is what made the
    earlier figure optimistic.

    **When can the position be held?** The capturable fraction is the share of
    the episode's life during which the position could be open once the round
    trip completes, which is ``(duration - round_trip) / duration``. An episode
    shorter than the round trip captures nothing at all, because the edge closes
    before the trade can be completed. This is a statement about time and it
    does not depend on the shape of the edge.

    **How much edge is in that window?** The expected capture is the mean of the
    edge over the window, not its value at the first instant. Once both legs are
    open the position is held until the edge closes, so the edge available is
    the average of what remains across the window. Returning the value at the
    moment the round trip completes reports the best case in the window as if it
    were the expectation, and under linear decay it is exactly double the mean.

    ## The edge profile

    Two things are measured: the peak value, and when it occurred. The episode
    ends with the edge at zero. The profile therefore rises linearly from zero
    to the peak at its measured offset and decays linearly to zero at the end.
    That tent is the lowest profile consistent with the measurements, since the
    edge cannot exceed its own maximum, and it is an assumption rather than a
    measurement: the rise is not observed, only bounded. It is stated here
    rather than applied silently.
    """

    def assess(
        self,
        episodes: Sequence[Episode],
        assumption: RoundTripAssumption,
    ) -> LatencyCaptureReport:
        if not episodes:
            raise InsufficientDataError(
                "latency capture requires at least one measured opportunity episode"
            )
        round_trip = assumption.round_trip_ms
        captures: list[EpisodeCapture] = []
        for episode in episodes:
            if episode.duration_ms <= round_trip:
                fraction = 0.0
            else:
                fraction = (episode.duration_ms - round_trip) / episode.duration_ms
            captured = _mean_edge_over_window(
                episode.peak_edge,
                episode.peak_offset_ms,
                episode.duration_ms,
                round_trip,
            )
            net = captured - assumption.adverse_move_allowance
            if fraction <= 0.0 or net <= 0.0:
                status = CaptureStatus.NOT_CAPTURABLE
            elif fraction < assumption.minimum_capturable_fraction:
                status = CaptureStatus.MARGINAL
            else:
                status = CaptureStatus.CAPTURABLE
            captures.append(
                EpisodeCapture(
                    label=episode.label,
                    duration_ms=episode.duration_ms,
                    peak_edge=episode.peak_edge,
                    peak_offset_ms=episode.peak_offset_ms,
                    round_trip_ms=round_trip,
                    capturable_fraction=fraction,
                    captured_edge=captured,
                    net_captured_edge=net,
                    status=status,
                )
            )
        durations = sorted(episode.duration_ms for episode in episodes)
        return LatencyCaptureReport(
            episodes=len(episodes),
            capturable=sum(1 for item in captures if item.status is CaptureStatus.CAPTURABLE),
            marginal=sum(1 for item in captures if item.status is CaptureStatus.MARGINAL),
            not_capturable=sum(
                1 for item in captures if item.status is CaptureStatus.NOT_CAPTURABLE
            ),
            round_trip_ms=round_trip,
            median_duration_ms=durations[len(durations) // 2],
            maximum_duration_ms=durations[-1],
            mean_peak_edge=sum(episode.peak_edge for episode in episodes) / len(episodes),
            mean_captured_edge=sum(item.captured_edge for item in captures) / len(captures),
            mean_net_captured_edge=sum(item.net_captured_edge for item in captures) / len(captures),
            assumptions=assumption,
            captures=tuple(captures),
        )

    def episodes_from_durations(
        self,
        durations_ms: Sequence[float],
        peak_edges: Sequence[float],
    ) -> tuple[Episode, ...]:
        """Build episodes from parallel duration and peak-edge sequences."""
        if len(durations_ms) != len(peak_edges):
            raise ValueError("durations and peak edges must have the same length")
        return tuple(
            Episode(label=f"EP{index:03d}", duration_ms=float(duration), peak_edge=float(peak))
            for index, (duration, peak) in enumerate(zip(durations_ms, peak_edges, strict=True))
        )
