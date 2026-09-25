# Event-Time Synchronization

## Modes

`anchor_a` uses every Broker A timestamp and selects the nearest Broker B observation inside the configured tolerance. This mode is fast but can reuse one Broker B tick for several Broker A updates.

`symmetric` keeps only mutual-nearest matches: Broker A must be nearest to Broker B and Broker B must independently be nearest to Broker A. This produces a one-to-one comparison set and prevents duplicate reuse of a quote. The report includes synchronized mode, signed delay, and unmatched counts for both feeds.

## Tick updates

Some brokers return multiple bid/ask updates with the same timestamp. Raw Parquet storage preserves these duplicates and records their count. Cross-broker tick comparison defaults to explicit `last` aggregation, selecting the last update at each timestamp. `tick_aggregation=none` rejects duplicates instead.

## Selection bias

Mutual matching improves quote reuse but does not guarantee economically simultaneous observations. Sparse feeds, different update rates, market closures, and timestamp corruption can still leave few or no matches. Opportunity frequency from one observation is not stable evidence and must be reported with observation count and duration.

## Future work

A full event-time state machine can model interval validity, sequence IDs, quote revisions, and session boundaries. The current implementation deliberately does not interpolate prices or carry a stale quote across a rejected match.
