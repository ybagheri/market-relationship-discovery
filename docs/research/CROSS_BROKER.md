# Cross-Broker Comparison

## Objective

Cross-broker comparison distinguishes theoretical price differences from bid/ask-crossing research discrepancies. A crossable observation requires one broker's ask to be below the other broker's bid by more than the configured additional cost. This is not called risk-free arbitrage or guaranteed execution.

## Synchronization

`CrossBrokerComparisonEngine` supports `anchor_a` and one-to-one mutual-nearest `symmetric` synchronization. Signed source delay and unmatched counts are retained. Tick duplicate timestamp updates are preserved in raw storage and explicitly aggregated as `last` by default; `none` rejects them.

The dashboard visualizes persisted comparison previews. It does not replace the full-resolution engine or establish an executable timeline.

## Tick comparison

Tick data reports mid, bid, and ask differences in both directions. The two gross directional edges are:

- Broker B bid minus Broker A ask
- Broker A bid minus Broker B ask

Each edge is reduced by `additional_cost`. Positive net observations are grouped into contiguous opportunity episodes with direction, start, end, duration, observation count, and maximum/mean edge. Summary metrics include frequency, duration, delay, spread-inclusive differences, and unmatched observations.

## Bar safety

Bar comparison uses close prices and is always classified as `theoretical_bar_price_comparison`. It never creates crossable opportunities, even when the price difference is large. Bar data cannot establish tick-level execution.

## Contract safety gate

Tick comparisons can receive two `ContractSpecification` JSON files. Missing specs are labeled unverified. Incompatible contracts, missing trade modes, and contract-size or tick-value differences requiring normalization block opportunity episodes. A validated classification requires compatible currency, point/digits, volume constraints, trade mode, contract size, and tick value.

## Reproducibility

The `compare-brokers` CLI accepts CSV or Parquet files and records both source filenames and SHA-256 hashes, symbol, broker labels, observation type, alignment tolerance, additional cost, period, and aligned preview rows in an `EXP-*` JSON report.

## Visualization

Persisted `EXP-*.json` comparison reports are available in the dashboard. The discrepancy explorer plots selectable bid/ask/mid, net-edge, PnL, and delay metrics with the configured cost reference and crossable observations. The broker comparison view plots aligned mid prices for both broker labels. These are read-only descriptive views over the report preview, not execution evidence.

## Limitations

The engine normalizes compatible contract size and tick-value differences, but does not model currency conversion, funding, rebates, trading sessions, symbol construction, or broker-specific execution rules. Additional cost is a single fixed research assumption. A positive crossable episode is only a candidate for deeper execution research.
