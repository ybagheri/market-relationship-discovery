🇬🇧 English: [English README](README.md)

# کشف روابط بازار

یک پلتفرم پژوهش کمّی با Python برای کشف و اعتبارسنجی روابط بازار، قیمت‌های مصنوعی، ناهمگونی‌های قیمتی، اختلاف داده‌های بروکرها، روابط مثلثی ارز، اثرهای lead/lag و نامزدهای آربیتراژ آماری.

> **فقط پژوهش:** این پروژه سود آربیتراژ را تضمین نمی‌کند. حساب متصل به MT5 باید به‌طور قطعی در حالت `DEMO` باشد و در مرحله فعلی هیچ عملیات اجرای سفارش پیاده‌سازی نشده است.

## وضعیت پروژه

پلتفرم پژوهشی از نظر قابلیت تا انتهای فازهای مستندشده کامل است. اجرای زنده غیرفعال و خارج از دامنه کار باقی مانده است.

**کار فعلی درستی اندازه‌گیری است، نه افزودن قابلیت.** بررسی کامل خط لوله پژوهشی دسته‌ای از نقص‌ها را پیدا کرد که همه یک شکل داشتند: کد عددی تولید می‌کرد که معتبر به‌نظر می‌رسید، آن را وارد گزارش می‌کرد، و اجازه می‌داد به‌عنوان شاهد خوانده شود. هیچ‌کدام با تست پاس نشدند، چون تست‌ها بررسی می‌کردند که خط لوله نتیجه‌ای سالم تولید کرده، نه اینکه آن نتیجه درست باشد. نسخه ۱٫۹٫۰ موارد یافت‌شده را اصلاح می‌کند.

هر آیتم فهرست **زیاد** در آن بررسی اکنون اصلاح شده است، هرکدام با تست رگرسیونی که روی کد پیش از تغییر شکست می‌خورد. چهار مورد پس از ۱٫۹٫۰:

- `-` کاراکتر identifier بود، پس `A-B` یک نماد واحد می‌شد که هرگز در پنل وجود ندارد و تفریق دور ریخته می‌شد. نام بروکر دارای خط تیره مثل `XAU-USD` اکنون داخل گیومه نوشته می‌شود، چون بروکرها واقعاً چنین نام‌هایی منتشر می‌کنند و حذف خط تیره آن‌ها را به تفریق خاموش تبدیل می‌کرد
- بروکری که `contract_size` را نصف می‌کرد ولی `tick_value` را نه، قابل نرمال‌سازی پذیرفته می‌شد، پس کنار فرصتی که در غیر این صورت crossable بود یک PnL نرمال‌شده گزارش می‌شد. هیچ حجمی چنین جفتی را آشتی نمی‌دهد، پس اکنون رد می‌شود
- دروازه observation نامزدی را که هرگز ارزیابی نشده بود، چنین گزارش می‌کرد که داده‌اش اندازه‌گیری و برای مدت کوتاه یافته شده است
- `CostAwareAnalyzer` و `CostModel` هیچ caller نداشتند و فرض latency‌ای نگه می‌داشتند که هرگز اعمال نمی‌کردند؛ مسیر تک‌نمادی هیچ اختلاف اجرایی ادعا نمی‌کند، پس به‌جای وصل کردن حذف شدند

اصلاح‌شده در ۱٫۹٫۰، هرکدام با تست رگرسیونی:

- هم‌ترازی cross-broker روی داده نامرتب جست‌وجو می‌کرد، تیک‌ها را به همسایه اشتباه وصل می‌کرد و بی‌صدا observationها را دور می‌ریخت
- opportunityها بر اساس مجاورت سطر گروه‌بندی می‌شدند، پس دو لحظه مجزا یک opportunity طولانی و قابل capture گزارش می‌شد
- لبه ترکیبی cross-broker روی هر دو پا ارزش‌گذاری و جمع می‌شد، که opportunity متقارن را تقریباً دو برابر می‌کرد
- confidence_max_drawdown کوانتیل اشتباه را می‌خواند و کرانی ملایم‌تر از drawdown معمول گزارش می‌کرد
- drawdown بدون seed صفر محاسبه می‌شد، پس منحنی‌ای که زیر سقف خودش شروع می‌کرد هیچ drawdownی گزارش نمی‌کرد
- win rate روی همه barها میانگین‌گیری می‌شد نه روی tradeهای گرفته‌شده
- aggregate در walk-forward پنجره‌های test هم‌پوشان را دوباره می‌شمرد
- شمارش ی‌باره پنجره‌‌های test هم‌پوشان در aggregate هاش‌تاری
- رتبه‌بند ridge روی آمار خلاصه‌شده از کل سری هر candidate آموزش می‌دید و امتیاز out-of-sample را آلوده می‌کرد
- بررسی فقط‌دمو برای کل عمر adapter کش می‌شد، پس ترمینالی که در میانه کار عوض شده بود همچنان خودش را تأیید می‌کرد
- DemoSafetyError به‌عنوان خطای عادی اتصال گزارش می‌شد
- فیلدهای مفقود یا خراب گزارش به صفر رندر می‌شدند که خطای خواندن را به ادعایی درباره بازار تبدیل می‌کرد
- p-value مربوط به Engle–Granger از توزیع بدون متغیر گرفته می‌شد، پس جفت‌هایی که residualشان ریشه واحد نزدیک دارد هم‌انباشت گزارش می‌شدند و همان عدد، خانواده false-discovery را با سوگیری تغذیه می‌کرد

فهرست **زیاد** آن بررسی اکنون پاک است. نقص‌های باز، آیتم‌های **متوسط** و **کم** در بخش **اصلاحات باز** نقشه راه فهرست شده‌اند و به‌طور ضمنی رها نشده‌اند. آن‌ها را به ترتیبی که نقشه راه می‌آورد بردار.

کشف symbol کل کاتالوگ بروکر را با نام، توضیح و alias جست‌وجو می‌کند و می‌گوید کدام قاعده تطبیق یافت. آزمون‌های ایستایی و هم‌انباشت از ADF و KPSS در statsmodels استفاده می‌کنند، حداقل ۳۰ observation هم‌تراز می‌خواهند، و وقتی داده از پشتیبانی آزمون برنمی‌آید به‌جای نتیجه، دلیل صریح برمی‌گردانند.

## قابلیت‌ها

- آداپتور فقط‌خواندنی MetaTrader 5 برای tick، bar، symbol، حساب و مشخصات ترمینال
- رد اتصال حسابی که به‌طور قطعی `DEMO` تشخیص داده نشود
- تأیید حالت دمو سرعان بعود‌از ذریر بر سرعتقب‌ ، چونکه ترمینال بدون ری‌اس‌تارت قابل تعویض حساب است
- مدل UTC برای bid، ask، mid و spread
- موتور فرمول عمومی برای روابط قیمتی مصنوعی
- تفکیک اختلاف نظری از اختلاف آگاه به bid/ask
- مدل هزینه قابل پیکربندی
- تحلیل Pearson، Spearman، rolling z-score، half-life و lead/lag
- تشخیص ایستایی و هم‌انباشت با آزمون‌های ADF و KPSS از `statsmodels` و دلیل صریح در حالت نامشخص
- اصلاح p-value مربوط به Engle–Granger برای متغیر cointegrating خودش، و گزارش مقدار تعدیل‌نشده در کنار آن
- گزارش جفت‌های تقریباً چندخطی به‌عنوان `unavailable` به‌جای p-value صفر
- کشف نماد بر اساس نام بروکر، توضیح بروکر و alias
- فیلتر آگاه به قابلیت معامله، به‌طوری که نماد غیرقابل‌معامله هرگز به‌عنوان نامزد نمایش داده نشود
- ابزارهای کیفیت داده و هم‌ترازی timestamp
- چند پروفایل broker و collection ترتیبی فقط‌خواندنی
- datasetهای tick و bar در Parquet همراه manifest بازتولیدپذیری
- پژوهش تاریخی bar بدون ادعای اجرای tick-level
- بک‌تست observation بعدی بدون استفاده از edge هم‌زمان سیگنال
- foldهای walk-forward با انتخاب threshold فقط روی train
- سیگنال چندمرحله‌ای علی، feature builder و گزارش هر stage
- شناسه experiment، hash منبع، پارامترها و گزارش JSON بازتولیدپذیر
- شبیه‌سازی Monte Carlo با circular block-bootstrap و seed بازتولیدپذیر
- اندازه‌گیری drawdown از سرمایه اولیه، ی‌سان در backtester و simulator
- سناریوهای spread، slippage، latency و stress ترکیبی که نمی‌توانند بهتر از baseline شوند
- سناریو‌های stress که نمی‌توانند بهتر از baseline بشوند
- همگام‌سازی نزدیک‌ترین timestamp بین brokerها با delay و تعداد unmatched صریح
- پژوهش crossable در سطح tick فقط پس از هزینه اضافی قابل پیکربندی
- فرکانس، مدت opportunity و provenance دو منبع در مقایسه brokerها
- دریافت فراداده رسمی قرارداد MT5 و خروجی JSON
- compatibility gate که جفتی را رد می‌کند وقتی contract size و tick value آن با هم مقیاس نشوند، چون هیچ حجمی نمی‌تواند آن‌ها را آشتی دهد
- collection موازی با process مستقل برای هر پروفایل broker
- نرمال‌سازی volume و PnL آگاه به قرارداد
- مدل margin که صفر اعلام‌شده بروکر را «گزارش‌نشده» می‌داند، هرگز رایگان
- امکان پر شدن با رعایت گام و سقف حجم broker، همراه گزارش partial fill
- پایی که با `volume_max` محدود می‌شود جفت بین‌بروکری را مسدود می‌کند، نه اینکه از گیت اجرایی رد شود
- latency رفت‌وبرگشت اندازه‌گیری‌شده از execution log، بدون ثبت سفارش
- انباشت هزینه نگهداری شبانه شامل گردش سه‌برابری
- سنجش تأخیر با مقایسه مدت اندازه‌گیری‌شده opportunity و زمان رفت‌وبرگشت
- جاروب حساسیت که دوام یک نتیجه پر شدن را از فرض آن اندازه می‌گیرد
- نتیجه‌گیری امکان اجرا با تفکیک دلایل مسدودکننده و مشورتی
- نام نماد مجزا برای هر broker تا پژوهش بین‌بروکری با نام‌های متفاوت ممکن بماند
- کنترل کشف کاذب در خانواده نامزدهای کشف‌شده
- حذف تکرار نامزدها بر اساس معادل‌سازی اثبات‌شده فرمول، با canonicalisation نحوی به‌عنوان fallback
- گزارش پوشش بین‌نمادی و تحلیل بزرگ‌ترین پنجره مشترک
- پرچم contested وقتی نتیجه ADF و KPSS اختلاف دارد
- داشبورد چند broker با تطبیق نماد و بررسی سلامت در هر پروفایل
- داشبورد کشف که مدرک ارزیابی‌شده را از کاتالوگ اعلام‌شده جدا می‌کند
- رد داده‌ای نامرتب به‌جای تطبیق اشتباه با همسایه‌ی اشتباه‌ی نادرست
- طبیق متقارن mutual-nearest در event-time بدون استفاده دوباره از tick تکراری با عدم reuse تکراری quote
- محدود شدن به پیوستگی زمانی دیوار‌ہاست‌، با فاصله قابل پیکربندی
- ارزش‌گذاری ی‌باره لبه cross-broker‌، با گزارش اختلاف دو پا به‌جای جمع آن‌ها
- حفظ raw tick و aggregation صریح timestamp
- چارچوب کاتالوگ رابطه و تولید نامزد
- داشبورد Streamlit با هشدار دائمی حالت پژوهشی/دمو
- نمودارهای تعاملی اختلاف و مقایسه broker از گزارش‌های ذخیره‌شده experiment
- تشخیص علی regime نوسان کم، عادی و زیاد
- گراف جهت‌دار وابستگی فرمول با عمق محدود
- بارگذاری bar price panel از CSV/Parquet wide یا long
- ارزیابی تاریخی candidate با discrepancy، correlation، persistence و regime
- رتبه‌بندی قطعی chronological با ridge عددی و RMSE out-of-sample
- رتبه‌بندی ridge قطعی chronological با NumPy و RMSE خارج از نمونه، فقط با feature‌‌های علی
- پایداری rolling beta و diagnosticهای retrospective هم‌انباشت/ایستایی

## مدل ایمنی

در مرحله جاری هیچ تابعی مانند `order_send` وجود ندارد. اختلاف قیمت تنها زمانی «آربیتراژ بدون ریسک» نامیده می‌شود که زمان‌بندی داده، مشخصات قرارداد، مسیر اجرا و هزینه‌ها چنین نتیجه‌ای را پشتیبانی کنند. اختلاف mid-price به‌تنهایی فقط یک اختلاف نظری است.

در تنظیمات، `demo_only=true` الزامی است. اگر حالت حساب MT5 قابل اثبات نباشد، آداپتور اتصال را قطع کرده و خطا می‌دهد.

این اثبات یک بررسی لحظه‌ای است و ترمینال فرایندی جدا و طولانی‌عمر است که اپراتور می‌تواند بدون ری‌استارت آن را به حساب دیگری login کند. بنابراین حساب پس از سپری شدن `MT5__ACCOUNT_VERIFICATION_TTL_SECONDS` (پیش‌فرض ۳۰۰ ثانیه) دوباره بررسی می‌شود تا نشستی که در میانه کار حسابش عوض شده همچنان خودش را تأیید نکند، و هر manifest دیتاست حالت حساب را همان‌طور که در لحظه نوشتن بوده ثبت می‌کند. `is_connected` خود ترمینال را بررسی می‌کند، نه صرفاً وجود handle را، پس نشستی که جای دیگری بسته شده متصل گزارش نمی‌شود. بسته نشدن تمیز ترمینال فقط log می‌شود و خطا نمی‌دهد، چون `disconnect` هنگام خروج از context هم اجرا می‌شود و نباید جای نتیجه کار واقعی caller را بگیرد.

`DemoSafetyError` در `doctor` و داشبورد با وضعیت جداگانه `demo_safety_refused` گزارش می‌شود. این رد یعنی ترمینال متصل شد و حساب قابل اثبات به‌عنوان demo نبود، یعنی پلتفرم دقیقاً درست عمل کرده است، نه یک مشکل پیکربندی.

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
MT5__TICK_LOOKBACK_HOURS=24
MT5__TICK_MAX_LOOKBACK_HOURS=168
BROKERS={"DEMO":{"terminal_path":"C:\\\\path\\\\to\\\\demo\\\\terminal64.exe","demo_only":true}}
DATA__TIMEZONE=UTC
DATA__MAX_ALIGNMENT_DELAY_MS=100
```

مقادیر خالی اختیاری مانند `MT5__LOGIN=` به معنای «پیکربندی‌نشده» است، نه خطای اعتبارسنجی. آداپتور عمداً تنظیم password غیرخالی را نمی‌پذیرد. احراز هویت MT5 باید توسط خود ترمینال مدیریت شود. مقدار `source_utc_offset_minutes` پیش‌فرض صفر است و فقط پس از تأیید اختلاف ساعت منبع تغییر می‌کند؛ timestamp اصلی MT5 در `source_timestamp` حفظ می‌شود.

درخواست tick به عقب از زمان جاری جست‌وجو می‌کند و تا زمانی که tick کافی پیدا نشود پنجره را گشاد می‌کند، زیرا خارج از ساعت معامله آخرین tick می‌تواند ساعت‌ها عقب‌تر باشد. `MT5__TICK_LOOKBACK_HOURS` پنجره اولیه و `MT5__TICK_MAX_LOOKBACK_HOURS` سقف آن را تعیین می‌کند.

## شروع سریع

```bash
python -m market_relationship_discovery doctor
python -m market_relationship_discovery doctor --broker-profile ALPARI_2
python -m market_relationship_discovery mt5-info --broker-profile ALPARI_2
python -m market_relationship_discovery symbols --search gold
python -m market_relationship_discovery symbols --search silver --json
python -m market_relationship_discovery symbols --all
python -m market_relationship_discovery collect --broker-profile DEMO --symbol XAUUSD --symbol EURUSD --symbol XAUEUR --data-type bar --timeframe M1 --limit 500
python -m market_relationship_discovery collect --symbol XAUUSD --data-type tick --limit 500
python -m market_relationship_discovery collect --parallel --max-workers 2 --broker-profile BROKER_A --broker-profile BROKER_B --symbol EURUSD --data-type tick --limit 500
python -m market_relationship_discovery symbol-specs --broker-profile DEMO --symbol EURUSD --output config/specs/demo_eurusd.json
python -m market_relationship_discovery research --broker-profile DEMO --relationship XAUEUR_SYNTHETIC --limit 500
python -m market_relationship_discovery discover --input data\prices.csv --regime-window 20 --rolling-beta-window 30 --statistical-significance 0.05 --max-depth 1 --training-fraction 0.7 --ridge-alpha 1.0 --output reports\research
python -m market_relationship_discovery backtest examples\no_lookahead_signals.csv
python -m market_relationship_discovery multi-backtest examples\walk_forward_signals.csv --stage-column momentum_score --stage-column confirmation_score --stage-weight 0.5 --stage-weight 0.5
python -m market_relationship_discovery walk-forward examples\walk_forward_signals.csv --train-size 12 --validation-size 8 --test-size 8 --step 8 --threshold 0 --threshold 0.5 --threshold 0.9
python -m market_relationship_discovery robustness examples\walk_forward_signals.csv --simulations 1000 --seed 42 --block-size 3
python -m market_relationship_discovery compare-brokers examples\broker_a_ticks.csv examples\broker_b_ticks.csv --broker-a BrokerA --broker-b BrokerB --symbol EURUSD --kind tick --max-delay-ms 100 --additional-cost 0.0001 --sync-mode symmetric --tick-aggregation last --contract-a examples\broker_a_contract.json --contract-b examples\broker_b_contract.json
```

روابط اولیه شامل `EURGBP = EURUSD / GBPUSD`، `EURJPY = EURUSD * USDJPY`، `GBPJPY = GBPUSD * USDJPY`، `XAUEUR = XAUUSD / EURUSD` و نسبت طلا به نقره است.

## چند broker

هر broker پیکربندی‌شده یک پروفایل مستقل و فقط‌دمو با نگاشت نماد مخصوص خود است.
آن‌ها را جداگانه تشخیص دهید، چون موفقیت یک پروفایل درباره پروفایل دیگر چیزی نمی‌گوید:

```bash
python -m market_relationship_discovery doctor --broker-profile ALPARI_1
python -m market_relationship_discovery doctor --broker-profile ALPARI_2
python -m market_relationship_discovery collect --parallel --max-workers 2 --broker-profile ALPARI_1 --broker-profile ALPARI_2 --symbol EURUSD --data-type tick --limit 500
python -m market_relationship_discovery compare-brokers a.parquet b.parquet --broker-a Alpari-MT5-Demo --broker-b AMarkets-Demo --symbol BTCUSD --symbol-a BITCOIN --symbol-b BTCUSD --contract-a specs/a.json --contract-b specs/b.json --volume 1.0 --leverage 500
```

بروکرها به‌ندرت یک ابزار را یکسان نام‌گذاری می‌کنند، و ticker یکسان به‌معنای قرارداد
یکسان نیست. دو بروکر دمو که در ۲۰۲۶-۰۹-۲۶ مشاهده شدند بیت‌کوین را با نام `BITCOIN`
و `BTCUSD` منتشر می‌کنند، طلا را با اختلاف ده‌برابری در tick value قیمت‌گذاری می‌کنند،
و بیت‌کوین را در یکی تا سنت و در دیگری به دلار کامل. دروازه قرارداد این مقایسه را
مسدود می‌کند و فرصت کاذب گزارش نمی‌دهد. [مدل اجرا و سرمایه](docs/research/EXECUTION_MODEL.fa.md)
را ببینید.

## داشبورد

```bash
python -m market_relationship_discovery dashboard
```

داشبورد همیشه عبارت `DEMO / RESEARCH MODE — NO LIVE TRADING` را نمایش می‌دهد. این داشبورد نمودارهای تعاملی فقط‌خواندنی برای اختلاف و mid price همگام brokerها دارد که از گزارش‌های `EXP-*.json` در `DATA__REPORTS_DIRECTORY` خوانده می‌شوند. preview گزارش حداکثر ۲۰ observation همگام دارد؛ برای refresh دوباره `compare-brokers` را اجرا کنید.

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
- [نگاشت نمادها و نام‌گذاری بروکر](docs/mt5/SYMBOL_MAPPING.fa.md)
- [آموزش شروع سریع](docs/tutorials/QUICKSTART.fa.md)
- [روش‌شناسی پژوهش](docs/research/METHODOLOGY.fa.md)
- [بک‌تست](docs/research/BACKTESTING.fa.md)
- [اعتبارسنجی walk-forward](docs/research/WALK_FORWARD.fa.md)
- [پایداری Monte Carlo](docs/research/MONTE_CARLO.fa.md)
- [مقایسه چند بروکر](docs/research/CROSS_BROKER.fa.md)
- [مشخصات قرارداد](docs/research/CONTRACT_SPECIFICATION.fa.md)
- [مدل اجرا و سرمایه](docs/research/EXECUTION_MODEL.fa.md)
- [آزمون چندگانه و کشف](docs/research/MULTIPLE_TESTING.fa.md)
- [پوشش پنل و خانواده نامزدها](docs/research/PANEL_COVERAGE.fa.md)
- [collection موازی MT5](docs/mt5/PARALLEL_COLLECTION.fa.md)
- [نرمال‌سازی PnL](docs/research/PNL_NORMALIZATION.fa.md)
- [همگام‌سازی event-time](docs/research/EVENT_TIME.fa.md)
- [داشبورد](docs/dashboard/DASHBOARD.fa.md)
- [کشف پیشرفته](docs/research/ADVANCED_DISCOVERY.fa.md)
- [نقشه راه](docs/roadmap/ROADMAP.fa.md)
- [سیاست امنیت](SECURITY.md)

## محدودیت‌ها

داده و ساخت CFD در بروکرهای مختلف می‌تواند متفاوت باشد. رابطه مصنوعی ممکن است از نظر ریاضی معتبر ولی غیرقابل معامله باشد. داده bar نمی‌تواند آربیتراژ در سطح tick را اثبات کند. همبستگی، هم‌انباشت یا بازگشت به میانگین تاریخی، مزیت آینده را تضمین نمی‌کند. هزینه، تأخیر، لغزش، ساعات بازار و مشخصات symbol باید جداگانه اعتبارسنجی شوند.

## مجوز

هنوز مجوزی انتخاب نشده است. تا زمان افزودن مجوز توسط مالک پروژه، اجازه استفاده مجدد از این مخزن داده نشده است.
