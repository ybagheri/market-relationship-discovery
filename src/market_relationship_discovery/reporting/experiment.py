from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from market_relationship_discovery.domain.experiment import ExperimentManifest


class ExperimentReportWriter:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def write(self, payload: dict[str, object], manifest: ExperimentManifest) -> Path:
        self._directory.mkdir(parents=True, exist_ok=True)
        report = {
            "manifest": manifest.to_dict(),
            "results": payload,
            "disclaimer": "Research results are hypotheses and are not guaranteed returns.",
        }
        target = self._directory / f"{manifest.experiment_id}.json"
        with NamedTemporaryFile(
            dir=self._directory,
            mode="w",
            encoding="utf-8",
            suffix=".json",
            delete=False,
        ) as temporary:
            json.dump(report, temporary, ensure_ascii=False, indent=2, default=_json_default)
            temporary_path = Path(temporary.name)
        try:
            temporary_path.replace(target)
        finally:
            temporary_path.unlink(missing_ok=True)
        return target


def _json_default(value: object) -> object:
    if isinstance(value, (datetime, Path)):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise TypeError
