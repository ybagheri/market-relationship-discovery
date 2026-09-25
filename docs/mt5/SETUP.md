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
5. Open the terminal once and sign in through MetaTrader's own UI.
6. Run `python -m market_relationship_discovery doctor`.

The official Python package selects the terminal through its executable path. It does not expose a safe supported argument for forcing an arbitrary data directory, so the configured data path is a diagnostic path rather than an override.

## Symbol names

Do not assume `XAUUSD`, `XAGUSD`, or `XAUEUR`. Inspect and search:

```bash
python -m market_relationship_discovery symbols --search gold
python -m market_relationship_discovery symbols --search eur
python -m market_relationship_discovery symbols --search silver
python -m market_relationship_discovery symbols --search jpy
```

Store resolved mappings in `.env`. Broker suffixes and prefixes are meaningful and must not be hard-coded in the engine.

## Safety diagnosis

`doctor` checks Python, dependencies, the executable, the data path, storage permissions, connection, terminal metadata, account mode, and symbols. A non-demo or unknown account mode is a critical failure.

## Troubleshooting

- Close a manually opened copy of the same terminal if initialization cannot select it.
- Confirm Windows and Python architectures both support the official package.
- Run the terminal once so its market watch list is populated.
- Check that the account is authorized for market data.
- Compare the executable and data folder only on the local machine; do not publish those paths.
