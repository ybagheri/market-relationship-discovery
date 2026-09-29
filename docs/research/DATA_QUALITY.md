# Data Quality

## Collection checks

Every stored dataset is rejected before writing when required columns, values, quote invariants, or OHLC/volume invariants fail. Duplicate timestamps are counted **within one symbol of one broker**, because two symbols quoting the same instant is the normal case for a multi-symbol collection and two brokers quoting one instant is the basis of a comparison; a repeated timestamp for the same symbol from the same broker is the case that corrupts a series. Tick feeds may contain multiple legitimate quote updates at one timestamp; these raw rows are preserved and counted in the manifest. Comparison applies an explicit `last` or `none` tick-aggregation policy. No row is silently repaired or dropped.

Prices are read explicitly rather than compared as they arrive, so a column holding text is a reported data problem instead of a bare `TypeError` from a string comparison. A value that is present but unparseable is reported as `unreadable_price`, which is deliberately distinct from a value that is absent: one is a bad reading and the other is no reading.

A manifest records dataset ID, broker profile, server, symbol, data type, timeframe, source period, row count, software version, collection parameters, offset, and quality counters. Parquet and JSON files are written through temporary files and then atomically renamed.

## Time normalization

All normalized timestamps are timezone-aware UTC. The raw MT5 timestamp is retained as `source_timestamp`. Some local installations expose a verified broker-clock offset even though the integration otherwise behaves as UTC. Such an offset must be configured explicitly with `source_utc_offset_minutes`; the default is zero.

Every calculation in the platform is UTC. `DATA__TIMEZONE` selects the timezone a cross-broker report *displays*, so a reader can recognise an observation against a local clock; the underlying instant is unchanged, so two reports in different timezones describe the same observations. It is validated as a real IANA name so a typo is refused rather than silently ignored, and it is deliberately **not** part of the `doctor` safety verdict: it previously was, while no data path honoured it, which failed a safety check that had nothing to do with safety and implied a control that did not exist.

Do not infer an offset from price behavior. Compare a current source timestamp with the machine UTC clock, verify the cause, configure the value locally, and retain the raw timestamp. Historical collection converts the requested UTC range back to the source clock before calling MT5.

## Research alignment

Bar series use backward alignment with a configured tolerance. A missing or stale dependency is dropped and delay is retained for reporting. Bar closes are research observations only and cannot be labeled executable.

Three alignment implementations exist and they are not interchangeable:

- `market_data.alignment` aligns two frames within a tolerance. It returns only matched rows, because an unmatched row is not a measurement, and the `align` entry point reports how many left and right rows found no partner.
- `market_data.cross_broker` aligns two broker feeds within a tolerance and counts the rows it dropped, in both the anchored and symmetric modes.
- `research.service` aligns several symbols for a single-broker relationship study, where a shared window is chosen first and the delay is kept per symbol.

The symmetric event-time match in `cross_broker` is a different rule chosen on purpose: it pairs each quote with the mutual nearest neighbour so no quote is reused, which reusing one quote would prevent. A count of matched observations from a nearest-neighbour rule is therefore not comparable to one from a within-tolerance rule, and the two must not be substituted for each other.

## Limitations

The current validator does not yet detect every feed gap, contract-specification mismatch, session boundary, or abnormal tick-interval pattern. Those checks are planned.
