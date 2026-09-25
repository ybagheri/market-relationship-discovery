# اعتبارسنجی Walk-Forward

## هدف

Walk-forward انتخاب پارامتر را از ارزیابی جدا می‌کند. هر fold سه پنجره زمانی train، validation و test دارد. سیگنال زمان `t` فقط با observation بعدی در همان پنجره ارزیابی جفت می‌شود.

## پیاده‌سازی فعلی

`WalkForwardSplitter` از یک `DatetimeIndex` یکتا، مرتب و UTC foldهای rolling می‌سازد. پنجره‌های train، validation و test در هر fold همپوشانی ندارند. اگر step از اندازه train کوچک‌تر باشد، پنجره train بعدی می‌تواند شامل مشاهدات test قبلی باشد که در طراحی rolling مورد انتظار است؛ پنجره‌های test باید ترتیبی بمانند و برای انتخاب threshold فعلی استفاده نشوند.

`WalkForwardValidator` thresholdهای فعال‌سازی را فقط روی train ارزیابی می‌کند، threshold با بیشترین میانگین edge خالص observation بعدی را انتخاب می‌کند، عملکرد validation را گزارش می‌دهد و سپس همان threshold ثابت را روی test اجرا می‌کند. fold با تعداد معامله train ناکافی علامت‌گذاری می‌شود و هیچ trade وارد test aggregate نمی‌کند.

آخرین timestamp هر پنجره اجرا نمی‌شود چون observation بعدی آن خارج از همان پنجره است. این مرز محافظه‌کارانه مانع استفاده سیگنال از outcome در مرز train/validation/test می‌شود.

## پژوهش چندمرحله‌ای

`MultiStageBacktester` ستون‌های score علی را با weight و threshold صریح ترکیب می‌کند. `CausalFeatureBuilder` rolling z-score، momentum و realized volatility را فقط از مقادیر جاری و گذشته می‌سازد. ensemble در observation بعدی ارزیابی می‌شود و هر stage جداگانه نیز گزارش می‌گردد.

خود ستون stage باید علی باشد. موتور نمی‌تواند تشخیص دهد که یک ستون خارجی آینده را در خود دارد.

## بازتولیدپذیری

هر آزمایش CLI شناسه `EXP-*`، زمان UTC ساخت، نسخه نرم‌افزار، نام فایل منبع، hash SHA-256، بازه داده، پارامترها، محدودیت‌ها و مسیر گزارش JSON را ثبت می‌کند. مسیر مطلق منبع در گزارش ذخیره نمی‌شود.

## محدودیت‌ها

selector فعلی فقط threshold اسکالر را مدیریت می‌کند. مدل ML دلخواه، بهینه‌سازی ترکیبی پارامتر یا اصلاح multiple testing انجام نمی‌شود. نتیجه walk-forward همچنان فرضیه تاریخی است و عملکرد آینده را تضمین نمی‌کند.
