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
    """Chronological ridge ranking over causal features only.

    Every feature must be computable from observations up to and including its
    own timestamp. A statistic summarised over a candidate's whole series cannot
    be used here: it encodes the evaluation period, and the model would then be
    scored out of sample against features derived from the answer. Half-life and
    the full-sample correlation summaries were previously in the feature set for
    exactly that reason, and the constant ``observation_fraction`` carried no
    information at all.
    """

    feature_names = (
        "abs_zscore",
        "discrepancy_volatility",
        "regime_low",
        "regime_normal",
        "regime_high",
        "expanding_pearson",
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
            expanding = _expanding_pearson(
                frame.get("actual"),
                frame.get("synthetic"),
                minimum_observations=MINIMUM_EXPANDING_OBSERVATIONS,
            )
            for position, record in enumerate(frame.to_dict(orient="records")):
                timestamp = pd.to_datetime(record.get("timestamp"), utc=True, errors="coerce")
                target = record.get("next_abs_zscore")
                regime = str(record.get("regime", "unknown"))
                # Built from the row itself and its own history, so the warm-up
                # rows stay undefined instead of reading as a perfect score.
                values = [
                    abs(float(record.get("zscore", 0.0))),
                    record.get("discrepancy_volatility", 0.0),
                    float(regime == "low_volatility"),
                    float(regime == "normal_volatility"),
                    float(regime == "high_volatility"),
                    expanding[position] if position < len(expanding) else float("nan"),
                ]
                if pd.isna(timestamp) or target is None or not np.isfinite(float(target)):
                    continue
                if not all(np.isfinite(float(value)) for value in values):
                    continue
                rows.append([timestamp, evaluation.candidate.name, float(target), *values])
        return rows


# Warm-up length of the expanding correlation. Below this the estimate is not
# meaningful, and those rows are dropped by the ranker's finite-value filter.
MINIMUM_EXPANDING_OBSERVATIONS = 10


def _expanding_pearson(
    left: pd.Series | None,
    right: pd.Series | None,
    minimum_observations: int,
) -> list[float]:
    """Correlation over the expanding window ending at each observation.

    Computed in closed form from cumulative sums so it costs one pass rather than
    a correlation per row. A row with too little history, or a window with no
    variance in either series, yields NaN and is excluded from the model rather
    than being filled with a value that looks like evidence.
    """
    if left is None or right is None:
        return []
    x = pd.to_numeric(left, errors="coerce").to_numpy(dtype=float)
    y = pd.to_numeric(right, errors="coerce").to_numpy(dtype=float)
    size = min(len(x), len(y))
    if size == 0:
        return []
    x, y = x[:size], y[:size]
    # Centred before accumulating. The textbook one-pass form subtracts
    # quantities of the order of sum(x)*sum(y) to recover a covariance two orders
    # smaller, which loses most of the available precision on price-level data
    # and can even flip the sign of the result. Shifting by a constant leaves the
    # correlation unchanged and keeps every accumulated term small.
    x = x - x[0]
    y = y - y[0]
    count = np.arange(1, size + 1, dtype=float)
    sum_x = np.cumsum(x)
    sum_y = np.cumsum(y)
    sum_xx = np.cumsum(x * x)
    sum_yy = np.cumsum(y * y)
    sum_xy = np.cumsum(x * y)
    covariance = sum_xy - sum_x * sum_y / count
    variance_x = sum_xx - sum_x * sum_x / count
    variance_y = sum_yy - sum_y * sum_y / count
    denominator = np.sqrt(
        np.where(variance_x > 0.0, variance_x, np.nan)
        * np.where(variance_y > 0.0, variance_y, np.nan)
    )
    correlation = np.where(denominator > 0.0, covariance / denominator, np.nan)
    # A correlation cannot leave its own bounds; accumulated rounding must not
    # be allowed to report a value the statistic cannot take.
    correlation = np.clip(correlation, -1.0, 1.0)
    correlation[count < minimum_observations] = np.nan
    return [float(value) for value in correlation]
