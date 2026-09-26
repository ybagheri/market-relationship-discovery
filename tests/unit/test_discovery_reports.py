"""Tests for the discovery report loaders, frames, and charts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from market_relationship_discovery.dashboard.charts import (
    candidate_significance_figure,
    coverage_figure,
)
from market_relationship_discovery.dashboard.reports import (
    ADVANCED_DISCOVERY_EXPERIMENT_TYPE,
    as_count,
    as_float,
    as_records,
    as_str_list,
    candidate_frame,
    coverage_frame,
    list_discovery_reports,
    load_discovery_report,
)

DISCOVERY_REPORT: dict[str, Any] = {
    "manifest": {
        "experiment_id": "EXP-TEST-0001",
        "experiment_type": ADVANCED_DISCOVERY_EXPERIMENT_TYPE,
        "created_at": "2026-09-26T00:00:00+00:00",
        "source_file_name": "panel.csv",
    },
    "results": {
        "candidates": [
            {
                "name": "EURGBP_SYNTHETIC",
                "target": "EURGBP",
                "formula": "EURUSD / GBPUSD",
                "status": "requires_further_validation",
                "summary": {
                    "pearson": 0.99,
                    "spearman": 0.98,
                    "half_life": 1.2,
                    "mean_absolute_discrepancy": 0.0001,
                    "latest_zscore": 0.2,
                },
            },
            {
                "name": "XAUEUR_SYNTHETIC",
                "target": "XAUEUR",
                "formula": "XAUUSD / EURUSD",
                "status": "requires_further_validation",
                "summary": {
                    "pearson": 0.999,
                    "spearman": 0.999,
                    "half_life": 3.9,
                    "mean_absolute_discrepancy": 0.22,
                    "latest_zscore": 1.1,
                },
            },
        ],
        "ranking": {"model": "numpy_ridge"},
        "multiplicity": {
            "method": "fdr_bh",
            "alpha": 0.05,
            "tests": 2,
            "retained_after_correction": 1,
            "contested": 1,
            "hypotheses": [
                {
                    "label": "EURGBP_SYNTHETIC",
                    "raw_p_value": 0.00067,
                    "adjusted_p_value": 0.00134,
                    "survived_correction": True,
                    "contested": True,
                },
                {
                    "label": "XAUEUR_SYNTHETIC",
                    "raw_p_value": 0.0562,
                    "adjusted_p_value": 0.0562,
                    "survived_correction": False,
                    "contested": False,
                },
            ],
        },
        "deduplication": {
            "input_candidates": 2,
            "kept_candidates": 2,
            "removed_duplicates": [],
            "unparsable_formulas": [],
        },
        "coverage": {
            "union_rows": 1370,
            "fully_overlapping_rows": 1370,
            "analysed_symbols": ["EURUSD", "GBPUSD", "EURGBP"],
            "excluded_symbols": ["USDJPY"],
            "issues": ["symbols ending before the union window end: USDJPY"],
            "coverage": [
                {
                    "symbol": "EURUSD",
                    "observations": 1370,
                    "coverage_fraction": 1.0,
                    "largest_gap": 0,
                },
                {
                    "symbol": "USDJPY",
                    "observations": 120,
                    "coverage_fraction": 0.08,
                    "largest_gap": 900,
                },
            ],
        },
        "regimes": {},
        "limitations": ["Research simulation only."],
    },
}


def write_report(
    directory: Path, payload: dict[str, Any], name: str = "EXP-TEST-0001.json"
) -> Path:
    path = directory / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_discovery_reports_are_listed_with_multiplicity_counts(tmp_path: Path) -> None:
    write_report(tmp_path, DISCOVERY_REPORT)

    references = list_discovery_reports(tmp_path)

    assert len(references) == 1
    assert references[0].candidate_count == 2
    assert references[0].retained_after_correction == 1
    assert references[0].contested == 1
    assert references[0].source_file_name == "panel.csv"


def test_comparison_reports_are_not_listed_as_discovery_reports(tmp_path: Path) -> None:
    write_report(
        tmp_path,
        {
            "manifest": {
                "experiment_id": "EXP-CB",
                "experiment_type": "cross_broker_comparison",
                "created_at": "2026-09-26T00:00:00+00:00",
            },
            "results": {"summary": {}},
        },
        name="EXP-CB.json",
    )

    assert list_discovery_reports(tmp_path) == ()


def test_unreadable_reports_are_skipped_rather_than_raising(tmp_path: Path) -> None:
    (tmp_path / "EXP-BROKEN.json").write_text("{not json", encoding="utf-8")
    write_report(tmp_path, DISCOVERY_REPORT)

    references = list_discovery_reports(tmp_path)

    assert len(references) == 1


def test_load_discovery_report_exposes_every_section(tmp_path: Path) -> None:
    path = write_report(tmp_path, DISCOVERY_REPORT)

    loaded = load_discovery_report(path)

    assert loaded["manifest"]["experiment_id"] == "EXP-TEST-0001"
    assert loaded["multiplicity"]["method"] == "fdr_bh"
    assert loaded["deduplication"]["kept_candidates"] == 2
    assert loaded["coverage"]["union_rows"] == 1370
    assert loaded["limitations"] == ["Research simulation only."]


def test_loading_an_unreadable_report_raises(tmp_path: Path) -> None:
    path = tmp_path / "EXP-MISSING.json"
    path.write_text("{}", encoding="utf-8")

    try:
        load_discovery_report(path)
    except ValueError as error:
        assert "could not read" in str(error)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected a ValueError")


def test_candidate_frame_joins_significance_onto_candidates(tmp_path: Path) -> None:
    path = write_report(tmp_path, DISCOVERY_REPORT)

    frame = candidate_frame(path)

    assert list(frame["name"]) == ["EURGBP_SYNTHETIC", "XAUEUR_SYNTHETIC"]
    assert frame["survived_correction"].tolist() == [True, False]
    assert frame["contested"].tolist() == [True, False]
    assert frame["adjusted_p_value"].iloc[0] == 0.00134
    assert frame["pearson"].iloc[0] == 0.99


def test_candidate_frame_marks_a_candidate_missing_from_the_family(tmp_path: Path) -> None:
    payload = json.loads(json.dumps(DISCOVERY_REPORT))
    payload["results"]["multiplicity"]["hypotheses"] = [
        {
            "label": "EURGBP_SYNTHETIC",
            "raw_p_value": 0.001,
            "adjusted_p_value": 0.002,
            "survived_correction": True,
            "contested": False,
        }
    ]
    path = write_report(tmp_path, payload)

    frame = candidate_frame(path)

    by_name = dict(zip(frame["name"], frame["survived_correction"], strict=True))
    assert by_name["EURGBP_SYNTHETIC"] is True
    assert by_name["XAUEUR_SYNTHETIC"] is False


def test_coverage_frame_marks_which_symbols_were_analysed(tmp_path: Path) -> None:
    path = write_report(tmp_path, DISCOVERY_REPORT)

    frame = coverage_frame(path)

    analysed = dict(zip(frame["symbol"], frame["analysed"], strict=True))
    assert analysed["EURUSD"] is True
    assert analysed["USDJPY"] is False


def test_frames_survive_a_report_with_no_candidates(tmp_path: Path) -> None:
    payload = json.loads(json.dumps(DISCOVERY_REPORT))
    payload["results"]["candidates"] = []
    path = write_report(tmp_path, payload)

    assert candidate_frame(path).empty
    assert not coverage_frame(path).empty


def test_typed_readers_tolerate_unexpected_json() -> None:
    assert as_count(3) == 3
    assert as_count("3") == 0
    assert as_count(None) == 0
    assert as_count(True) == 0
    assert as_float(0.25) == 0.25
    assert as_float("x", 0.05) == 0.05
    assert as_records([{"a": 1}, "skip", 3]) == [{"a": 1}]
    assert as_str_list(["a", None, 2]) == ["a", "2"]
    assert as_str_list("not a list") == []


def test_significance_figure_plots_raw_and_adjusted(tmp_path: Path) -> None:
    path = write_report(tmp_path, DISCOVERY_REPORT)
    frame = candidate_frame(path)

    figure = candidate_significance_figure(frame, 0.05)

    assert len(figure.data) == 2
    assert {trace.name for trace in figure.data} == {"raw p-value", "adjusted p-value"}
    assert figure.layout.yaxis.title.text == "p-value"
    assert any(getattr(shape, "y0", None) == 0.05 for shape in figure.layout.shapes)


def test_significance_figure_handles_an_empty_frame() -> None:
    figure = candidate_significance_figure(pd.DataFrame(), 0.05)

    assert figure.layout.title.text == "No candidate significance results"


def test_coverage_figure_orders_and_labels_symbols(tmp_path: Path) -> None:
    path = write_report(tmp_path, DISCOVERY_REPORT)
    frame = coverage_frame(path)

    figure = coverage_figure(frame, 1370)

    trace = figure.data[0]
    assert list(trace.x) == ["EURUSD", "USDJPY"]
    assert "1370 rows" in figure.layout.title.text
    assert list(trace.marker.color) == ["seagreen", "lightgray"]


def test_coverage_figure_handles_an_empty_frame() -> None:
    figure = coverage_figure(pd.DataFrame(), None)

    assert figure.layout.title.text == "No coverage information"
