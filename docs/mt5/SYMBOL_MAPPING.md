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

Recorded from an Alpari MT5 demo terminal, build 6184, on 2026-09-26. These values are observations, not guarantees, and must be re-discovered for any other broker or account.

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

Additional instruments on this account included `GOLDInd` (`Gold Index`), `GOLDZ6` (`Gold December 2026`), `NAS100` (`NASDAQ 100 Index`), and `WTI` (`WTI Crude Oil`).

Two observations matter for research:

- A zero reported spread does not mean a free trade. It usually means the symbol is quoted without a live bid/ask feed at that moment, so the executable classification must not be inferred from it.
- Most of the catalog, including many share CFDs, is published with a disabled trade mode. Those symbols are excluded from discovery results by default.

## Recording local mappings

Put resolved values in `.env`, which is never committed:

```dotenv
SYMBOL_MAPPING={"XAUUSD":"XAUUSD","XAGUSD":"XAGUSD","XAUEUR":"XAUEUR"}
```

Keep the example mapping in `.env.example` free of machine-specific values.

## Verifying a symbol before research

```bash
python -m market_relationship_discovery doctor
python -m market_relationship_discovery symbols --search XAUUSD
python -m market_relationship_discovery symbol-specs --symbol XAUUSD --output config/specs/demo_xauusd.json
```

`symbol-specs` captures the official contract metadata used by the cross-broker compatibility gate. A discrepancy measured across brokers with different contract sizes, currencies, or tick values is not comparable, and the research layer blocks that comparison rather than reporting a misleading edge.
