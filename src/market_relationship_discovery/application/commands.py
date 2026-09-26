from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from market_relationship_discovery.application.advanced_research import AdvancedDiscoveryService
from market_relationship_discovery.application.experiments import ResearchExperimentService
from market_relationship_discovery.application.parallel_collection import (
    CollectionJob,
    ParallelCollectionCoordinator,
    collect_broker_job,
)
from market_relationship_discovery.config.settings import MT5Settings, Settings
from market_relationship_discovery.discovery.engine import CandidateDiscoveryEngine
from market_relationship_discovery.domain.dataset import CollectionBatch, DataType
from market_relationship_discovery.domain.errors import MarketRelationshipError
from market_relationship_discovery.infrastructure.mt5.adapter import MT5Adapter
from market_relationship_discovery.market_data.symbols import SymbolMapper
from market_relationship_discovery.relationships.catalog import RelationshipCatalog
from market_relationship_discovery.research.service import HistoricalRelationshipResearcher
from market_relationship_discovery.statistics.multiplicity import (
    DEFAULT_METHOD as DEFAULT_MULTIPLICITY_METHOD,
)
from market_relationship_discovery.statistics.multiplicity import MultiplicityMethod


def collect_historical_data(
    settings: Settings,
    broker_profiles: list[str],
    canonical_symbols: list[str],
    data_type: DataType,
    timeframe: str | None,
    start: datetime | None,
    end: datetime | None,
    limit: int | None,
    parallel: bool = False,
    max_workers: int | None = None,
) -> dict[str, object]:
    if parallel:
        jobs = tuple(
            _build_collection_job(
                settings,
                order,
                profile_name,
                canonical_symbols,
                data_type,
                timeframe,
                start,
                end,
                limit,
            )
            for order, profile_name in enumerate(broker_profiles)
        )
        batches = ParallelCollectionCoordinator().run(
            jobs,
            max_workers or settings.data.collection_max_workers,
        )
    else:
        batches = tuple(
            _collect_broker_job(
                settings,
                profile_name,
                canonical_symbols,
                data_type,
                timeframe,
                start,
                end,
                limit,
            )
            for profile_name in broker_profiles
        )
    return _collection_payload(batches)


def _build_collection_job(
    settings: Settings,
    order: int,
    profile_name: str,
    canonical_symbols: list[str],
    data_type: DataType,
    timeframe: str | None,
    start: datetime | None,
    end: datetime | None,
    limit: int | None,
) -> CollectionJob:
    profile, mapping = resolve_profile(settings, profile_name)
    return CollectionJob(
        order,
        profile_name,
        profile,
        mapping,
        tuple(canonical_symbols),
        data_type,
        timeframe,
        start,
        end,
        limit,
        settings.data.raw_directory,
        settings.data.collection_attempts,
    )


def _collect_broker_job(
    settings: Settings,
    profile_name: str,
    canonical_symbols: list[str],
    data_type: DataType,
    timeframe: str | None,
    start: datetime | None,
    end: datetime | None,
    limit: int | None,
) -> CollectionBatch:
    return collect_broker_job(
        _build_collection_job(
            settings,
            0,
            profile_name,
            canonical_symbols,
            data_type,
            timeframe,
            start,
            end,
            limit,
        )
    )


def _collection_payload(batches: tuple[CollectionBatch, ...]) -> dict[str, object]:
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


def run_advanced_research(
    source_path: Path,
    minimum_observations: int,
    regime_window: int,
    regime_low_quantile: float,
    regime_high_quantile: float,
    max_depth: int,
    training_fraction: float,
    ridge_alpha: float,
    rolling_beta_window: int = 30,
    statistical_significance: float = 0.05,
    output_directory: Path | None = None,
    multiplicity_method: MultiplicityMethod = DEFAULT_MULTIPLICITY_METHOD,
    minimum_symbols_for_window: int = 2,
) -> dict[str, object]:
    from market_relationship_discovery.discovery.ranker import CandidateRankingConfig

    return AdvancedDiscoveryService().run(
        source_path,
        minimum_observations=minimum_observations,
        regime_window=regime_window,
        regime_low_quantile=regime_low_quantile,
        regime_high_quantile=regime_high_quantile,
        max_depth=max_depth,
        rolling_beta_window=rolling_beta_window,
        statistical_significance=statistical_significance,
        ranking_config=CandidateRankingConfig(
            training_fraction=training_fraction,
            ridge_alpha=ridge_alpha,
        ),
        output_directory=output_directory,
        multiplicity_method=multiplicity_method,
        minimum_symbols_for_window=minimum_symbols_for_window,
    )


def run_historical_research(
    settings: Settings,
    broker_profile: str,
    relationship_name: str,
    timeframe: str,
    limit: int,
    rolling_beta_window: int = 30,
    statistical_significance: float = 0.05,
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
            rolling_beta_window,
            statistical_significance,
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
