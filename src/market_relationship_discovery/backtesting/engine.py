from dataclasses import dataclass

import numpy as np
import pandas as pd

from market_relationship_discovery.domain.market import Quote


@dataclass(frozen=True, slots=True)
class BacktestMetrics:
    observations: int
    opportunities: int
    gross_edge: float
    net_edge: float
    win_rate: float | None
    average_return: float | None
    maximum_adverse_excursion: float
    maximum_favorable_excursion: float
    drawdown: float
    cost_percentage: float | None


@dataclass(frozen=True, slots=True)
class NoLookAheadTrade:
    decision_timestamp: object
    execution_timestamp: object
    signal: float
    gross_edge: float
    cost: float

    @property
    def net_edge(self) -> float:
        return self.gross_edge - self.cost


@dataclass(frozen=True, slots=True)
class NoLookAheadResult:
    metrics: BacktestMetrics
    trades: tuple[NoLookAheadTrade, ...]


class ResearchBacktester:
    def run(self, gross_edges: pd.Series, costs: pd.Series) -> BacktestMetrics:
        aligned = pd.concat([gross_edges, costs], axis=1).dropna()
        if len(aligned) and (aligned.iloc[:, 1] < 0).any():
            raise ValueError("costs cannot be negative")
        net = aligned.iloc[:, 0] - aligned.iloc[:, 1]
        opportunities = int((aligned.iloc[:, 0] > 0).sum())
        equity = net.cumsum()
        drawdown = equity - equity.cummax()
        return BacktestMetrics(
            observations=len(aligned),
            opportunities=opportunities,
            gross_edge=float(aligned.iloc[:, 0].sum()),
            net_edge=float(net.sum()),
            win_rate=float((net > 0).mean()) if len(net) else None,
            average_return=float(net.mean()) if len(net) else None,
            maximum_adverse_excursion=float(np.minimum(aligned.iloc[:, 0].to_numpy(), 0).sum()),
            maximum_favorable_excursion=float(np.maximum(aligned.iloc[:, 0].to_numpy(), 0).sum()),
            drawdown=float(drawdown.min()) if len(drawdown) else 0.0,
            cost_percentage=(
                float(aligned.iloc[:, 1].sum() / aligned.iloc[:, 0].sum() * 100.0)
                if float(aligned.iloc[:, 0].sum()) != 0
                else None
            ),
        )

    def run_next_observation(
        self,
        signals: pd.Series,
        gross_edges: pd.Series,
        costs: pd.Series,
    ) -> NoLookAheadResult:
        frame = pd.concat(
            [
                signals.rename("signal"),
                gross_edges.rename("gross_edge"),
                costs.rename("cost"),
            ],
            axis=1,
            join="outer",
        ).sort_index()
        if frame.index.has_duplicates:
            raise ValueError("backtest timestamps must be unique")
        next_gross = frame["gross_edge"].shift(-1)
        next_cost = frame["cost"].shift(-1)
        trades = tuple(
            NoLookAheadTrade(
                decision_timestamp=timestamp,
                execution_timestamp=frame.index[position + 1],
                signal=float(frame.at[timestamp, "signal"]),
                gross_edge=float(next_gross.at[timestamp]),
                cost=float(next_cost.at[timestamp]),
            )
            for position, timestamp in enumerate(frame.index[:-1])
            if pd.notna(frame.at[timestamp, "signal"])
            and bool(frame.at[timestamp, "signal"])
            and pd.notna(next_gross.at[timestamp])
            and pd.notna(next_cost.at[timestamp])
        )
        trade_frame = pd.DataFrame(
            [(trade.gross_edge, trade.cost) for trade in trades],
            index=pd.RangeIndex(len(trades)),
            columns=["gross_edge", "cost"],
        )
        metrics = self.run(trade_frame["gross_edge"], trade_frame["cost"])
        return NoLookAheadResult(metrics, trades)


def quotes_to_frame(quotes: list[Quote]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "timestamp": quote.timestamp,
                "broker": quote.broker,
                "symbol": quote.symbol,
                "bid": quote.bid,
                "ask": quote.ask,
                "mid": quote.mid,
                "spread": quote.spread,
                "volume": quote.volume,
                "source": quote.source,
            }
            for quote in quotes
        ]
    )
