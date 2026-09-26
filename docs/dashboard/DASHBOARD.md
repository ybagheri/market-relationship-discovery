# Dashboard

## Purpose

The Streamlit dashboard is a read-only research presentation. It always displays `DEMO / RESEARCH MODE — NO LIVE TRADING` and never places, routes, or simulates orders.

## Multiple brokers

The sidebar lists every configured broker profile, with the default profile first.
Selecting a profile drives the Overview and Market Monitor views.

A previous version assumed a single terminal, which made a second configured
broker invisible. The market monitor also requested quotes using canonical
research names such as `XAUUSD`, which fails on a broker that publishes the
instrument under a different label. Symbols are now resolved per profile through
the same `SymbolMapper` the CLI and collector use, so one broker publishing gold
as `XAUUSD` and bitcoin as `BITCOIN` needs no dashboard change. Symbols a broker
does not offer are listed rather than silently skipped.

Each profile is diagnosed independently, because a passing check on one says
nothing about another. A failed or unconfigured profile is reported as data so
one closed terminal cannot break the page.

## Report source

The dashboard scans `DATA__REPORTS_DIRECTORY` for `EXP-*.json` files whose experiment type is `cross_broker_comparison`. The `Discrepancy Explorer` and `Broker Comparison` tabs read the persisted manifest, summary, opportunities, execution verdict, and aligned preview.

Run `compare-brokers` again after collecting or comparing new sources. A report stores at most 20 aligned preview rows, so the charts are intentionally a quick inspection surface rather than a full-resolution data explorer.

## Discrepancy Explorer

The explorer plots one selectable metric over UTC timestamps:

- `mid_difference`
- `bid_difference`
- `ask_difference`
- `net_crossable_edge`
- `normalized_net_pnl`
- `alignment_delay_ms`

The configured additional cost is shown as a reference line. Crossable observations are highlighted separately. The aligned table and opportunity episodes remain visible below the chart.

## Broker Comparison

The broker view plots aligned `a_mid` and `b_mid` values using the broker labels stored in the report. It is descriptive only: a visible price difference does not establish simultaneous execution, account permissions, liquidity, or guaranteed profit.

## Execution and capital

Both comparison views show the execution verdict recorded with the report: whether the sized position is ruled out by a known constraint, whether capital was verified, the total margin across both legs, the binding fill ratio, and the reasons behind the verdict. A report written before this layer existed says so explicitly, because the absence of a verdict must not be read as approval.

## Safety and limitations

Dashboard code does not read or display account passwords or logins. Charts remain descriptive: they add no funding, commission, margin, slippage, latency, or partial-fill modelling beyond what the report already records. Use the underlying research and validation reports before drawing conclusions.

## Testing

`tests/integration/test_dashboard_render.py` executes the page script with
Streamlit's `AppTest`. A socket check only proves the server started, because
Streamlit runs the page script when a browser opens a session, so a crash in the
script is otherwise invisible. The suite asserts the script renders without
exception, the safety banner is present, the documented tabs exist, and the
profile selector is populated.
