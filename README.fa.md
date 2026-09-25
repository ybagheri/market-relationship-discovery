🇬🇧 English: [English README](README.md)

# کشف روابط بازار

یک پلتفرم پژوهش کمّی با Python برای کشف و اعتبارسنجی روابط بازار، قیمت‌های مصنوعی، ناهمگونی‌های قیمتی، اختلاف داده‌های بروکرها، روابط مثلثی ارز، اثرهای lead/lag و نامزدهای آربیتراژ آماری.

> **فقط پژوهش:** این پروژه سود آربیتراژ را تضمین نمی‌کند. حساب متصل به MT5 باید به‌طور قطعی در حالت `DEMO` باشد و در مرحله فعلی هیچ عملیات اجرای سفارش پیاده‌سازی نشده است.

## وضعیت پروژه

فازهای زیرساخت تا پژوهش چند broker ایمن از نظر قرارداد پیاده‌سازی شده‌اند. اکنون ingestion دمو، collection موازی در process جدا، پژوهش بدون look-ahead و walk-forward، robustness، مقایسه همگام و safety gate مشخصات قرارداد وجود دارد. اجرای PnL نرمال‌شده و همگام‌سازی event-time متقارن هنوز در حال توسعه‌اند.

## قابلیت‌ها

- آداپتور فقط‌خواندنی MetaTrader 5 برای tick، bar، symbol، حساب و مشخصات ترمینال
- رد اتصال حسابی که به‌طور قطعی `DEMO` تشخیص داده نشود
- مدل UTC برای bid، ask، mid و spread
- موتور فرمول عمومی برای روابط قیمتی مصنوعی
- تفکیک اختلاف نظری از اختلاف آگاه به bid/ask
- مدل هزینه قابل پیکربندی
- تحلیل Pearson، Spearman، rolling z-score، half-life و lead/lag
- ابزارهای کیفیت داده و هم‌ترازی timestamp
- چند پروفایل broker و collection ترتیبی فقط‌خواندنی
- datasetهای tick و bar در Parquet همراه manifest بازتولیدپذیری
- پژوهش تاریخی bar بدون ادعای اجرای tick-level
- بک‌تست observation بعدی بدون استفاده از edge هم‌زمان سیگنال
- foldهای walk-forward با انتخاب threshold فقط روی train
- سیگنال چندمرحله‌ای علی، feature builder و گزارش هر stage
- شناسه experiment، hash منبع، پارامترها و گزارش JSON بازتولیدپذیر
- شبیه‌سازی Monte Carlo با circular block-bootstrap و seed بازتولیدپذیر
- سناریوهای spread، slippage، latency و stress ترکیبی
- همگام‌سازی نزدیک‌ترین timestamp بین brokerها با delay و تعداد unmatched صریح
- پژوهش crossable در سطح tick فقط پس از هزینه اضافی قابل پیکربندی
- فرکانس، مدت opportunity و provenance دو منبع در مقایسه brokerها
- دریافت فراداده رسمی قرارداد MT5 و خروجی JSON
- compatibility gate که در نیاز به normalization، opportunity را block می‌کند
- collection موازی با process مستقل برای هر پروفایل broker
- چارچوب کاتالوگ رابطه و تولید نامزد
- داشبورد Streamlit با هشدار دائمی حالت پژوهشی/دمو

## مدل ایمنی

در مرحله جاری هیچ تابعی مانند `order_send` وجود ندارد. اختلاف قیمت تنها زمانی «آربیتراژ بدون ریسک» نامیده می‌شود که زمان‌بندی داده، مشخصات قرارداد، مسیر اجرا و هزینه‌ها چنین نتیجه‌ای را پشتیبانی کنند. اختلاف mid-price به‌تنهایی فقط یک اختلاف نظری است.

در تنظیمات، `demo_only=true` الزامی است. اگر حالت حساب MT5 قابل اثبات نباشد، آداپتور اتصال را قطع کرده و خطا می‌دهد.

## معماری

```text
CLI / Streamlit Dashboard
          |
 Research and Discovery
          |
 Statistics / Backtesting / Costs
          |
 Relationships and Synthetic Pricing
          |
 Validation and Market Data Alignment
          |
 MT5 Read-Only Adapter / Storage
```

معماری در [مستند معماری](docs/architecture/ARCHITECTURE.fa.md) و [جریان داده](docs/architecture/DATA_FLOW.fa.md) توضیح داده شده است.

## نصب

Python 3.12 یا جدیدتر و Windows همراه MetaTrader 5 برای اتصال واقعی به ترمینال توصیه می‌شود.

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
```

## پیکربندی

مقدار `.env.example` را در `.env` کپی کنید. مسیر ترمینال، پوشه‌های محلی و نگاشت symbolهای مخصوص بروکر باید فقط در `.env` بمانند. فایل `.env` و هر نوع credential را commit نکنید.

```dotenv
MT5__TERMINAL_PATH=C:\\path\\to\\terminal64.exe
MT5__DATA_PATH=C:\\path\\to\\terminal\\data
MT5__DEMO_ONLY=true
MT5__SOURCE_UTC_OFFSET_MINUTES=0
BROKERS={"DEMO":{"terminal_path":"C:\\\\path\\\\to\\\\demo\\\\terminal64.exe","demo_only":true}}
DATA__TIMEZONE=UTC
DATA__MAX_ALIGNMENT_DELAY_MS=100
```

آداپتور عمداً تنظیم password غیرخالی را نمی‌پذیرد. احراز هویت MT5 باید توسط خود ترمینال مدیریت شود. مقدار `source_utc_offset_minutes` پیش‌فرض صفر است و فقط پس از تأیید اختلاف ساعت منبع تغییر می‌کند؛ timestamp اصلی MT5 در `source_timestamp` حفظ می‌شود.

## شروع سریع

```bash
python -m market_relationship_discovery doctor
python -m market_relationship_discovery mt5-info
python -m market_relationship_discovery symbols --search gold
python -m market_relationship_discovery collect --broker-profile DEMO --symbol XAUUSD --symbol EURUSD --symbol XAUEUR --data-type bar --timeframe M1 --limit 500
python -m market_relationship_discovery collect --parallel --max-workers 2 --broker-profile BROKER_A --broker-profile BROKER_B --symbol EURUSD --data-type tick --limit 500
python -m market_relationship_discovery symbol-specs --broker-profile DEMO --symbol EURUSD --output config/specs/demo_eurusd.json
python -m market_relationship_discovery research --broker-profile DEMO --relationship XAUEUR_SYNTHETIC --limit 500
python -m market_relationship_discovery discover --symbol EURUSD GBPUSD
python -m market_relationship_discovery backtest examples\no_lookahead_signals.csv
python -m market_relationship_discovery multi-backtest examples\walk_forward_signals.csv --stage-column momentum_score --stage-column confirmation_score --stage-weight 0.5 --stage-weight 0.5
python -m market_relationship_discovery walk-forward examples\walk_forward_signals.csv --train-size 12 --validation-size 8 --test-size 8 --step 8 --threshold 0 --threshold 0.5 --threshold 0.9
python -m market_relationship_discovery robustness examples\walk_forward_signals.csv --simulations 1000 --seed 42 --block-size 3
python -m market_relationship_discovery compare-brokers examples\broker_a_ticks.csv examples\broker_b_ticks.csv --broker-a BrokerA --broker-b BrokerB --symbol EURUSD --kind tick --max-delay-ms 100 --additional-cost 0.0001 --contract-a examples\broker_a_contract.json --contract-b examples\broker_b_contract.json
```

روابط اولیه شامل `EURGBP = EURUSD / GBPUSD`، `EURJPY = EURUSD * USDJPY`، `GBPJPY = GBPUSD * USDJPY`، `XAUEUR = XAUUSD / EURUSD` و نسبت طلا به نقره است.

## داشبورد

```bash
python -m market_relationship_discovery dashboard
```

داشبورد همیشه عبارت `DEMO / RESEARCH MODE — NO LIVE TRADING` را نمایش می‌دهد.

## کنترل کیفیت

```bash
pytest
ruff check .
black --check .
mypy
```

## مستندات

- [راهنمای انگلیسی](README.md)
- [راه‌اندازی MT5](docs/mt5/SETUP.fa.md)
- [آموزش شروع سریع](docs/tutorials/QUICKSTART.fa.md)
- [روش‌شناسی پژوهش](docs/research/METHODOLOGY.fa.md)
- [بک‌تست](docs/research/BACKTESTING.fa.md)
- [اعتبارسنجی walk-forward](docs/research/WALK_FORWARD.fa.md)
- [پایداری Monte Carlo](docs/research/MONTE_CARLO.fa.md)
- [مقایسه چند بروکر](docs/research/CROSS_BROKER.fa.md)
- [مشخصات قرارداد](docs/research/CONTRACT_SPECIFICATION.fa.md)
- [collection موازی MT5](docs/mt5/PARALLEL_COLLECTION.fa.md)
- [نقشه راه](docs/roadmap/ROADMAP.fa.md)
- [سیاست امنیت](SECURITY.md)

## محدودیت‌ها

داده و ساخت CFD در بروکرهای مختلف می‌تواند متفاوت باشد. رابطه مصنوعی ممکن است از نظر ریاضی معتبر ولی غیرقابل معامله باشد. داده bar نمی‌تواند آربیتراژ در سطح tick را اثبات کند. همبستگی، هم‌انباشت یا بازگشت به میانگین تاریخی، مزیت آینده را تضمین نمی‌کند. هزینه، تأخیر، لغزش، ساعات بازار و مشخصات symbol باید جداگانه اعتبارسنجی شوند.

## مجوز

هنوز مجوزی انتخاب نشده است. تا زمان افزودن مجوز توسط مالک پروژه، اجازه استفاده مجدد از این مخزن داده نشده است.
