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
5. ترمینال را یک‌بار باز کنید و از رابط خود MetaTrader وارد شوید.
6. فرمان `python -m market_relationship_discovery doctor` را اجرا کنید.

package رسمی Python ترمینال را از مسیر executable انتخاب می‌کند. آرگومان امن و پشتیبانی‌شده‌ای برای اجبار به پوشه داده دلخواه ارائه نمی‌کند؛ بنابراین مسیر داده فقط برای تشخیص محلی است.

## نام symbolها

فرض نکنید که بروکر حتماً `XAUUSD`، `XAGUSD` یا `XAUEUR` دارد. ابتدا جست‌وجو کنید:

```bash
python -m market_relationship_discovery symbols --search gold
python -m market_relationship_discovery symbols --search eur
python -m market_relationship_discovery symbols --search silver
python -m market_relationship_discovery symbols --search jpy
```

نگاشت‌های واقعی را در `.env` ذخیره کنید. پسوند و پیشوند بروکر باید در موتور ثابت نشوند.

## ایمنی

`doctor` نسخه Python، وابستگی‌ها، executable، پوشه داده، دسترسی ذخیره‌سازی، اتصال، ترمینال، mode حساب و symbolها را بررسی می‌کند. حساب غیر دمو یا mode نامشخص خطای بحرانی است.

## عیب‌یابی

- اگر انتخاب ترمینال ممکن نیست، نسخه دستی همان ترمینال را ببندید.
- مطمئن شوید package رسمی از معماری Python و Windows پشتیبانی می‌کند.
- ترمینال را یک‌بار اجرا کنید تا market watch شکل بگیرد.
- دسترسی حساب به داده بازار را بررسی کنید.
- مسیر executable و داده را فقط محلی بررسی کنید و منتشر نکنید.
