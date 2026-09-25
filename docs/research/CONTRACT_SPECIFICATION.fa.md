# مشخصات قرارداد

## هدف

فراداده قرارداد مانع مقایسه تفاوت خام قیمت به‌گونه‌ای می‌شود که دو symbol دو broker مانند quote، volume و رفتار PnL یکسان فرض شوند. نبود یا ناسازگاری specification در پلتفرم یک نگرانی ایمنی است و به‌صورت خودکار و بی‌صدا نرمال نمی‌شود.

## فیلدهای ثبت‌شده

`ContractSpecification` شامل broker/server، symbol واقعی، description، path، ارز base و profit، digits، point، spread، trade mode، contract size، کران و گام volume، tick size، tick value و margin اولیه است. `MT5Adapter.contract_specification` فیلدهای رسمی `trade_contract_size`، `trade_tick_size` و `trade_tick_value_profit` را می‌خواند.

فرمان `symbol-specs` symbol پیکربندی‌شده را resolve و specification را به‌صورت JSON ذخیره می‌کند:

```bash
python -m market_relationship_discovery symbol-specs --broker-profile DEMO --symbol EURUSD --output config/specs/demo_eurusd.json
```

فایل specification محلی، ورودی پژوهشی است و اگر جزئیات ماشین داشته باشد نباید commit شود.

## سیاست سازگاری

`ContractSpecificationAnalyzer` یکی از این وضعیت‌ها را گزارش می‌کند:

- `compatible`: ارزها، point/digits، محدودیت volume، trade mode، contract size و tick value مطابق‌اند
- `normalization_required`: محدودیت quote مطابق است اما contract size یا tick value فرق دارد
- `incompatible`: ارزها، point/digits، محدودیت volume یا trade mode فرق دارند
- `review_required`: فقط یک specification وجود دارد یا trade mode در دسترس نیست
- `unverified`: هیچ specification ارائه نشده است

بدون spec، مقایسه tick برچسب `crossable_research_contract_unverified` می‌گیرد. فقط با spec سازگار برچسب validated می‌گیرد. قراردادهای نیازمند normalization، ناسازگار یا نیازمند review، episode opportunity را block می‌کنند و تعداد observation مثبت مسدودشده را گزارش می‌دهند.

## محدودیت‌ها

سازگاری ثابت نمی‌کند که ساخت symbol، venue زیربنایی، swap، rebate، نقدینگی یا قوانین اجرا یکسان‌اند. نسبت contract size و tick value گزارش می‌شود اما شبیه‌سازی اجرای cross-broker با PnL نرمال‌شده پیاده‌سازی نشده است. metadata رسمی مفقود باید دستی فراهم یا حل شود و نباید حدس زده شود.
