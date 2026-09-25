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
