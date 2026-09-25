import json
from datetime import UTC, datetime
from pathlib import Path

from market_relationship_discovery.domain.experiment import create_experiment_manifest
from market_relationship_discovery.reporting.experiment import ExperimentReportWriter


def test_experiment_report_records_source_hash_and_parameters(tmp_path: Path) -> None:
    source = tmp_path / "signals.csv"
    related = tmp_path / "related.csv"
    source.write_text("timestamp,signal\n", encoding="utf-8")
    related.write_text("timestamp,signal\n", encoding="utf-8")
    manifest = create_experiment_manifest(
        "walk_forward",
        source,
        datetime.now(UTC),
        datetime.now(UTC),
        {"train": 10},
        (related,),
    )

    report_path = ExperimentReportWriter(tmp_path / "reports").write({"aggregate": {}}, manifest)
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["manifest"]["source_sha256"]
    assert report["manifest"]["related_sources"][0]["file_name"] == "related.csv"
    assert report["manifest"]["parameters"]["train"] == 10
    assert report["disclaimer"]
    assert report_path.name == f"{manifest.experiment_id}.json"
