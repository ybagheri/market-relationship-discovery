from __future__ import annotations

from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from market_relationship_discovery.application.collector import (
    CollectionRequest,
    HistoricalCollector,
)
from market_relationship_discovery.config.settings import MT5Settings
from market_relationship_discovery.domain.dataset import CollectionBatch, DataType
from market_relationship_discovery.domain.errors import MarketRelationshipError
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
        worker_count = min(max_workers, len(jobs))
        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            futures: dict[Future[CollectionBatch], CollectionJob] = {
                executor.submit(collect_broker_job, job): job for job in jobs
            }
            for future in as_completed(futures):
                job = futures[future]
                try:
                    results[job.order] = future.result()
                except Exception as exc:
                    raise ParallelCollectionError(
                        f"parallel collection failed for broker profile {job.broker_profile}: {exc}"
                    ) from exc
        return tuple(results[order] for order in sorted(results))


def collect_broker_job(job: CollectionJob) -> CollectionBatch:
    with MT5Adapter(job.mt5_settings) as adapter:
        available = adapter.symbols(visible_only=False)
        mapper = SymbolMapper(job.symbol_mapping)
        broker_symbols = tuple(
            mapper.resolve(symbol, available).broker_symbol for symbol in job.canonical_symbols
        )
        request = CollectionRequest(
            broker_profile=job.broker_profile,
            symbols=broker_symbols,
            data_type=job.data_type,
            timeframe=job.timeframe,
            start=job.start,
            end=job.end,
            limit=job.limit,
            source_utc_offset_minutes=job.mt5_settings.source_utc_offset_minutes,
        )
        repository = ParquetQuoteRepository(job.raw_directory)
        return HistoricalCollector(adapter, repository).collect(request)
