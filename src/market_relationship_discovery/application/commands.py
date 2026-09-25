from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from market_relationship_discovery.application.collector import (
    CollectionRequest,
    HistoricalCollector,
)
from market_relationship_discovery.application.experiments import ResearchExperimentService
from market_relationship_discovery.config.settings import MT5Settings, Settings
from market_relationship_discovery.discovery.engine import CandidateDiscoveryEngine
from market_relationship_discovery.domain.dataset import CollectionBatch, DataType
from market_relationship_discovery.domain.errors import MarketRelationshipError
from market_relationship_discovery.infrastructure.mt5.adapter import MT5Adapter
from market_relationship_discovery.infrastructure.storage.quotes import ParquetQuoteRepository
from market_relationship_discovery.market_data.symbols import SymbolMapper
from market_relationship_discovery.relationships.catalog import RelationshipCatalog
from market_relationship_discovery.research.service import HistoricalRelationshipResearcher


def collect_historical_data(
    settings: Settings,
    broker_profiles: list[str],
    canonical_symbols: list[str],
    data_type: DataType,
    timeframe: str | None,
    start: datetime | None,
    end: datetime | None,
    limit: int | None,
) -> dict[str, object]:
    batches: list[CollectionBatch] = []
    for profile_name in broker_profiles:
        profile, mapping = resolve_profile(settings, profile_name)
        with MT5Adapter(profile) as adapter:
            available = adapter.symbols(visible_only=False)
            mapper = SymbolMapper(mapping)
            broker_symbols = tuple(
                mapper.resolve(symbol, available).broker_symbol for symbol in canonical_symbols
            )
            request = CollectionRequest(
                broker_profile=profile_name,
                symbols=broker_symbols,
                data_type=data_type,
                timeframe=timeframe,
                start=start,
                end=end,
                limit=limit,
                source_utc_offset_minutes=profile.source_utc_offset_minutes,
            )
            repository = ParquetQuoteRepository(settings.data.raw_directory)
            batches.append(HistoricalCollector(adapter, repository).collect(request))
    return {
        "batches": [
            {
                "broker_profile": batch.broker_profile,
                "rows": batch.rows,
                "datasets": [
                    {
                        "data_path": str(dataset.data_path),
                        "manifest_path": str(dataset.manifest_path),
                        "manifest": dataset.manifest.to_dict(),
                    }
                    for dataset in batch.datasets
                ],
            }
            for batch in batches
        ]
    }


def discover_relationships(
    symbols: list[str],
    minimum_observations: int,
) -> dict[str, object]:
    candidates = CandidateDiscoveryEngine().generate(symbols, minimum_observations)
    return {
        "candidates": [asdict(candidate) for candidate in candidates],
        "disclaimer": "Research candidates are not guaranteed profitable or executable.",
    }


def run_historical_research(
    settings: Settings,
    broker_profile: str,
    relationship_name: str,
    timeframe: str,
    limit: int,
) -> dict[str, object]:
    catalog = RelationshipCatalog()
    relationship = next(
        (item for item in catalog.all() if item.name.casefold() == relationship_name.casefold()),
        None,
    )
    if relationship is None:
        raise MarketRelationshipError(f"Unknown relationship: {relationship_name}")
    profile, mapping = resolve_profile(settings, broker_profile)
    with MT5Adapter(profile) as adapter:
        available = adapter.symbols(visible_only=False)
        mapper = SymbolMapper(mapping)
        required_symbols = sorted(relationship.dependencies() | {relationship.target})
        broker_symbols = {
            symbol: mapper.resolve(symbol, available).broker_symbol for symbol in required_symbols
        }
        series: dict[str, pd.DataFrame] = {}
        for canonical, broker_symbol in broker_symbols.items():
            bars = adapter.recent_bars(broker_symbol, timeframe, limit)
            series[canonical] = pd.DataFrame(
                [
                    {
                        "timestamp": bar.timestamp,
                        "broker": bar.broker,
                        "symbol": bar.symbol,
                        "close": bar.close,
                    }
                    for bar in bars
                ]
            )
        broker_server = adapter.account_info().server
        summary = HistoricalRelationshipResearcher(
            settings.data.max_alignment_delay_ms,
            settings.research.zscore_window,
            settings.research.minimum_observations,
        ).run(relationship, series)
    return {
        "broker_profile": broker_profile,
        "broker": broker_server,
        "timeframe": timeframe,
        "symbols": broker_symbols,
        "summary": summary.to_dict(),
        "limitations": [
            "Bar close data cannot establish a tick-level executable discrepancy.",
            "Correlation and historical discrepancy do not guarantee future returns.",
        ],
    }


def run_no_lookahead_backtest(
    path: Path,
    signal_column: str,
    gross_edge_column: str,
    cost_column: str,
    output_directory: Path | None = None,
) -> dict[str, object]:
    return ResearchExperimentService().run_no_lookahead(
        path,
        signal_column,
        gross_edge_column,
        cost_column,
        output_directory,
    )


def resolve_profile(settings: Settings, name: str) -> tuple[MT5Settings, dict[str, str]]:
    if name == "default":
        return settings.mt5, settings.symbol_mapping
    profile = settings.brokers.get(name)
    if profile is None:
        available = sorted(settings.brokers)
        raise MarketRelationshipError(f"Unknown broker profile {name!r}; configured: {available}")
    return profile, profile.symbol_mapping or settings.symbol_mapping
