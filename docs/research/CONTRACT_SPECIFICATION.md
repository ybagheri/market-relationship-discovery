# Contract Specifications

## Purpose

Contract metadata prevents raw price differences from being compared as if two broker symbols had the same quote, volume, and PnL behavior. The platform treats missing or incompatible specifications as a safety concern rather than silently normalizing them.

## Captured fields

`ContractSpecification` records broker/server, actual symbol, description, path, base and profit currencies, digits, point, spread, trade mode, contract size, volume bounds and step, tick size, tick value, and initial margin. `MT5Adapter.contract_specification` reads the official `SymbolInfo` fields `trade_contract_size`, `trade_tick_size`, and `trade_tick_value_profit`.

The `symbol-specs` command resolves configured broker symbols and writes the specification as JSON:

```bash
python -m market_relationship_discovery symbol-specs --broker-profile DEMO --symbol EURUSD --output config/specs/demo_eurusd.json
```

Local specification files are research inputs and should not be committed when they contain machine-specific details.

## Compatibility policy

`ContractSpecificationAnalyzer` reports one of:

- `compatible`: currencies, point/digits, volume constraints, trade mode, contract size, and tick value match
- `normalization_required`: quote constraints match but contract size or tick value differs
- `incompatible`: currencies, point/digits, volume constraints, or trade modes differ
- `review_required`: only one specification exists or trade mode is unavailable
- `unverified`: neither specification was provided

A tick comparison is labeled `crossable_research_contract_unverified` without specs. It is labeled validated only for compatible specs. Normalization-required, incompatible, and review-required contracts block opportunity episodes and report the number of blocked positive observations.

## Limitations

Compatibility does not prove identical symbol construction, underlying venue, swap, rebates, liquidity, or execution rules. Contract size and tick-value ratios are reported but PnL-normalized cross-broker execution simulation is not implemented. Missing official metadata must be supplied or resolved manually rather than guessed.
