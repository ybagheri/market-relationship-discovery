"""Parallel collection must fail without leaving the pool mid-write.

Three defects lived in the coordinator. Raising inside the `with` block unwound
into the executor's own shutdown, so a failure in one worker stopped the others
while they were still writing datasets. A `DemoSafetyError` was wrapped as
`ParallelCollectionError`, making a safety refusal indistinguishable by type from
a transient connection error. And `DataQualityError` was retried, which re-ran
the symbols that had already succeeded and minted a fresh `dataset_id` for each,
orphaning every superseded dataset on disk.
"""

from __future__ import annotations

from concurrent.futures import Future
from typing import cast

import pytest

from market_relationship_discovery.application.parallel_collection import (
    CollectionJob,
    ParallelCollectionCoordinator,
    ParallelCollectionError,
)
from market_relationship_discovery.config.settings import MT5Settings
from market_relationship_discovery.domain.dataset import (
    CollectionBatch,
    DataType,
    StoredDataset,
)
from market_relationship_discovery.domain.errors import (
    DataQualityError,
    DemoSafetyError,
    MT5ConnectionError,
)


class FakeExecutor:
    """Stands in for the process pool and records whether shutdown was reached."""

    instance: FakeExecutor | None = None

    def __init__(self, max_workers: int) -> None:
        self.max_workers = max_workers
        self.jobs: list[CollectionJob] = []
        self.entered = 0
        self.exited = 0
        FakeExecutor.instance = self

    def __enter__(self) -> FakeExecutor:
        self.entered += 1
        return self

    def __exit__(self, *_: object) -> None:
        self.exited += 1
        return None

    def submit(self, function: object, job: CollectionJob) -> Future[CollectionBatch]:
        self.jobs.append(job)
        future: Future[CollectionBatch] = Future()
        future.set_result(function(job))
        return future


def job(order: int, profile: str, symbols: tuple[str, ...] = ("EURUSD",)) -> CollectionJob:
    return CollectionJob(
        order,
        profile,
        MT5Settings(),
        {},
        symbols,
        DataType.BAR,
        "M1",
        None,
        None,
        10,
        "data/raw",
    )


def _patch_executor(monkeypatch: pytest.MonkeyPatch, executor: type) -> None:
    monkeypatch.setattr(
        "market_relationship_discovery.application.parallel_collection.ProcessPoolExecutor",
        executor,
    )


def test_a_demo_refusal_is_not_disguised_as_a_connection_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A safety refusal must keep its type across the parallel path.

    The sequential collector and `doctor` both report it distinctly. Wrapping it
    as `ParallelCollectionError` made it indistinguishable by type from a
    transient connection error, so a caller that retries connection failures
    would also retry a refusal that can never succeed.
    """

    class RefusingExecutor(FakeExecutor):
        def submit(
            self, function: object, collection_job: CollectionJob
        ) -> Future[CollectionBatch]:
            future: Future[CollectionBatch] = Future()
            future.set_exception(DemoSafetyError("account mode is not DEMO"))
            return future

    _patch_executor(monkeypatch, RefusingExecutor)

    with pytest.raises(DemoSafetyError, match="ALPARI_1"):
        ParallelCollectionCoordinator().run((job(0, "ALPARI_1"),), 1)


def test_a_connection_failure_is_still_reported_as_a_collection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingExecutor(FakeExecutor):
        def submit(
            self, function: object, collection_job: CollectionJob
        ) -> Future[CollectionBatch]:
            future: Future[CollectionBatch] = Future()
            future.set_exception(MT5ConnectionError("terminal closed"))
            return future

    _patch_executor(monkeypatch, FailingExecutor)

    with pytest.raises(ParallelCollectionError) as caught:
        ParallelCollectionCoordinator().run((job(0, "ALPARI_1"),), 1)

    assert not isinstance(caught.value, DemoSafetyError)


def test_the_pool_is_drained_before_the_failure_is_raised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every job must reach a terminal state before the error propagates.

    Raising from inside the `with` block unwound into the executor's shutdown,
    which stopped the pool while the remaining workers were still writing.
    """
    executor_state: dict[str, int] = {}

    class TrackingExecutor(FakeExecutor):
        def __enter__(self) -> TrackingExecutor:
            executor_state["entered"] = executor_state.get("entered", 0) + 1
            return self

        def __exit__(self, *_: object) -> None:
            executor_state["exited"] = executor_state.get("exited", 0) + 1
            return None

        def submit(
            self, function: object, collection_job: CollectionJob
        ) -> Future[CollectionBatch]:
            future: Future[CollectionBatch] = Future()
            if collection_job.broker_profile == "A":
                future.set_exception(MT5ConnectionError("terminal closed"))
            else:
                future.set_result(CollectionBatch("B", ()))
            return future

    _patch_executor(monkeypatch, TrackingExecutor)

    with pytest.raises(ParallelCollectionError):
        ParallelCollectionCoordinator().run((job(0, "A"), job(1, "B")), 2)

    assert executor_state.get("exited") == 1, "the pool must be shut down cleanly first"


def test_every_failing_profile_is_named_not_just_the_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingExecutor(FakeExecutor):
        def submit(
            self, function: object, collection_job: CollectionJob
        ) -> Future[CollectionBatch]:
            future: Future[CollectionBatch] = Future()
            future.set_exception(MT5ConnectionError(f"boom {collection_job.broker_profile}"))
            return future

    _patch_executor(monkeypatch, FailingExecutor)

    with pytest.raises(ParallelCollectionError) as caught:
        ParallelCollectionCoordinator().run((job(0, "A"), job(1, "B")), 2)

    message = str(caught.value)
    assert "A" in message and "B" in message
    assert "2 broker profile" in message


def test_a_quality_failure_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed quality check is a verdict, not a transient fault.

    Retrying it re-ran the request, and each attempt minted a new `dataset_id`,
    so three attempts produced three partially-written datasets where one error
    was reported.
    """
    attempts: list[str] = []

    class FakeAdapter:
        def __init__(self, settings: MT5Settings) -> None:
            self.settings = settings

        def __enter__(self) -> FakeAdapter:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def symbols(self, visible_only: bool = ...) -> list[str]:
            return ["EURUSD", "GBPUSD"]

    class FakeRepository:
        def __init__(self, raw_directory: object) -> None:
            self.raw_directory = raw_directory

        def write(self, frame: object, manifest: object) -> object:
            return manifest

    class ExplodingCollector:
        def __init__(self, adapter: object, repository: object) -> None:
            self.adapter = adapter
            self.repository = repository

        def collect(self, request: object) -> CollectionBatch:
            attempts.append(request.broker_profile)  # type: ignore[attr-defined]
            raise DataQualityError("quality check failed")

    module = "market_relationship_discovery.application.parallel_collection"
    monkeypatch.setattr(f"{module}.MT5Adapter", FakeAdapter)
    monkeypatch.setattr(f"{module}.ParquetQuoteRepository", FakeRepository)
    monkeypatch.setattr(f"{module}.HistoricalCollector", ExplodingCollector)

    from market_relationship_discovery.application.parallel_collection import (
        collect_broker_job,
    )

    with pytest.raises(DataQualityError):
        collect_broker_job(job(0, "A", ("EURUSD", "GBPUSD")))

    assert len(attempts) == 1, f"a quality failure was retried {len(attempts)} times"


def test_a_connection_failure_does_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """The retry that remains must be the one that can resolve."""
    attempts: list[int] = []

    class FakeAdapter:
        def __init__(self, settings: MT5Settings) -> None:
            self.settings = settings

        def __enter__(self) -> FakeAdapter:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def symbols(self, visible_only: bool = ...) -> list[str]:
            return ["EURUSD"]

    class FakeRepository:
        def __init__(self, raw_directory: object) -> None:
            self.raw_directory = raw_directory

    class FlakyCollector:
        def __init__(self, adapter: object, repository: object) -> None:
            self.adapter = adapter
            self.repository = repository

        def collect(self, request: object) -> CollectionBatch:
            attempts.append(1)
            if len(attempts) < 2:
                raise MT5ConnectionError("feed stalled")
            return CollectionBatch("A", (cast(StoredDataset, object()),))

    module = "market_relationship_discovery.application.parallel_collection"
    monkeypatch.setattr(f"{module}.MT5Adapter", FakeAdapter)
    monkeypatch.setattr(f"{module}.ParquetQuoteRepository", FakeRepository)
    monkeypatch.setattr(f"{module}.HistoricalCollector", FlakyCollector)
    monkeypatch.setattr(f"{module}.time.sleep", lambda seconds: None)

    from market_relationship_discovery.application.parallel_collection import (
        collect_broker_job,
    )

    result = collect_broker_job(job(0, "A", ("EURUSD",)))

    assert len(attempts) == 2
    assert result.broker_profile == "A"
