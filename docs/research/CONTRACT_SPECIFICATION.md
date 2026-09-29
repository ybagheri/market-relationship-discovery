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
- `normalization_required`: quote constraints match and contract size and tick value differ **in the same proportion**, so the two legs describe one instrument at a different lot size
- `incompatible`: currencies, point/digits, volume constraints, or trade modes differ, or contract size and tick value do not scale together
- `review_required`: only one specification exists or trade mode is unavailable
- `unverified`: neither specification was provided

A tick comparison is labeled `crossable_research_contract_unverified` without specs. It is labeled validated only for compatible specs. Incompatible and review-required contracts block opportunity episodes and report the number of blocked positive observations; a normalization-required pair does not block, because its legs can be reconciled by volume.

## Contract size and tick value must scale together

One lot covers `contract_size` units of the base currency, and a price move of `tick_size` is worth `tick_value`. The two therefore describe the same economic quantity: the money value of one unit of the underlying, which is

```text
tick_value / (tick_size * contract_size)
```

A broker quoting the same instrument at a different lot size scales both fields together — halving the contract size halves the tick value — and the pair is `normalization_required`. If only one of them moves, the two specifications value the same position differently at *every* volume, so no normalization reconciles them and the pair is `incompatible`. The earlier code returned `normalization_required` in that case, reported a normalized PnL beside an otherwise crossable opportunity, and flagged the disagreement only as an advisory `_contract_legs_disagree` suffix on the classification.

The comparison uses a 1% relative tolerance, tighter than the 5% leg-agreement tolerance, because it compares two numbers describing the same instrument rather than two valuations of a market outcome. A broker publishing a field at limited precision is tolerated; a broker describing a different scale is refused.

## Limitations

Compatibility does not prove identical symbol construction, underlying venue, swap, rebates, liquidity, or execution rules. Contract size and tick-value ratios are reported but PnL-normalized cross-broker execution simulation is not implemented. Missing official metadata must be supplied or resolved manually rather than guessed.
