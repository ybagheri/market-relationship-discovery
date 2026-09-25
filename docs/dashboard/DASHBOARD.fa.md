# داشبورد

## هدف

داشبورد Streamlit یک نمایش فقط‌خواندنی پژوهشی است. همیشه `DEMO / RESEARCH MODE — NO LIVE TRADING` را نمایش می‌دهد و هیچ سفارشی ارسال، مسیریابی یا شبیه‌سازی نمی‌کند.

## منبع گزارش

داشبورد پوشه `DATA__REPORTS_DIRECTORY` را برای فایل‌های `EXP-*.json` با نوع experiment برابر `cross_broker_comparison` جست‌وجو می‌کند. تب‌های `Discrepancy Explorer` و `Broker Comparison`، manifest، summary، opportunity و aligned preview ذخیره‌شده را می‌خوانند.

پس از collection یا comparison جدید، دوباره `compare-brokers` را اجرا کنید. هر گزارش حداکثر ۲۰ ردیف aligned preview دارد؛ بنابراین نمودارها عمداً سطح بازرسی سریع هستند، نه data explorer با وضوح کامل.

## discrepancy explorer

این تب یکی از معیارهای زیر را روی timestampهای UTC رسم می‌کند:

- `mid_difference`
- `bid_difference`
- `ask_difference`
- `net_crossable_edge`
- `normalized_net_pnl`
- `alignment_delay_ms`

هزینه اضافی پیکربندی‌شده به‌صورت خط مرجع نمایش داده می‌شود و observationهای crossable جدا مشخص می‌شوند. جدول aligned و episodeهای opportunity زیر نمودار باقی می‌مانند.

## broker comparison

نمای broker، مقادیر همگام `a_mid` و `b_mid` را با برچسب brokerهای گزارش رسم می‌کند. این نما توصیفی است: اختلاف قیمت قابل مشاهده به‌تنهایی اجرای هم‌زمان، مجوز حساب، نقدینگی یا سود تضمینی را ثابت نمی‌کند.

## ایمنی و محدودیت‌ها

کد داشبورد password یا login حساب را نمی‌خواند و نمایش نمی‌دهد. نمودارها funding، کمیسیون، margin، slippage، latency، partial fill یا مدل اجرای broker-specific را فراتر از موارد ثبت‌شده در گزارش اضافه نمی‌کنند. پیش از نتیجه‌گیری، گزارش‌های پژوهش و اعتبارسنجی اصلی را بررسی کنید.
