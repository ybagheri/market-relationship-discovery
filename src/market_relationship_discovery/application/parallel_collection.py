from __future__ import annotations

import time
from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from market_relationship_discovery.application.collector import (
    CollectionRequest,
    HistoricalCollector,
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
    MarketRelationshipError,
    MT5ConnectionError,
)
from market_relationship_discovery.infrastructure.mt5.adapter import MT5Adapter
from market_relationship_discovery.infrastructure.storage.quotes import ParquetQuoteRepository
from market_relationship_discovery.market_data.symbols import SymbolMapper


@dataclass(frozen=True, slots=True)
class CollectionJob:
    order: int
    broker_profile: str
    mt5_settings: MT5Settings
    symbol_mapping: dict[str, str]
    canonical_symbols: tuple[str, ...]
    data_type: DataType
    timeframe: str | None
    start: datetime | None
    end: datetime | None
    limit: int | None
    raw_directory: Path
    collection_attempts: int = 3


class ParallelCollectionError(MarketRelationshipError):
    pass


class ParallelCollectionCoordinator:
    def run(
        self,
        jobs: tuple[CollectionJob, ...],
        max_workers: int,
    ) -> tuple[CollectionBatch, ...]:
        if max_workers < 1:
            raise ValueError("max_workers must be positive")
        if not jobs:
            raise ValueError("at least one collection job is required")
        if len({job.broker_profile for job in jobs}) != len(jobs):
            raise ValueError("broker profiles must be unique for parallel collection")
        results: dict[int, CollectionBatch] = {}
        failures: list[tuple[CollectionJob, BaseException]] = []
        worker_count = min(max_workers, len(jobs))
        # A failure is collected rather than raised from inside the `with` block.
        # Raising there unwinds into the executor's own shutdown, which stops the
        # pool while the other workers are still writing datasets: the run then
        # reports a failure *and* leaves half-written output on disk. Letting the
        # pool drain first means every job reaches a terminal state and the
        # failure names every profile that failed, not just the first to finish.
        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            futures: dict[Future[CollectionBatch], CollectionJob] = {
                executor.submit(collect_broker_job, job): job for job in jobs
            }
            for future in as_completed(futures):
                job = futures[future]
                try:
                    results[job.order] = future.result()
                except Exception as exc:
                    failures.append((job, exc))
        if failures:
            self._raise_for(failures, succeeded=sorted(results))
        return tuple(results[order] for order in sorted(results))

    @staticmethod
    def _raise_for(
        failures: list[tuple[CollectionJob, BaseException]],
        succeeded: list[int],
    ) -> None:
        """Raise the most specific failure, summarising the rest.

        A `DemoSafetyError` means the terminal connected and the account was not
        provably demo. That is the platform working as intended, not a transient
        connection error, and wrapping it as `ParallelCollectionError` makes a
        safety refusal indistinguishable by type from a retryable failure. The
        safety error is therefore re-raised as itself, so the caller keeps the
        distinction that the sequential path and `doctor` both preserve. Any
        other failure is reported once, naming every profile that failed rather
        than only the first to finish.
        """
        for job, exc in failures:
            if isinstance(exc, DemoSafetyError):
                raise DemoSafetyError(
                    f"parallel collection refused for broker profile "
                    f"{job.broker_profile}: {exc}"
                ) from exc
        details = "; ".join(f"{job.broker_profile}: {exc}" for job, exc in failures)
        raise ParallelCollectionError(
            f"parallel collection failed for {len(failures)} broker profile(s) "
            f"({details}); {len(succeeded)} completed"
        )


def collect_broker_job(job: CollectionJob) -> CollectionBatch:
    """Collect one broker profile, retrying only failures that can resolve.

    Retries are per *symbol* rather than per request. A whole-request retry
    re-runs the symbols that already succeeded, and every run mints a fresh
    `dataset_id`, so a failure on the last symbol leaves the earlier datasets
    orphaned on disk with no manifest referencing them. Retrying one symbol
    collects each one exactly once per attempt, so a successful collection
    cannot be duplicated by a later failure.

    `DataQualityError` is not retried. It is the data failing a check, not a
    transient condition, so repeating the same request repeats the same verdict
    three times and then reports one error in place of three identical ones.
    """
    last_error: MT5ConnectionError | None = None
    collected: dict[str, StoredDataset] = {}
    pending = list(dict.fromkeys(job.canonical_symbols))
    for attempt in range(1, job.collection_attempts + 1):
        if not pending:
            break
        try:
            with MT5Adapter(job.mt5_settings) as adapter:
                mapper = SymbolMapper(job.symbol_mapping)
                for symbol in pending:
                    resolved = mapper.resolve(symbol, adapter.symbols(visible_only=False))
                    request = CollectionRequest(
                        broker_profile=job.broker_profile,
                        symbols=(resolved.broker_symbol,),
                        data_type=job.data_type,
                        timeframe=job.timeframe,
                        start=job.start,
                        end=job.end,
                        limit=job.limit,
                        source_utc_offset_minutes=job.mt5_settings.source_utc_offset_minutes,
                        tick_lookback_hours=job.mt5_settings.tick_max_lookback_hours,
                    )
                    repository = ParquetQuoteRepository(job.raw_directory)
                    batch = HistoricalCollector(adapter, repository).collect(request)
                    # Only symbols that have not already been written are
                    # retried, so a symbol collected on an earlier attempt is
                    # never written twice under a second dataset_id.
                    collected[symbol] = batch.datasets[0]
            pending = []
        except DataQualityError:
            # A failed quality check is a verdict about the data, not a
            # transient fault. Retrying it would mint a new dataset_id per
            # attempt and orphan each superseded one.
            raise
        except MT5ConnectionError as exc:
            last_error = exc
            pending = [symbol for symbol in pending if symbol not in collected]
            if attempt < job.collection_attempts and pending:
                time.sleep(0.5 * attempt)
                continue
            raise
    if len(collected) != len(dict.fromkeys(job.canonical_symbols)):
        if last_error is not None:
            raise last_error
        raise ParallelCollectionError(
            f"collection did not complete for {job.broker_profile}: "
            f"{sorted(collected)} collected, {pending} missing"
        )
    return CollectionBatch(job.broker_profile, tuple(collected.values()))
