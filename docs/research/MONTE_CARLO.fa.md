# پایداری Monte Carlo

## هدف

تحلیل Monte Carlo بررسی می‌کند یک توالی تاریخی از tradeها تحت resampling و فرض‌های stress چگونه رفتار می‌کند. این تحلیل آزمون حساسیت است، نه پیش‌بینی، احتمال سود زنده یا تضمین.

## روش نمونه‌گیری

`MonteCarloRobustnessSimulator` از circular block bootstrap با block size قابل پیکربندی استفاده می‌کند. نمونه‌گیری blockهای پیوسته وابستگی و ترتیب کوتاه‌مدت را بهتر از shuffle مستقل حفظ می‌کند. indexهای نمونه‌گیری‌شده و shockهای تصادفی در هر simulation بین سناریوها مشترک‌اند تا common random numbers فراهم شود.

simulator میانگین و median edge خالص کل، quantile پایین و بالای confidence، احتمال نتیجه شبیه‌سازی‌شده مثبت، expected shortfall، بدترین نتیجه، drawdown میانه و سطح confidence، میانگین win rate و میانگین تعداد trade مشاهده‌شده را گزارش می‌دهد.

## سناریوهای stress

سناریوهای named، تبدیل‌های بدون بعد روی tradeهای پژوهشی ثبت‌شده‌اند:

- `baseline`: gross edge و cost اصلی
- `wider_spread`: cost کل در ۱٫۵ ضرب می‌شود
- `slippage`: cost کل در ۱٫۲۵ ضرب می‌شود
- `latency`: ۵ درصد احتمال از دست رفتن trade
- `combined_stress`: cost دو برابر و ۱۰ درصد trade از دست‌رفته

شوک بازدهی نامنفی را می‌توان به سناریوهای غیر baseline افزود. multiplierها فرض‌اند و باید براساس instrument، timeframe و مسیر اجرا کالیبره شوند.

## بازتولیدپذیری

فرمان `robustness` تعداد simulation، سطح confidence، seed، block size، پارامتر سناریوها، hash منبع، نسخه نرم‌افزار و بازه UTC داده را در گزارش JSON با شناسه `EXP-*` ثبت می‌کند.

## محدودیت‌ها

block bootstrap نمی‌تواند همه تغییر regime، وابستگی بین tradeها، فروپاشی نقدینگی، قطع feed یا شکست ساختاری بازار را مدل کند. costها تجمیعی‌اند و بدون داده جداگانه در آزمایش ورودی نمی‌توان آن‌ها را به کمیسیون، spread، funding و slippage تفکیک کرد. win rate بالای داده نمونه مصنوعی شواهد بازار نیست.
