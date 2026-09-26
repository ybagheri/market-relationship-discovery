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


def candidate_significance_figure(candidates: pd.DataFrame, alpha: float) -> go.Figure:
    """Raw against adjusted p-value per candidate, with the alpha threshold.

    Plotting both makes the effect of the correction visible: a candidate whose
    adjusted value crosses the line no longer survives, and the gap between the
    two bars is exactly what multiplicity cost.
    """
    figure = go.Figure()
    if candidates.empty or "adjusted_p_value" not in candidates:
        figure.update_layout(
            title="No candidate significance results",
            xaxis_title="Candidate",
            yaxis_title="p-value",
        )
        return figure
    ordered = candidates.sort_values("adjusted_p_value", na_position="last")
    names = [str(name) for name in ordered["name"]]
    figure.add_trace(
        go.Bar(
            x=names,
            y=pd.to_numeric(ordered.get("raw_p_value"), errors="coerce"),
            name="raw p-value",
            marker={"color": "steelblue"},
            hovertemplate="%{x}<br>raw p=%{y}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Bar(
            x=names,
            y=pd.to_numeric(ordered.get("adjusted_p_value"), errors="coerce"),
            name="adjusted p-value",
            marker={"color": "indianred"},
            hovertemplate="%{x}<br>adjusted p=%{y}<extra></extra>",
        )
    )
    figure.add_hline(
        y=alpha,
        line={"dash": "dash", "color": "gray"},
        annotation_text=f"alpha={alpha}",
        annotation_position="top left",
    )
    figure.update_layout(
        title="Candidate significance after false-discovery control — not tradability",
        xaxis_title="Candidate",
        yaxis_title="p-value",
        barmode="group",
        hovermode="x unified",
    )
    return figure


def coverage_figure(coverage: pd.DataFrame, union_rows: int | None) -> go.Figure:
    """Per-symbol coverage of the analysed panel.

    A symbol that covers almost none of the union window cannot be compared with
    one that covers all of it, so this chart is the context for every candidate
    computed from the same panel.
    """
    figure = go.Figure()
    if coverage.empty or "coverage_fraction" not in coverage:
        figure.update_layout(
            title="No coverage information",
            xaxis_title="Symbol",
            yaxis_title="Coverage of union window",
        )
        return figure
    ordered = coverage.sort_values("coverage_fraction", ascending=False)
    names = [str(name) for name in ordered["symbol"]]
    analysed = (
        [bool(value) for value in ordered["analysed"]]
        if "analysed" in ordered
        else [True] * len(names)
    )
    figure.add_trace(
        go.Bar(
            x=names,
            y=pd.to_numeric(ordered["coverage_fraction"], errors="coerce"),
            name="analysed",
            marker={"color": ["seagreen" if flag else "lightgray" for flag in analysed]},
            customdata=pd.to_numeric(ordered.get("observations"), errors="coerce"),
            hovertemplate="%{x}<br>coverage=%{y}<br>observations=%{customdata}<extra></extra>",
        )
    )
    title = "Panel coverage by symbol — grey symbols were excluded from analysis"
    if union_rows:
        title = f"{title} (union window {int(union_rows)} rows)"
    figure.update_layout(
        title=title,
        xaxis_title="Symbol",
        yaxis_title="Fraction of union window",
        hovermode="x unified",
    )
    return figure
