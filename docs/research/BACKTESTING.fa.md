# بک‌تست

## کنترل‌های پژوهشی پیاده‌سازی‌شده

`ResearchBacktester.run_next_observation` سیگنال زمان `t` را فقط با edge و هزینه زمان `t+1` جفت می‌کند. `WalkForwardValidator` threshold فعال‌سازی را فقط روی train انتخاب می‌کند، validation را گزارش می‌دهد و threshold ثابت را روی هر پنجره test اجرا می‌کند. سیگنال و outcome نمی‌توانند از انتهای پنجره عبور کنند.

`MultiStageBacktester` ستون‌های score علی را با weight و threshold صریح ترکیب می‌کند. ensemble و هر stage جداگانه گزارش می‌شوند. `CausalFeatureBuilder` rolling z-score، momentum و realized volatility را فقط از مقادیر جاری و گذشته می‌سازد.

## بازتولیدپذیری

آزمایش‌های CLI شناسه `EXP-*` و گزارش JSON شامل نسخه نرم‌افزار، نام و SHA-256 فایل منبع، بازه UTC، پارامترها، پنجره fold، معیارها، معاملات و محدودیت‌ها تولید می‌کنند.

## کنترل‌های آینده

- fit مدل‌های دلخواه فقط باید داده train بگیرد.
- بهینه‌سازی ترکیبی به کنترل multiple testing نیاز دارد.
- لغزش، spread، latency و شکاف session باید سناریو آزموده شوند.
- walk-forward جایگزین تست پایداری Monte Carlo نیست.
- ستون stage خارجی باید از نظر علی بودن ممیزی شود.

## تفسیر

نتیجه مثبت فقط فرضیه‌ای زیر فرض‌هاست و سود تضمینی نیست. فایل‌های CSV نمونه fixture قطعی نرم‌افزار هستند و شواهد بازار نیستند. هیچ اجرای سفارش یا شبیه‌سازی fill پیاده‌سازی نشده است.
