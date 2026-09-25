from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from market_relationship_discovery import __version__


@dataclass(frozen=True, slots=True)
class SourceFingerprint:
    file_name: str
    sha256: str


@dataclass(frozen=True, slots=True)
class ExperimentManifest:
    experiment_id: str
    created_at: datetime
    software_version: str
    experiment_type: str
    source_file_name: str
    source_sha256: str
    data_start: datetime
    data_end: datetime
    parameters: dict[str, object] = field(default_factory=dict)
    limitations: tuple[str, ...] = ()
    related_sources: tuple[SourceFingerprint, ...] = ()

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["created_at"] = self.created_at.isoformat()
        result["data_start"] = self.data_start.isoformat()
        result["data_end"] = self.data_end.isoformat()
        result["limitations"] = list(self.limitations)
        result["related_sources"] = [asdict(source) for source in self.related_sources]
        return result


def create_experiment_manifest(
    experiment_type: str,
    source_path: Path,
    data_start: datetime,
    data_end: datetime,
    parameters: dict[str, object],
    related_paths: tuple[Path, ...] = (),
) -> ExperimentManifest:
    return ExperimentManifest(
        experiment_id=f"EXP-{datetime.now(UTC):%Y%m%d}-{uuid4().hex[:8]}",
        created_at=datetime.now(UTC),
        software_version=__version__,
        experiment_type=experiment_type,
        source_file_name=source_path.name,
        source_sha256=_sha256(source_path),
        data_start=data_start,
        data_end=data_end,
        parameters=parameters,
        limitations=(
            "Research simulation only; no order execution was performed.",
            "Historical results do not guarantee future returns or executable arbitrage.",
        ),
        related_sources=tuple(
            SourceFingerprint(path.name, _sha256(path)) for path in related_paths
        ),
    )


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
