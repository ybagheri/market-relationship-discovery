from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

DISCREPANCY_COLUMNS = (
    "mid_difference",
    "bid_difference",
    "ask_difference",
    "net_crossable_edge",
    "normalized_net_pnl",
    "alignment_delay_ms",
)


def discrepancy_figure(
    aligned: pd.DataFrame,
    column: str,
    additional_cost: float,
) -> go.Figure:
    figure = go.Figure()
    if aligned.empty or column not in aligned:
        figure.update_layout(
            title="No aligned observations",
            xaxis_title="Timestamp (UTC)",
            yaxis_title=column,
        )
        return figure

    timestamps = (
        aligned["timestamp"] if "timestamp" in aligned else pd.Series(dtype="datetime64[ns]")
    )
    values = pd.to_numeric(aligned[column], errors="coerce")
    figure.add_trace(
        go.Scatter(
            x=timestamps,
            y=values,
            name=column,
            mode="lines+markers",
            connectgaps=False,
            hovertemplate="%{x|%Y-%m-%d %H:%M:%S UTC}<br>" + column + "=%{y}<extra></extra>",
        )
    )
    if values.notna().any():
        first = timestamps[values.notna()].iloc[0]
        last = timestamps[values.notna()].iloc[-1]
        figure.add_trace(
            go.Scatter(
                x=[first, last],
                y=[additional_cost, additional_cost],
                name="additional_cost",
                mode="lines",
                line={"dash": "dash", "color": "gray"},
                hovertemplate="additional_cost=%{y}<extra></extra>",
            )
        )
    if "is_crossable" in aligned:
        crossable = aligned["is_crossable"].astype(bool)
        if crossable.any():
            figure.add_trace(
                go.Scatter(
                    x=timestamps[crossable],
                    y=values[crossable],
                    name="crossable observations",
                    mode="markers",
                    marker={"color": "red", "size": 8},
                    hovertemplate="crossable<br>%{x|%Y-%m-%d %H:%M:%S UTC}<br>"
                    + column
                    + "=%{y}<extra></extra>",
                )
            )
    figure.update_layout(
        title=f"{column} — research, not executable",
        xaxis_title="Timestamp (UTC)",
        yaxis_title=column,
        hovermode="x unified",
    )
    return figure


def broker_price_figure(
    aligned: pd.DataFrame,
    broker_a: str,
    broker_b: str,
) -> go.Figure:
    figure = go.Figure()
    if aligned.empty or "a_mid" not in aligned or "b_mid" not in aligned:
        figure.update_layout(
            title="No broker prices", xaxis_title="Timestamp (UTC)", yaxis_title="Mid"
        )
        return figure
    timestamps = (
        aligned["timestamp"] if "timestamp" in aligned else pd.Series(dtype="datetime64[ns]")
    )
    for column, name in (("a_mid", broker_a), ("b_mid", broker_b)):
        figure.add_trace(
            go.Scatter(
                x=timestamps,
                y=pd.to_numeric(aligned[column], errors="coerce"),
                name=name,
                mode="lines",
                connectgaps=False,
                hovertemplate="%{x|%Y-%m-%d %H:%M:%S UTC}<br>" + name + "=%{y}<extra></extra>",
            )
        )
    figure.update_layout(
        title="Broker mid prices — research, not executable",
        xaxis_title="Timestamp (UTC)",
        yaxis_title="Mid price",
        hovermode="x unified",
    )
    return figure
