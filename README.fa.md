🇬🇧 English: [English README](README.md)

# کشف روابط بازار

یک پلتفرم پژوهش کمّی با Python برای کشف و اعتبارسنجی روابط بازار، قیمت‌های مصنوعی، ناهمگونی‌های قیمتی، اختلاف داده‌های بروکرها، روابط مثلثی ارز، اثرهای lead/lag و نامزدهای آربیتراژ آماری.

> **فقط پژوهش:** این پروژه سود آربیتراژ را تضمین نمی‌کند. حساب متصل به MT5 باید به‌طور قطعی در حالت `DEMO` باشد و در مرحله فعلی هیچ عملیات اجرای سفارش پیاده‌سازی نشده است.

## وضعیت پروژه

زیرساخت اولیه پیاده‌سازی شده است. اتصال خواندنی به MT5، تأیید حساب دمو، مدل نرمال‌شده quote، موتور فرمول‌محور قیمت مصنوعی، لایه اختلاف و هزینه، آمار پایه، تست‌ها، CLI و زیرساخت داشبورد موجودند. بک‌تست پیشرفته و ورود داده چند بروکری هنوز تکمیل نشده‌اند.

## قابلیت‌ها

- آداپتور فقط‌خواندنی MetaTrader 5 برای tick، bar، symbol، حساب و مشخصات ترمینال
- رد اتصال حسابی که به‌طور قطعی `DEMO` تشخیص داده نشود
- مدل UTC برای bid، ask، mid و spread
- موتور فرمول عمومی برای روابط قیمتی مصنوعی
- تفکیک اختلاف نظری از اختلاف آگاه به bid/ask
- مدل هزینه قابل پیکربندی
- تحلیل Pearson، Spearman، rolling z-score، half-life و lead/lag
- ابزارهای کیفیت داده و هم‌ترازی timestamp
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
DATA__TIMEZONE=UTC
DATA__MAX_ALIGNMENT_DELAY_MS=100
```

آداپتور عمداً تنظیم password غیرخالی را نمی‌پذیرد. احراز هویت MT5 باید توسط خود ترمینال مدیریت شود.

## شروع سریع

```bash
python -m market_relationship_discovery doctor
python -m market_relationship_discovery mt5-info
python -m market_relationship_discovery symbols --search gold
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
- [نقشه راه](docs/roadmap/ROADMAP.fa.md)
- [سیاست امنیت](SECURITY.md)

## محدودیت‌ها

داده و ساخت CFD در بروکرهای مختلف می‌تواند متفاوت باشد. رابطه مصنوعی ممکن است از نظر ریاضی معتبر ولی غیرقابل معامله باشد. داده bar نمی‌تواند آربیتراژ در سطح tick را اثبات کند. همبستگی، هم‌انباشت یا بازگشت به میانگین تاریخی، مزیت آینده را تضمین نمی‌کند. هزینه، تأخیر، لغزش، ساعات بازار و مشخصات symbol باید جداگانه اعتبارسنجی شوند.

## مجوز

هنوز مجوزی انتخاب نشده است. تا زمان افزودن مجوز توسط مالک پروژه، اجازه استفاده مجدد از این مخزن داده نشده است.
