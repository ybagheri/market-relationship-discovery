# Symbol Mapping

## Why mapping exists

The platform works with canonical research symbols such as `XAUUSD`, `EURUSD`, and `XAUEUR`. Brokers publish their own names, and those names are not predictable:

- Alpari publishes gold as `XAUUSD` described as `Gold (Spot)`, not as `GOLD` or `XAUUSD.a`.
- Some brokers append a session or instance suffix such as `.a`, `m`, `#`, or `Ind`.
- An index instrument may exist as a plain ticker, as a futures contract such as `GOLDZ6`, or not at all.
- A synthetic cross such as `XAUEUR` may be a listed instrument on one broker and absent on another.

Nothing in the pricing engine hard-codes a broker name. Resolution happens in one place, and every resolved symbol is reported with the strategy that produced it.

## Resolution order

`SymbolMapper.resolve` tries, in order:

1. `configuration` — an explicit `SYMBOL_MAPPING` entry from `.env`.
2. `normalized_name` — an exact match after removing case and non-alphanumeric characters, so `EUR/USD.a` still resolves to `EURUSD`.
3. `alias` — a configured alias such as `gold` matching a broker name.

If nothing matches, resolution raises `SymbolNotFoundError` rather than guessing.

## Discovery before configuration

Run discovery first and record what the broker actually offers:

```bash
python -m market_relationship_discovery symbols
python -m market_relationship_discovery symbols --search gold
python -m market_relationship_discovery symbols --search silver
python -m market_relationship_discovery symbols --search dollar
```

The header reports the catalog size and how many symbols are tradable. A broker may list several hundred symbols while only a handful appear in the watch window, which is why discovery does not default to visible symbols.

## Observed Alpari demo catalog

Recorded from Alpari-branded demo terminals on 2026-09-26. The two installations are **different brokers** despite the shared brand: `Alpari-MT5-Demo` build 6184 with leverage 500, and `AMarkets-Demo` build 6230 with leverage 1000. These values are observations, not guarantees, and must be re-discovered for any other broker or account.

### Broker A — `Alpari-MT5-Demo`

879 published symbols, 128 tradable. Most of the catalog, including many share CFDs, carries a disabled trade mode.

| Canonical | Broker symbol | Broker description | Digits | Spread (points) | Trade mode |
| --- | --- | --- | --- | --- | --- |
| `XAUUSD` | `XAUUSD` | `Gold (Spot)` | 2 | 19 | full |
| `XAGUSD` | `XAGUSD` | `Silver (Spot)` | 3 | 29 | full |
| `XAUEUR` | `XAUEUR` | `Gold vs. Euro` | 2 | 0 | full |
| `XAUAUD` | `XAUAUD` | `Gold vs Australian Dollar` | 2 | 0 | full |
| `XAUGBP` | `XAUGBP` | `Gold vs Great Britain Pound` | 2 | 0 | full |
| `XAUJPY` | `XAUJPY` | `Gold vs Japanese Yen` | 0 | 0 | full |
| `XAUCNH` | `XAUCNH` | `Gold vs Chinese Renminbi` | 2 | 0 | full |
| `XAGEUR` | `XAGEUR` | `Silver vs Euro` | 3 | 0 | full |
| `XAGJPY` | `XAGJPY` | `Silver vs Japanese Yen` | 1 | 0 | full |
| `XAGAUD` | `XAGAUD` | `Silver vs Australian Dollar` | 3 | 0 | full |
| `EURUSD` | `EURUSD` | `Euro vs US Dollar` | 5 | 18 | full |
| `EURGBP` | `EURGBP` | `Euro vs Great Britain Pound` | 5 | 0 | full |
| `EURJPY` | `EURJPY` | `Euro vs Japanese Yen` | 3 | 0 | full |
| `BTCUSD` | `BITCOIN` | `1 LOT = 1 BITCOIN` | 2 | 0 | full |

Additional instruments on this account included `GOLDInd` (`Gold Index`), `GOLDZ6` (`Gold December 2026`), `NAS100` (`NASDAQ 100 Index`), and `WTI` (`WTI Crude Oil`).

### Broker B — `AMarkets-Demo`

521 published symbols, all 521 tradable. Instrument construction differs even where the ticker matches: gold sits under `Metals CFD\XAUUSD` rather than `Metals\Spot Metals\XAUUSD`.

| Canonical | Broker symbol | Broker description | Digits | Spread (points) | Trade mode |
| --- | --- | --- | --- | --- | --- |
| `XAUUSD` | `XAUUSD` | `Gold vs US Dollar` | 2 | 39 | full |
| `XAGUSD` | `XAGUSD` | `Silver vs US Dollar` | 3 | 0 | full |
| `XAUEUR` | `XAUEUR` | `Gold vs Euro` | 2 | 0 | full |
| `EURUSD` | `EURUSD` | `Euro vs US Dollar` | 5 | 20 | full |
| `EURGBP` | `EURGBP` | `Euro vs Great Britain Pound` | 5 | 0 | full |
| `EURJPY` | `EURJPY` | `Euro vs Japanese Yen` | 3 | 0 | full |
| `BTCUSD` | `BTCUSD` | `Bitcoin vs US Dollar` | 0 | 0 | full |

### Cross-broker contract differences that matter

| Symbol | Broker A | Broker B | Consequence |
| --- | --- | --- | --- |
| `EURUSD` | tick value 1.0, spread 18 | tick value 1.0, spread 20 | Compatible; no opportunity survives the spread |
| `XAUUSD` | tick value 0.1, `Spot Metals` | tick value 1.0, `Metals CFD` | `normalization_required`; a ten times PnL difference per identical price move |
| `BTCUSD` | `tick_size` 0.01, `digits` 2 | `tick_size` 1.0, `digits` 0 | `incompatible`; broker B quotes in whole dollars |

A shared ticker does not imply a shared contract. Comparing these feeds on price alone would misstate the PnL of a gold position by a factor of ten and would invent a bitcoin opportunity out of broker B's rounding.

Four observations matter for research:

- A zero reported spread does not mean a free trade. It usually means the symbol is quoted without a live bid/ask feed at that moment, so the executable classification must not be inferred from it.
- Most of broker A's catalog is published with a disabled trade mode and is excluded from discovery by default.
- `digits` and `tick_size` differ between brokers for the same instrument, so tick granularity must be validated before any price comparison.
- `margin_initial` is `0.0` for every symbol on both brokers. That means *not reported*, not free margin. See [execution and capital model](../research/EXECUTION_MODEL.md).

## Recording local mappings

Put resolved values in `.env`, which is never committed. Each broker profile carries its own mapping because brokers rarely agree on a name:

```dotenv
BROKERS={"ALPARI_1":{"terminal_path":"...","demo_only":true,"symbol_mapping":{"BTCUSD":"BITCOIN"}},
         "ALPARI_2":{"terminal_path":"...","demo_only":true,"symbol_mapping":{"BTCUSD":"BTCUSD"}}}
```

Keep the example mapping in `.env.example` free of machine-specific values.

## Comparing the same instrument across brokers

Collection stores the **broker** name, so a cross-broker study needs the label present in each source:

```bash
python -m market_relationship_discovery compare-brokers a.parquet b.parquet \
  --broker-a Alpari-MT5-Demo --broker-b AMarkets-Demo \
  --symbol BTCUSD --symbol-a BITCOIN --symbol-b BTCUSD \
  --contract-a specs/a_btcusd.json --contract-b specs/b_btcusd.json
```

`--symbol` is the research symbol used for reporting; `--symbol-a` and `--symbol-b` select each source's own label.

## Verifying a symbol before research

```bash
python -m market_relationship_discovery doctor
python -m market_relationship_discovery symbols --search XAUUSD
python -m market_relationship_discovery symbol-specs --symbol XAUUSD --output config/specs/demo_xauusd.json
```

`symbol-specs` captures the official contract metadata used by the cross-broker compatibility gate. A discrepancy measured across brokers with different contract sizes, currencies, or tick values is not comparable, and the research layer blocks that comparison rather than reporting a misleading edge.
