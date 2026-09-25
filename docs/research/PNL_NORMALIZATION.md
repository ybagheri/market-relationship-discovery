# PnL Normalization

## Purpose

Raw price edges are not comparable across brokers when contract size or tick value differs. `ContractEdgeNormalizer` converts a common-currency net price edge into a research PnL estimate for a specified Broker A volume.

## Volume normalization

To expose equivalent base quantities, Broker B volume is calculated as:

```text
volume_B = volume_A × contract_size_A / contract_size_B
```

## PnL normalization

For compatible profit currencies, each leg is valued from official tick metadata:

```text
leg_PnL = net_price_edge × leg_volume × tick_value / tick_size
net_PnL = Broker_A_PnL + Broker_B_PnL
```

The cross-broker report includes broker B volume per unit of broker A volume, mean normalized net PnL, maximum normalized net PnL, and opportunity-level normalized values. Contract-size or tick-value differences are labeled `normalization_required` and are handled only when complete specifications are available. Incompatible currencies, point/digit constraints, or unavailable trade modes still block opportunities.

## Costs and limits

`additional_cost` remains a fixed raw-price assumption and is subtracted before PnL conversion. The normalizer does not model currency conversion, swap, commission differences, rebates, margin, partial fills, queue position, or instrument-specific PnL conventions. A positive normalized value is a research metric, not realized profit.

## Validation note

A live two-demo-terminal validation produced only one mutually synchronized EURUSD observation and therefore reported a research candidate with zero duration. This sparse result is explicitly insufficient evidence of an executable opportunity and must not be interpreted as a strategy.
