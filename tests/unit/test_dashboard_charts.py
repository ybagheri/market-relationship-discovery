import json
from pathlib import Path

import pandas as pd

from market_relationship_discovery.dashboard.charts import broker_price_figure, discrepancy_figure
from market_relationship_discovery.dashboard.reports import (
    aligned_frame,
    list_comparison_reports,
    opportunity_frame,
)


def _write_report(
    path: Path,
    experiment_id: str,
    created_at: str,
    preview: list[dict[str, object]],
    opportunities: list[dict[str, object]] | None = None,
) -> None:
    path.write_text(
        json.dumps(
            {
                "manifest": {
                    "experiment_id": experiment_id,
                    "created_at": created_at,
                    "experiment_type": "cross_broker_comparison",
                    "parameters": {
                        "broker_a": "Alpari",
                        "broker_b": "AMarkets",
                        "symbol": "EURUSD",
                        "comparison_kind": "tick",
                    },
                },
                "results": {
                    "summary": {
                        "broker_a": "Alpari",
                        "broker_b": "AMarkets",
                        "symbol": "EURUSD",
                        "additional_cost": 0.0001,
                    },
                    "aligned_preview": preview,
                    "opportunities": opportunities or [],
                },
            }
        ),
        encoding="utf-8",
    )


def test_comparison_reports_are_listed_newest_first(tmp_path: Path) -> None:
    _write_report(tmp_path / "EXP-old.json", "EXP-old", "2026-09-24T00:00:00+00:00", [])
    _write_report(tmp_path / "EXP-new.json", "EXP-new", "2026-09-25T00:00:00+00:00", [])
    (tmp_path / "EXP-other.json").write_text(
        json.dumps({"manifest": {"experiment_type": "monte_carlo_robustness"}}),
        encoding="utf-8",
    )

    references = list_comparison_reports(tmp_path)

    assert [reference.experiment_id for reference in references] == ["EXP-new", "EXP-old"]
    assert references[0].broker_a == "Alpari"
    assert references[0].broker_b == "AMarkets"


def test_aligned_frame_coerces_timestamps_and_crossable_values(tmp_path: Path) -> None:
    path = tmp_path / "EXP-1.json"
    _write_report(
        path,
        "EXP-1",
        "2026-09-25T00:00:00+00:00",
        [
            {
                "timestamp": "2026-09-25T00:00:00+00:00",
                "broker_b_timestamp": "2026-09-25T00:00:01+00:00",
                "mid_difference": "0.0012",
                "is_crossable": True,
            }
        ],
    )

    frame = aligned_frame(path)

    assert str(frame.loc[0, "timestamp"].tz) == "UTC"
    assert frame.loc[0, "mid_difference"] == 0.0012
    assert bool(frame.loc[0, "is_crossable"])


def test_aligned_frame_accepts_legacy_symbol_columns(tmp_path: Path) -> None:
    path = tmp_path / "EXP-legacy.json"
    _write_report(
        path,
        "EXP-legacy",
        "2026-09-25T00:00:00+00:00",
        [
            {
                "timestamp": "2026-09-25T00:00:00+00:00",
                "symbol_x": "EURUSD",
                "symbol_y": "EURUSD",
                "a_mid": 1.1,
                "b_mid": 1.0,
            }
        ],
    )

    frame = aligned_frame(path)

    assert frame.loc[0, "a_mid"] == 1.1
    assert "symbol_x" in frame.columns


def test_discrepancy_figure_includes_cost_reference_and_crossable_markers() -> None:
    aligned = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2026-09-25T00:00:00Z"]),
            "mid_difference": [0.0012],
            "is_crossable": [True],
        }
    )

    figure = discrepancy_figure(aligned, "mid_difference", 0.0001)

    assert len(figure.data) == 3
    assert [trace.name for trace in figure.data] == [
        "mid_difference",
        "additional_cost",
        "crossable observations",
    ]
    assert "research" in figure.layout.title.text


def test_broker_price_figure_uses_broker_labels(tmp_path: Path) -> None:
    aligned = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2026-09-25T00:00:00Z"]),
            "a_mid": [1.1],
            "b_mid": [1.0],
        }
    )

    figure = broker_price_figure(aligned, "Alpari", "AMarkets")

    assert [trace.name for trace in figure.data] == ["Alpari", "AMarkets"]


def test_empty_aligned_frame_yields_figure_without_traces() -> None:
    figure = discrepancy_figure(pd.DataFrame(), "mid_difference", 0.0001)

    assert not figure.data
    assert figure.layout.title.text == "No aligned observations"


def test_opportunity_frame_parses_timestamp_strings(tmp_path: Path) -> None:
    path = tmp_path / "EXP-opportunity.json"
    _write_report(
        path,
        "EXP-opportunity",
        "2026-09-25T00:00:00+00:00",
        [],
        [
            {
                "start": "2026-09-25 00:00:00+00:00",
                "end": "2026-09-25 00:00:01+00:00",
                "duration_ms": "1000",
            }
        ],
    )

    frame = opportunity_frame(path)

    assert str(frame.loc[0, "start"].tz) == "UTC"
    assert frame.loc[0, "duration_ms"] == 1000
