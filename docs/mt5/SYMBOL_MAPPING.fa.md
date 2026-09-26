# نگاشت نمادها (Symbol Mapping)

## چرا نگاشت لازم است

پلتفرم با نمادهای پژوهشی canonical مانند `XAUUSD`، `EURUSD` و `XAUEUR` کار می‌کند. بروکرها نام‌های خودشان را منتشر می‌کنند و این نام‌ها قابل پیش‌بینی نیستند:

- Alpari طلا را با نام `XAUUSD` و توضیح `Gold (Spot)` منتشر می‌کند، نه `GOLD` یا `XAUUSD.a`.
- برخی بروکرها پسوند session یا instance مانند `.a`، `m`، `#` یا `Ind` اضافه می‌کنند.
- یک ابزار index ممکن است به‌صورت ticker ساده، قرارداد آتی مانند `GOLDZ6`، یا اصلاً موجود نباشد.
- یک cross مصنوعی مانند `XAUEUR` ممکن است در یک بروکر نماد فهرست‌شده باشد و در بروکر دیگر اصلاً وجود نداشته باشد.

هیچ‌چیز در موتور قیمت‌گذاری نام بروکر را hard-code نمی‌کند. تطبیق در یک نقطه انجام می‌شود و هر نماد تطبیق‌یافته همراه با راهبردی که آن را تولید کرده گزارش می‌شود.

## ترتیب تطبیق

`SymbolMapper.resolve` به‌ترتیب زیر تلاش می‌کند:

1. `configuration` — ورودی صریح `SYMBOL_MAPPING` از فایل `.env`.
2. `normalized_name` — تطابق دقیق پس از حذف حروف بزرگ/کوچک و نویسه‌های غیرالفبایی، بنابراین `EUR/USD.a` همچنان به `EURUSD` تطبیق می‌کند.
3. `alias` — یک نام مستعار مانند `gold` که با نام بروکر مطابقت دارد.

اگر هیچ‌کدام مطابقت نکند، تطبیق به‌جای حدس زدن `SymbolNotFoundError` صادر می‌کند.

## کشف پیش از پیکربندی

ابتدا کشف را اجرا کنید و آنچه بروکر واقعاً ارائه می‌دهد ثبت کنید:

```bash
python -m market_relationship_discovery symbols
python -m market_relationship_discovery symbols --search gold
python -m market_relationship_discovery symbols --search silver
python -m market_relationship_discovery symbols --search dollar
```

سرصفحه، اندازه کاتالوگ و تعداد نمادهای قابل معامله را گزارش می‌کند. یک بروکر ممکن است چند صد نماد منتشر کند در حالی که تنها چند نماد در watch window دیده می‌شود؛ به همین دلیل کشف به‌صورت پیش‌فرض روی همه کاتالوگ انجام می‌شود.

## کاتالوگ مشاهده‌شده Alpari دمو

ثبت‌شده از ترمینال دموی Alpari MT5، build 6184، در تاریخ 2026-09-26. این مقادیر مشاهده هستند نه تضمین، و برای هر بروکر یا حساب دیگری باید دوباره کشف شوند.

| Canonical | نماد بروکر | توضیح بروکر | Digits | Spread (points) | Trade mode |
| --- | --- | --- | --- | --- | --- |
| `XAUUSD` | `XAUUSD` | `Gold (Spot)` | 2 | 19 | full |
| `XAGUSD` | `XAGUSD` | `Silver (Spot)` | 3 | 29 | full |
| `XAUEUR` | `XAUEUR` | `Gold vs. Euro` | 2 | 0 | full |
| `XAUAUD` | `XAUAUD` | `Gold vs Australian Dollar` | 2 | 0 | full |
| `XAUGBP` | `XAUGBP` | `Gold vs Great Britain Pound` | 2 | 0 | full |
| `XAUJPY` | `XAUJPY` | `Gold vs Japanese Yen` | 0 | 0 | full |
| `XAUCNH` | `XAUCNH` | `Gold vs Chinese Renminbi` | 2 | 0 | full |
| `XAGEUR` | `XAGEUR` | `Silver vs Euro` | 3 | 0 | full |
| `XAGJPY` | `XAGJPY` | `Silver vs Japanese Yen` | 1 | 0 | full |
| `XAGAUD` | `XAGAUD` | `Silver vs Australian Dollar` | 3 | 0 | full |
| `EURUSD` | `EURUSD` | `Euro vs US Dollar` | 5 | 18 | full |
| `EURGBP` | `EURGBP` | `Euro vs Great Britain Pound` | 5 | 0 | full |
| `EURJPY` | `EURJPY` | `Euro vs Japanese Yen` | 3 | 0 | full |

ابزارهای دیگر این حساب شامل `GOLDInd` (`Gold Index`)، `GOLDZ6` (`Gold December 2026`)، `NAS100` (`NASDAQ 100 Index`) و `WTI` (`WTI Crude Oil`) بودند.

دو نکته برای پژوهش اهمیت دارد:

- spread گزارش‌شده صفر به معنای معامله رایگان نیست. معمولاً یعنی نماد در آن لحظه بدون feed زنده bid/ask قیمت‌گذاری می‌شود، بنابراین طبقه‌بندی اجرایی نباید از آن استنتاج شود.
- بیشتر کاتالوگ، از جمله بسیاری از CFD سهام، با trade mode غیرفعال منتشر می‌شود. این نمادها به‌صورت پیش‌فرض از نتایج کشف حذف می‌شوند.

## ثبت نگاشت‌های محلی

مقادیر تطبیق‌یافته را در `.env` قرار دهید که هرگز commit نمی‌شود:

```dotenv
SYMBOL_MAPPING={"XAUUSD":"XAUUSD","XAGUSD":"XAGUSD","XAUEUR":"XAUEUR"}
```

نگاشت نمونه در `.env.example` را بدون مقادیر وابسته به ماشین نگه دارید.

## بررسی یک نماد پیش از پژوهش

```bash
python -m market_relationship_discovery doctor
python -m market_relationship_discovery symbols --search XAUUSD
python -m market_relationship_discovery symbol-specs --symbol XAUUSD --output config/specs/demo_xauusd.json
```

`symbol-specs` فراداده قرارداد رسمی را ثبت می‌کند که دروازه سازگاری بین بروکرها از آن استفاده می‌کند. اختلاف اندازه‌گیری‌شده بین بروکرهایی با اندازه قرارداد، ارز یا tick value متفاوت قابل مقایسه نیست، و لایه پژوهش به‌جای گزارش مزیت گمراه‌کننده، آن مقایسه را مسدود می‌کند.
