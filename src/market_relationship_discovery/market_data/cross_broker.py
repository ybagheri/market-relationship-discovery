from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

import numpy as np
import pandas as pd

from market_relationship_discovery.costs.execution import (
    DEFAULT_MINIMUM_FILL_RATIO,
    ExecutionAssessment,
    ExecutionAssessor,
    FillSimulator,
    MarginModel,
)
from market_relationship_discovery.costs.latency import (
    Episode,
    LatencyCaptureModel,
    LatencyCaptureReport,
    RoundTripAssumption,
)
from market_relationship_discovery.costs.measurement import LatencySource
from market_relationship_discovery.domain.errors import DataQualityError, InsufficientDataError
from market_relationship_discovery.market_data.contract import (
    ContractCompatibilityStatus,
    ContractEdgeNormalizer,
    ContractSpecification,
    ContractSpecificationAnalyzer,
)


class ComparisonKind(StrEnum):
    TICK = "tick"
    BAR = "bar"


class TickAggregation(StrEnum):
    LAST = "last"
    NONE = "none"


class SynchronizationMode(StrEnum):
    ANCHOR_A = "anchor_a"
    SYMMETRIC = "symmetric"


class OpportunityDirection(StrEnum):
    BUY_A_SELL_B = "buy_a_sell_b"
    BUY_B_SELL_A = "buy_b_sell_a"


# Fallback continuity threshold, used only when the sample is too short to
# estimate the feed's own tick cadence.
DEFAULT_EPISODE_GAP_MS = 1000.0

# An episode ends once the silence is this many times wider than a typical
# inter-tick gap, which separates "the edge persisted" from "the feed went quiet
# and the edge reappeared later".
EPISODE_GAP_SPACING_MULTIPLE = 50.0


@dataclass(frozen=True, slots=True)
class CrossBrokerRequest:
    broker_a: str
    broker_b: str
    symbol: str
    comparison_kind: ComparisonKind
    max_alignment_delay_ms: int
    additional_cost: float = 0.0
    contract_a: ContractSpecification | None = None
    contract_b: ContractSpecification | None = None
    synchronization_mode: SynchronizationMode = SynchronizationMode.ANCHOR_A
    tick_aggregation: TickAggregation = TickAggregation.LAST
    volume: float = 1.0
    leverage: int | None = None
    minimum_fill_ratio: float = DEFAULT_MINIMUM_FILL_RATIO
    latency_per_leg_ms: float = 50.0
    adverse_move_allowance: float = 0.0
    minimum_capturable_fraction: float = 0.25
    latency_source: LatencySource = LatencySource.ASSUMED
    latency_sample_count: int = 0
    # Appended rather than inserted: the request is built positionally in the
    # application layer, so a field added in the middle would silently shift
    # every later argument.
    maximum_episode_gap_ms: int | None = None

    def __post_init__(self) -> None:
        if not self.broker_a or not self.broker_b or not self.symbol:
            raise ValueError("broker names and symbol are required")
        if self.broker_a == self.broker_b:
            raise ValueError("cross-broker comparison requires two distinct broker labels")
        if self.max_alignment_delay_ms < 0:
            raise ValueError("max_alignment_delay_ms cannot be negative")
        if not isfinite(self.additional_cost) or self.additional_cost < 0:
            raise ValueError("additional_cost must be finite and non-negative")
        if (self.contract_a is None) != (self.contract_b is None):
            raise ValueError("both contract specifications must be provided together")
        if not isfinite(self.volume) or self.volume <= 0:
            raise ValueError("volume must be finite and positive")
        if self.leverage is not None and self.leverage <= 0:
            raise ValueError("leverage must be positive when provided")
        if not 0.0 <= self.minimum_fill_ratio <= 1.0:
            raise ValueError("minimum_fill_ratio must be between zero and one")
        if self.latency_per_leg_ms <= 0:
            raise ValueError(
                "latency_per_leg_ms must be positive; a zero round trip would report every "
                "episode as fully capturable"
            )
        if self.adverse_move_allowance < 0:
            raise ValueError("adverse_move_allowance cannot be negative")
        if not 0.0 <= self.minimum_capturable_fraction <= 1.0:
            raise ValueError("minimum_capturable_fraction must be between zero and one")
        if self.maximum_episode_gap_ms is not None and self.maximum_episode_gap_ms < 0:
            raise ValueError("maximum_episode_gap_ms cannot be negative")

    @property
    def episode_gap_ms(self) -> float:
        """Configured wall-clock gap separating one episode from the next."""
        if self.maximum_episode_gap_ms is not None:
            return self.maximum_episode_gap_ms
        return DEFAULT_EPISODE_GAP_MS

    def resolved_episode_gap_ms(self, aligned: pd.DataFrame) -> float:
        """The gap actually used, derived from the feed's own tick cadence.

        The alignment tolerance is a *matching* tolerance: it says two quotes may
        describe the same instant. It says nothing about how long a trader could
        have held a position, so it cannot be reused as a continuity threshold —
        a normal tick feed quotes far more often than that, and reusing it would
        shatter every real episode into single observations.

        A gap therefore ends an episode once it is much wider than the feed's own
        typical spacing, which adapts to a dense tick stream and to a sparse
        minute-bar feed alike. A caller who knows the feed's cadence can set
        ``maximum_episode_gap_ms`` and skip the estimate entirely.
        """
        if self.maximum_episode_gap_ms is not None:
            return float(self.maximum_episode_gap_ms)
        if len(aligned) < 3:
            return float(DEFAULT_EPISODE_GAP_MS)
        spacing = aligned["timestamp"].diff().dt.total_seconds() * 1000.0
        typical = float(spacing[spacing > 0].median())
        if not isfinite(typical) or typical <= 0.0:
            return float(DEFAULT_EPISODE_GAP_MS)
        return max(typical * EPISODE_GAP_SPACING_MULTIPLE, float(self.max_alignment_delay_ms))


@dataclass(frozen=True, slots=True)
class CrossBrokerOpportunity:
    direction: OpportunityDirection
    start: pd.Timestamp
    end: pd.Timestamp
    duration_ms: float
    observations: int
    maximum_gross_edge: float
    maximum_net_edge: float
    mean_net_edge: float
    maximum_normalized_net_pnl: float | None
    mean_normalized_net_pnl: float | None
    # Where inside the episode the maximum was observed. The latency model
    # cannot use the peak as a starting value without knowing when it arrives,
    # and a report that omits this cannot be reproduced faithfully.
    peak_offset_ms: float = 0.0


@dataclass(frozen=True, slots=True)
class CrossBrokerSummary:
    broker_a: str
    broker_b: str
    symbol: str
    comparison_kind: ComparisonKind
    synchronization_mode: SynchronizationMode
    tick_aggregation: TickAggregation
    classification: str
    broker_a_rows: int
    broker_b_rows: int
    broker_a_duplicate_timestamps: int
    broker_b_duplicate_timestamps: int
    aligned_observations: int
    unmatched_broker_a_rows: int
    unmatched_broker_b_rows: int
    mean_alignment_delay_ms: float
    p95_alignment_delay_ms: float
    mean_absolute_price_difference: float
    maximum_absolute_price_difference: float
    mean_bid_difference: float | None
    mean_ask_difference: float | None
    crossable_observations: int
    crossable_observation_fraction: float
    maximum_gross_crossable_edge: float | None
    maximum_net_crossable_edge: float | None
    opportunity_count: int
    opportunity_observations: int
    opportunity_rate_per_hour: float
    median_opportunity_duration_ms: float
    maximum_opportunity_duration_ms: float
    additional_cost: float
    contract_status: ContractCompatibilityStatus
    contract_issues: tuple[str, ...]
    contract_blocked_observations: int
    contract_normalization_applied: bool
    broker_b_volume_per_broker_a_volume: float | None
    mean_normalized_net_pnl: float | None
    maximum_normalized_net_pnl: float | None
    normalized_pnl_legs_agree: bool | None
    normalized_pnl_leg_disagreement_ratio: float | None
    execution: ExecutionAssessment | None
    latency: LatencyCaptureReport | None


@dataclass(frozen=True, slots=True)
class CrossBrokerAnalysis:
    summary: CrossBrokerSummary
    opportunities: tuple[CrossBrokerOpportunity, ...]
    aligned_observations: pd.DataFrame


class CrossBrokerComparisonEngine:
    def compare(
        self,
        broker_a: pd.DataFrame,
        broker_b: pd.DataFrame,
        request: CrossBrokerRequest,
    ) -> CrossBrokerAnalysis:
        left_duplicates = self._duplicate_count(broker_a, request.comparison_kind)
        right_duplicates = self._duplicate_count(broker_b, request.comparison_kind)
        left = self._prepare(
            broker_a,
            request.comparison_kind,
            "a",
            request.symbol,
            request.tick_aggregation,
        )
        right = self._prepare(
            broker_b,
            request.comparison_kind,
            "b",
            request.symbol,
            request.tick_aggregation,
        )
        if request.synchronization_mode is SynchronizationMode.ANCHOR_A:
            right = right.assign(_right_timestamp=right["timestamp"])
            aligned = pd.merge_asof(
                left,
                right,
                left_on="timestamp",
                right_on="timestamp",
                direction="nearest",
                tolerance=pd.Timedelta(milliseconds=request.max_alignment_delay_ms),
            ).rename(columns={"_right_timestamp": "broker_b_timestamp"})
        else:
            aligned = self._symmetric_align(
                left,
                right,
                request.max_alignment_delay_ms,
            )
        match_column = "b_bid" if request.comparison_kind is ComparisonKind.TICK else "b_close"
        aligned = aligned[aligned[match_column].notna()].copy()
        if aligned.empty:
            raise InsufficientDataError("no cross-broker observations satisfy alignment tolerance")
        aligned["alignment_delay_ms"] = (
            aligned["broker_b_timestamp"] - aligned["timestamp"]
        ).dt.total_seconds() * 1000.0
        if request.comparison_kind is ComparisonKind.BAR:
            aligned["price_difference"] = aligned["a_close"] - aligned["b_close"]
            return self._bar_summary(
                aligned,
                left,
                right,
                request,
                left_duplicates,
                right_duplicates,
            )
        analysis = self._tick_summary(
            aligned,
            left,
            right,
            request,
            left_duplicates,
            right_duplicates,
        )
        return analysis

    @staticmethod
    def _duplicate_count(frame: pd.DataFrame, kind: ComparisonKind) -> int:
        if kind is not ComparisonKind.TICK or "timestamp" not in frame.columns:
            return 0
        return int(pd.to_datetime(frame["timestamp"], utc=True, errors="raise").duplicated().sum())

    @staticmethod
    def _prepare(
        frame: pd.DataFrame,
        kind: ComparisonKind,
        side: str,
        symbol: str,
        tick_aggregation: TickAggregation,
    ) -> pd.DataFrame:
        required = {"timestamp", "symbol"}
        # A tuple, not a set: set iteration order varies with PYTHONHASHSEED, which
        # would make the persisted aligned-preview column order differ between runs.
        price_columns = ("bid", "ask") if kind is ComparisonKind.TICK else ("close",)
        missing = (set(required) | set(price_columns)) - set(frame.columns)
        if missing:
            raise DataQualityError(f"broker {side} data is missing columns: {sorted(missing)}")
        result = frame.copy()
        result["timestamp"] = pd.to_datetime(result["timestamp"], utc=True, errors="raise")
        if result["timestamp"].isna().any():
            raise DataQualityError(f"broker {side} timestamps must be valid")
        # Event-time matching requires a sorted series. A single MT5 request is not
        # guaranteed to return rows in chronological order, and searching an
        # unsorted array silently pairs each tick with the wrong neighbour instead
        # of failing, so the ordering is established once here rather than being
        # compensated for in each alignment mode.
        result = result.sort_values("timestamp", kind="stable").reset_index(drop=True)
        if not result["timestamp"].is_monotonic_increasing:
            raise DataQualityError(f"broker {side} timestamps must be chronologically ordered")
        duplicate_timestamps = int(result["timestamp"].duplicated().sum())
        if duplicate_timestamps and (
            kind is ComparisonKind.BAR or tick_aggregation is TickAggregation.NONE
        ):
            raise DataQualityError(f"broker {side} timestamps must be unique")
        if duplicate_timestamps and tick_aggregation is TickAggregation.LAST:
            result = result.drop_duplicates("timestamp", keep="last")
        if result.empty:
            raise DataQualityError(f"broker {side} returned no rows for symbol {symbol}")
        symbols = set(result["symbol"].astype(str))
        if symbols != {symbol}:
            raise DataQualityError(f"broker {side} data must contain only symbol {symbol}")
        if kind is ComparisonKind.TICK:
            for column in ("bid", "ask"):
                result[column] = pd.to_numeric(result[column], errors="raise")
            # Non-finite prices satisfy every comparison below, so they must be
            # rejected explicitly rather than left to propagate into the edge
            # columns as a silently discarded direction.
            if not np.isfinite(result[["bid", "ask"]].to_numpy()).all():
                raise DataQualityError(f"broker {side} tick prices must be finite")
            if (result["bid"] <= 0).any() or (result["ask"] < result["bid"]).any():
                raise DataQualityError(f"broker {side} tick prices are invalid")
        else:
            result["close"] = pd.to_numeric(result["close"], errors="raise")
            if not np.isfinite(result["close"].to_numpy()).all():
                raise DataQualityError(f"broker {side} close prices must be finite")
            if (result["close"] <= 0).any():
                raise DataQualityError(f"broker {side} close prices are invalid")
        return result[["timestamp", "symbol", *price_columns]].rename(
            columns={column: f"{side}_{column}" for column in price_columns}
        )

    @staticmethod
    def _symmetric_align(
        left: pd.DataFrame,
        right: pd.DataFrame,
        tolerance_ms: int,
    ) -> pd.DataFrame:
        left_ns = left["timestamp"].astype("int64").to_numpy()
        right_ns = right["timestamp"].astype("int64").to_numpy()
        a_to_b = CrossBrokerComparisonEngine._nearest_indices(left_ns, right_ns)
        b_to_a = CrossBrokerComparisonEngine._nearest_indices(right_ns, left_ns)
        tolerance_ns = tolerance_ms * 1_000_000
        candidate_b = np.clip(a_to_b, 0, len(right) - 1)
        valid = (a_to_b >= 0) & (np.abs(right_ns[candidate_b] - left_ns) <= tolerance_ns)
        a_indices = np.arange(len(left))
        valid &= b_to_a[candidate_b] == a_indices
        matched_a = np.flatnonzero(valid)
        matched_b = a_to_b[matched_a]
        left_selected = left.iloc[matched_a].reset_index(drop=True)
        right_selected = (
            right.iloc[matched_b].drop(columns=["timestamp", "symbol"]).reset_index(drop=True)
        )
        right_selected["broker_b_timestamp"] = right.iloc[matched_b]["timestamp"].to_numpy()
        return pd.concat([left_selected, right_selected], axis=1)

    @staticmethod
    def _nearest_indices(source_ns: np.ndarray, target_ns: np.ndarray) -> np.ndarray:
        positions = np.searchsorted(target_ns, source_ns, side="left")
        right_positions = np.clip(positions, 0, len(target_ns) - 1)
        left_positions = np.clip(positions - 1, 0, len(target_ns) - 1)
        right_distance = np.abs(target_ns[right_positions] - source_ns)
        left_distance = np.abs(target_ns[left_positions] - source_ns)
        choose_left = left_distance < right_distance
        return np.where(choose_left, left_positions, right_positions).astype(int)

    def _tick_summary(
        self,
        aligned: pd.DataFrame,
        left: pd.DataFrame,
        right: pd.DataFrame,
        request: CrossBrokerRequest,
        left_duplicates: int,
        right_duplicates: int,
    ) -> CrossBrokerAnalysis:
        aligned["a_mid"] = (aligned["a_bid"] + aligned["a_ask"]) / 2.0
        aligned["b_mid"] = (aligned["b_bid"] + aligned["b_ask"]) / 2.0
        aligned["mid_difference"] = aligned["a_mid"] - aligned["b_mid"]
        aligned["bid_difference"] = aligned["a_bid"] - aligned["b_bid"]
        aligned["ask_difference"] = aligned["a_ask"] - aligned["b_ask"]
        buy_a_gross = aligned["b_bid"] - aligned["a_ask"]
        buy_b_gross = aligned["a_bid"] - aligned["b_ask"]
        buy_a_net = buy_a_gross - request.additional_cost
        buy_b_net = buy_b_gross - request.additional_cost
        aligned["buy_a_sell_b_gross_edge"] = buy_a_gross
        aligned["buy_b_sell_a_gross_edge"] = buy_b_gross
        aligned["buy_a_sell_b_net_edge"] = buy_a_net
        aligned["buy_b_sell_a_net_edge"] = buy_b_net
        buy_a_wins = buy_a_net >= buy_b_net
        aligned["crossable_direction"] = np.where(
            buy_a_wins,
            OpportunityDirection.BUY_A_SELL_B.value,
            OpportunityDirection.BUY_B_SELL_A.value,
        )
        aligned["gross_crossable_edge"] = np.where(
            buy_a_wins,
            buy_a_gross,
            buy_b_gross,
        )
        aligned["net_crossable_edge"] = np.where(buy_a_wins, buy_a_net, buy_b_net)
        compatibility = ContractSpecificationAnalyzer().compare(
            request.contract_a,
            request.contract_b,
        )
        contract_blocks = compatibility.status in {
            ContractCompatibilityStatus.INCOMPATIBLE,
            ContractCompatibilityStatus.REVIEW_REQUIRED,
        }
        normalization_available = compatibility.status in {
            ContractCompatibilityStatus.COMPATIBLE,
            ContractCompatibilityStatus.NORMALIZATION_REQUIRED,
        }
        if normalization_available and request.contract_a and request.contract_b:
            normalizer = ContractEdgeNormalizer()
            normalized = [
                normalizer.normalize(
                    float(edge),
                    request.contract_a,
                    request.contract_b,
                )
                for edge in aligned["net_crossable_edge"]
            ]
            aligned["normalized_net_pnl"] = [item.net_pnl for item in normalized]
            volume_ratio = normalized[0].broker_b_volume if normalized else None
            # The two legs describe one position, so they should value it
            # identically. When they do not, the specifications are mutually
            # inconsistent and the reported PnL rests on one of them.
            legs_agree = all(item.legs_agree for item in normalized)
            worst_ratio = max(
                (item.leg_disagreement_ratio for item in normalized),
                default=0.0,
            )
        else:
            aligned["normalized_net_pnl"] = np.nan
            volume_ratio = None
            legs_agree = None
            worst_ratio = None
        potential = aligned["net_crossable_edge"] > 0
        blocked_count = int((potential & contract_blocks).sum())
        aligned["is_crossable"] = potential if not contract_blocks else False
        execution = self._execution_assessment(aligned, request)
        if execution is not None and not execution.executable:
            aligned["is_crossable"] = False
        opportunities = self._episodes(aligned, request.resolved_episode_gap_ms(aligned))
        latency = self._latency_capture(opportunities, request)
        crossable = aligned[aligned["is_crossable"]]
        period_hours = self._period_hours(aligned)
        durations = [opportunity.duration_ms for opportunity in opportunities]
        if contract_blocks:
            classification = "blocked_by_contract_specification"
        elif execution is not None and not execution.executable:
            classification = "blocked_by_execution_feasibility"
        elif compatibility.status is ContractCompatibilityStatus.UNVERIFIED:
            classification = "crossable_research_contract_unverified"
        elif compatibility.status is ContractCompatibilityStatus.NORMALIZATION_REQUIRED:
            classification = "crossable_after_cost_pnl_normalized_research"
        else:
            classification = "crossable_after_cost_contract_validated_research"
        if (
            execution is not None
            and execution.executable
            and not execution.capital_verified
            and classification.startswith("crossable")
        ):
            classification = f"{classification}_capital_unverified"
        if latency is not None and not latency.survives:
            classification = f"{classification}_not_capturable_within_latency"
        if legs_agree is False:
            # Reported alongside the PnL it qualifies: the two legs are supposed
            # to value one position identically, so a disagreement means the
            # specifications are inconsistent, not that the edge is larger.
            classification = f"{classification}_contract_legs_disagree"
        summary = CrossBrokerSummary(
            broker_a=request.broker_a,
            broker_b=request.broker_b,
            symbol=request.symbol,
            comparison_kind=request.comparison_kind,
            synchronization_mode=request.synchronization_mode,
            tick_aggregation=request.tick_aggregation,
            classification=classification,
            broker_a_rows=len(left),
            broker_b_rows=len(right),
            broker_a_duplicate_timestamps=left_duplicates,
            broker_b_duplicate_timestamps=right_duplicates,
            aligned_observations=len(aligned),
            unmatched_broker_a_rows=len(left) - len(aligned),
            unmatched_broker_b_rows=(len(right) - aligned["broker_b_timestamp"].nunique()),
            mean_alignment_delay_ms=float(aligned["alignment_delay_ms"].mean()),
            p95_alignment_delay_ms=float(aligned["alignment_delay_ms"].quantile(0.95)),
            mean_absolute_price_difference=float(aligned["mid_difference"].abs().mean()),
            maximum_absolute_price_difference=float(aligned["mid_difference"].abs().max()),
            mean_bid_difference=float(aligned["bid_difference"].mean()),
            mean_ask_difference=float(aligned["ask_difference"].mean()),
            crossable_observations=len(crossable),
            crossable_observation_fraction=len(crossable) / len(aligned),
            maximum_gross_crossable_edge=(
                float(aligned["gross_crossable_edge"].max())
                if len(aligned) and not contract_blocks
                else None
            ),
            maximum_net_crossable_edge=(
                float(aligned["net_crossable_edge"].max())
                if len(aligned) and not contract_blocks
                else None
            ),
            opportunity_count=len(opportunities),
            opportunity_observations=len(crossable),
            opportunity_rate_per_hour=len(opportunities) / period_hours,
            median_opportunity_duration_ms=float(np.median(durations)) if durations else 0.0,
            maximum_opportunity_duration_ms=max(durations, default=0.0),
            additional_cost=request.additional_cost,
            contract_status=compatibility.status,
            contract_issues=compatibility.issues,
            contract_blocked_observations=blocked_count,
            contract_normalization_applied=(
                compatibility.status is ContractCompatibilityStatus.NORMALIZATION_REQUIRED
                and not contract_blocks
            ),
            broker_b_volume_per_broker_a_volume=volume_ratio,
            mean_normalized_net_pnl=(
                float(aligned["normalized_net_pnl"].mean()) if normalization_available else None
            ),
            maximum_normalized_net_pnl=(
                float(aligned["normalized_net_pnl"].max()) if normalization_available else None
            ),
            normalized_pnl_legs_agree=legs_agree,
            normalized_pnl_leg_disagreement_ratio=worst_ratio,
            execution=execution,
            latency=latency,
        )
        return CrossBrokerAnalysis(summary, opportunities, aligned)

    @staticmethod
    def _latency_capture(
        opportunities: tuple[CrossBrokerOpportunity, ...],
        request: CrossBrokerRequest,
    ) -> LatencyCaptureReport | None:
        """Compare each measured episode against the time an order actually takes.

        The episodes are the ones the comparison already measured, so this adds no
        new data. It answers whether the observed window was long enough to act
        in, which the episode counts alone cannot say.
        """
        episodes = [
            Episode(
                label=f"{opportunity.direction.value}:{opportunity.start.isoformat()}",
                duration_ms=opportunity.duration_ms,
                peak_edge=opportunity.maximum_net_edge,
                peak_offset_ms=opportunity.peak_offset_ms,
            )
            for opportunity in opportunities
            if opportunity.maximum_net_edge > 0
        ]
        if not episodes:
            return None
        assumption = RoundTripAssumption(
            latency_per_leg_ms=request.latency_per_leg_ms,
            legs=2,
            adverse_move_allowance=request.adverse_move_allowance,
            minimum_capturable_fraction=request.minimum_capturable_fraction,
            latency_source=request.latency_source,
            latency_sample_count=request.latency_sample_count,
        )
        capture = LatencyCaptureModel().assess(episodes, assumption)
        return capture

    def _execution_assessment(
        self,
        aligned: pd.DataFrame,
        request: CrossBrokerRequest,
    ) -> ExecutionAssessment | None:
        """Assess whether a sized position could be held at both brokers.

        The assessment uses the widest observed discrepancy, because that is the
        most favourable case for execution. If capital or fill feasibility fails
        even there, no smaller or less favourable opportunity can be executable.
        """
        if aligned.empty:
            return None
        request_volume = request.volume
        broker_b_volume = request_volume
        if request.contract_a is not None and request.contract_b is not None:
            broker_b_volume = (
                request_volume * request.contract_a.contract_size / request.contract_b.contract_size
            )
        widest = aligned.loc[aligned["gross_crossable_edge"].idxmax()]
        assessor = ExecutionAssessor(
            margin_model=MarginModel(request.leverage),
            fill_simulator=FillSimulator(),
            leverage=request.leverage,
            minimum_fill_ratio=request.minimum_fill_ratio,
        )
        return assessor.assess(
            request.contract_a,
            request.contract_b,
            request_volume,
            broker_b_volume,
            float(widest["a_mid"]),
            float(widest["b_mid"]),
        )

    def _bar_summary(
        self,
        aligned: pd.DataFrame,
        left: pd.DataFrame,
        right: pd.DataFrame,
        request: CrossBrokerRequest,
        left_duplicates: int,
        right_duplicates: int,
    ) -> CrossBrokerAnalysis:
        compatibility = ContractSpecificationAnalyzer().compare(
            request.contract_a,
            request.contract_b,
        )
        # Bar comparisons are theoretical only, so no execution feasibility is
        # assessed. A close price cannot establish that a position could be
        # opened and closed at those levels.
        summary = CrossBrokerSummary(
            broker_a=request.broker_a,
            broker_b=request.broker_b,
            symbol=request.symbol,
            comparison_kind=request.comparison_kind,
            synchronization_mode=request.synchronization_mode,
            tick_aggregation=request.tick_aggregation,
            classification="theoretical_bar_price_comparison",
            broker_a_rows=len(left),
            broker_b_rows=len(right),
            broker_a_duplicate_timestamps=left_duplicates,
            broker_b_duplicate_timestamps=right_duplicates,
            aligned_observations=len(aligned),
            unmatched_broker_a_rows=len(left) - len(aligned),
            unmatched_broker_b_rows=(len(right) - aligned["broker_b_timestamp"].nunique()),
            mean_alignment_delay_ms=float(aligned["alignment_delay_ms"].mean()),
            p95_alignment_delay_ms=float(aligned["alignment_delay_ms"].quantile(0.95)),
            mean_absolute_price_difference=float(aligned["price_difference"].abs().mean()),
            maximum_absolute_price_difference=float(aligned["price_difference"].abs().max()),
            mean_bid_difference=None,
            mean_ask_difference=None,
            crossable_observations=0,
            crossable_observation_fraction=0.0,
            maximum_gross_crossable_edge=None,
            maximum_net_crossable_edge=None,
            opportunity_count=0,
            opportunity_observations=0,
            opportunity_rate_per_hour=0.0,
            median_opportunity_duration_ms=0.0,
            maximum_opportunity_duration_ms=0.0,
            additional_cost=request.additional_cost,
            contract_status=compatibility.status,
            contract_issues=compatibility.issues,
            contract_blocked_observations=0,
            contract_normalization_applied=False,
            broker_b_volume_per_broker_a_volume=None,
            mean_normalized_net_pnl=None,
            maximum_normalized_net_pnl=None,
            normalized_pnl_legs_agree=None,
            normalized_pnl_leg_disagreement_ratio=None,
            execution=None,
            latency=None,
        )
        return CrossBrokerAnalysis(summary, (), aligned)

    @staticmethod
    def _episodes(
        aligned: pd.DataFrame,
        maximum_gap_ms: float,
    ) -> tuple[CrossBrokerOpportunity, ...]:
        positive = aligned[aligned["is_crossable"]]
        if positive.empty:
            return ()
        # An episode is a continuous run in time, not a run of adjacent rows. Two
        # crossable observations separated by a quiet period are two separate
        # instants, and no position is held across the gap between them. Grouping
        # on index adjacency would report that hole as one long opportunity and
        # then hand the inflated duration to the latency model as if it were
        # capturable.
        gaps = positive["timestamp"].diff() > pd.Timedelta(milliseconds=maximum_gap_ms)
        groups = positive.groupby(gaps.cumsum(), sort=True)
        opportunities: list[CrossBrokerOpportunity] = []
        for _, episode in groups:
            maximum = episode.loc[episode["net_crossable_edge"].idxmax()]
            start = episode["timestamp"].iloc[0]
            end = episode["timestamp"].iloc[-1]
            opportunities.append(
                CrossBrokerOpportunity(
                    direction=OpportunityDirection(maximum["crossable_direction"]),
                    start=start,
                    end=end,
                    duration_ms=max(0.0, (end - start).total_seconds() * 1000.0),
                    peak_offset_ms=max(
                        0.0, (maximum["timestamp"] - start).total_seconds() * 1000.0
                    ),
                    observations=len(episode),
                    maximum_gross_edge=float(maximum["gross_crossable_edge"]),
                    maximum_net_edge=float(maximum["net_crossable_edge"]),
                    mean_net_edge=float(episode["net_crossable_edge"].mean()),
                    maximum_normalized_net_pnl=(
                        float(episode["normalized_net_pnl"].max())
                        if pd.notna(episode["normalized_net_pnl"].max())
                        else None
                    ),
                    mean_normalized_net_pnl=(
                        float(episode["normalized_net_pnl"].mean())
                        if pd.notna(episode["normalized_net_pnl"].max())
                        else None
                    ),
                )
            )
        return tuple(opportunities)

    @staticmethod
    def _period_hours(aligned: pd.DataFrame) -> float:
        """Wall-clock hours the aligned sample spans.

        Read from the first and last aligned timestamp rather than the row
        positions, so the rate cannot be inflated by an unsorted sample.
        """
        if len(aligned) < 2:
            return 1.0 / 3600.0
        seconds = (aligned["timestamp"].max() - aligned["timestamp"].min()).total_seconds()
        return max(float(seconds) / 3600.0, 1.0 / 3600.0)
