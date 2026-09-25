from __future__ import annotations

from concurrent.futures import Future

import pytest

from market_relationship_discovery.application.parallel_collection import (
    CollectionJob,
    ParallelCollectionCoordinator,
    ParallelCollectionError,
)
from market_relationship_discovery.config.settings import MT5Settings
from market_relationship_discovery.domain.dataset import CollectionBatch, DataType


class FakeExecutor:
    instance: FakeExecutor | None = None

    def __init__(self, max_workers: int) -> None:
        self.max_workers = max_workers
        self.jobs: list[CollectionJob] = []
        FakeExecutor.instance = self

    def __enter__(self) -> FakeExecutor:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def submit(self, function: object, job: CollectionJob) -> Future[CollectionBatch]:
        self.jobs.append(job)
        future: Future[CollectionBatch] = Future()
        future.set_result(function(job))
        return future


def job(order: int, profile: str) -> CollectionJob:
    return CollectionJob(
        order,
        profile,
        MT5Settings(),
        {},
        ("EURUSD",),
        DataType.BAR,
        "M1",
        None,
        None,
        10,
        "data/raw",
    )


def test_parallel_coordinator_preserves_profile_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "market_relationship_discovery.application.parallel_collection.ProcessPoolExecutor",
        FakeExecutor,
    )
    monkeypatch.setattr(
        "market_relationship_discovery.application.parallel_collection.collect_broker_job",
        lambda item: CollectionBatch(item.broker_profile, ()),
    )
    jobs = (job(1, "B"), job(0, "A"))

    result = ParallelCollectionCoordinator().run(jobs, 4)

    assert [batch.broker_profile for batch in result] == ["A", "B"]
    assert FakeExecutor.instance is not None
    assert FakeExecutor.instance.max_workers == 2


def test_parallel_coordinator_rejects_duplicate_profiles() -> None:
    with pytest.raises(ValueError, match="unique"):
        ParallelCollectionCoordinator().run((job(0, "A"), job(1, "A")), 2)


def test_parallel_coordinator_wraps_worker_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingExecutor(FakeExecutor):
        def submit(
            self, function: object, collection_job: CollectionJob
        ) -> Future[CollectionBatch]:
            future: Future[CollectionBatch] = Future()
            future.set_exception(RuntimeError("terminal failed"))
            return future

    monkeypatch.setattr(
        "market_relationship_discovery.application.parallel_collection.ProcessPoolExecutor",
        FailingExecutor,
    )

    with pytest.raises(ParallelCollectionError, match="broker profile A"):
        ParallelCollectionCoordinator().run((job(0, "A"),), 1)
