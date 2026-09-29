from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import pandas as pd

from market_relationship_discovery.domain.market import Quote


class OutcomeConvention(StrEnum):
    """Which bar a `gross_edge` value is labelled with.

    A return series can be labelled at the instant it starts or at the instant
    it ends, and the two readings differ by exactly one bar. The engine has to
    pick one, because "the next observation" is meaningless without it, and a
    caller that assumed the other reading gets a backtest that is internally
    consistent and one bar wrong.

    The reading is therefore named at the call site instead of being inherited.
    """

    #: `edge[t]` is the return earned over `[t, t+1)`. The value at `t` is not
    #: known until `t+1` closes, so a decision made at `t` is settled by it.
    EARNED_OVER_FOLLOWING_BAR = "earned_over_following_bar"

    #: `edge[t]` is the return that was already realised at `t`, covering
    #: `[t-1, t)`. A decision made at `t` cannot be settled by it, and pairing
    #: the two would score the decision against a bar that closed before it.
    REALISED_AT_BAR = "realised_at_bar"


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
    observation_win_rate: float | None


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

    @property
    def was_taken(self) -> bool:
        """Whether this trade carried a positive gross edge.

        A negative gross edge is not an opportunity that failed, it is the cost
        of being in the market, so metrics distinguishing trades from idle bars
        use this rather than the sign of the net edge.
        """
        return self.gross_edge > 0.0


@dataclass(frozen=True, slots=True)
class NoLookAheadResult:
    metrics: BacktestMetrics
    trades: tuple[NoLookAheadTrade, ...]


def _require_one_observation_grid(
    signals: pd.Series,
    gross_edges: pd.Series,
    costs: pd.Series,
) -> None:
    """Refuse inputs that do not describe the same sequence of observations.

    Reported as the number of observations each column carries, because the
    failure is not that a timestamp is missing but that the columns are counting
    different things, and the reader has to be able to see which.
    """
    named = (
        ("signal", signals),
        ("gross edge", gross_edges),
        ("cost", costs),
    )
    for name, series in named:
        if not isinstance(series.index, pd.DatetimeIndex):
            raise TypeError(f"{name} observations must be indexed by timestamp")
    reference_name, reference = named[0]
    for name, series in named[1:]:
        if not series.index.equals(reference.index):
            raise ValueError(
                "signal, gross edge, and cost must share one observation grid: "
                f"{reference_name} has {len(reference.index)} observations, "
                f"{name} has {len(series.index)}"
            )
    if reference.index.hasnans:
        raise ValueError("backtest timestamps cannot be missing")
    if not reference.index.is_monotonic_increasing:
        raise ValueError("backtest timestamps must be sorted")


def _outcome_offset(convention: OutcomeConvention) -> int:
    """Bars between a decision and the bar that settles it.

    Zero under `REALISED_AT_BAR` is correct and not a degenerate case: the
    decision and the outcome describe the same bar, and both are computed from
    data up to that bar's close. The invariant is that no value is read from
    before the decision, not that every trade spans two bars.
    """
    if convention is OutcomeConvention.EARNED_OVER_FOLLOWING_BAR:
        return 1
    if convention is OutcomeConvention.REALISED_AT_BAR:
        return 0
    raise ValueError(f"unknown outcome convention: {convention}")


class ResearchBacktester:
    def run(self, gross_edges: pd.Series, costs: pd.Series) -> BacktestMetrics:
        aligned = pd.concat([gross_edges, costs], axis=1).dropna()
        if len(aligned) and (aligned.iloc[:, 1] < 0).any():
            raise ValueError("costs cannot be negative")
        net = aligned.iloc[:, 0] - aligned.iloc[:, 1]
        taken = (aligned.iloc[:, 0] > 0).to_numpy()
        opportunities = int(taken.sum())
        equity = net.cumsum()
        # The running peak is seeded with the starting equity of zero. Without it
        # a curve that opens below its own high never registers a decline, so a
        # strategy that loses money first reports no drawdown at all.
        drawdown = equity - np.maximum.accumulate(np.r_[0.0, equity.to_numpy()])[1:]
        traded_net = net[taken]
        return BacktestMetrics(
            observations=len(aligned),
            opportunities=opportunities,
            gross_edge=float(aligned.iloc[:, 0].sum()),
            net_edge=float(net.sum()),
            # Measured over the trades that were actually taken. Averaging over
            # every bar would dilute the rate toward zero and would mean
            # something different here than on the trade-level path.
            win_rate=float((traded_net > 0).mean()) if len(traded_net) else None,
            average_return=float(traded_net.mean()) if len(traded_net) else None,
            maximum_adverse_excursion=float(np.minimum(net.to_numpy(), 0).sum()),
            maximum_favorable_excursion=float(np.maximum(net.to_numpy(), 0).sum()),
            drawdown=float(drawdown.min()) if len(drawdown) else 0.0,
            cost_percentage=(
                float(aligned.iloc[:, 1].sum() / aligned.iloc[:, 0].sum() * 100.0)
                if float(aligned.iloc[:, 0].sum()) != 0
                else None
            ),
            # The rate over every observation, kept because the two paths through
            # this record are compared in reports and a reader needs to see which
            # population each number describes.
            observation_win_rate=float((net > 0).mean()) if len(net) else None,
        )

    def run_next_observation(
        self,
        signals: pd.Series,
        gross_edges: pd.Series,
        costs: pd.Series,
        outcome_convention: OutcomeConvention = OutcomeConvention.EARNED_OVER_FOLLOWING_BAR,
    ) -> NoLookAheadResult:
        """Pair each decision with an outcome that had not closed at the decision.

        The no-lookahead property here is a claim about time: a decision taken
        at bar ``t`` is settled by an outcome that had not finished forming at
        ``t``. Two things have to hold for that, and only the first is obvious
        from the argument list.

        **The outcome column has to be labelled consistently**, which is
        ``outcome_convention``. Under ``EARNED_OVER_FOLLOWING_BAR`` the value at
        ``t`` covers ``[t, t+1)`` and is unknown until ``t+1`` closes, so the
        decision at ``t`` is settled by the value at ``t+1``. Under
        ``REALISED_AT_BAR`` the value at ``t`` already covers ``[t-1, t)`` and
        closed *before* the decision was made, so settling ``t`` with it would
        score the decision against a bar that had already finished. The two
        readings differ by one bar and produce equally plausible reports, so
        the choice is declared rather than inherited.

        **The three inputs have to share one observation grid**, or "the next
        bar" refers to no single series. An outer join cannot stand in for that.
        When the outcome column is on a finer grid than the signal, the union's
        next row is a fraction of a second after the decision, an outcome whose
        period overlaps the bar the decision was computed from, and the reported
        execution bar is later than the decision only in the most literal sense.
        That is a lookahead the caller cannot see, so it is refused.
        """
        _require_one_observation_grid(signals, gross_edges, costs)
        outcome_offset = _outcome_offset(outcome_convention)
        frame = pd.concat(
            [
                signals.rename("signal"),
                gross_edges.rename("gross_edge"),
                costs.rename("cost"),
            ],
            axis=1,
        ).sort_index()
        if frame.index.has_duplicates:
            raise ValueError("backtest timestamps must be unique")
        # The bar a decision is settled by, relative to the decision bar. Under
        # the forward labelling that is the following bar; under the realised
        # labelling a decision may only be settled by the bar it was taken on.
        settled_gross = frame["gross_edge"].shift(-outcome_offset)
        settled_cost = frame["cost"].shift(-outcome_offset)
        # The last `outcome_offset` bars have no bar to settle them.
        decidable = frame.index[: len(frame.index) - outcome_offset]
        trades = tuple(
            NoLookAheadTrade(
                decision_timestamp=timestamp,
                execution_timestamp=frame.index[position + outcome_offset],
                signal=float(frame.at[timestamp, "signal"]),
                gross_edge=float(settled_gross.at[timestamp]),
                cost=float(settled_cost.at[timestamp]),
            )
            for position, timestamp in enumerate(decidable)
            if pd.notna(frame.at[timestamp, "signal"])
            and bool(frame.at[timestamp, "signal"])
            and pd.notna(settled_gross.at[timestamp])
            and pd.notna(settled_cost.at[timestamp])
        )
        return NoLookAheadResult(self.summarize_trades(trades), trades)

    def summarize_trades(self, trades: tuple[NoLookAheadTrade, ...]) -> BacktestMetrics:
        trade_frame = pd.DataFrame(
            [(trade.gross_edge, trade.cost) for trade in trades],
            index=pd.RangeIndex(len(trades)),
            columns=["gross_edge", "cost"],
        )
        return self.run(trade_frame["gross_edge"], trade_frame["cost"])


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
