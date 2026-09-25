# کشف پیشرفته

## دامنه

کشف پیشرفته روی bar price panel کار می‌کند و نامزد پژوهشی تولید می‌کند. ادعا نمی‌کند که رابطه تاریخی قابل اجرا یا سودآور است و برای fit مدل رتبه‌بندی از observation آینده استفاده نمی‌کند.

## ورودی price panel

`discover --input` فایل CSV یا Parquet را در دو قالب می‌پذیرد:

- Wide: `timestamp,EURUSD,GBPUSD,EURGBP`
- Long: `timestamp,symbol,close`

ورودی long به wide تبدیل می‌شود. timestamp به UTC تبدیل و panel مرتب می‌شود، timestamp تکراری در wide و جفت تکراری `(timestamp, symbol)` رد می‌شود، قیمت باید عددی و مثبت باشد و مقدار گمشده forward-fill نمی‌شود.

## خط پردازش

1. بارگذاری و اعتبارسنجی panel.
2. ساخت hypergraph جهت‌دار از کاتالوگ روابط declarative؛ هر فرمول یک edge با همه source symbolهای آن است.
3. گسترش روابط از symbolهای موجود تا عمق `--max-depth`.
4. ارزیابی discrepancy، Pearson، Spearman، half-life، rolling z-score، regime علی و پایداری rolling beta.
5. گزارش diagnosticهای retrospective هم‌انباشت OLS-residual، ADF با lag ثابت و KPSS سطح.
6. fit مدل ridge استانداردشده NumPy فقط روی بخش زمانی train.
7. پیش‌بینی و رتبه‌بندی candidateها در observationهای بعدی بر اساس میانگین z-score مطلق پیش‌بینی‌شده.
8. نوشتن گزارش `EXP-*.json` با hash منبع، پارامترها، regimeها، edgeهای گراف، خلاصه candidateها، ranking و محدودیت‌ها.

## regime

نوسان، انحراف معیار rolling بازده log است. آستانه‌های کم و زیاد quantileهای expanding از نوسان مشاهده‌شده تا همان timestamp هستند؛ بنابراین داده آینده برچسب‌های قبلی را تغییر نمی‌دهد. segment قیمت ثابت normal volatility برچسب می‌گیرد.

## diagnosticهای آماری

`--rolling-beta-window` پنجره علی beta را کنترل می‌کند. خلاصه پایداری beta شامل تعداد پنجره معتبر، کسر علامت، سازگاری علامت و پراکندگی است. هم‌انباشت از ADF تقریبی روی residual برآورد OLS استفاده می‌کند؛ ADF از تقریب normal با lag ثابت و KPSS از تقریب CUSUM سطح استفاده می‌کند. این آزمون‌ها retrospective full-sample هستند و feature رتبه‌بندی نیستند.

## ایمنی ranking

مدل ridge قطعی است، seed تصادفی ندارد و به scikit-learn نیاز ندارد. `next_abs_zscore` فقط outcome برچسب‌گذاری‌شده برای train/evaluation است و هرگز feature ورودی نیست. observation ناکافی status صریح می‌گیرد و از فهرست ranked حذف می‌شود.

خروجی فقط ترتیب پژوهشی است، نه ادعای سودآوری. bar data اجرای tick را ثابت نمی‌کند و گزارش funding، کمیسیون، margin، slippage، latency، partial fill یا قوانین broker-specific را مدل نمی‌کند.
