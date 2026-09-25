# Quickstart

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Set local MT5 paths in `.env`, open the demo terminal, and run:

```bash
python -m market_relationship_discovery doctor
python -m market_relationship_discovery symbols --search gold
python -m market_relationship_discovery collect --broker-profile DEMO --symbol XAUUSD --symbol EURUSD --symbol XAUEUR --data-type bar --timeframe M1 --limit 500
python -m market_relationship_discovery research --broker-profile DEMO --relationship XAUEUR_SYNTHETIC --limit 500
python -m market_relationship_discovery discover --symbol EURUSD GBPUSD
python -m market_relationship_discovery backtest examples\no_lookahead_signals.csv
python -m market_relationship_discovery multi-backtest examples\walk_forward_signals.csv --stage-column momentum_score --stage-column confirmation_score --stage-weight 0.5 --stage-weight 0.5
python -m market_relationship_discovery walk-forward examples\walk_forward_signals.csv --train-size 12 --validation-size 8 --test-size 8 --step 8 --threshold 0 --threshold 0.5 --threshold 0.9
python -m market_relationship_discovery dashboard
```

The mathematical engine can be tested without MT5:

```python
from datetime import UTC, datetime
from market_relationship_discovery.domain.market import Quote
from market_relationship_discovery.synthetic.engine import SyntheticPriceEngine

quotes = {
    "XAUUSD": Quote.create(datetime.now(UTC), "Demo", "XAUUSD", 2999.0, 3001.0, "test"),
    "EURUSD": Quote.create(datetime.now(UTC), "Demo", "EURUSD", 1.1999, 1.2001, "test"),
    "XAUEUR": Quote.create(datetime.now(UTC), "Demo", "XAUEUR", 2499.0, 2501.0, "test"),
}
result = SyntheticPriceEngine().evaluate("XAUUSD / EURUSD", quotes, "XAUEUR")
print(result.theoretical_price)
```

A result near `2500` validates the formula, not profitability.
