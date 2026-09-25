from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from market_relationship_discovery.discovery.evaluator import EvaluatedCandidate


@dataclass(frozen=True, slots=True)
class CandidateRankingConfig:
    training_fraction: float = 0.70
    ridge_alpha: float = 1.0
    minimum_train_rows: int = 30
    minimum_evaluation_rows: int = 1


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    name: str
    rank: int
    predicted_mean_next_abs_zscore: float
    out_of_sample_rmse: float
    evaluation_rows: int


@dataclass(frozen=True, slots=True)
class CandidateRankingResult:
    model: str
    feature_names: tuple[str, ...]
    training_end: pd.Timestamp | None
    evaluation_start: pd.Timestamp | None
    candidates: tuple[RankedCandidate, ...]


DEFAULT_RANKING_CONFIG = CandidateRankingConfig()


class RidgeCandidateRanker:
    feature_names = (
        "abs_zscore",
        "discrepancy_volatility",
        "regime_low",
        "regime_normal",
        "regime_high",
        "pearson",
        "spearman",
        "half_life",
        "observation_fraction",
    )

    def rank(
        self,
        evaluations: Sequence[EvaluatedCandidate],
        config: CandidateRankingConfig = DEFAULT_RANKING_CONFIG,
    ) -> CandidateRankingResult:
        if not 0.0 < config.training_fraction < 1.0:
            raise ValueError("training_fraction must be between zero and one")
        if config.ridge_alpha <= 0:
            raise ValueError("ridge_alpha must be positive")
        rows = self._rows(evaluations)
        if not rows:
            return CandidateRankingResult("numpy_ridge", self.feature_names, None, None, ())
        frame = pd.DataFrame(rows, columns=["timestamp", "name", "target", *self.feature_names])
        frame = frame.sort_values(["timestamp", "name"], kind="stable").reset_index(drop=True)
        timestamps = frame["timestamp"].drop_duplicates().tolist()
        split = max(1, int(len(timestamps) * config.training_fraction))
        if split >= len(timestamps):
            return CandidateRankingResult("numpy_ridge", self.feature_names, None, None, ())
        train = frame[frame["timestamp"].isin(timestamps[:split])]
        evaluation = frame[frame["timestamp"].isin(timestamps[split:])]
        if (
            len(train) < config.minimum_train_rows
            or len(evaluation) < config.minimum_evaluation_rows
        ):
            return CandidateRankingResult(
                "numpy_ridge",
                self.feature_names,
                train["timestamp"].max(),
                evaluation["timestamp"].min() if not evaluation.empty else None,
                (),
            )
        train_matrix = train[list(self.feature_names)].to_numpy(dtype=float)
        evaluation_matrix = evaluation[list(self.feature_names)].to_numpy(dtype=float)
        mean = train_matrix.mean(axis=0)
        scale = train_matrix.std(axis=0)
        scale[scale == 0.0] = 1.0
        train_scaled = (train_matrix - mean) / scale
        evaluation_scaled = (evaluation_matrix - mean) / scale
        design = np.column_stack([np.ones(len(train_scaled)), train_scaled])
        penalty = np.eye(design.shape[1])
        penalty[0, 0] = 0.0
        coefficients = np.linalg.solve(
            design.T @ design + config.ridge_alpha * penalty,
            design.T @ train["target"].to_numpy(dtype=float),
        )
        evaluation_design = np.column_stack([np.ones(len(evaluation_scaled)), evaluation_scaled])
        predictions = evaluation_design @ coefficients
        evaluation = evaluation.assign(prediction=predictions)
        summaries: list[RankedCandidate] = []
        for name, group in evaluation.groupby("name", sort=True):
            summaries.append(
                RankedCandidate(
                    name=str(name),
                    rank=0,
                    predicted_mean_next_abs_zscore=float(group["prediction"].mean()),
                    out_of_sample_rmse=float(
                        np.sqrt(np.mean(np.square(group["prediction"] - group["target"])))
                    ),
                    evaluation_rows=len(group),
                )
            )
        summaries.sort(key=lambda item: (-item.predicted_mean_next_abs_zscore, item.name))
        ranked = tuple(
            RankedCandidate(
                name=item.name,
                rank=rank,
                predicted_mean_next_abs_zscore=item.predicted_mean_next_abs_zscore,
                out_of_sample_rmse=item.out_of_sample_rmse,
                evaluation_rows=item.evaluation_rows,
            )
            for rank, item in enumerate(summaries, start=1)
        )
        return CandidateRankingResult(
            "numpy_ridge",
            self.feature_names,
            train["timestamp"].max(),
            evaluation["timestamp"].min(),
            ranked,
        )

    @staticmethod
    def _rows(evaluations: Sequence[EvaluatedCandidate]) -> list[object]:
        rows: list[object] = []
        for evaluation in evaluations:
            frame = evaluation.frame
            if frame.empty or "timestamp" not in frame:
                continue
            observations = max(len(frame), 1)
            summary = evaluation.summary
            for record in frame.to_dict(orient="records"):
                timestamp = pd.to_datetime(record.get("timestamp"), utc=True, errors="coerce")
                target = record.get("next_abs_zscore")
                regime = str(record.get("regime", "unknown"))
                values = [
                    abs(float(record.get("zscore", 0.0))),
                    record.get("discrepancy_volatility", 0.0),
                    float(regime == "low_volatility"),
                    float(regime == "normal_volatility"),
                    float(regime == "high_volatility"),
                    summary.get("pearson", np.nan),
                    summary.get("spearman", np.nan),
                    summary.get("half_life") if summary.get("half_life") is not None else 0.0,
                    len(frame) / observations,
                ]
                if pd.isna(timestamp) or target is None or not np.isfinite(float(target)):
                    continue
                if not all(np.isfinite(float(value)) for value in values):
                    continue
                rows.append([timestamp, evaluation.candidate.name, float(target), *values])
        return rows
