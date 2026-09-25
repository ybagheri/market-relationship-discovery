from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

import numpy as np
import pandas as pd

from market_relationship_discovery.domain.errors import DataQualityError, InsufficientDataError
from market_relationship_discovery.market_data.contract import (
    ContractCompatibilityStatus,
    ContractSpecification,
    ContractSpecificationAnalyzer,
)


class ComparisonKind(StrEnum):
    TICK = "tick"
    BAR = "bar"


class OpportunityDirection(StrEnum):
    BUY_A_SELL_B = "buy_a_sell_b"
    BUY_B_SELL_A = "buy_b_sell_a"


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


@dataclass(frozen=True, slots=True)
class CrossBrokerSummary:
    broker_a: str
    broker_b: str
    symbol: str
    comparison_kind: ComparisonKind
    classification: str
    broker_a_rows: int
    broker_b_rows: int
    aligned_observations: int
    unmatched_broker_a_rows: int
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
        left = self._prepare(broker_a, request.comparison_kind, "a", request.symbol)
        right = self._prepare(broker_b, request.comparison_kind, "b", request.symbol)
        right = right.assign(_right_timestamp=right["timestamp"])
        aligned = pd.merge_asof(
            left.sort_values("timestamp"),
            right.sort_values("timestamp"),
            left_on="timestamp",
            right_on="timestamp",
            direction="nearest",
            tolerance=pd.Timedelta(milliseconds=request.max_alignment_delay_ms),
        )
        aligned = aligned.rename(columns={"_right_timestamp": "broker_b_timestamp"})
        match_column = "b_bid" if request.comparison_kind is ComparisonKind.TICK else "b_close"
        aligned = aligned[aligned[match_column].notna()].copy()
        if aligned.empty:
            raise InsufficientDataError("no cross-broker observations satisfy alignment tolerance")
        aligned["alignment_delay_ms"] = (
            aligned["broker_b_timestamp"] - aligned["timestamp"]
        ).dt.total_seconds() * 1000.0
        if request.comparison_kind is ComparisonKind.BAR:
            aligned["price_difference"] = aligned["a_close"] - aligned["b_close"]
            return self._bar_summary(aligned, left, right, request)
        analysis = self._tick_summary(aligned, left, right, request)
        return analysis

    @staticmethod
    def _prepare(
        frame: pd.DataFrame,
        kind: ComparisonKind,
        side: str,
        symbol: str,
    ) -> pd.DataFrame:
        required = {"timestamp", "symbol"}
        price_columns = {"bid", "ask"} if kind is ComparisonKind.TICK else {"close"}
        missing = (required | price_columns) - set(frame.columns)
        if missing:
            raise DataQualityError(f"broker {side} data is missing columns: {sorted(missing)}")
        result = frame.copy()
        result["timestamp"] = pd.to_datetime(result["timestamp"], utc=True, errors="raise")
        if result["timestamp"].isna().any() or result["timestamp"].duplicated().any():
            raise DataQualityError(f"broker {side} timestamps must be valid and unique")
        symbols = set(result["symbol"].astype(str))
        if symbols != {symbol}:
            raise DataQualityError(f"broker {side} data must contain only symbol {symbol}")
        if kind is ComparisonKind.TICK:
            for column in ("bid", "ask"):
                result[column] = pd.to_numeric(result[column], errors="raise")
            if (result["bid"] <= 0).any() or (result["ask"] < result["bid"]).any():
                raise DataQualityError(f"broker {side} tick prices are invalid")
        else:
            result["close"] = pd.to_numeric(result["close"], errors="raise")
            if (result["close"] <= 0).any():
                raise DataQualityError(f"broker {side} close prices are invalid")
        return result.rename(columns={column: f"{side}_{column}" for column in price_columns})

    def _tick_summary(
        self,
        aligned: pd.DataFrame,
        left: pd.DataFrame,
        right: pd.DataFrame,
        request: CrossBrokerRequest,
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
            ContractCompatibilityStatus.NORMALIZATION_REQUIRED,
            ContractCompatibilityStatus.INCOMPATIBLE,
            ContractCompatibilityStatus.REVIEW_REQUIRED,
        }
        potential = aligned["net_crossable_edge"] > 0
        blocked_count = int((potential & contract_blocks).sum())
        aligned["is_crossable"] = potential if not contract_blocks else False
        opportunities = self._episodes(aligned)
        crossable = aligned[aligned["is_crossable"]]
        period_hours = self._period_hours(aligned)
        durations = [opportunity.duration_ms for opportunity in opportunities]
        if contract_blocks:
            classification = "blocked_by_contract_specification"
        elif compatibility.status is ContractCompatibilityStatus.UNVERIFIED:
            classification = "crossable_research_contract_unverified"
        else:
            classification = "crossable_after_cost_contract_validated_research"
        summary = CrossBrokerSummary(
            broker_a=request.broker_a,
            broker_b=request.broker_b,
            symbol=request.symbol,
            comparison_kind=request.comparison_kind,
            classification=classification,
            broker_a_rows=len(left),
            broker_b_rows=len(right),
            aligned_observations=len(aligned),
            unmatched_broker_a_rows=len(left) - len(aligned),
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
        )
        return CrossBrokerAnalysis(summary, opportunities, aligned)

    def _bar_summary(
        self,
        aligned: pd.DataFrame,
        left: pd.DataFrame,
        right: pd.DataFrame,
        request: CrossBrokerRequest,
    ) -> CrossBrokerAnalysis:
        compatibility = ContractSpecificationAnalyzer().compare(
            request.contract_a,
            request.contract_b,
        )
        summary = CrossBrokerSummary(
            broker_a=request.broker_a,
            broker_b=request.broker_b,
            symbol=request.symbol,
            comparison_kind=request.comparison_kind,
            classification="theoretical_bar_price_comparison",
            broker_a_rows=len(left),
            broker_b_rows=len(right),
            aligned_observations=len(aligned),
            unmatched_broker_a_rows=len(left) - len(aligned),
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
        )
        return CrossBrokerAnalysis(summary, (), aligned)

    @staticmethod
    def _episodes(aligned: pd.DataFrame) -> tuple[CrossBrokerOpportunity, ...]:
        positive = aligned[aligned["is_crossable"]]
        if positive.empty:
            return ()
        groups = positive.groupby(
            (positive.index.to_series().diff() != 1).cumsum(),
            sort=True,
        )
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
                    observations=len(episode),
                    maximum_gross_edge=float(maximum["gross_crossable_edge"]),
                    maximum_net_edge=float(maximum["net_crossable_edge"]),
                    mean_net_edge=float(episode["net_crossable_edge"].mean()),
                )
            )
        return tuple(opportunities)

    @staticmethod
    def _period_hours(aligned: pd.DataFrame) -> float:
        if len(aligned) < 2:
            return 1.0 / 3600.0
        seconds = (aligned["timestamp"].iloc[-1] - aligned["timestamp"].iloc[0]).total_seconds()
        return max(float(seconds) / 3600.0, 1.0 / 3600.0)
