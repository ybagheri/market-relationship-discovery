from __future__ import annotations

from typing import cast

import streamlit as st

from market_relationship_discovery import __version__
from market_relationship_discovery.config import get_settings
from market_relationship_discovery.dashboard.charts import (
    DISCREPANCY_COLUMNS,
    broker_price_figure,
    discrepancy_figure,
)
from market_relationship_discovery.dashboard.reports import (
    aligned_frame,
    list_comparison_reports,
    load_comparison_report,
    opportunity_frame,
)
from market_relationship_discovery.infrastructure.mt5.adapter import MT5Adapter
from market_relationship_discovery.relationships.catalog import RelationshipCatalog

st.set_page_config(page_title="Market Relationship Discovery", layout="wide")
st.warning("DEMO / RESEARCH MODE — NO LIVE TRADING")
settings = get_settings()
st.title("Market Relationship Discovery")
st.caption(f"Version {__version__} — research candidates are not guaranteed opportunities")

overview, monitor, relationships, discrepancy, brokers, limitations = st.tabs(
    [
        "Overview",
        "Market Monitor",
        "Relationship Explorer",
        "Discrepancy Explorer",
        "Broker Comparison",
        "Limitations",
    ]
)

with overview:
    st.write(f"Configured terminal: `{settings.mt5.terminal_path or 'not configured'}`")
    st.write(f"Demo-only safety: **{settings.mt5.demo_only}**")
    st.write("No order execution methods are implemented.")

with monitor:
    if st.button("Connect to configured MT5 terminal"):
        try:
            with MT5Adapter(settings.mt5) as adapter:
                account = adapter.account_info()
                st.success(f"Connected to {account.server} ({account.mode})")
                rows = [
                    {
                        "Symbol": symbol,
                        "Bid": adapter.current_quote(symbol).bid,
                        "Ask": adapter.current_quote(symbol).ask,
                        "Timestamp (UTC)": adapter.current_quote(symbol).timestamp,
                    }
                    for symbol in list(settings.symbol_mapping)[:8]
                ]
                st.dataframe(rows, use_container_width=True)
        except Exception as exc:
            st.error(str(exc))

with relationships:
    catalog = RelationshipCatalog()
    st.dataframe(
        [
            {
                "Name": item.name,
                "Target": item.target,
                "Formula": item.formula,
                "Status": item.classification,
            }
            for item in catalog.all()
        ],
        use_container_width=True,
    )

report_directory = settings.data.reports_directory
reports = list_comparison_reports(report_directory)
report_labels = {
    reference: (
        f"{reference.symbol} | {reference.broker_a} vs {reference.broker_b} | "
        f"{reference.created_at}"
    )
    for reference in reports
}

with discrepancy:
    st.subheader("Cross-broker discrepancy")
    if not reports:
        st.info(f"No cross-broker comparison reports found in {report_directory}.")
    else:
        selected_report = st.selectbox(
            "Comparison report",
            options=reports,
            format_func=lambda reference: report_labels[reference],
        )
        report = load_comparison_report(selected_report.path)
        aligned = aligned_frame(selected_report.path)
        opportunities = opportunity_frame(selected_report.path)
        summary = cast(dict[str, object], report["summary"])
        additional_cost_value = summary.get("additional_cost", 0.0)
        additional_cost = (
            float(additional_cost_value) if isinstance(additional_cost_value, (int, float)) else 0.0
        )
        st.write(
            f"**{summary.get('broker_a', 'Broker A')} vs {summary.get('broker_b', 'Broker B')}** "
            f"— {summary.get('symbol', 'unknown')}"
        )
        column = st.selectbox("Metric", options=DISCREPANCY_COLUMNS)
        st.plotly_chart(
            discrepancy_figure(aligned, column, additional_cost),
            use_container_width=True,
        )
        st.caption(
            f"Aligned observations: {len(aligned)} | report preview is limited to 20 rows | "
            "research only, not executable"
        )
        st.dataframe(aligned, use_container_width=True)
        if not opportunities.empty:
            st.dataframe(opportunities, use_container_width=True)

with brokers:
    st.subheader("Broker mid-price comparison")
    if not reports:
        st.info("Select a cross-broker comparison report in Discrepancy Explorer.")
    else:
        selected_report = st.selectbox(
            "Comparison report",
            options=reports,
            format_func=lambda reference: report_labels[reference],
            key="broker_report",
        )
        report = load_comparison_report(selected_report.path)
        summary = cast(dict[str, object], report["summary"])
        aligned = aligned_frame(selected_report.path)
        st.plotly_chart(
            broker_price_figure(
                aligned,
                str(summary.get("broker_a", "Broker A")),
                str(summary.get("broker_b", "Broker B")),
            ),
            use_container_width=True,
        )
        st.caption(
            "Mid prices are descriptive observations and do not establish executable arbitrage."
        )

with limitations:
    st.markdown("""
Correlation is not arbitrage. A mid-price discrepancy can vanish after spread,
commission, slippage, latency, session differences, feed differences, and symbol
construction. Historical mean reversion does not guarantee future behavior.

Dashboard charts are read-only research views over persisted experiment previews.
They do not place, route, or simulate orders.
""")
