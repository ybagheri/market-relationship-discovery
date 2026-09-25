# شروع سریع

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

مسیرهای محلی MT5 را در `.env` قرار دهید، ترمینال دمو را باز کنید و اجرا کنید:

```bash
python -m market_relationship_discovery doctor
python -m market_relationship_discovery symbols --search gold
python -m market_relationship_discovery collect --broker-profile DEMO --symbol XAUUSD --symbol EURUSD --symbol XAUEUR --data-type bar --timeframe M1 --limit 500
python -m market_relationship_discovery collect --parallel --max-workers 2 --broker-profile BROKER_A --broker-profile BROKER_B --symbol EURUSD --data-type tick --limit 500
python -m market_relationship_discovery symbol-specs --broker-profile DEMO --symbol EURUSD --output config/specs/demo_eurusd.json
python -m market_relationship_discovery research --broker-profile DEMO --relationship XAUEUR_SYNTHETIC --limit 500
python -m market_relationship_discovery discover --input data\prices.csv --rolling-beta-window 30 --statistical-significance 0.05
python -m market_relationship_discovery backtest examples\no_lookahead_signals.csv
python -m market_relationship_discovery multi-backtest examples\walk_forward_signals.csv --stage-column momentum_score --stage-column confirmation_score --stage-weight 0.5 --stage-weight 0.5
python -m market_relationship_discovery walk-forward examples\walk_forward_signals.csv --train-size 12 --validation-size 8 --test-size 8 --step 8 --threshold 0 --threshold 0.5 --threshold 0.9
python -m market_relationship_discovery robustness examples\walk_forward_signals.csv --simulations 1000 --seed 42 --block-size 3
python -m market_relationship_discovery compare-brokers examples\broker_a_ticks.csv examples\broker_b_ticks.csv --broker-a BrokerA --broker-b BrokerB --symbol EURUSD --kind tick --max-delay-ms 100 --additional-cost 0.0001 --contract-a examples\broker_a_contract.json --contract-b examples\broker_b_contract.json
python -m market_relationship_discovery dashboard
```

موتور ریاضی بدون MT5 نیز قابل تست است:

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

نتیج نزدیک `2500` فقط فرمول را اعتبارسنجی می‌کند و سودآوری را اثبات نمی‌کند.
