from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path


class DataType(StrEnum):
    TICK = "tick"
    BAR = "bar"


@dataclass(frozen=True, slots=True)
class DatasetManifest:
    dataset_id: str
    created_at: datetime
    broker_profile: str
    broker_server: str
    symbol: str
    data_type: DataType
    timeframe: str | None
    start: datetime
    end: datetime
    rows: int
    source: str
    software_version: str
    file_name: str
    parameters: dict[str, object] = field(default_factory=dict)
    quality: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["data_type"] = self.data_type.value
        result["created_at"] = self.created_at.isoformat()
        result["start"] = self.start.isoformat()
        result["end"] = self.end.isoformat()
        return result


@dataclass(frozen=True, slots=True)
class StoredDataset:
    data_path: Path
    manifest_path: Path
    manifest: DatasetManifest


@dataclass(frozen=True, slots=True)
class CollectionBatch:
    broker_profile: str
    datasets: tuple[StoredDataset, ...]

    @property
    def rows(self) -> int:
        return sum(dataset.manifest.rows for dataset in self.datasets)
