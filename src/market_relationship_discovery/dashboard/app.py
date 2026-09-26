from __future__ import annotations

from typing import cast

import streamlit as st

from market_relationship_discovery import __version__
from market_relationship_discovery.application.commands import resolve_profile
from market_relationship_discovery.config import get_settings
from market_relationship_discovery.dashboard.brokers import (
    ProfileStatus,
    configured_profiles,
    monitor_symbols,
    profile_health,
    quote_rows,
)
from market_relationship_discovery.dashboard.charts import (
    DISCREPANCY_COLUMNS,
    broker_price_figure,
    candidate_significance_figure,
    coverage_figure,
    discrepancy_figure,
)
from market_relationship_discovery.dashboard.reports import (
    aligned_frame,
    as_count,
    as_float,
    as_records,
    as_str_list,
    candidate_frame,
    coverage_frame,
    list_comparison_reports,
    list_discovery_reports,
    load_comparison_report,
    load_discovery_report,
    opportunity_frame,
)
from market_relationship_discovery.infrastructure.mt5.adapter import MT5Adapter
from market_relationship_discovery.relationships.catalog import RelationshipCatalog

st.set_page_config(page_title="Market Relationship Discovery", layout="wide")
st.warning("DEMO / RESEARCH MODE — NO LIVE TRADING")
settings = get_settings()
st.title("Market Relationship Discovery")
st.caption(f"Version {__version__} — research candidates are not guaranteed opportunities")

profiles = configured_profiles(settings)
profile_labels = {item.name: item.label for item in profiles}
selected_profile = st.sidebar.selectbox(
    "Broker profile",
    options=[item.name for item in profiles],
    format_func=lambda name: profile_labels[name],
    help="Each profile is an independent demo-only terminal.",
)


def _render_execution(execution: dict[str, object]) -> None:
    """Show the capital and fill verdict recorded with a comparison report.

    A report written before this layer existed has no execution block, so the
    absence is stated rather than being read as approval.
    """
    st.subheader("Execution and capital")
    if not execution:
        st.info(
            "This report predates margin, funding, and fill modelling. "
            "Capital adequacy and achievable size are unknown."
        )
        return
    if execution.get("executable"):
        st.success("No known configured constraint rules out the sized position.")
    else:
        st.error("A known constraint rules out the sized position.")
    st.write(f"Capital verified: **{execution.get('capital_verified')}**")
    total_margin = execution.get("total_margin")
    if isinstance(total_margin, (int, float)):
        st.write(f"Total margin across both legs: **{float(total_margin):.2f}**")
    else:
        st.write("Total margin across both legs: **unknown**")
    st.write(f"Binding fill ratio: **{execution.get('binding_fill_ratio')}**")
    for leg in ("margin_a", "margin_b", "fill_a", "fill_b"):
        block = execution.get(leg)
        if isinstance(block, dict):
            st.write(f"`{leg}`: {block}")
    reasons = execution.get("reasons")
    if isinstance(reasons, list) and reasons:
        st.markdown("**Reasons**")
        for reason in reasons:
            st.markdown(f"- {reason}")
    st.caption(
        "Fill estimates respect volume step and maximum but do not model queue "
        "position, partial-fill probability, or rejection."
    )
    _render_latency(cast(dict[str, object], report.get("latency", {})))


def _render_latency(latency: dict[str, object]) -> None:
    """Show how much of each measured episode survives a round trip.

    An episode count alone is misleading: a crossable tick that existed for one
    instant is counted the same as one that stayed open for a minute.
    """
    st.subheader("Latency capture")
    if not latency:
        st.info(
            "This report predates latency capture modelling, or no measurable "
            "opportunity episode was recorded. Whether the observed windows were "
            "long enough to act in is unknown."
        )
        return
    episodes = as_count(latency.get("episodes"))
    capturable = as_count(latency.get("capturable"))
    assumptions = latency.get("assumptions")
    round_trip = as_float(_as_float_dict(assumptions).get("round_trip_ms"), 0.0)
    st.write(
        f"Episodes **{episodes}** | capturable **{capturable}** | "
        f"marginal **{as_count(latency.get('marginal'))}** | "
        f"not capturable **{as_count(latency.get('not_capturable'))}** | "
        f"round trip **{round_trip} ms**"
    )
    st.write(
        f"Median episode **{as_float(latency.get('median_duration_ms')):.0f} ms** | "
        f"longest **{as_float(latency.get('maximum_duration_ms')):.0f} ms** | "
        f"mean peak edge **{as_float(latency.get('mean_peak_edge')):.6f}** | "
        f"mean captured edge **{as_float(latency.get('mean_captured_edge')):.6f}**"
    )
    if capturable == 0:
        st.error(
            "No measured episode outlasted the round trip, so none of the "
            "observed opportunities could be acted on under these assumptions."
        )
    captures = as_records(latency.get("captures"))
    if captures:
        st.dataframe(
            [
                {
                    "Episode": item.get("label"),
                    "Duration (ms)": item.get("duration_ms"),
                    "Peak edge": item.get("peak_edge"),
                    "Capturable fraction": item.get("capturable_fraction"),
                    "Net captured edge": item.get("net_captured_edge"),
                    "Status": item.get("status"),
                }
                for item in captures
            ],
            width="stretch",
        )
    st.caption(
        "Capturable fraction assumes linear edge decay over a measured episode. "
        "Queue position, book depth, and fill probability are not modelled."
    )


def _as_float_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


overview, monitor, relationships, discovery, discrepancy, brokers, limitations = st.tabs(
    [
        "Overview",
        "Market Monitor",
        "Relationship Explorer",
        "Discovery",
        "Discrepancy Explorer",
        "Broker Comparison",
        "Limitations",
    ]
)

with overview:
    st.subheader("Configured brokers")
    st.caption(
        "Every profile is diagnosed independently. A passing check on one profile "
        "says nothing about another."
    )
    st.dataframe(
        [item.to_dict() for item in profiles],
        width="stretch",
    )
    if st.button("Check every configured profile"):
        rows = [profile_health(settings, item.name).to_dict() for item in profiles]
        st.dataframe(rows, width="stretch")
        unknown = [row for row in rows if row["status"] == ProfileStatus.CONNECTED_UNKNOWN_MODE]
        if unknown:
            st.error(
                "A connected account could not be verified as DEMO: "
                ", ".join(str(row["profile"]) for row in unknown)
            )
        elif all(row["status"] == ProfileStatus.CONNECTED_DEMO for row in rows):
            st.success("Every configured profile is connected and demonstrably DEMO.")

    st.subheader("Selected profile")
    reference = next(item for item in profiles if item.name == selected_profile)
    st.write(f"Profile: **{reference.label}**")
    st.write(f"Configured terminal: `{reference.terminal_path or 'not configured'}`")
    st.write(f"Demo-only safety: **{reference.demo_only}**")
    st.write("No order execution methods are implemented.")

with monitor:
    st.caption(
        "Symbols are resolved to each broker's own label. A broker that publishes "
        "gold as `XAUUSD` and bitcoin as `BITCOIN` needs no configuration change here."
    )
    if st.button(f"Connect to {profile_labels[selected_profile]}"):
        try:
            profile, _ = resolve_profile(settings, selected_profile)
            with MT5Adapter(profile) as adapter:
                account = adapter.account_info()
                st.success(f"Connected to {account.server} ({account.mode})")
                resolved, missing = monitor_symbols(settings, selected_profile, adapter)
                st.dataframe(quote_rows(adapter, resolved), width="stretch")
                if missing:
                    st.info("Not offered by this broker: " + ", ".join(missing))
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
        width="stretch",
    )
    st.caption(
        "This is the declared catalog, not evidence. Use the Discovery tab for "
        "evaluated candidates from a real run."
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
discovery_reports = list_discovery_reports(report_directory)
discovery_labels = {
    reference: (
        f"{reference.source_file_name} | {reference.candidate_count} tested | "
        f"{reference.retained_after_correction} retained | {reference.created_at}"
    )
    for reference in discovery_reports
}

with discovery:
    st.subheader("Evaluated candidates")
    if not discovery_reports:
        st.info(
            f"No advanced discovery reports found in {report_directory}. "
            "Run `discover --input <panel.csv>` to produce one."
        )
    else:
        selected = st.selectbox(
            "Discovery report",
            options=discovery_reports,
            format_func=lambda reference: discovery_labels[reference],
            key="discovery_report",
        )
        loaded = load_discovery_report(selected.path)
        multiplicity = cast(dict[str, object], loaded["multiplicity"])
        coverage = cast(dict[str, object], loaded["coverage"])
        deduplication = cast(dict[str, object], loaded["deduplication"])

        alpha = as_float(multiplicity.get("alpha"), 0.05)
        st.write(
            f"Method **{multiplicity.get('method')}** at alpha **{alpha}** | "
            f"tests **{multiplicity.get('tests')}** | "
            f"expected false positives **{multiplicity.get('expected_false_positives')}** | "
            f"unadjusted rejections **{multiplicity.get('unadjusted_rejections')}** | "
            f"after correction **{multiplicity.get('adjusted_rejections')}**"
        )

        candidates = candidate_frame(selected.path)
        if candidates.empty:
            st.warning("This report contains no candidate rows.")
        else:
            st.plotly_chart(
                candidate_significance_figure(candidates, alpha),
                width="stretch",
            )
            contested = as_count(multiplicity.get("contested"))
            if contested:
                st.warning(
                    f"{contested} candidate(s) are **contested**: the ADF and KPSS "
                    "stationarity tests disagreed, so the verdict rests on one of "
                    "two conflicting tests."
                )
            st.dataframe(
                candidates[
                    [
                        column
                        for column in (
                            "name",
                            "target",
                            "formula",
                            "status",
                            "raw_p_value",
                            "adjusted_p_value",
                            "survived_correction",
                            "contested",
                            "pearson",
                            "half_life",
                            "mean_absolute_discrepancy",
                        )
                        if column in candidates
                    ]
                ],
                width="stretch",
            )

        st.subheader("Panel coverage")
        st.caption(
            "Symbols collected in one request can cover different calendar ranges. "
            "Only symbols present throughout the analysed window take part."
        )
        union_rows = coverage.get("union_rows")
        st.plotly_chart(
            coverage_figure(
                coverage_frame(selected.path),
                as_count(union_rows) or None,
            ),
            width="stretch",
        )
        excluded = as_str_list(coverage.get("excluded_symbols"))
        if excluded:
            st.info("Excluded from analysis: " + ", ".join(excluded))
        issues = as_str_list(coverage.get("issues"))
        if issues:
            st.markdown("**Coverage findings**")
            for issue in issues:
                st.markdown(f"- {issue}")

        removed = as_records(deduplication.get("removed_duplicates"))
        if removed:
            st.info(
                f"{len(removed)} duplicate candidate(s) were collapsed before testing: "
                + ", ".join(str(item.get("removed")) for item in removed)
            )
        unparsable = as_str_list(deduplication.get("unparsable_formulas"))
        if unparsable:
            st.warning(
                "Candidates with an unusable formula were excluded: " + ", ".join(unparsable)
            )

        recorded_limitations = as_str_list(loaded["limitations"])
        if recorded_limitations:
            with st.expander("Limitations recorded with this run"):
                for limitation in recorded_limitations:
                    st.markdown(f"- {limitation}")

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
            width="stretch",
        )
        st.caption(
            f"Aligned observations: {len(aligned)} | report preview is limited to 20 rows | "
            "research only, not executable"
        )
        st.dataframe(aligned, width="stretch")
        if not opportunities.empty:
            st.dataframe(opportunities, width="stretch")
        _render_execution(cast(dict[str, object], report.get("execution", {})))

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
            width="stretch",
        )
        st.caption(
            "Mid prices are descriptive observations and do not establish executable arbitrage."
        )
        _render_execution(cast(dict[str, object], report.get("execution", {})))

with limitations:
    st.markdown("""
Correlation is not arbitrage. A mid-price discrepancy can vanish after spread,
commission, slippage, latency, session differences, feed differences, and symbol
construction. Historical mean reversion does not guarantee future behavior.

Dashboard charts are read-only research views over persisted experiment previews.
They do not place, route, or simulate orders.
""")
