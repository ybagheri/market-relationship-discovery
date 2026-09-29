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
- `normalization_required`: محدودیت quote مطابق است و contract size و tick value **با یک نسبت** فرق دارند، پس دو پا یک ابزار را با اندازه لات متفاوت توصیف می‌کنند
- `incompatible`: ارزها، point/digits، محدودیت volume یا trade mode فرق دارند، یا contract size و tick value با هم مقیاس نمی‌شوند
- `review_required`: فقط یک specification وجود دارد یا trade mode در دسترس نیست
- `unverified`: هیچ specification ارائه نشده است

بدون spec، مقایسه tick برچسب `crossable_research_contract_unverified` می‌گیرد. فقط با spec سازگار برچسب validated می‌گیرد. قراردادهای ناسازگار یا نیازمند review، episode opportunity را block می‌کنند و تعداد observation مثبت مسدودشده را گزارش می‌دهند؛ جفت نیازمند normalization مسدود نمی‌شود، چون پاهایش با حجم قابل تطبیق‌اند.

## سقف حجم یعنی ابزار متفاوت نیست

تنها `volume_max` یک جفت را ناسازگار نمی‌کند. دو بروکری که قرارداد یکسان منتشر می‌کنند اما سقف متفاوت دارند، یک ابزار را توصیف می‌کنند و مطالعه‌ای در اندازه‌ای که هر دو می‌پذیرند معتبر است. روی جفت دموی زنده در ۲۰۲۶-۰۹-۲۹ مشاهده شد: WTI در هر دو بروکر `contract_size` (۱۰۰۰)، `tick_size` و `tick_value` (۱۰) یکسان دارد و فقط در مقدار مجاز فرق می‌کند، ۵ لات در برابر ۱۰۰. رد کردن مقایسه هیچ مطالعه cross-broker را برای نمادی که قراردادش توافق است باقی نمی‌گذاشت.

سقف در همان نقطه‌ای که به آن مربوط است اعمال می‌شود. fill assessor اندازه‌ای را که بروکر نمی‌تواند بگیرد، برای هر پا جداگانه رد می‌کند، پس مطالعه ادامه می‌یابد و اندازه همان‌جا که محاسبه می‌شود gate می‌شود. سقف در `advisories` گزارش می‌شود نه در `issues`، چون `issues` تصمیم مسدودسازی را می‌گیرند و ورودی آنجا صرف خوانده شدن مقایسه را مسدود می‌کرد. خلاصه cross-broker آن را با `contract_advisories` حمل می‌کند.

سقف هرگز یک ناسازگاری واقعی را نرم نمی‌کند: جفتی که در ارز سود هم فرق دارد همچنان `incompatible` است و سقف در کنار دلیل گزارش می‌شود.

## contract size و tick value باید با هم مقیاس شوند

یک لات `contract_size` واحد از ارز پایه را پوشش می‌دهد و جابه‌جایی قیمت به اندازه `tick_size` معادل `tick_value` ارزش دارد. این دو پس یک کمیت اقتصادی را توصیف می‌کنند: ارزش پولی یک واحد از دارایی پایه، یعنی

```text
tick_value / (tick_size * contract_size)
```

بروکری که همان ابزار را با اندازه لات متفاوت قیمت‌گذاری می‌کند هر دو فیلد را با هم مقیاس می‌دهد — نصف کردن contract size یعنی نصف شدن tick value — و آن جفت `normalization_required` است. اما اگر تنها یکی از آن دو حرکت کند، دو specification در *هر* حجمی یک موقعیت را متفاوت ارزش‌گذاری می‌کنند، پس هیچ normalization آن‌ها را آشتی نمی‌دهد و جفت `incompatible` است. کد پیشین در این حالت `normalization_required` برمی‌گرداند، یک PnL نرمال‌شده کنار فرصتی که در غیر این صورت crossable بود گزارش می‌کرد، و اختلاف را فقط به‌صورت پسوند مشورتی `_contract_legs_disagree` روی classification می‌زد.

مقایسه با تلورانس نسبی ۱٪ انجام می‌شود که از تلورانس ۵٪ توافق پاها سخت‌گیرانه‌تر است، چون دو عددی را مقایسه می‌کند که *همان ابزار* را توصیف می‌کنند نه دو ارزش‌گذاری از یک نتیجه بازار. بروکری که فیلدی را با دقت محدود منتشر می‌کند تحمل می‌شود؛ بروکری که مقیاس متفاوتی را توصیف می‌کند رد می‌شود.

## محدودیت‌ها

سازگاری ثابت نمی‌کند که ساخت symbol، venue زیربنایی، swap، rebate، نقدینگی یا قوانین اجرا یکسان‌اند. نسبت contract size و tick value گزارش می‌شود اما شبیه‌سازی اجرای cross-broker با PnL نرمال‌شده پیاده‌سازی نشده است. metadata رسمی مفقود باید دستی فراهم یا حل شود و نباید حدس زده شود.
