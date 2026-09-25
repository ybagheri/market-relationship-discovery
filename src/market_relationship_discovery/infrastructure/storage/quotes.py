from __future__ import annotations

import json
import re
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import cast

import pandas as pd

from market_relationship_discovery.domain.dataset import DatasetManifest, StoredDataset


class ParquetQuoteRepository:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def write(self, frame: pd.DataFrame, manifest: DatasetManifest) -> StoredDataset:
        target_directory = (
            self._directory
            / self._safe(manifest.broker_profile)
            / manifest.data_type.value
            / self._safe(manifest.symbol)
            / self._safe(manifest.timeframe or "none")
        )
        target_directory.mkdir(parents=True, exist_ok=True)
        data_path = target_directory / f"{manifest.dataset_id}.parquet"
        manifest_path = target_directory / f"{manifest.dataset_id}.json"
        with NamedTemporaryFile(dir=target_directory, suffix=".parquet", delete=False) as temporary:
            data_temporary = Path(temporary.name)
        try:
            frame.to_parquet(data_temporary, index=False)
            data_temporary.replace(data_path)
            self._write_manifest(manifest_path, manifest)
        finally:
            data_temporary.unlink(missing_ok=True)
        return StoredDataset(data_path, manifest_path, manifest)

    def read(self, path: Path) -> pd.DataFrame:
        return pd.read_parquet(path)

    def read_manifest(self, path: Path) -> dict[str, object]:
        return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))

    @staticmethod
    def _write_manifest(path: Path, manifest: DatasetManifest) -> None:
        with NamedTemporaryFile(
            dir=path.parent,
            suffix=".json",
            mode="w",
            encoding="utf-8",
            delete=False,
        ) as temporary:
            json.dump(manifest.to_dict(), temporary, ensure_ascii=False, indent=2)
            temporary_path = Path(temporary.name)
        try:
            temporary_path.replace(path)
        finally:
            temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _safe(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
