"""Read measured round-trip latency from a user-supplied execution log.

This module is a file reader. It never connects to a terminal, never places an
order, and never measures latency itself. The log must have been produced by
some other system; the platform only summarises it and records its provenance.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from pathlib import Path

import numpy as np
import pandas as pd

from market_relationship_discovery.domain.errors import DataQualityError


class LatencyStatistic(StrEnum):
    MEAN = "mean"
    MEDIAN = "median"
    P95 = "p95"
    MAXIMUM = "maximum"
    MINIMUM = "minimum"


class LatencySource(StrEnum):
    ASSUMED = "assumed"
    MEASURED = "measured"


@dataclass(frozen=True, slots=True)
class MeasuredLatencySample:
    round_trip_ms: float
    symbol: str | None = None
    broker: str | None = None


@dataclass(frozen=True, slots=True)
class MeasuredLatencyBaseline:
    statistic: LatencyStatistic
    round_trip_ms: float
    sample_count: int
    minimum_ms: float
    median_ms: float
    p95_ms: float
    maximum_ms: float
    source_file_name: str
    symbol: str | None = None
    broker: str | None = None

    def per_leg(self, legs: int) -> float:
        if legs < 1:
            raise ValueError("a round trip needs at least one leg")
        return self.round_trip_ms / legs

    def to_dict(self) -> dict[str, object]:
        return {
            "source_kind": LatencySource.MEASURED.value,
            "statistic": self.statistic.value,
            "round_trip_ms": self.round_trip_ms,
            "per_leg_ms": self.per_leg(2),
            "sample_count": self.sample_count,
            "minimum_ms": self.minimum_ms,
            "median_ms": self.median_ms,
            "p95_ms": self.p95_ms,
            "maximum_ms": self.maximum_ms,
            "source_file_name": self.source_file_name,
            "symbol": self.symbol,
            "broker": self.broker,
        }


def load_measured_latency(
    path: Path,
    statistic: LatencyStatistic = LatencyStatistic.MEDIAN,
    symbol: str | None = None,
    broker: str | None = None,
) -> MeasuredLatencyBaseline:
    if path.suffix.lower() in {".csv", ".parquet"}:
        frame = pd.read_parquet(path) if path.suffix.lower() == ".parquet" else pd.read_csv(path)
        samples = _samples_from_frame(frame)
    elif path.suffix.lower() == ".json":
        samples = _samples_from_json(path)
    else:
        raise DataQualityError("latency log must be CSV, Parquet, or JSON")
    if symbol is not None:
        samples = tuple(item for item in samples if item.symbol == symbol)
    if broker is not None:
        samples = tuple(item for item in samples if item.broker == broker)
    if not samples:
        raise DataQualityError("latency log contains no observations for the requested filters")
    return _summarise(samples, statistic, path.name, symbol, broker)


def _samples_from_frame(frame: pd.DataFrame) -> tuple[MeasuredLatencySample, ...]:
    column = next(
        (name for name in ("round_trip_ms", "round_trip", "latency_ms") if name in frame),
        None,
    )
    if column is None:
        raise DataQualityError("latency log requires round_trip_ms, round_trip, or latency_ms")
    return tuple(
        _sample(
            row.get(column),
            row.get("symbol"),
            row.get("broker"),
        )
        for row in frame.to_dict(orient="records")
    )


def _samples_from_json(path: Path) -> tuple[MeasuredLatencySample, ...]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataQualityError("latency log is not readable JSON") from error
    if isinstance(payload, dict):
        for key in ("samples", "executions", "latency_log"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
        else:
            if "round_trip_ms" in payload:
                return (
                    _sample(
                        payload.get("round_trip_ms"),
                        payload.get("symbol"),
                        payload.get("broker"),
                    ),
                )
            raise DataQualityError("JSON latency log requires a samples list or round_trip_ms")
    if not isinstance(payload, list):
        raise DataQualityError("JSON latency log must contain a list of observations")
    samples: list[MeasuredLatencySample] = []
    for item in payload:
        if not isinstance(item, dict):
            raise DataQualityError("every latency observation must be an object")
        samples.append(
            _sample(
                item.get("round_trip_ms", item.get("round_trip", item.get("latency_ms"))),
                item.get("symbol"),
                item.get("broker"),
            )
        )
    return tuple(samples)


def _sample(value: object, symbol: object, broker: object) -> MeasuredLatencySample:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DataQualityError("measured round trip must be numeric")
    round_trip = float(value)
    if not isfinite(round_trip) or round_trip <= 0:
        raise DataQualityError(
            "a measured round trip must be positive; a zero round trip would report every "
            "episode as fully capturable"
        )
    return MeasuredLatencySample(
        round_trip_ms=round_trip,
        symbol=str(symbol) if symbol is not None else None,
        broker=str(broker) if broker is not None else None,
    )


def _summarise(
    samples: tuple[MeasuredLatencySample, ...],
    statistic: LatencyStatistic,
    source_file_name: str,
    symbol: str | None,
    broker: str | None,
) -> MeasuredLatencyBaseline:
    values = np.asarray([item.round_trip_ms for item in samples], dtype=float)
    selected: float
    match statistic:
        case LatencyStatistic.MEAN:
            selected = float(values.mean())
        case LatencyStatistic.MEDIAN:
            selected = float(np.median(values))
        case LatencyStatistic.P95:
            selected = float(np.quantile(values, 0.95))
        case LatencyStatistic.MAXIMUM:
            selected = float(values.max())
        case LatencyStatistic.MINIMUM:
            selected = float(values.min())
    return MeasuredLatencyBaseline(
        statistic=statistic,
        round_trip_ms=selected,
        sample_count=len(values),
        minimum_ms=float(values.min()),
        median_ms=float(np.median(values)),
        p95_ms=float(np.quantile(values, 0.95)),
        maximum_ms=float(values.max()),
        source_file_name=source_file_name,
        symbol=symbol,
        broker=broker,
    )
