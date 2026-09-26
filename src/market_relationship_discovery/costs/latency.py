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
    """

    label: str
    duration_ms: float
    peak_edge: float

    def __post_init__(self) -> None:
        if self.duration_ms < 0:
            raise ValueError("duration_ms cannot be negative")
        if not self.peak_edge > 0:
            raise ValueError("peak_edge must be positive for a capturable episode")


@dataclass(frozen=True, slots=True)
class RoundTripAssumption:
    """Time and adverse-move assumptions for completing both legs."""

    latency_per_leg_ms: float = 50.0
    legs: int = 2
    adverse_move_allowance: float = 0.0
    minimum_capturable_fraction: float = 0.25

    def __post_init__(self) -> None:
        if self.latency_per_leg_ms < 0:
            raise ValueError("latency_per_leg_ms cannot be negative")
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
        }


@dataclass(frozen=True, slots=True)
class EpisodeCapture:
    """Capture estimate for a single episode."""

    label: str
    duration_ms: float
    peak_edge: float
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


class LatencyCaptureModel:
    """Estimate how much of a measured episode survives a round trip.

    The capturable fraction is the share of the episode's life during which the
    position could still be open when the round trip completes, which under
    linear decay is ``(duration - round_trip) / duration``. An episode shorter
    than the round trip captures nothing at all, because the edge closes before
    the trade can be completed.
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
            if round_trip <= 0:
                fraction = 1.0
            elif episode.duration_ms <= round_trip:
                fraction = 0.0
            else:
                fraction = (episode.duration_ms - round_trip) / episode.duration_ms
            captured = episode.peak_edge * fraction
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
