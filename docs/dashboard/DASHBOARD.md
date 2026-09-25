# Dashboard

## Purpose

The Streamlit dashboard is a read-only research presentation. It always displays `DEMO / RESEARCH MODE — NO LIVE TRADING` and never places, routes, or simulates orders.

## Report source

The dashboard scans `DATA__REPORTS_DIRECTORY` for `EXP-*.json` files whose experiment type is `cross_broker_comparison`. The `Discrepancy Explorer` and `Broker Comparison` tabs read the persisted manifest, summary, opportunities, and aligned preview.

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

## Safety and limitations

Dashboard code does not read or display account passwords or logins. The charts do not add funding, commission, margin, slippage, latency, partial-fill, or broker-specific execution modeling beyond what is already recorded in the report. Use the underlying research and validation reports before drawing conclusions.
