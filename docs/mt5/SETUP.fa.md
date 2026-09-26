# راه‌اندازی MT5

## پیش‌نیازها

- Windows و MetaTrader 5
- Python 3.12 یا جدیدتر
- ترمینال متصل به حسابی که حالت `DEMO` آن قابل تأیید باشد
- عدم وابستگی مخزن به credential حساب

## پیکربندی

1. فایل `.env.example` را به `.env` کپی کنید.
2. مقدار `MT5__TERMINAL_PATH` را برابر مسیر محلی `terminal64.exe` قرار دهید.
3. `MT5__DATA_PATH` را برای تشخیص وضعیت با پوشه داده همان ترمینال تنظیم کنید.
4. مقدار `MT5__DEMO_ONLY=true` را حفظ کنید.
5. تا زمانی که offset ساعت منبع تأیید نشده، `MT5__SOURCE_UTC_OFFSET_MINUTES=0` را حفظ کنید.
6. ترمینال را یک‌بار باز کنید و از رابط خود MetaTrader وارد شوید.
7. فرمان `python -m market_relationship_discovery doctor` را اجرا کنید.

package رسمی Python ترمینال را از مسیر executable انتخاب می‌کند. آرگومان امن و پشتیبانی‌شده‌ای برای اجبار به پوشه داده دلخواه ارائه نمی‌کند؛ بنابراین مسیر داده فقط برای تشخیص محلی است.

ترمینال‌های دیگر به‌صورت پروفایل JSON زیر `BROKERS` تنظیم می‌شوند. همه پروفایل‌ها فقط‌دمو باقی می‌مانند. collection پیش‌فرض ترتیبی است. گزینه `--parallel` برای هر پروفایل یک worker process جدا می‌سازد چون ماژول رسمی Python در هر process یک اتصال سراسری دارد. [collection موازی](PARALLEL_COLLECTION.fa.md) را ببینید.

## نام symbolها

فرض نکنید که بروکر حتماً `XAUUSD`، `XAGUSD` یا `XAUEUR` دارد. بروکرها نام متفاوتی می‌گذارند و ممکن است بسیار بیشتر از آنچه در watch window ترمینال دیده می‌شود نماد منتشر کنند. کشف، پرس‌وجو را هم روی نام نماد، هم روی توضیح broker و هم روی جدول aliasهای canonical تطبیق می‌دهد و گزارش می‌دهد کدام قاعده مطابقت کرده است.

```bash
python -m market_relationship_discovery symbols --search gold
python -m market_relationship_discovery symbols --search silver
python -m market_relationship_discovery symbols --search eur
python -m market_relationship_discovery symbols --search dollar
python -m market_relationship_discovery symbols --search XAUUSD --json
```

به‌صورت پیش‌فرض جست‌وجو کل کاتالوگ بروکر را پوشش می‌دهد و نمادهایی را که بروکر غیرقابل‌معامله اعلام کرده کنار می‌گذارد. پرچم‌های مفید:

| پرچم | اثر |
| --- | --- |
| `--search TEXT` | تطبیق نام، توضیح یا alias |
| `--visible-only` | محدود به watch window ترمینال |
| `--all` | شامل نمادهای غیرقابل‌معامله |
| `--json` | خروجی machine-readable با فراداده |

سرصفحه `catalog_size`، `tradable` و `match_count` را گزارش می‌کند که سریع‌ترین راه برای دیدن پیشنهاد واقعی بروکر است. هر ردیف `mode`، `tradable`، `matched`، `canonical` و توضیح بروکر را نشان می‌دهد.

نگاشت‌های واقعی را در `.env` ذخیره کنید. پسوند و پیشوند بروکر باید در موتور ثابت نشوند. پیش از مقایسه چند broker با contract gate، فراداده محلی قرارداد را با `symbol-specs` خروجی بگیرید.

نمادی که trade mode آن نامشخص باشد غیرقابل‌معامله در نظر گرفته می‌شود، بنابراین نبود فراداده هرگز به‌عنوان فرصت اجرایی تفسیر نمی‌شود. جزئیات بیشتر در [نگاشت نمادها](SYMBOL_MAPPING.fa.md) آمده است.

## جمع‌آوری tick

درخواست tick یک پنجره را تا زمان جاری جست‌وجو می‌کند و جدیدترین ردیف‌ها را نگه می‌دارد و تا زمانی که tick کافی پیدا نشود پنجره را گشاد می‌کند. خارج از ساعت معامله، آخرین tick می‌تواند ساعت‌ها عقب‌تر از ساعت سیستم باشد؛ بنابراین `MT5__TICK_LOOKBACK_HOURS` پنجره اولیه و `MT5__TICK_MAX_LOOKBACK_HOURS` سقف گشادشدن را تعیین می‌کند. نتیجه خالی پس از حداکثر lookback به‌جای خطای عمومی اتصال، صریحاً اعلام می‌کند که بازار ممکن است بسته باشد.

## ساعت منبع

timestamp جاری MT5 را با UTC سیستم مقایسه کنید. اگر offset تأییدشده ساعت منبع وجود دارد، `source_utc_offset_minutes` را صریح در پروفایل مربوط تنظیم کنید. collector مقدار خام را در `source_timestamp` و offset را در manifest نگه می‌دارد. offset را هرگز از قیمت استنباط یا repair نکنید.

## ایمنی

`doctor` نسخه Python، وابستگی‌ها، executable، پوشه داده، دسترسی ذخیره‌سازی، اتصال، ترمینال، mode حساب و symbolها را بررسی می‌کند. حساب غیر دمو یا mode نامشخص خطای بحرانی است.

## عیب‌یابی

- اگر انتخاب ترمینال ممکن نیست، نسخه دستی همان ترمینال را ببندید.
- مطمئن شوید package رسمی از معماری Python و Windows پشتیبانی می‌کند.
- ترمینال را یک‌بار اجرا کنید تا market watch شکل بگیرد.
- دسترسی حساب به داده بازار را بررسی کنید.
- مسیر executable و داده را فقط محلی بررسی کنید و منتشر نکنید.
