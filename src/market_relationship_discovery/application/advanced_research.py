from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from market_relationship_discovery.discovery.evaluator import GraphCandidateEvaluator
from market_relationship_discovery.discovery.graph import GraphRelationshipDiscoveryEngine
from market_relationship_discovery.discovery.ranker import (
    CandidateRankingConfig,
    RidgeCandidateRanker,
)
from market_relationship_discovery.domain.experiment import create_experiment_manifest
from market_relationship_discovery.market_data.panel import load_price_panel
from market_relationship_discovery.relationships.catalog import RelationshipCatalog
from market_relationship_discovery.relationships.graph import RelationshipGraph
from market_relationship_discovery.reporting.experiment import ExperimentReportWriter
from market_relationship_discovery.statistics.regime import RegimeDetector

DEFAULT_RANKING_CONFIG = CandidateRankingConfig()


class AdvancedDiscoveryService:
    def run(
        self,
        source_path: Path,
        *,
        minimum_observations: int = 30,
        regime_window: int = 20,
        regime_low_quantile: float = 0.20,
        regime_high_quantile: float = 0.80,
        max_depth: int = 1,
        rolling_beta_window: int = 30,
        statistical_significance: float = 0.05,
        ranking_config: CandidateRankingConfig = DEFAULT_RANKING_CONFIG,
        output_directory: Path | None = None,
    ) -> dict[str, object]:
        prices = load_price_panel(source_path)
        if prices.empty:
            raise ValueError("advanced research source is empty")
        symbols = tuple(sorted(str(column) for column in prices.columns))
        graph = RelationshipGraph.from_definitions(RelationshipCatalog().all())
        candidates = GraphRelationshipDiscoveryEngine(graph, max_depth=max_depth).discover(symbols)
        evaluations = GraphCandidateEvaluator().evaluate(
            prices,
            candidates,
            minimum_observations=minimum_observations,
            regime_window=regime_window,
            regime_low_quantile=regime_low_quantile,
            regime_high_quantile=regime_high_quantile,
            rolling_beta_window=rolling_beta_window,
            statistical_significance=statistical_significance,
        )
        ranking = RidgeCandidateRanker().rank(evaluations, ranking_config)
        regimes = {
            str(symbol): RegimeDetector()
            .detect(
                prices[symbol],
                window=regime_window,
                low_quantile=regime_low_quantile,
                high_quantile=regime_high_quantile,
            )
            .summary()
            for symbol in symbols
        }
        payload: dict[str, object] = {
            "regimes": regimes,
            "graph": {
                "nodes": list(graph.nodes),
                "edges": [asdict(edge) for edge in graph.edges],
                "max_depth": max_depth,
            },
            "candidates": [
                {
                    "name": evaluation.candidate.name,
                    "target": evaluation.candidate.target,
                    "formula": evaluation.candidate.formula,
                    "status": evaluation.candidate.status.value,
                    "summary": evaluation.summary,
                }
                for evaluation in evaluations
            ],
            "ranking": {
                "model": ranking.model,
                "feature_names": list(ranking.feature_names),
                "training_end": ranking.training_end,
                "evaluation_start": ranking.evaluation_start,
                "candidates": [asdict(candidate) for candidate in ranking.candidates],
            },
            "limitations": [
                "Regime thresholds are causal expanding quantiles, not forecasts.",
                "ML-assisted ranking is a deterministic research ordering, not profitability "
                "evidence.",
                "Bar prices and formula relationships do not establish tick execution.",
                "Cointegration, ADF, and KPSS are retrospective full-sample diagnostics.",
            ],
        }
        manifest = create_experiment_manifest(
            "advanced_relationship_discovery",
            source_path,
            prices.index[0].to_pydatetime(),
            prices.index[-1].to_pydatetime(),
            {
                "minimum_observations": minimum_observations,
                "regime_window": regime_window,
                "regime_low_quantile": regime_low_quantile,
                "regime_high_quantile": regime_high_quantile,
                "max_depth": max_depth,
                "rolling_beta_window": rolling_beta_window,
                "statistical_significance": statistical_significance,
                "training_fraction": ranking_config.training_fraction,
                "ridge_alpha": ranking_config.ridge_alpha,
                "minimum_train_rows": ranking_config.minimum_train_rows,
            },
        )
        response: dict[str, object] = {"experiment": manifest.to_dict(), "results": payload}
        if output_directory is not None:
            response["report_path"] = str(
                ExperimentReportWriter(output_directory).write(payload, manifest)
            )
        return response
