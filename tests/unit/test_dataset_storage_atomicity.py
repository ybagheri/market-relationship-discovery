"""A dataset is the pair of files, and only the pair counts as written.

The data file was moved to its final path *before* the manifest was written, so
a manifest failure left the bytes on disk occupying `ds-N.parquet` with no
`ds-N.json` beside them. That is worse than losing the write: a reader that
trusts the manifest sees nothing, so the dataset is invisible, yet the next
write of the same `dataset_id` silently overwrites those bytes. The failure
leaves the store in a state where a later run cannot tell a real dataset from
the debris of a failed one.

The fix reverses the order and withdraws the manifest if the data move then
fails, because the other bad state is a manifest pointing at a file that is not
there. Both directions are asserted below, since testing only the one that
motivated the change would leave the introduced failure unchecked.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from market_relationship_discovery.domain.dataset import DatasetManifest, DataType
from market_relationship_discovery.infrastructure.storage.quotes import ParquetQuoteRepository


def frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-09-25", periods=5, freq="min", tz="UTC"),
            "broker": "A",
            "symbol": "EURUSD",
            "bid": [1.1] * 5,
            "ask": [1.2] * 5,
        }
    )


def manifest(dataset_id: str = "ds-1") -> DatasetManifest:
    return DatasetManifest(
        dataset_id=dataset_id,
        created_at=datetime(2026, 9, 25, tzinfo=UTC),
        broker_profile="ALPARI_1",
        broker_server="Alpari-Demo",
        symbol="EURUSD",
        data_type=DataType.TICK,
        timeframe="M1",
        start=datetime(2026, 9, 25, tzinfo=UTC),
        end=datetime(2026, 9, 25, 0, 4, tzinfo=UTC),
        rows=5,
        source="demo",
        software_version="1.9.0",
        file_name=f"{dataset_id}.parquet",
    )


def test_a_manifest_failure_leaves_no_data_file_behind(tmp_path: Path) -> None:
    """The orphaned dataset: bytes on disk that no manifest describes."""
    repository = ParquetQuoteRepository(tmp_path)

    with (
        patch.object(ParquetQuoteRepository, "_write_manifest", side_effect=OSError("disk full")),
        pytest.raises(OSError, match="disk full"),
    ):
        repository.write(frame(), manifest())

    assert list(tmp_path.rglob("*.parquet")) == []
    assert list(tmp_path.rglob("*.json")) == []


def test_a_failed_data_move_does_not_leave_a_manifest_pointing_at_nothing(
    tmp_path: Path,
) -> None:
    """The failure the reversed order introduces, asserted rather than assumed.

    Publishing the manifest first means a failure between the two steps would
    otherwise leave a manifest describing a file that was never moved, which is
    the mirror image of the orphan. The manifest is withdrawn instead.
    """
    repository = ParquetQuoteRepository(tmp_path)
    real_replace = Path.replace

    def fail_on_data_move(self: Path, target: object) -> Path:
        if str(target).endswith(".parquet"):
            raise OSError("cross-device link")
        return real_replace(self, target)

    with (
        patch.object(Path, "replace", fail_on_data_move),
        pytest.raises(OSError, match="cross-device link"),
    ):
        repository.write(frame(), manifest())

    assert list(tmp_path.rglob("*.json")) == []
    assert list(tmp_path.rglob("*.parquet")) == []


def test_a_failed_write_leaves_no_temporary_file_behind(tmp_path: Path) -> None:
    """Cleanup is unconditional, on the failure path as well as the success one."""
    repository = ParquetQuoteRepository(tmp_path)

    with (
        patch.object(ParquetQuoteRepository, "_write_manifest", side_effect=OSError("disk full")),
        pytest.raises(OSError),
    ):
        repository.write(frame(), manifest())

    assert [path.name for path in tmp_path.rglob("*") if path.name.startswith("tmp")] == []


def test_a_successful_write_is_unchanged_by_the_reordering(tmp_path: Path) -> None:
    """The fix must not change what a working write produces."""
    repository = ParquetQuoteRepository(tmp_path)

    stored = repository.write(frame(), manifest("ds-ok"))

    assert stored.data_path.is_file()
    assert stored.manifest_path.is_file()
    assert len(repository.read(stored.data_path)) == 5
    assert repository.read_manifest(stored.manifest_path)["dataset_id"] == "ds-ok"


def test_a_rewritten_dataset_replaces_both_files_together(tmp_path: Path) -> None:
    """Both halves carry the same `dataset_id`, so a rewrite is coherent.

    This is the property the orphan broke: a later write could land on the same
    data path while the store still held no manifest, leaving the two files
    describing different moments in time.
    """
    repository = ParquetQuoteRepository(tmp_path)

    first = repository.write(frame(), manifest("ds-rw"))
    second = repository.write(frame().assign(bid=[9.9] * 5), manifest("ds-rw"))

    assert first.data_path == second.data_path
    assert first.manifest_path == second.manifest_path
    assert list(tmp_path.rglob("*.parquet")) == [second.data_path]
    assert list(tmp_path.rglob("*.json")) == [second.manifest_path]
    assert repository.read(second.data_path)["bid"].tolist() == [9.9] * 5
