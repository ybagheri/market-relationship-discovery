from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import cast

import pandas as pd

from market_relationship_discovery.domain.errors import DataQualityError
from market_relationship_discovery.domain.experiment import create_experiment_manifest
from market_relationship_discovery.market_data.contract import ContractSpecification
from market_relationship_discovery.market_data.cross_broker import (
    ComparisonKind,
    CrossBrokerComparisonEngine,
    CrossBrokerRequest,
    SynchronizationMode,
    TickAggregation,
)
from market_relationship_discovery.reporting.experiment import ExperimentReportWriter


class CrossBrokerExperimentService:
    def run(
        self,
        source_a: Path,
        source_b: Path,
        broker_a: str,
        broker_b: str,
        symbol: str,
        comparison_kind: ComparisonKind,
        max_alignment_delay_ms: int,
        additional_cost: float,
        output_directory: Path | None = None,
        contract_a_path: Path | None = None,
        contract_b_path: Path | None = None,
        synchronization_mode: SynchronizationMode = SynchronizationMode.ANCHOR_A,
        tick_aggregation: TickAggregation = TickAggregation.LAST,
        volume: float = 1.0,
        leverage: int | None = None,
        minimum_fill_ratio: float = 0.0,
        symbol_a: str | None = None,
        symbol_b: str | None = None,
    ) -> dict[str, object]:
        """Compare two broker feeds for the same research instrument.

        ``symbol`` is the research symbol used for reporting. Brokers rarely name
        an instrument identically, and collection stores the broker name, so
        ``symbol_a`` and ``symbol_b`` select the label actually present in each
        source. Without them a cross-broker study is impossible whenever the
        names differ, which is the normal case.
        """
        resolved_symbol_a = symbol_a or symbol
        resolved_symbol_b = symbol_b or symbol
        frame_a = self._load(source_a, resolved_symbol_a, symbol)
        frame_b = self._load(source_b, resolved_symbol_b, symbol)
        request = CrossBrokerRequest(
            broker_a,
            broker_b,
            symbol,
            comparison_kind,
            max_alignment_delay_ms,
            additional_cost,
            self._load_contract(contract_a_path),
            self._load_contract(contract_b_path),
            synchronization_mode,
            tick_aggregation,
            volume,
            leverage,
            minimum_fill_ratio,
        )
        analysis = CrossBrokerComparisonEngine().compare(frame_a, frame_b, request)
        start = min(frame_a["timestamp"].min(), frame_b["timestamp"].min()).to_pydatetime()
        end = max(frame_a["timestamp"].max(), frame_b["timestamp"].max()).to_pydatetime()
        manifest = create_experiment_manifest(
            "cross_broker_comparison",
            source_a,
            start,
            end,
            {
                "source_b_file_name": source_b.name,
                "broker_a": broker_a,
                "broker_b": broker_b,
                "symbol": symbol,
                "symbol_a": resolved_symbol_a,
                "symbol_b": resolved_symbol_b,
                "comparison_kind": comparison_kind.value,
                "max_alignment_delay_ms": max_alignment_delay_ms,
                "additional_cost": additional_cost,
                "contract_a_file_name": (contract_a_path.name if contract_a_path else None),
                "contract_b_file_name": (contract_b_path.name if contract_b_path else None),
                "synchronization_mode": synchronization_mode.value,
                "tick_aggregation": tick_aggregation.value,
                "volume": volume,
                "leverage": leverage,
                "minimum_fill_ratio": minimum_fill_ratio,
            },
            (source_b,),
        )
        execution = analysis.summary.execution
        payload: dict[str, object] = {
            "summary": asdict(analysis.summary),
            "opportunities": [asdict(opportunity) for opportunity in analysis.opportunities],
            "aligned_preview": self._preview(analysis.aligned_observations),
            "execution": (execution.to_dict() if execution is not None else None),
            "limitations": [
                "Crossable is a positive research edge after configured additional cost, "
                "not guaranteed execution.",
                "Broker feeds, symbols, sessions, latency, and contract specifications may differ.",
                "Bar comparisons are theoretical and never classified as crossable.",
                "Margin is unavailable when the broker does not report it and no leverage is "
                "configured; an unknown margin is never treated as free margin.",
                "Fill estimates respect volume step and maximum but do not model queue position, "
                "partial-fill probability, or rejection.",
            ],
        }
        response: dict[str, object] = {
            "experiment": manifest.to_dict(),
            "results": payload,
        }
        if output_directory is not None:
            response["report_path"] = str(
                ExperimentReportWriter(output_directory).write(payload, manifest)
            )
        return response

    @staticmethod
    def _load_contract(path: Path | None) -> ContractSpecification | None:
        if path is None:
            return None
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            if len(payload) != 1 or not isinstance(payload[0], dict):
                raise ValueError("contract file must contain exactly one specification")
            payload = payload[0]
        if not isinstance(payload, dict):
            raise ValueError("contract file must contain a specification object")
        return ContractSpecification.from_dict(payload)

    @staticmethod
    def _load(path: Path, symbol: str, canonical_symbol: str) -> pd.DataFrame:
        frame = pd.read_parquet(path) if path.suffix.lower() == ".parquet" else pd.read_csv(path)
        if "symbol" not in frame:
            raise DataQualityError("cross-broker source requires a symbol column")
        frame = frame[frame["symbol"].astype(str) == symbol].copy()
        if frame.empty:
            raise DataQualityError(f"cross-broker source has no rows for {symbol}")
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="raise")
        # Relabel to the research symbol so both feeds carry one comparable
        # identity downstream while the broker label stays recorded here.
        frame["broker_symbol"] = symbol
        frame["symbol"] = canonical_symbol
        return frame

    @staticmethod
    def _preview(frame: pd.DataFrame) -> list[dict[str, object]]:
        preview = frame.head(20).copy()
        for column in ("timestamp", "broker_b_timestamp"):
            if column in preview:
                preview[column] = preview[column].map(
                    lambda value: value.isoformat() if pd.notna(value) else None
                )
        preview = preview.astype(object).where(pd.notna(preview), None)
        return cast(list[dict[str, object]], preview.to_dict(orient="records"))
