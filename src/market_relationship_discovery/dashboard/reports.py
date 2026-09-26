from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pandas as pd

CROSS_BROKER_EXPERIMENT_TYPE = "cross_broker_comparison"


@dataclass(frozen=True, slots=True)
class ComparisonReportRef:
    path: Path
    experiment_id: str
    created_at: str
    broker_a: str
    broker_b: str
    symbol: str
    comparison_kind: str


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
