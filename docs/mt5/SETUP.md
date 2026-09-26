# MT5 Setup

## Requirements

- Windows and MetaTrader 5
- Python 3.12 or newer
- A terminal connected to an account that can be verified as `DEMO`
- No repository dependency on account credentials

## Configuration

1. Copy `.env.example` to `.env`.
2. Set `MT5__TERMINAL_PATH` to the local `terminal64.exe` path.
3. Set `MT5__DATA_PATH` to the matching terminal data directory for diagnostics.
4. Keep `MT5__DEMO_ONLY=true`.
5. Keep `MT5__SOURCE_UTC_OFFSET_MINUTES=0` unless a source clock offset has been verified.
6. Open the terminal once and sign in through MetaTrader's own UI.
7. Run `python -m market_relationship_discovery doctor`.

The official Python package selects the terminal through its executable path. It does not expose a safe supported argument for forcing an arbitrary data directory, so the configured data path is a diagnostic path rather than an override.

Additional terminals are configured as JSON profiles under `BROKERS`. Each profile remains demo-only. Sequential collection is the default. `--parallel` creates one isolated worker process per profile because the official Python module owns a process-global terminal connection. See [parallel collection](PARALLEL_COLLECTION.md).

## Symbol names

Do not assume `XAUUSD`, `XAGUSD`, or `XAUEUR`. Brokers name instruments differently, and a broker can expose far more symbols than appear in the terminal watch window. Discovery matches a query against the symbol name, the broker-supplied description, and the canonical alias table, and reports which rule matched.

```bash
python -m market_relationship_discovery symbols --search gold
python -m market_relationship_discovery symbols --search silver
python -m market_relationship_discovery symbols --search eur
python -m market_relationship_discovery symbols --search dollar
python -m market_relationship_discovery symbols --search XAUUSD --json
```

By default the search covers the whole broker catalog and excludes symbols the broker reports as not tradable. Useful flags:

| Flag | Effect |
| --- | --- |
| `--search TEXT` | Match name, description, or alias |
| `--visible-only` | Restrict to the terminal watch window |
| `--all` | Include symbols the broker marks not tradable |
| `--json` | Machine-readable output with metadata |

The header line reports `catalog_size`, `tradable`, and `match_count`, which is the quickest way to see how much a broker actually offers. Each row shows `mode`, `tradable`, `matched`, `canonical`, and the broker description.

Store resolved mappings in `.env`. Broker suffixes and prefixes are meaningful and must not be hard-coded in the engine. Export local contract metadata with `symbol-specs` before contract-gated cross-broker comparison.

A symbol whose trade mode is unknown is treated as not tradable, so missing metadata can never be read as an executable opportunity.

## Tick collection

Tick requests search a window ending at the current time and keep the newest rows, widening the window while too few ticks are available. Outside trading hours the most recent tick can be far behind the clock, so `MT5__TICK_LOOKBACK_HOURS` sets the initial window and `MT5__TICK_MAX_LOOKBACK_HOURS` caps the widening. An empty result after the maximum lookback reports that the market may be closed rather than a generic connection failure.

## Source clock

Compare a current MT5 timestamp with machine UTC. If a verified source clock offset exists, set `source_utc_offset_minutes` explicitly in the relevant profile. The collector preserves the raw value in `source_timestamp`, and the manifest records the configured offset. Never infer or repair this offset from prices.

## Safety diagnosis

`doctor` checks Python, dependencies, the executable, the data path, storage permissions, connection, terminal metadata, account mode, and symbols. A non-demo or unknown account mode is a critical failure.

## Troubleshooting

- Close a manually opened copy of the same terminal if initialization cannot select it.
- Confirm Windows and Python architectures both support the official package.
- Run the terminal once so its market watch list is populated.
- Check that the account is authorized for market data.
- Compare the executable and data folder only on the local machine; do not publish those paths.
