from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pandas as pd

CROSS_BROKER_EXPERIMENT_TYPE = "cross_broker_comparison"
ADVANCED_DISCOVERY_EXPERIMENT_TYPE = "advanced_relationship_discovery"


@dataclass(frozen=True, slots=True)
class ComparisonReportRef:
    path: Path
    experiment_id: str
    created_at: str
    broker_a: str
    broker_b: str
    symbol: str
    comparison_kind: str


@dataclass(frozen=True, slots=True)
class DiscoveryReportRef:
    """A persisted advanced discovery run.

    Carries the candidate count rather than the full candidate list so a picker
    can list many runs cheaply.
    """

    path: Path
    experiment_id: str
    created_at: str
    source_file_name: str
    candidate_count: int
    retained_after_correction: int
    contested: int


def list_comparison_reports(reports_directory: Path) -> tuple[ComparisonReportRef, ...]:
    references: list[ComparisonReportRef] = []
    for path in reports_directory.glob("EXP-*.json"):
        report = _read_report(path)
        if report is None:
            continue
        manifest = _as_dict(report.get("manifest"))
        results = _as_dict(report.get("results"))
        summary = _as_dict(results.get("summary"))
        parameters = _as_dict(manifest.get("parameters"))
        if manifest.get("experiment_type") != CROSS_BROKER_EXPERIMENT_TYPE:
            continue
        broker_a = str(summary.get("broker_a") or parameters.get("broker_a") or "Broker A")
        broker_b = str(summary.get("broker_b") or parameters.get("broker_b") or "Broker B")
        symbol = str(summary.get("symbol") or parameters.get("symbol") or "unknown")
        comparison_kind = str(
            summary.get("comparison_kind") or parameters.get("comparison_kind") or "unknown"
        )
        references.append(
            ComparisonReportRef(
                path=path,
                experiment_id=str(manifest.get("experiment_id") or path.stem),
                created_at=str(manifest.get("created_at") or ""),
                broker_a=broker_a,
                broker_b=broker_b,
                symbol=symbol,
                comparison_kind=comparison_kind,
            )
        )
    return tuple(sorted(references, key=lambda item: item.created_at, reverse=True))


def load_comparison_report(path: Path) -> dict[str, object]:
    report = _read_report(path)
    if report is None:
        raise ValueError(f"could not read comparison report: {path}")
    results = _as_dict(report.get("results"))
    return {
        "manifest": _as_dict(report.get("manifest")),
        "summary": _as_dict(results.get("summary")),
        "opportunities": _as_list(results.get("opportunities")),
        "aligned_preview": _as_list(results.get("aligned_preview")),
        "execution": _as_dict(results.get("execution")),
        "latency": _as_dict(results.get("latency")),
        "limitations": _as_list(results.get("limitations")),
    }


def aligned_frame(path: Path) -> pd.DataFrame:
    report = load_comparison_report(path)
    frame = pd.DataFrame(cast(list[dict[str, object]], report["aligned_preview"]))
    if frame.empty:
        return pd.DataFrame(columns=["timestamp", "is_crossable"])
    for column in ("timestamp", "broker_b_timestamp"):
        if column in frame:
            frame[column] = pd.to_datetime(frame[column], utc=True, errors="coerce")
    numeric_columns = (
        "a_bid",
        "a_ask",
        "b_bid",
        "b_ask",
        "a_mid",
        "b_mid",
        "mid_difference",
        "bid_difference",
        "ask_difference",
        "net_crossable_edge",
        "normalized_net_pnl",
        "alignment_delay_ms",
    )
    for column in numeric_columns:
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if "is_crossable" in frame:
        frame["is_crossable"] = frame["is_crossable"].astype("boolean").fillna(False).astype(bool)
    return frame


def opportunity_frame(path: Path) -> pd.DataFrame:
    report = load_comparison_report(path)
    frame = pd.DataFrame(cast(list[dict[str, object]], report["opportunities"]))
    if frame.empty:
        return frame
    for column in ("start", "end"):
        if column in frame:
            frame[column] = pd.to_datetime(frame[column], utc=True, errors="coerce")
    for column in ("duration_ms", "observations", "maximum_net_edge", "mean_normalized_net_pnl"):
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def list_discovery_reports(reports_directory: Path) -> tuple[DiscoveryReportRef, ...]:
    references: list[DiscoveryReportRef] = []
    for path in reports_directory.glob("EXP-*.json"):
        report = _read_report(path)
        if report is None:
            continue
        manifest = _as_dict(report.get("manifest"))
        if manifest.get("experiment_type") != ADVANCED_DISCOVERY_EXPERIMENT_TYPE:
            continue
        results = _as_dict(report.get("results"))
        multiplicity = _as_dict(results.get("multiplicity"))
        references.append(
            DiscoveryReportRef(
                path=path,
                experiment_id=str(manifest.get("experiment_id") or path.stem),
                created_at=str(manifest.get("created_at") or ""),
                source_file_name=str(manifest.get("source_file_name") or ""),
                candidate_count=as_count(multiplicity.get("tests")),
                retained_after_correction=as_count(multiplicity.get("retained_after_correction")),
                contested=as_count(multiplicity.get("contested")),
            )
        )
    return tuple(sorted(references, key=lambda item: item.created_at, reverse=True))


def load_discovery_report(path: Path) -> dict[str, object]:
    report = _read_report(path)
    if report is None:
        raise ValueError(f"could not read discovery report: {path}")
    results = _as_dict(report.get("results"))
    return {
        "manifest": _as_dict(report.get("manifest")),
        "candidates": _as_list(results.get("candidates")),
        "ranking": _as_dict(results.get("ranking")),
        "multiplicity": _as_dict(results.get("multiplicity")),
        "deduplication": _as_dict(results.get("deduplication")),
        "coverage": _as_dict(results.get("coverage")),
        "regimes": _as_dict(results.get("regimes")),
        "limitations": _as_list(results.get("limitations")),
    }


def candidate_frame(path: Path) -> pd.DataFrame:
    """One row per candidate, with its survival and contested status.

    The adjusted p-value and the contested flag are the columns that decide how
    a reader should treat a result, so they are joined onto the candidate rather
    than left in a separate block.
    """
    report = load_discovery_report(path)
    candidates = as_records(report["candidates"])
    frame = pd.DataFrame(candidates)
    if frame.empty:
        return pd.DataFrame(
            columns=["name", "target", "formula", "adjusted_p_value", "survived_correction"]
        )
    multiplicity = _as_dict(report["multiplicity"])
    hypotheses = {
        str(item.get("label")): item for item in as_records(multiplicity.get("hypotheses"))
    }
    frame["raw_p_value"] = frame["name"].map(
        lambda name: hypotheses.get(str(name), {}).get("raw_p_value")
    )
    frame["adjusted_p_value"] = frame["name"].map(
        lambda name: hypotheses.get(str(name), {}).get("adjusted_p_value")
    )
    frame["survived_correction"] = frame["name"].map(
        lambda name: bool(hypotheses.get(str(name), {}).get("survived_correction", False))
    )
    frame["contested"] = frame["name"].map(
        lambda name: bool(hypotheses.get(str(name), {}).get("contested", False))
    )
    for column in ("raw_p_value", "adjusted_p_value"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    summary_columns = {
        "pearson": "pearson",
        "spearman": "spearman",
        "half_life": "half_life",
        "mean_absolute_discrepancy": "mean_absolute_discrepancy",
        "latest_zscore": "latest_zscore",
    }
    for source, target in summary_columns.items():
        frame[target] = frame["summary"].map(lambda block, key=source: _as_dict(block).get(key))
        frame[target] = pd.to_numeric(frame[target], errors="coerce")
    return frame


def coverage_frame(path: Path) -> pd.DataFrame:
    """Per-symbol coverage of the panel the run analysed."""
    report = load_discovery_report(path)
    coverage = _as_dict(report["coverage"])
    frame = pd.DataFrame(as_records(coverage.get("coverage")))
    if frame.empty:
        return pd.DataFrame(columns=["symbol", "observations", "coverage_fraction"])
    analysed = set(cast(list[str], coverage.get("analysed_symbols") or []))
    frame["analysed"] = frame["symbol"].map(lambda symbol: str(symbol) in analysed)
    for column in ("observations", "coverage_fraction", "largest_gap"):
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _read_report(path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return _as_dict(payload) or None


def _as_dict(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def _as_list(value: object) -> list[object]:
    return cast(list[object], value) if isinstance(value, list) else []


def as_count(value: object) -> int:
    """Read a count from a report field, defaulting to zero.

    Reports are JSON, so a count may be absent or a non-numeric value. Reading
    it defensively keeps a partially written report from breaking a view.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return int(value)


def as_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value)


def as_records(value: object) -> list[dict[str, object]]:
    """Read a list of JSON objects, dropping anything that is not an object."""
    return [item for item in _as_list(value) if isinstance(item, dict)]


def as_str_list(value: object) -> list[str]:
    """Read a list of report values as strings, ignoring absent values."""
    return [str(item) for item in _as_list(value) if item is not None]
