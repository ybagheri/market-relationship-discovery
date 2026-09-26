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

## Latency capture

An opportunity count is misleading on its own. A crossable tick that existed for
a single instant is counted exactly like one that stayed open for a minute, and
a round trip takes time.

The latency model compares each **measured** episode against the time an order
actually takes. It introduces no new data: the durations come from the episodes
the cross-broker comparison already measured.

The capturable fraction is the share of an episode's life during which the
position could still be open when the round trip completes, which under linear
decay is `(duration − round_trip) / duration`. An episode shorter than the round
trip captures nothing, because the edge closes before the trade completes.

| Verdict | Meaning |
| --- | --- |
| `capturable` | Retained at least `minimum_capturable_fraction` of the episode |
| `marginal` | Survived the round trip but left too little to be worth taking |
| `not_capturable` | Closed before the round trip completed, or the adverse move erased it |

When no episode is capturable the classification gains
`_not_capturable_within_latency`.

### Observed on two live demo brokers

Real XAUUSD comparison between `Alpari-MT5-Demo` and `AMarkets-Demo`, 500 ticks
per side, 16 measured episodes:

| Round trip | Capturable | Median episode | Mean peak edge | Mean captured edge |
| --- | --- | --- | --- | --- |
| 100 ms (50 ms × 2 legs) | 2 of 16 | 0 ms | 0.0513 | 0.0069 |
| 6000 ms | 0 of 16 | 0 ms | 0.0513 | 0.0000 |

Reporting "16 opportunities" without this was misleading by roughly an order of
magnitude. The median episode lasted **zero** milliseconds: most crossable
observations were a single aligned tick. At a 100 ms round trip only the two
episodes that persisted for six seconds could be acted on at all, and the mean
capturable edge fell to about 13 percent of the peak.

This is the clearest argument for reporting feasibility alongside opportunity
counts. The episode count is real; the question is whether any of it survives
the time it takes to act.

### Assumptions and limits

Decay is modelled as **linear**. A different decay shape would change the
captured fraction, and assuming a shape while presenting the result as measured
would be dishonest, so the simplest assumption is used and stated.

The adverse-move allowance defaults to zero and is a configured input, not an
estimate. It is reported visibly so it cannot be mistaken for a measured
quantity.

**Not modelled:** queue position, order-book depth, partial-fill probability,
exchange rejection, and market impact. None of these can be observed from
research data. A `capturable` verdict means no *known* constraint rules the
episode out; it is not a prediction that a fill occurs.

### Configuration

```bash
python -m market_relationship_discovery compare-brokers a.parquet b.parquet \
  --broker-a Alpari-MT5-Demo --broker-b AMarkets-Demo --symbol XAUUSD \
  --kind tick --latency-per-leg-ms 50 --adverse-move-allowance 0.0005 \
  --minimum-capturable-fraction 0.25
```

```dotenv
COSTS__LATENCY_ASSUMPTION_MS=50
COSTS__ADVERSE_MOVE_ALLOWANCE=0.0
COSTS__MINIMUM_CAPTURABLE_FRACTION=0.25
```

`COSTS__LATENCY_ASSUMPTION_MS` existed in the configuration and was passed into
`CostModel`, but was never used in any calculation. It now drives this model.

### A zero round trip is refused

`latency_per_leg_ms` must be **positive**. A zero round trip reports every
episode as fully capturable, which is the most flattering answer the model can
produce, and it is exactly what a forgotten configuration value silently yields.
The same reasoning that treats a broker-reported margin of zero as *not reported*
applies to an absent latency assumption: it is unknown, not free.

`COSTS__LATENCY_ASSUMPTION_MS` therefore defaults to `50` and rejects zero.
This was found by running the model on live data without the flag set, which
reported 100 percent capturable.

## Live bitcoin, the most misleading dataset in the project

Bitcoin trades continuously, so it is the only instrument here with genuine
24-hour opportunity durations. Collected 800 live ticks from each broker on
2026-09-26, both feeds active within five seconds of each other.

Run **with** contract specifications:

| Measure | Value |
| --- | --- |
| Classification | `blocked_by_contract_specification` |
| Contract status | `incompatible` |
| Issues | point sizes differ, tick sizes differ, maximum volumes differ |
| Aligned observations | 296 |
| **Blocked observations** | **287** |
| Crossable observations | 0 |
| Opportunities | 0 |

287 of 296 observations had a positive raw cross-broker edge and every one was
blocked. Maximum gross edge was **$17.00** on an $84,000 asset, about two basis
points, with **zero spread on both feeds**: broker A had `bid == ask` on 99.5
percent of ticks and broker B on 100 percent.

This is the most attractive-looking result in the entire dataset, and it is not
tradable. Three independent reasons:

- **The contracts are not comparable.** Broker B quotes bitcoin in whole dollars
  (`digits` 0, `tick_size` 1.0) while broker A quotes to the half dollar
  (`digits` 2). Volume maxima differ by 30 times, 300 lots against 10.
- **The feeds do not track each other closely enough for the edge to mean
  anything.** The mean absolute difference between brokers was $5.84, while
  broker A's own mean tick-to-tick move was $3.68. The cross-broker difference
  is *larger* than the asset's own movement between ticks.
- **A zero-spread demo feed is not evidence about live execution.** Neither
  broker charges a spread on this instrument, so any cross-broker comparison on
  it is measuring feed construction rather than a tradable dislocation.

The difference is also not a one-way gap. 62 percent of aligned observations had
broker A below broker B and 35 percent had it above, with a mean of −$2.89 and a
standard deviation of $6.85. That is a noisy relationship around a small offset,
not a persistent dislocation. Reading only the mean would have inverted the
conclusion.

Run **without** contract specifications, the same data produces
`crossable_research_contract_unverified_capital_unverified` with 97 percent of
observations crossable, ten opportunity episodes, a median episode of 65
seconds, and 91 percent of the mean peak edge captured at a 100 ms round trip.

That contrast is the point. Omitting a check does not make the finding weaker; it
removes the label that says the finding is unverified. Both runs were made, and
the gated one is the correct one.

### Why bitcoin opportunities last longer than gold

| Instrument | Episodes | Median duration | Capturable at 100 ms |
| --- | --- | --- | --- |
| XAUUSD | 16 | 0 ms | 2 |
| BTCUSD | 10 | 65,500 ms | 8 |

Gold's crossable states were single aligned ticks that flickered away instantly.
Bitcoin's persist for over a minute because both feeds are continuously active,
so a crossable state survives many ticks. The latency model separates these
regimes cleanly, and an episode count alone would not have.

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
