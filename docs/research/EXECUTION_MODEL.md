# Execution and Capital Model

## Why this layer exists

A cross-broker price difference is not an amount of money. Before a discrepancy
can be called an opportunity, three further questions must be answered:

- how much capital must be committed to hold both legs,
- what does holding the position cost in overnight funding,
- can the requested size actually be filled at either broker.

This layer answers them. It is a research model: it produces feasibility verdicts
and capital figures, and it never places an order.

## What it does not model

Queue position, partial-fill probability, order rejection, requotes, and
execution latency are not modelled. A verdict of `executable` means no
*known* configured constraint rules the position out. It is not a prediction
that a fill will occur.

## Margin

`MarginModel` prefers the broker-reported figure. When MetaTrader reports
`margin_initial` as `0.0`, that means **not reported**, not free: the field is
zero for many CFD symbols whose accounts are still subject to leverage limits.
Reading it as free margin would make an unaffordable position look affordable.

The source of every figure is reported explicitly:

| `MarginSource` | Meaning |
| --- | --- |
| `broker_reported` | The broker supplied a positive margin value |
| `leverage_derived` | Computed as notional divided by configured leverage |
| `unavailable` | Neither is available; capital adequacy is unknown |

Notional is `volume × contract_size × price`. Both legs of a cross-broker pair
commit capital at the same time, so the pair requires the sum, not the larger
side alone.

## Fill feasibility

`FillSimulator` reduces a requested size to what a broker would accept:

- volumes are rounded **down** to `volume_step`, because brokers reject
  off-step orders rather than rounding them up,
- sizes above `volume_max` are capped and reported as `above_maximum`,
- sizes below `volume_min` are refused as `below_minimum`,
- an absent contract specification yields `unknown_contract`.

A capped fill remains *executable*, because PnL scales with filled volume. The
reduced size is reported through `binding_fill_ratio` and the fill objects
rather than being hidden. `minimum_fill_ratio` is the control for callers that
require a minimum achievable size.

## Funding

`FundingModel` accrues a configurable daily rate against the notional for each
whole night held, including the triple-swap rollover on a configurable weekday.
A position opened and closed within one session accrues nothing, which is why
funding is applied per opportunity episode rather than per tick observation.

Funding is deliberately a function of holding time. Folding it into a flat
per-trade constant would hide the holding-time risk that makes a small
discrepancy unprofitable.

## Verdicts and classification

`ExecutionAssessor` combines margin and fill feasibility. It separates two
different situations that are easy to conflate:

- **Known infeasibility** — a size the broker cannot accept, or a fill ratio
  below the configured minimum. This blocks the opportunity.
- **Unknown capital** — margin cannot be determined. This does *not* delete the
  observation, because an unknown margin is a confidence problem rather than
  proof of infeasibility. It is surfaced by appending `_capital_unverified` to
  the classification and listing the reason.

Configuring `leverage` removes the caveat, because margin becomes derivable.

## Observed behaviour on two live demo brokers

Recorded on 2026-09-26 against two Alpari-branded demo terminals that are
distinct brokers: `Alpari-MT5-Demo` (build 6184, leverage 500) and
`AMarkets-Demo` (build 6230, leverage 1000). These are observations from one
moment, not guarantees.

### EURUSD: compatible contracts, no opportunity

Contracts matched on point, tick size, contract size, tick value, and volume
bounds, so the status was `compatible`. Across 160 aligned observations the mean
mid difference was about 0.2 pip while the quoted spreads were 18 and 20 points.
Result: **zero crossable observations and zero opportunities**. The feeds agree
closely, and no discrepancy survives the spread.

### XAUUSD: ten times tick value apart, net negative

Both brokers publish `XAUUSD` with `contract_size` 100 and `tick_size` 0.01, but
broker A reports `tick_value` 0.1 and broker B reports 1.0. The status was
`normalization_required` and PnL normalization was applied. Broker A's path is
`Metals\Spot Metals\XAUUSD` while broker B's is `Metals CFD\XAUUSD`, so the
instruments are not constructed identically despite the shared ticker.

The result is the clearest illustration of why gross numbers mislead. The
maximum normalized net PnL across observations was **+23.10**, which looks like
a tradable edge in isolation. The **mean** normalized net PnL was **-14.50**.
Most observations lost money. Reporting only the maximum would invert the
conclusion.

With one lot and 500:1 leverage the model reported total margin of 1714.72
across both legs, both fills complete, and `capital_verified` true.

### BTCUSD: blocked, and correctly so

Broker A publishes bitcoin as `BITCOIN` (`Cryptopairs`-style CFD, `digits` 2,
`tick_size` 0.01) and broker B as `BTCUSD` (`digits` 0, `tick_size` 1.0). The
two live quotes were about 83915 and 83923, and across 165 aligned observations
the mean absolute difference was **5.98**.

That 5.98 is not a market dislocation. Broker B quotes bitcoin in whole dollars,
so up to about 0.50 of the difference is its own rounding, and the remaining gap
reflects two different liquidity pools. The contract status was `incompatible`
with issues `point sizes differ` and `tick sizes differ`, and the classification
was `blocked_by_contract_specification` with zero opportunities.

Without the contract gate a researcher would have seen a six-dollar cross-broker
bitcoin spread and concluded arbitrage. The gate is what prevents that.

## Usage

```bash
python -m market_relationship_discovery compare-brokers a.parquet b.parquet \
  --broker-a Alpari-MT5-Demo --broker-b AMarkets-Demo \
  --symbol BTCUSD --symbol-a BITCOIN --symbol-b BTCUSD \
  --contract-a specs/a_btcusd.json --contract-b specs/b_btcusd.json \
  --volume 1.0 --leverage 500 --minimum-fill-ratio 0.5 \
  --kind tick --sync-mode symmetric --output reports/research
```

Related configuration under `COSTS__`:

```dotenv
COSTS__VOLUME=1.0
COSTS__LEVERAGE=500
COSTS__FUNDING_ENABLED=true
COSTS__FUNDING_DAILY_RATE=0.0004
COSTS__MINIMUM_FILL_RATIO=0.5
COSTS__HOLDING_DAYS=1
```
