# Data Quality

## Collection checks

Every stored dataset is rejected before writing when required columns are missing, values are absent, timestamps are duplicated, quotes contain invalid bid/ask values, or OHLC/volume invariants fail. The system does not silently repair or drop rows.

A manifest records dataset ID, broker profile, server, symbol, data type, timeframe, source period, row count, software version, collection parameters, offset, and quality counters. Parquet and JSON files are written through temporary files and then atomically renamed.

## Time normalization

All normalized timestamps are timezone-aware UTC. The raw MT5 timestamp is retained as `source_timestamp`. Some local installations expose a verified broker-clock offset even though the integration otherwise behaves as UTC. Such an offset must be configured explicitly with `source_utc_offset_minutes`; the default is zero.

Do not infer an offset from price behavior. Compare a current source timestamp with the machine UTC clock, verify the cause, configure the value locally, and retain the raw timestamp. Historical collection converts the requested UTC range back to the source clock before calling MT5.

## Research alignment

Bar series use backward alignment with a configured tolerance. A missing or stale dependency is dropped and delay is retained for reporting. Bar closes are research observations only and cannot be labeled executable.

## Limitations

The current validator does not yet detect every feed gap, contract-specification mismatch, session boundary, or abnormal tick-interval pattern. Those checks are planned.
