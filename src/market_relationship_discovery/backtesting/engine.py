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
